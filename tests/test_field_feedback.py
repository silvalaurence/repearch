"""Regression tests for the fixes driven by one real run (PickleHub, Expo + Supabase, Chapters 1-3).

Each test names the feedback item it protects, so the behaviour a student paid for in field
time cannot be quietly "optimised" away later. Run with: pytest -q
"""
import json
import struct
import subprocess
import re
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
NOISE = ROOT / "examples" / "scan-noise-project"
VARIANT = ROOT / "templates" / "four-chapter"

sys.path.insert(0, str(SCRIPTS))
from build_docx import caption_from, column_widths, figure_warning  # noqa: E402


def run(*args, check=True):
    return subprocess.run([sys.executable, "-I", *map(str, args)], capture_output=True, text=True, check=check)


def scan_of(project, tmp_path):
    out = tmp_path / "scan.json"
    run(SCRIPTS / "scan_repo.py", project, "--out", out)
    return json.loads(out.read_text())


def make_png(path, width, height):
    """A one-colour PNG written with the standard library only.

    The figure checks need a real image with a real size; Pillow is deliberately not a
    dependency of this skill, so the header is written by hand.
    """
    raw = b"".join(b"\x00" + b"\xff" * (3 * width) for _ in range(height))

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    Path(path).write_bytes(png)


def missing_section(gaps_text):
    m = re.search(r"## Missing sections\n\n(.*?)(?=\n## |\Z)", gaps_text, re.S)
    return m.group(1) if m else ""


# ---------------------------------------------------------------- scan accuracy (item 1)

def test_scanner_ignores_tool_folders_build_output_and_vendored_packs(tmp_path):
    """The reported run scanned 663 files and called a vendored agent skill a Python backend."""
    d = scan_of(NOISE, tmp_path)
    assert d["file_count"] <= 12, f"still scanning junk: {d['file_count']} files"
    assert "Python" not in d["languages"], "the vendored skill's scripts were counted as project code"
    assert "legacy_ghost_table" not in d["tables"], "a SQL dump in backups/ became project schema"
    assert "agent" not in d["folders"] and "dist" not in d["folders"] and "backups" not in d["folders"]
    assert d["vendored_packs"] >= 1 and d["ignored_folders"] >= 4
    assert not any(p.startswith(("dist/", "backups/", ".expo/", "agent/"))
                   for p in d["test_files"] + d["other_test_files"] + d["server_files"] + d["migrations"])


def test_scanner_ignores_a_folder_the_student_names(tmp_path):
    out = tmp_path / "s2.json"
    run(SCRIPTS / "scan_repo.py", NOISE, "--out", out, "--ignore", "server")
    assert json.loads(out.read_text())["server_files"] == [], "--ignore server did nothing"


def test_keep_vendored_is_available_when_the_pack_is_the_project(tmp_path):
    """A student whose repo IS a skill must still be able to scan it."""
    d = scan_of(NOISE, tmp_path)
    out = tmp_path / "wide.json"
    run(SCRIPTS / "scan_repo.py", NOISE, "--out", out, "--keep-vendored")
    wide = json.loads(out.read_text())
    assert "Python" in wide["languages"] and "Python" not in d["languages"]


def test_own_tests_are_separated_from_files_thatmerely_look_like_tests(tmp_path):
    """52 'test files' were reported; 50 belonged to a vendored skill and only 3 were real."""
    d = scan_of(NOISE, tmp_path)
    assert d["test_files"] == ["tests/session.test.ts"]
    assert "src/components/Button.test.tsx" in d["other_test_files"]
    assert not any("agent/" in t for t in d["test_files"] + d["other_test_files"])


def test_migrations_are_kept_as_evidence_of_iterations(tmp_path):
    """Item 15: sprint-numbered migrations are real proof for the iterative model - keep them."""
    d = scan_of(NOISE, tmp_path)
    assert len(d["migrations"]) == 2
    outdir = tmp_path / "out"
    run(SCRIPTS / "gen_sections.py", tmp_path / "scan.json", "--out", outdir)
    auto = (outdir / "auto_sections.md").read_text()
    assert "Schema Change History" in auto and "0002_add_court_hours.sql" in auto


def test_env_vars_are_the_ones_the_app_reads(tmp_path):
    """COLORTERM and REMOTION_* were reported as the project's configuration."""
    d = scan_of(NOISE, tmp_path)
    for noise in ("COLORTERM", "REMOTION_TELEMETRY_DISABLED", "SHELL", "npm_config_typescript"):
        assert noise not in d["env_vars"] and noise not in d.get("env_declared", [])
    assert d["env_declared"] == ["EXPO_PUBLIC_SUPABASE_ANON_KEY", "EXPO_PUBLIC_SUPABASE_URL",
                                 "SUPABASE_SERVICE_ROLE_KEY"]
    outdir = tmp_path / "out"
    run(SCRIPTS / "gen_sections.py", tmp_path / "scan.json", "--out", outdir)
    auto = (outdir / "auto_sections.md").read_text()
    assert "EXPO_PUBLIC_SUPABASE_URL" in auto and "COLORTERM" not in auto


# ------------------------------------------------------------- stated facts (items 2, 3)

def test_a_version_is_only_printed_for_the_package_it_belongs_to(tmp_path):
    """React was reported at the version of @react-native-async-storage."""
    run(SCRIPTS / "scan_repo.py", NOISE, "--out", tmp_path / "scan.json")
    outdir = tmp_path / "out"
    run(SCRIPTS / "gen_sections.py", tmp_path / "scan.json", "--out", outdir)
    auto = (outdir / "auto_sections.md").read_text()
    assert "| React | frontend | 18.2.0 |" in auto
    assert "| Jest | testing | - |" in auto          # jest-expo is not jest: no version claimed
    assert "^2.2.0" not in auto


def test_an_unwired_backend_is_not_drawn_as_a_tier(tmp_path):
    """server.ts / routes.ts are a dead prototype; the paper must not gain a server box."""
    run(SCRIPTS / "scan_repo.py", NOISE, "--out", tmp_path / "scan.json")
    outdir = tmp_path / "out"
    r = run(SCRIPTS / "gen_sections.py", tmp_path / "scan.json", "--out", outdir)
    arch = (outdir / "diagrams" / "architecture.mmd").read_text()
    assert "Application server" not in arch and "Backend" not in arch
    assert "Database" in arch and "Frontend" in arch
    assert "legacy prototype, not wired" in r.stdout


# ------------------------------------------------------- readable figures (items 5, 12, 13)

def test_er_figure_holds_relationships_and_the_detail_file_holds_columns(tmp_path):
    """A 21-table diagram with every attribute was unusable as a printed figure."""
    run(SCRIPTS / "scan_repo.py", NOISE, "--out", tmp_path / "scan.json")
    outdir = tmp_path / "out"
    run(SCRIPTS / "gen_sections.py", tmp_path / "scan.json", "--out", outdir)
    er = (outdir / "diagrams" / "er.mmd").read_text()
    detail = (outdir / "diagrams" / "er_detail.mmd").read_text()
    assert "full_name" not in er and '"member_id"' in er
    assert "full_name" in detail


def test_a_large_schema_is_split_into_page_sized_sheets(tmp_path):
    scan = tmp_path / "scan.json"
    tables = {"t0": [{"name": "id", "type": "bigint", "flags": ["PK"]}]}
    for i in range(1, 14):
        tables[f"t{i}"] = [{"name": "id", "type": "bigint", "flags": ["PK"]},
                           {"name": "prev_id", "type": "bigint", "flags": ["FK"], "ref": f"t{i - 1}"}]
    scan.write_text(json.dumps({"manifests": {}, "languages": {}, "routes": [], "tables": tables,
                                "env_vars": [], "env_declared": [], "test_files": [], "migrations": [],
                                "todos": [], "server_files": [], "api_calls": []}))
    outdir = tmp_path / "out"
    run(SCRIPTS / "gen_sections.py", scan, "--out", outdir)
    assert (outdir / "diagrams" / "er_part1.mmd").exists()
    assert (outdir / "diagrams" / "er_part2.mmd").exists()
    assert "will not fit one readable figure" in (outdir / "auto_sections.md").read_text()


def test_a_diagram_caption_is_taken_from_the_markdown_not_invented(tmp_path):
    """The auto-caption stamped '[STUDENT: add a figure number and caption]' into a finished draft."""
    assert caption_from("**Figure 3.1 The system flowchart**") == "Figure 3.1 The system flowchart"
    assert caption_from("**Business Model Canvas**") is None      # not a figure caption
    assert caption_from("plain prose") is None
    assert "add a figure number" not in (SCRIPTS / "build_docx.py").read_text()

    out = tmp_path / "output"
    out.mkdir()
    make_png(out / "flow.png", 400, 300)
    (out / "chapter3.md").write_text("# CHAPTER 3\n\n![Figure 3.1 Order flow](flow.png)\n")
    run(SCRIPTS / "build_docx.py", out, "--title", "T", "--out", tmp_path / "c.docx", "--no-render")
    from docx import Document
    texts = [p.text for p in Document(tmp_path / "c.docx").paragraphs]
    assert "Figure 3.1 Order flow" in texts
    assert not any("[STUDENT" in t and "figure" in t.lower() for t in texts)


def test_a_strip_or_a_tower_gets_warned_about(tmp_path):
    assert figure_warning("x", 5.5, 0.31) and "strip" in figure_warning("x", 5.5, 0.31)
    assert figure_warning("x", 1.3, 8.0) and "taller" in figure_warning("x", 1.3, 8.0)
    assert figure_warning("x", 5.0, 3.5) is None

    out = tmp_path / "output"
    out.mkdir()
    make_png(out / "wide.png", 900, 50)
    (out / "chapter3.md").write_text("# CHAPTER 3\n\n![Wide diagram](wide.png)\n")
    r = run(SCRIPTS / "build_docx.py", out, "--title", "T", "--out", tmp_path / "w.docx", "--no-render")
    assert "Figure warning" in r.stdout and "strip" in r.stdout


# ------------------------------------------------------------------ docx layout (items 6, 7)

def test_tables_use_the_content_and_the_whole_text_block(tmp_path):
    """Equal columns made a 3-character 'Key' column as wide as a 60-character description."""
    rows = [["id", "Primary key assigned by the database when a row is inserted"],
            ["qty", "Whole number of items the member booked"],
            ["st", "Current state of the booking, open or closed"],
            ["ref", "Reference code printed on the receipt"],
            ["nm", "Full name of the member as it appears on the receipt slip"]]
    widths = column_widths(["Key", "Description"], rows)
    assert sum(int(w) for w in widths) <= 6.0 * 914400, "columns must not overrun the text block"
    assert widths[1] > 3 * widths[0], "the description column gets the space, not the key column"

    out = tmp_path / "output"
    out.mkdir()
    (out / "chapter3.md").write_text(
        "# CHAPTER 3\n\n| Key | Description |\n|---|---|\n"
        "| id | Primary key assigned by the database when a row is inserted |\n| qty | Whole number of items |\n")
    docx = tmp_path / "t.docx"
    run(SCRIPTS / "build_docx.py", out, "--title", "T", "--out", docx, "--no-render")
    from docx import Document
    from docx.oxml.ns import qn
    tbl = Document(docx).tables[0]._tbl
    grid = [int(g.get(qn("w:w"))) for g in tbl.find(qn("w:tblGrid")).findall(qn("w:gridCol"))]
    assert sum(grid) == 8640, f"columns must fill the text block exactly, got {sum(grid)} twips"
    assert int(tbl.find(qn("w:tblPr")).find(qn("w:tblW")).get(qn("w:w"))) == 8640
    assert tbl.find(qn("w:tblPr")).find(qn("w:tblLayout")).get(qn("w:type")) == "fixed"
    cellmar = tbl.find(qn("w:tblPr")).find(qn("w:tblCellMar"))
    assert int(cellmar.find(qn("w:left")).get(qn("w:w"))) == 80, "cells need margins, not cramped text"
    for row in tbl.findall(qn("w:tr")):
        assert row.find(qn("w:trPr")).find(qn("w:cantSplit")) is not None, "no row may split across pages"
    header = tbl.findall(qn("w:tr"))[0]
    assert header.find(qn("w:trPr")).find(qn("w:tblHeader")) is not None, "header must repeat on page 2"
    assert header.find(qn("w:tc")).find(qn("w:tcPr")).find(qn("w:shd")) is not None
    cells = Document(docx).tables[0].rows[0].cells
    assert all(c.text.strip() for c in cells), "every header cell carries its label"
    cell_run = cells[0].paragraphs[0].runs[-1]
    assert cell_run.font.size.pt == 10 and cell_run.bold
    body_run = Document(docx).tables[0].rows[1].cells[1].paragraphs[0].runs[-1]
    assert body_run.font.size.pt == 10


def test_widow_control_and_heading_spacing_applied(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    (out / "chapter3.md").write_text(
        "# CHAPTER 3\n\n## Project Design\n\nA paragraph of real body text describing the design.\n")
    docx = tmp_path / "h.docx"
    run(SCRIPTS / "build_docx.py", out, "--title", "T", "--out", docx, "--no-render")
    from docx import Document
    doc = Document(docx)
    heading = [p for p in doc.paragraphs if p.text == "Project Design"][0]
    assert heading.paragraph_format.keep_with_next is True
    assert heading.paragraph_format.space_before.pt == 12
    assert doc.styles["Normal"].paragraph_format.widow_control is True


def test_a_heading_inside_a_chapter_is_a_real_heading(tmp_path):
    """'Software Engineering Methodology' rendered as plain centered text, absent from the TOC."""
    out = tmp_path / "output"
    out.mkdir()
    (out / "chapter3.md").write_text(
        "# CHAPTER III\n\n# DESIGN AND METHODOLOGY\n\n## Project Design\n\n"
        "# Software Engineering Methodology\n\nAgile with two-week sprints.\n")
    docx = tmp_path / "mid.docx"
    run(SCRIPTS / "build_docx.py", out, "--title", "T", "--out", docx, "--no-render")
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    doc = Document(docx)
    by_text = {p.text: p for p in doc.paragraphs}
    assert "Software Engineering Methodology" in by_text, "the heading was dropped or re-cased"
    mid = by_text["Software Engineering Methodology"]
    assert mid.style.name == "Heading 1", "a mid-chapter H1 must reach the table of contents"
    assert mid.alignment == WD_ALIGN_PARAGRAPH.LEFT
    assert by_text["CHAPTER III"].alignment == WD_ALIGN_PARAGRAPH.CENTER
    assert by_text["CHAPTER III"].paragraph_format.page_break_before is True
    assert by_text["DESIGN AND METHODOLOGY"].style.name == "Heading 1"
    assert by_text["Project Design"].style.name == "Heading 2"


# -------------------------------------------------------- honest title page (items 8, 9)

def test_title_page_flags_fill_the_identity_lines(tmp_path):
    """The builder claimed '0 placeholders' on a document with five blanks on page one."""
    out = tmp_path / "output"
    out.mkdir()
    (out / "chapter1.md").write_text("# CHAPTER 1\n\nThe system helps members book a court.\n")
    blank = tmp_path / "blank.docx"
    filled = tmp_path / "filled.docx"
    run(SCRIPTS / "build_docx.py", out, "--title", "App", "--out", blank, "--no-render")
    r = run(SCRIPTS / "build_docx.py", out, "--title", "App", "--out", filled, "--no-render",
            "--school", "St.rose College", "--college", "College of Computing Studies",
            "--degree", "BS Information Technology", "--authors", "A. Reyes, B. Cruz",
            "--date", "November 2026")
    assert "placeholders left to complete: 0" in r.stdout, r.stdout
    from docx import Document
    texts = [p.text for p in Document(filled).paragraphs]
    assert "St.rose College" in texts and "A. Reyes, B. Cruz" in texts
    assert any("[STUDENT: School name]" in p.text for p in Document(blank).paragraphs)


def test_title_page_can_come_from_the_preset(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    (out / "chapter1.md").write_text("# CHAPTER 1\n\nReal sentence.\n")
    preset = tmp_path / "school.json"
    preset.write_text(json.dumps({"title_page": {"school": "Preset High", "date": "May 2026"}}))
    docx = tmp_path / "p.docx"
    run(SCRIPTS / "build_docx.py", out, "--title", "App", "--preset", str(preset), "--out", docx, "--no-render")
    from docx import Document
    texts = [p.text for p in Document(docx).paragraphs]
    assert "Preset High" in texts and "May 2026" in texts
    assert any("[STUDENT: Degree program]" in t for t in texts), "an unsupplied field stays marked"


def test_gaps_report_reads_the_saved_document(tmp_path):
    """The checklist only read .md files, so the same five blanks went unreported."""
    out = tmp_path / "output"
    out.mkdir()
    (out / "chapter1.md").write_text("# CHAPTER 1\n\nReal sentence about the project.\n")
    docx = out / "Draft.docx"
    run(SCRIPTS / "build_docx.py", out, "--title", "App", "--chapters", "1", "--out", docx, "--no-render")
    run(SCRIPTS / "gaps_report.py", out, "--chapters", "1", "--docx", docx)
    gaps = (out / "GAPS.md").read_text()
    assert "Still blank in the saved .docx" in gaps
    assert "[STUDENT: School name]" in gaps
    assert "build_docx.py wrote them" in gaps


def test_a_line_the_builder_restyled_is_not_reported_as_a_new_blank(tmp_path):
    """Numbered items and bold runs reach Word looking different from the markdown.

    Comparing them character for character made every restyled line look like an
    undocumented blank, burying the five real ones on the title page.
    """
    out = tmp_path / "output"
    out.mkdir()
    (out / "chapter1.md").write_text(
        "# CHAPTER 1\n\n1. {{problem 1, from intake}}\n2. **Business Model Canvas** - "
        "[STUDENT: confirm which one you used]\n")
    docx = out / "D.docx"
    run(SCRIPTS / "build_docx.py", out, "--title", "App", "--chapters", "1", "--out", docx, "--no-render")
    run(SCRIPTS / "gaps_report.py", out, "--chapters", "1", "--docx", docx)
    gaps = (out / "GAPS.md").read_text()
    block = re.search(r"## Still blank in the saved \.docx \(\d+\)(.*?)(?=\n## |\Z)", gaps, re.S).group(1)
    assert "problem 1" not in block and "Business Model Canvas" not in block
    assert "School name" in block, "the title page blanks must still be listed"


def test_the_contents_page_builds_itself_on_open(tmp_path):
    """A blank table of contents looked like a broken document, and the fix was a right-click
    menu no capstone manual ever explains."""
    import zipfile
    out = tmp_path / "output"
    out.mkdir()
    (out / "chapter1.md").write_text("# CHAPTER 1\n\n# THE PROBLEM\n\nA real sentence.\n")
    docx = tmp_path / "toc.docx"
    run(SCRIPTS / "build_docx.py", out, "--title", "Toc", "--out", docx, "--no-render")
    with zipfile.ZipFile(docx) as z:
        body = z.read("word/document.xml").decode("utf-8")
        settings = z.read("word/settings.xml").decode("utf-8")
    assert 'w:dirty="true"' in body, "Word must be told to rebuild the field"
    assert 'w:fldCharType="separate"' in body, "the field needs a cached result, not an empty page"
    assert "Contents build themselves" in body
    assert '<w:updateFields w:val="true"/>' in settings
    assert settings.index("<w:updateFields") < settings.index("<w:compat"), "settings.xml has a fixed element order"


# ---------------------------------------------------------------------- scope (items 10, 11)

def test_a_chapter_1_to_3_run_is_not_told_it_lost_front_matter(tmp_path):
    """FRONT MATTER and BACK MATTER were reported 'Missing' for a Chapters 1-3 submission."""
    out = tmp_path / "output"
    out.mkdir()
    for name in ("chapter1.md", "chapter2.md", "chapter3.md"):
        (out / name).write_text((VARIANT / name).read_text())
    run(SCRIPTS / "gaps_report.py", out, "--format", "four-chapter", "--chapters", "1-3")
    gaps = (out / "GAPS.md").read_text()
    assert "Checking these parts only: CHAPTER 1, CHAPTER II, CHAPTER III." in gaps
    assert "FRONT MATTER" not in missing_section(gaps)
    assert "BACK MATTER" not in missing_section(gaps)


def test_chapters_need_no_hand_copied_preset(tmp_path):
    """Item 11: 'Add --chapters 1-3 instead of making me hand-copy a JSON file.'"""
    out = tmp_path / "output"
    out.mkdir()
    (out / "chapter3.md").write_text("# CHAPTER 3\n\nReal methodology.\n")
    flag = tmp_path / "flag.txt"
    run(SCRIPTS / "gaps_report.py", out, "--chapters", "1-3", "--out", flag)
    preset_file = tmp_path / "p.json"
    preset_file.write_text(json.dumps({"chapters": [1, 2, 3]}))
    via_preset = tmp_path / "preset.txt"
    run(SCRIPTS / "gaps_report.py", out, "--preset", str(preset_file), "--out", via_preset)
    assert flag.read_text() == via_preset.read_text(), "the flag and the preset must agree"


def test_the_builder_leaves_out_of_scope_pages_alone(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    for name in ("00-front-matter.md", "chapter1.md", "chapter2.md", "chapter3.md",
                 "chapter4.md", "90-back-matter.md"):
        (out / name).write_text((VARIANT / name).read_text())
    docx = tmp_path / "three.docx"
    r = run(SCRIPTS / "build_docx.py", out, "--title", "Three", "--chapters", "1-3",
            "--out", docx, "--no-render")
    assert "left out of this document" in r.stdout
    from docx import Document
    texts = [p.text for p in Document(docx).paragraphs]
    assert "CHAPTER IV" not in texts and "BACK MATTER" not in texts and "FRONT MATTER" not in texts
    assert "CHAPTER 1" in texts


def test_a_bad_chapter_spec_fails_with_a_plain_message(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    (out / "chapter1.md").write_text("# CHAPTER 1\n")
    for cmd in (run(SCRIPTS / "gaps_report.py", out, "--chapters", "zero", check=False),
                run(SCRIPTS / "build_docx.py", out, "--chapters", "9", "--out", tmp_path / "x.docx", check=False)):
        assert cmd.returncode != 0 and "Traceback" not in cmd.stderr


# ----------------------------------------------------------------- dry run (item 14)

def test_dry_run_prose_is_listed_as_claims_to_prove(tmp_path):
    """A sanctioned dry run must leave a list of everything the student has to verify."""
    out = tmp_path / "output"
    out.mkdir()
    (out / "chapter4.md").write_text(
        "# CHAPTER 4\n\n## Testing\n\n"
        "Alpha testing performed on 12 November 2026 with three respondents. "
        "[DRY-RUN: sessions observed at public courts in the researcher's locality.]\n")
    docx = out / "Draft.docx"
    r = run(SCRIPTS / "build_docx.py", out, "--title", "Dry", "--chapters", "4", "--out", docx, "--no-render")
    assert "sample passages a real submission must replace or prove: 1" in r.stdout

    run(SCRIPTS / "gaps_report.py", out, "--chapters", "4", "--docx", docx, "--dry-run")
    gaps = (out / "GAPS.md").read_text()
    assert "## Sentences you wrote yourself in this dry run (1)" in gaps
    assert "public courts" in gaps

    run(SCRIPTS / "gaps_report.py", out, "--chapters", "4", "--docx", docx)
    assert "## Sample prose marked as a dry run (1)" in (out / "GAPS.md").read_text()

    strict = run(SCRIPTS / "gaps_report.py", out, "--chapters", "4", "--docx", docx, "--dry-run",
                 "--strict", check=False)
    assert strict.returncode == 1, "sample prose must never pass a pre-submission check"


def test_the_saved_document_shows_dry_run_prose_in_its_own_colour(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    (out / "chapter4.md").write_text("# CHAPTER 4\n\nReal result. [DRY-RUN: assumed by the drafter.]\n")
    docx = tmp_path / "d.docx"
    run(SCRIPTS / "build_docx.py", out, "--title", "Dry", "--out", docx, "--no-render")
    from docx.enum.text import WD_COLOR_INDEX
    from docx import Document
    runs = [r for p in Document(docx).paragraphs for r in p.runs if "[DRY-RUN" in r.text]
    assert runs and runs[0].font.highlight_color == WD_COLOR_INDEX.BRIGHT_GREEN
    student = [r for p in Document(docx).paragraphs for r in p.runs if "[STUDENT" in r.text]
    assert student and student[0].font.highlight_color == WD_COLOR_INDEX.YELLOW
