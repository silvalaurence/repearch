#!/usr/bin/env python3
"""Build a formatted capstone .docx from markdown drafts.

Usage: python build_docx.py <folder_with_md_files> --title "Project Title" --out Capstone_Draft.docx
Default format (common in PH colleges): Times New Roman 12, double spaced, left margin 1.5 in,
other margins 1 in, page numbers bottom center, title page and table of contents.
Mermaid blocks are rendered to images when the `mmdc` tool (npm i -g @mermaid-js/mermaid-cli) is
installed; otherwise they stay as a highlighted code block with a note to render them at mermaid.live.
Images: ![Figure caption](path/to/image.png) in the markdown is embedded (path relative to the .md file).
A diagram with no image caption takes its caption from a bold `**Figure 3.1 ...**` line written
directly above the block; if there is none, no caption is invented.
Formats: --preset presets/default.json (font, size, line_spacing, left_margin, other_margin, title_page).
Title page identity: --school --college --degree --authors --date, or the same keys under
"title_page" in the preset. Whatever is not supplied stays visibly marked as unfinished.
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

# The scripts are run individually (and by the test suite with -I, which keeps the script's
# own folder off the path), so make it explicit before reaching for the shared chapter rule.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _chapters import parse  # noqa: E402
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_COLOR_INDEX
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Emu, Inches, Pt, RGBColor

PAGE_WIDTH_IN = 8.5   # letter portrait, the paper every college manual assumes
PAGE_HEIGHT_IN = 11.0
TABLE_PT = 10         # wide tables are the one place a smaller size reads better
CFG = {"font": "Times New Roman", "size": 12, "line_spacing": 2.0, "left_margin": 1.5,
       "other_margin": 1.0, "title_page": {}}
BACK_MATTER = ("references", "appendices", "survey")
SKIP_FILES = {"auto_sections.md", "gaps.md", "readme.md"}
RENDER = {"on": True, "base": ".", "count": 0, "warnings": []}
STUDENT_RE = re.compile(r"\[STUDENT[^\]]*\]")
DRYRUN_RE = re.compile(r"\[DRY-RUN[^\]]*\]")
BRACES_RE = re.compile(r"\{\{[^}]*\}\}")
# Neither Arial nor Times New Roman carries U+2713 or U+2717, so a comparative matrix of
# ticks and crosses prints as a row of empty boxes. Only these glyphs are moved to a font
# that has them; every other character stays in the school's own typeface.
SYMBOL_CHARS = "✓✔✗✘✕✖"
SYMBOL_FONT = {"win32": "Segoe UI Symbol", "darwin": "Apple Symbols"}.get(sys.platform, "DejaVu Sans")
SYMBOL_SPLIT = re.compile("([%s])" % re.escape(SYMBOL_CHARS))
TITLE_PARTS = [
    ("A Capstone Project", None, None),
    ("Presented to the Faculty of {}", "college", "College / Department"),
    ("{}", "school", "School name"),
    ("", None, None),
    ("In Partial Fulfillment of the Requirements for the Degree of", None, None),
    ("{}", "degree", "Degree program"),
    ("", None, None),
    ("By", None, None),
    ("{}", "authors", "Member names"),
    ("", None, None),
    ("{}", "date", "Month Year"),
]


def set_font(run, size=None, bold=None, italic=None, mono=False, symbol=False):
    name = SYMBOL_FONT if symbol else ("Courier New" if mono else CFG["font"])
    run.font.name = name                      # python-docx writes ascii and hAnsi together
    fonts = run._element.get_or_add_rPr().get_or_add_rFonts()
    fonts.set(qn("w:eastAsia"), name)
    fonts.set(qn("w:cs"), name)
    run.font.size = Pt(size or CFG["size"])
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic


def emit(paragraph, text, size=None, bold=None, italic=None, mono=False):
    """Add text as runs, splitting off the glyphs the school font cannot draw."""
    runs = []
    for chunk in SYMBOL_SPLIT.split(text):
        if not chunk:
            continue
        run = paragraph.add_run(chunk)
        set_font(run, size, bold, italic, mono, symbol=chunk in SYMBOL_CHARS)
        runs.append(run)
    return runs


def mark(run, kind):
    """Yellow for a part the student still owns, green for sample prose from a dry run."""
    run.font.highlight_color = WD_COLOR_INDEX.YELLOW if kind == "student" else WD_COLOR_INDEX.BRIGHT_GREEN


def add_field(paragraph, instr, cached=None, dirty=False):
    """One Word field: begin, instruction, cached result, end.

    An empty contents page reads as a broken document, so the field carries a placeholder
    result and is marked dirty. Word rebuilds a dirty field when it opens the file, and a
    reader that never updates fields still shows the student what the page is for.
    """
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    if dirty:
        begin.set(qn("w:dirty"), "true")
    run._r.append(begin)
    text = OxmlElement("w:instrText")
    text.set(qn("xml:space"), "preserve")
    text.text = instr
    run._r.append(text)
    if cached:
        separate = OxmlElement("w:fldChar")
        separate.set(qn("w:fldCharType"), "separate")
        run._r.append(separate)
        result = OxmlElement("w:t")
        result.text = cached
        run._r.append(result)
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.append(end)
    set_font(run)


def update_fields_on_open(doc):
    """Tell Word to rebuild every field - the table of contents among them - on opening.

    Without this the contents page stays blank until the student finds the right-click menu,
    which is the one step a capstone manual never explains.
    """
    settings = doc.settings.element
    if settings.find(qn("w:updateFields")) is not None:
        return
    el = OxmlElement("w:updateFields")
    el.set(qn("w:val"), "true")
    later = {qn(tag) for tag in ("w:hdrShapeDefaults", "w:footnotePr", "w:endnotePr", "w:compat",
                                 "w:rsids", "w:mathPr", "w:themeFontLang", "w:clrSchemeMapping",
                                 "w:shapeDefaults", "w:decimalSymbol", "w:listSeparator")}
    for child in settings:
        if child.tag in later:  # settings.xml has a required element order
            child.addprevious(el)
            return
    settings.append(el)


def add_inline(paragraph, text, size=None):
    """Handle **bold** and *italic* inline markdown, and highlight anything still unfinished."""
    for tok in re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)", text):
        if not tok:
            continue
        if tok.startswith("**") and tok.endswith("**"):
            runs = emit(paragraph, tok[2:-2], size, bold=True)
        elif tok.startswith("`") and tok.endswith("`"):
            runs = emit(paragraph, tok[1:-1], 11, mono=True)
        elif tok.startswith("*") and tok.endswith("*") and len(tok) > 2:
            runs = emit(paragraph, tok[1:-1], size, italic=True)
        else:
            runs = emit(paragraph, tok, size)
        if STUDENT_RE.search(tok):
            for run in runs:
                mark(run, "student")
        elif DRYRUN_RE.search(tok):
            for run in runs:
                mark(run, "dry-run")


def style_paragraph(p, spacing=2.0, align=None, after=0):
    pf = p.paragraph_format
    pf.line_spacing = spacing
    pf.space_after = Pt(after)
    pf.space_before = Pt(0)
    pf.widow_control = True
    if align is not None:
        p.alignment = align


def text_width_in():
    return PAGE_WIDTH_IN - CFG["left_margin"] - CFG["other_margin"]


def add_dxa(parent, tag, twips):
    """Set a table measurement Word reads in twentieths of a point."""
    for existing in parent.findall(qn(f"w:{tag}")):
        parent.remove(existing)
    el = OxmlElement(f"w:{tag}")
    el.set(qn("w:w"), str(int(round(twips))))
    el.set(qn("w:type"), "dxa")
    parent.append(el)


def row_property(row, tag, value=None):
    trPr = row._tr.get_or_add_trPr()
    el = OxmlElement(f"w:{tag}")
    if value is not None:
        el.set(qn("w:val"), value)
    trPr.append(el)


def shade(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tcPr.append(shd)


def column_widths(header, body):
    """Widths that follow the content and add up to exactly the text block.

    Word's equal columns turn a data dictionary into a fight between a four-character
    'Key' column and a sixty-character 'Description' column. The 90th percentile is used
    instead of the longest cell so one oversized row cannot starve the rest of the table.
    """
    n = len(header)
    need = []
    for i in range(n):
        cells = sorted([len(str(header[i]))] + [len(str(r[i])) for r in body if i < len(r)])
        need.append(max(min(cells[int(0.9 * (len(cells) - 1))], 60), 6))
    total = int(round(text_width_in() * 1440))  # Word lays tables out in twentieths of a point
    floor = min(720, total // n)
    raw = [max(int(round(total * w / sum(need))), floor) for w in need]
    widest = max(range(n), key=lambda i: raw[i])
    raw[widest] = max(raw[widest] + total - sum(raw), 1)  # absorb the rounding drift
    return [Emu(w * 635) for w in raw]


def add_table(doc, rows, caption=None):
    header, body = rows[0], rows[1:]
    if caption:
        add_caption(doc, caption)
    widths = column_widths(header, body)
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    t._tbl.tblPr.append(layout)
    add_dxa(t._tbl.tblPr, "tblW", text_width_in() * 1440)
    margins = OxmlElement("w:tblCellMar")
    for tag, val in (("top", 30), ("left", 80), ("bottom", 30), ("right", 80)):
        el = OxmlElement(f"w:{tag}")
        el.set(qn("w:w"), str(val))
        el.set(qn("w:type"), "dxa")
        margins.append(el)
    t._tbl.tblPr.append(margins)
    for i, w in enumerate(widths):
        t.columns[i].width = w
    for i, h in enumerate(header):
        c = t.rows[0].cells[i]
        c.width = widths[i]
        c.text = ""
        p = c.paragraphs[0]
        style_paragraph(p, 1.0)
        emit(p, h.strip(), TABLE_PT, bold=True)
        shade(c, "D9D9D9")
    row_property(t.rows[0], "tblHeader", "true")   # repeats on every page the table runs onto
    row_property(t.rows[0], "cantSplit")
    for r in body:
        cells = t.add_row().cells
        for i in range(len(header)):
            cells[i].width = widths[i]
            cells[i].text = ""
            p = cells[i].paragraphs[0]
            style_paragraph(p, 1.0)
            add_inline(p, r[i].strip() if i < len(r) else "", TABLE_PT)
        row_property(t.rows[-1], "cantSplit")      # no row half on one page and half on the next
    doc.add_paragraph()


def render_mermaid(code):
    exe = shutil.which("mmdc")
    if not exe:
        return None
    tmp = tempfile.mkdtemp(prefix="mmd_")
    src, dst = os.path.join(tmp, "d.mmd"), os.path.join(tmp, "d.png")
    open(src, "w", encoding="utf-8").write(code)
    cfg = os.path.join(tmp, "pp.json")
    open(cfg, "w").write('{"args": ["--no-sandbox", "--disable-setuid-sandbox"]}')
    try:
        subprocess.run([exe, "-i", src, "-o", dst, "-b", "white", "-s", "2", "-p", cfg],
                       check=True, capture_output=True, timeout=90)
    except (subprocess.SubprocessError, OSError):
        return None
    return dst if os.path.exists(dst) else None


def figure_warning(label, width, height):
    """Catch the diagrams that technically rendered but cannot be read.

    mermaid.live hands back whatever the graph wants, and a wide tree comes out 18:1 -
    at page width that is a strip a panelist cannot decipher. A strip is only the extreme
    case: a 3.4:1 chart prints 1.6 in tall, clears a height floor, and still loses every
    label once it is squeezed onto a page, so the width-to-height ratio is what is checked.
    """
    if height < 1.2:
        return (f"{label}: prints {width:.1f} x {height:.1f} in, a strip nobody can read. "
                "Group the nodes into row-wise subgraphs, or split it into two figures.")
    if width / height > 2.4:
        return (f"{label}: prints {width:.1f} x {height:.1f} in, {width / height:.1f} times wider "
                "than tall. Group the nodes into row-wise subgraphs, or split it into two figures.")
    if height / width > 3.0:
        return (f"{label}: prints {width:.1f} x {height:.1f} in, taller than it is wide. "
                "Try 'flowchart TB', or split the tree so each figure holds about fifteen leaves.")
    return None


def add_picture(doc, path, caption=None, label=None):
    p = doc.add_paragraph()
    style_paragraph(p, 1.0, WD_ALIGN_PARAGRAPH.CENTER, 6)
    p.paragraph_format.keep_with_next = True  # the caption travels with its figure or not at all
    try:
        from docx.image.image import Image as DocxImage
        img = DocxImage.from_file(path)
        ratio = img.px_height / img.px_width
    except Exception:  # noqa: BLE001
        set_font(p.add_run(f"[IMAGE NOT FOUND: {path}]"), 11, bold=True)
        mark(p.runs[0], "student")
        return
    max_w = min(5.5, text_width_in())
    max_h = PAGE_HEIGHT_IN - 2 * CFG["other_margin"] - 1.0
    width = max_w
    if width * ratio > max_h:
        width = max_h / ratio
    p.add_run().add_picture(path, width=Inches(width))
    RENDER["count"] += 1
    warn = figure_warning(label or os.path.basename(path), width, width * ratio)
    if warn:
        RENDER["warnings"].append(warn)
    if caption:
        c = doc.add_paragraph()
        style_paragraph(c, 1.0, WD_ALIGN_PARAGRAPH.CENTER, 12)
        c.paragraph_format.keep_with_next = False
        add_inline(c, f"*{caption}*", 10)


def caption_from(line):
    """A bold 'Figure 3.1 ...' line written above a diagram, or nothing.

    Silent is better than a placeholder note stamped into a finished draft: if the student
    gave no caption, the figure simply has none, and the gaps report is where that shows up.
    """
    if not line:
        return None
    m = re.match(r"^\*\*\s*((?:Figure|Fig\.|Table)\s+\S.*)\s*\*\*$", line.strip())
    return m.group(1).strip() if m else None


BOLD_ONLY = re.compile(r"^\*\*\s*([^*]+?)\s*\*\*$")
CAPTION_PUNCT = (".", ":", ";", "?", "!")


def unnumbered_caption(line):
    """A bold-only line above a table or diagram, e.g. **Summary of related studies**.

    Not every college manual numbers its tables, and a student told to drop the numbering
    should not lose every caption with it. The line has to earn the promotion, though: it
    is only ever called when the next block really is a table, a diagram or an image, and
    a bold run that ends in a full stop is a sentence the student emphasised, not a title.
    """
    if not line:
        return None
    m = BOLD_ONLY.match(line.strip())
    if not m:
        return None
    text = m.group(1).strip()
    if not text or len(text) > 120 or text.endswith(CAPTION_PUNCT):
        return None
    return text


def next_block(lines, i):
    """What the next non-blank line opens: 'table', 'mermaid', 'image', or None."""
    j = i + 1
    while j < len(lines) and not lines[j].strip():
        j += 1
    if j >= len(lines):
        return None
    s = lines[j].strip()
    if s.startswith("|"):
        return "table"
    if s.startswith("```mermaid"):
        return "mermaid"
    if s.startswith("!["):
        return "image"
    return None


def add_caption(doc, text):
    """A table caption sits above its table, the convention students are marked against."""
    p = doc.add_paragraph()
    style_paragraph(p, 1.0, WD_ALIGN_PARAGRAPH.CENTER, 4)
    p.paragraph_format.keep_with_next = True   # a caption orphaned from its table is a defect
    set_font(p.add_run(text), TABLE_PT, bold=True)
    return p


def add_heading(doc, title, level, page_break=False):
    """Every heading, including a mid-chapter one, is a real Word heading.

    A chapter file often opens with '# CHAPTER III' and '# DESIGN AND METHODOLOGY' and
    later carries '# Software Engineering Methodology'. All three belong in the table of
    contents with the spacing that keeps them off the bottom of a page, so none of them is
    plain centered text. A heading the student wrote in capitals is read as a chapter
    title and stays centered; a mixed-case one is a section heading and keeps its case.
    """
    p = doc.add_paragraph(style=doc.styles[f"Heading {min(level, 3)}"])
    if page_break:
        p.paragraph_format.page_break_before = True
    chapter_title = level == 1 and (page_break or title.isupper())
    set_font(p.add_run(title.upper() if chapter_title else title), CFG["size"], bold=True)
    for r in p.runs:
        r.font.color.rgb = RGBColor(0, 0, 0)
    pf = p.paragraph_format
    pf.line_spacing = 1.5
    pf.space_before = Pt(12)
    pf.space_after = Pt(6)
    pf.keep_with_next = True
    pf.widow_control = True
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER if chapter_title else WD_ALIGN_PARAGRAPH.LEFT
    return p


def render_markdown(doc, text):
    lines = text.splitlines()
    i = 0
    first_h1 = True
    last = ""
    pending = None   # a caption line held back until its table or diagram is reached
    while i < len(lines):
        line = lines[i].rstrip()
        if line.startswith("```"):
            lang = line[3:].strip()
            block = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                block.append(lines[i])
                i += 1
            i += 1
            if lang == "mermaid-placeholder":
                p = doc.add_paragraph()
                style_paragraph(p, 1.0)
                set_font(p.add_run("[DIAGRAM PLACEHOLDER: replace this with your real diagram. Example code removed.]"), 11, bold=True)
                mark(p.runs[0], "student")
                continue
            if lang == "mermaid":
                png = render_mermaid("\n".join(block)) if RENDER["on"] else None
                cap, pending = pending or caption_from(last), None
                if png:
                    add_picture(doc, png, cap, label="Mermaid diagram")
                    continue
                p = doc.add_paragraph()
                style_paragraph(p, 1.0)
                set_font(p.add_run("[DIAGRAM: render this Mermaid code at mermaid.live, export as an image, and replace this block]"),
                         11, bold=True)
                mark(p.runs[0], "student")
            for b in block:
                p = doc.add_paragraph()
                style_paragraph(p, 1.0)
                set_font(p.add_run(b), 10, mono=True)
            last = ""
            continue
        img = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$", line.strip())
        if img:
            path = img.group(2)
            if not os.path.isabs(path):
                path = os.path.join(RENDER["base"], path)
            cap, pending = img.group(1) or pending or caption_from(last) or None, None
            add_picture(doc, path, cap)
            last = line.strip()
            i += 1
            continue
        if line.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|?$", lines[i + 1].strip()):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                if not re.match(r"^\|[\s:|-]+\|?$", lines[i].strip()):
                    rows.append(lines[i].strip().strip("|").split("|"))
                i += 1
            cap, pending = pending or caption_from(last), None
            add_table(doc, rows, caption=cap)
            last = ""
            continue
        m = re.match(r"^(#{1,4})\s+(.*)", line)
        if m:
            level, title = len(m.group(1)), m.group(2).strip()
            add_heading(doc, title, level, page_break=(level == 1 and first_h1))
            if level == 1 and first_h1:
                first_h1 = False
            last = title
            i += 1
            continue
        if re.match(r"^\s*[-*]\s+", line):
            p = doc.add_paragraph(style="List Bullet")
            style_paragraph(p, 1.5)
            add_inline(p, re.sub(r"^\s*[-*]\s+", "", line))
            i += 1
            continue
        if re.match(r"^\s*\d+\.\s+", line):
            num = re.match(r"^\s*(\d+)\.\s+", line).group(1)
            p = doc.add_paragraph()
            style_paragraph(p, 1.5)
            p.paragraph_format.left_indent = Inches(0.5)
            p.paragraph_format.first_line_indent = Inches(-0.3)
            add_inline(p, f"{num}.  " + re.sub(r"^\s*\d+\.\s+", "", line))
            i += 1
            continue
        if not line.strip():
            i += 1
            continue
        if next_block(lines, i):
            cap = caption_from(line) or unnumbered_caption(line)
            if cap:                     # hold it back so it lands above the table, below the figure
                pending = cap
                last = line.strip()
                i += 1
                continue
        p = doc.add_paragraph()
        style_paragraph(p, CFG["line_spacing"], WD_ALIGN_PARAGRAPH.JUSTIFY)
        p.paragraph_format.first_line_indent = Inches(0.5)
        add_inline(p, line)
        last = line.strip()
        i += 1


def title_value(key, hint, args):
    given = getattr(args, key, None) or (CFG.get("title_page") or {}).get(key) or ""
    given = str(given).strip()
    return given if given else f"[STUDENT: {hint}]"


def readback(path):
    """Recount the marks in the file that was actually saved.

    The title page is written by this script rather than by the drafts, so counting the
    markdown alone once reported '0 placeholders' on a document with five blanks on page 1.
    """
    doc = Document(path)
    texts = [p.text for p in doc.paragraphs]
    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                texts.append(cell.text)
    blob = "\n".join(texts)
    return (len(STUDENT_RE.findall(blob)), len(BRACES_RE.findall(blob)), len(DRYRUN_RE.findall(blob)))


def chapter_number(f):
    base = os.path.basename(f).lower()
    m = re.search(r"chapter[-_ ]?(\d+)", base)
    return int(m.group(1)) if m else None


def rank(f):
    """Sort by the number in the file name: a leading one like 00-front-matter.md places
    the page anywhere you need it, a chapter number places the chapter, and a template
    the student added with neither lands after the chapters, before the back matter."""
    base = os.path.basename(f).lower()
    lead = re.match(r"(\d+)[^0-9]", base)
    if lead:
        return int(lead.group(1))
    ch = chapter_number(f)
    if ch:
        return ch
    for idx, key in enumerate(BACK_MATTER):
        if key in base:
            return 80 + idx
    return 60


def in_scope(files, chapters):
    """Keep only what this run hands in.

    A Chapter 1-3 submission has no front matter or appendices to bind, so leaving them
    out of the document beats telling the student to delete the pages by hand. A run that
    covers every chapter present is the whole paper and keeps all of it.
    """
    if not chapters:
        return files, []
    numbers = {n for n in (chapter_number(f) for f in files) if n}
    if not numbers or set(chapters) >= numbers:
        return files, []
    keep = [f for f in files if chapter_number(f) in chapters]
    return keep, [f for f in files if f not in keep]


def new_document(args, with_toc=True):
    """A blank page-set with the school's margins, a title page, and page numbers."""
    doc = Document()
    for s in doc.sections:
        s.left_margin, s.right_margin = Inches(CFG["left_margin"]), Inches(CFG["other_margin"])
        s.top_margin, s.bottom_margin = Inches(CFG["other_margin"]), Inches(CFG["other_margin"])
    normal = doc.styles["Normal"]
    normal.font.name = CFG["font"]
    normal.font.size = Pt(CFG["size"])
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), CFG["font"])
    normal.paragraph_format.widow_control = True

    # Title page
    for _ in range(6):
        style_paragraph(doc.add_paragraph(), 1.0)
    p = doc.add_paragraph()
    style_paragraph(p, 1.5, WD_ALIGN_PARAGRAPH.CENTER, 12)
    set_font(p.add_run(args.title.upper()), 14, bold=True)
    for template, key, hint in TITLE_PARTS:
        line = template.format(title_value(key, hint, args)) if key else template
        p = doc.add_paragraph()
        style_paragraph(p, 1.5, WD_ALIGN_PARAGRAPH.CENTER)
        add_inline(p, line)

    # Table of contents. Word fills it when the file opens; the note below is for the
    # readers that ignore that instruction.
    if with_toc:
        p = doc.add_paragraph()
        p.add_run().add_break(WD_BREAK.PAGE)
        p = doc.add_paragraph()
        style_paragraph(p, 1.5, WD_ALIGN_PARAGRAPH.CENTER, 6)
        set_font(p.add_run("TABLE OF CONTENTS"), 12, bold=True)
        p = doc.add_paragraph()
        style_paragraph(p, 1.0)
        add_field(p, 'TOC \\o "1-3" \\h \\z \\u',
                  cached="Contents build themselves when this file opens in Word.", dirty=True)
        p = doc.add_paragraph()
        set_font(p.add_run("(If the list above is still empty, the reader did not update its fields: "
                           "in Word, right-click it and choose Update Field > Update entire table.)"), 10, italic=True)
    update_fields_on_open(doc)

    # Page numbers on every page except the title page
    section = doc.sections[0]
    section.different_first_page_header_footer = True
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_field(footer, "PAGE")
    return doc


def write_document(args, files, out_path, with_toc=True):
    """Assemble one .docx from these markdown files and report what is still unfinished."""
    doc = new_document(args, with_toc=with_toc)
    for f in files:
        with open(f, "r", encoding="utf-8") as fh:
            text = fh.read()
        p = doc.add_paragraph()
        p.add_run().add_break(WD_BREAK.PAGE)
        render_markdown(doc, text)
    doc.save(out_path)
    return readback(out_path)


def reference_file(files):
    """The formatted reference list, if this folder has one (format_refs.py writes it)."""
    for f in files:
        if "references" in os.path.basename(f).lower():
            return f
    return None


def reference_entries(path):
    text = open(path, encoding="utf-8").read()
    return [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]


def first_author(entry):
    """The word an in-text citation uses: 'Davis, F. D. (1989)' -> 'Davis'."""
    m = re.match(r"^([A-Z][\w'\u2019-]+(?:\s+[A-Z][\w'\u2019-]+)*)\s*,", entry)
    if m:
        return m.group(1)
    m = re.match(r"^((?:[A-Z][\w'\u2019-]*\s+){0,5}[A-Z][\w'\u2019-]*)\.", entry)
    return m.group(1) if m else None


def cited_entries(entries, chapter_text):
    """Keep the references this chapter actually cites, plus any we cannot attribute.

    A chapter handed in on its own needs its own reference list, but shipping the whole
    bibliography under a chapter that cites six of twenty-four sources is the kind of thing
    a panelist notices. An entry with no readable author is kept rather than guessed at:
    leaving out a source the chapter did cite is the worse mistake.
    """
    keep = []
    for entry in entries:
        who = first_author(entry)
        if not who or re.search(r"\b" + re.escape(who) + r"\b", chapter_text):
            keep.append(entry)
    return keep


def write_split(args, files, refs_file):
    """One submission copy per chapter, each carrying only the references it cites."""
    stem = os.path.splitext(os.path.basename(args.out))[0]
    entries = reference_entries(refs_file) if refs_file else []
    written = []
    for f in files:
        n = chapter_number(f)
        if not n:
            continue
        with open(f, "r", encoding="utf-8") as fh:
            text = fh.read()
        out = os.path.join(os.path.dirname(os.path.abspath(args.out)), f"{stem} - Chapter {n}.docx")
        doc = new_document(args)
        p = doc.add_paragraph()
        p.add_run().add_break(WD_BREAK.PAGE)
        render_markdown(doc, text)
        kept = cited_entries(entries, text) if entries else []
        if kept:
            p = doc.add_paragraph()
            p.add_run().add_break(WD_BREAK.PAGE)
            add_heading(doc, "REFERENCES", 1, page_break=False)
            for entry in kept:
                p = doc.add_paragraph()
                style_paragraph(p, 1.5)
                p.paragraph_format.left_indent = Inches(0.5)
                p.paragraph_format.first_line_indent = Inches(-0.5)
                add_inline(p, entry)
        doc.save(out)
        written.append((out, len(kept)))
    return written


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--title", default="Capstone Project Title")
    ap.add_argument("--out", default="Capstone_Draft.docx")
    ap.add_argument("--preset", default=None, help="JSON file with font, size, line_spacing, left_margin, other_margin, title_page")
    ap.add_argument("--chapters", default=None, help="build only these chapters, e.g. 1-3 or 2,3; front and back matter join in only for a whole-paper run")
    ap.add_argument("--school", default=None, help="name of the school, for the title page")
    ap.add_argument("--college", default=None, help="college or department, for the title page")
    ap.add_argument("--degree", default=None, help="degree program, for the title page")
    ap.add_argument("--authors", default=None, help="group members, one line, for the title page")
    ap.add_argument("--date", default=None, help="month and year, for the title page")
    ap.add_argument("--no-render", action="store_true", help="do not render Mermaid diagrams to images")
    ap.add_argument("--split", action="store_true",
                    help="also write one .docx per chapter, for handing in a single chapter on its own")
    args = ap.parse_args()

    if args.preset:
        with open(args.preset, encoding="utf-8") as fh:
            # "chapters" and other non-format settings in a school preset are for gaps_report.py
            CFG.update({k: v for k, v in json.load(fh).items() if k in CFG})
    RENDER["on"] = not args.no_render

    files = sorted(f for f in glob.glob(os.path.join(args.folder, "*.md"))
                   if os.path.basename(f).lower() not in SKIP_FILES)
    if not files:
        sys.exit(f"No .md files in {args.folder}")
    chapters = parse(args.chapters, origin="--chapters") if args.chapters else None
    all_files = sorted(files, key=lambda f: (rank(f), f))
    files, skipped = in_scope(all_files, chapters)
    if not files:
        sys.exit(f"--chapters {args.chapters} matched no chapter file in {args.folder}")
    RENDER["base"] = args.folder

    student, braces, dryrun = write_document(args, files, args.out)
    print(f"Wrote {args.out} from {len(files)} files ({RENDER['count']} image(s) embedded)")
    if skipped:
        print("Outside --chapters, left out of this document: "
              + ", ".join(os.path.basename(f) for f in skipped))
    print(f"[STUDENT: ...] placeholders left to complete: {student}")
    if braces:
        print(f"Unfilled {{{{...}}}} fields: {braces}")
    if dryrun:
        print(f"[DRY-RUN] sample passages a real submission must replace or prove: {dryrun}")

    if args.split:
        refs = reference_file(all_files)
        if not refs:
            print("No references file in this folder, so the split documents carry no reference "
                  "list. Run format_refs.py first if each chapter is handed in on its own.")
        for out, kept in write_split(args, files, refs):
            note = f", {kept} of its own references" if kept else ""
            print(f"Wrote {out}{note}")
    for w in RENDER["warnings"]:
        print("Figure warning - " + w)


if __name__ == "__main__":
    main()
