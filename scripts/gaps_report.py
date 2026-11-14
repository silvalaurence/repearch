#!/usr/bin/env python3
"""Check drafts for unfinished parts and write GAPS.md.

Usage: python gaps_report.py output/ [--chapters 1-3] [--preset school.json]
       [--format four-chapter] [--survey Survey_Results.xlsx] [--docx Capstone_Draft.docx]
       [--dry-run] [--strict]
Finds: [STUDENT: ...] notes, unfilled {{placeholders}}, instruction lines in [Brackets],
missing chapters, empty survey, missing screenshots and references.
--strict exits with code 1 if anything is unfinished (handy before you submit).
Only the chapters in scope are required, so a school that wants one chapter is not nagged
about the rest, and a part outside the scope - front matter, back matter, appendices - is
not reported missing when the run is only some of the chapters. Use --chapters 1-3 on the
command line or "chapters" in a preset; the flag wins.
--format points at a school's own template folder; its files become the required parts, so a
format with front matter, four chapters, or extra sections is checked exactly as written.
--docx reads the built document too, because the title page is written by build_docx.py and
never appears in your markdown.
--dry-run accepts that some prose is sample text: every [DRY-RUN: ...] passage is listed on
its own, as a claim you must personally verify before this becomes a submission.
"""
import argparse
import glob
import os
import re
import sys

# The scripts are run individually (and by the test suite with -I, which keeps the script's
# own folder off the path), so make it explicit before reaching for the shared chapter rule.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _chapters import DEFAULT_CHAPTERS, from_preset, parse, resolve  # noqa: E402

STUDENT = re.compile(r"\[STUDENT[^\]]*\]")
DRY_RUN = re.compile(r"\[DRY-RUN[^\]]*\]")
BRACES = re.compile(r"\{\{[^}]*\}\}")
INSTRUCTION = re.compile(r"^\s*\[(?:Fill|Replace|Generate|Draw|Draft|Describe|List)\b[^\]]*\]?", re.I)
CHAPTER_LABELS = {1: "Chapter 1", 2: "Chapter 2 (Review of Related Literature)", 3: "Chapter 3",
                  4: "Chapter 4", 5: "Chapter 5 (Summary, Conclusion and Recommendation)"}


def required_sections(chapters):
    """Only parts the school actually asked for. References belong to Chapter 2, the
    appendices and the survey to the built-and-tested side of the paper in Chapters 4-5."""
    sections = {f"chapter{c}": CHAPTER_LABELS[c] for c in chapters}
    if max(chapters) >= 4:
        sections["appendices"] = "Appendices"
    return sections


def first_heading(path):
    """The first '# ...' line of a template, used as the part's name in the checklist."""
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            if line.startswith("# "):
                return line[2:].strip()
    return ""


def format_sections(folder):
    """One part per template file in a school's own format folder, labelled by the heading
    inside it. The folder is the list, so a school layout never needs a second copy of it."""
    sections = {}
    for path in sorted(glob.glob(os.path.join(folder, "*.md"))):
        stem = re.sub(r"^\d+[-_]?", "", os.path.splitext(os.path.basename(path))[0]).lower()
        sections[stem] = first_heading(path) or stem
    return sections


def scoped_sections(sections, chapters):
    """Drop the parts this run is not handing in.

    A Chapter 1-3 submission is not a whole document, so its front matter and back matter
    are not missing - they are simply not part of it yet. Only a run that covers every
    chapter in the format is treated as the complete paper.
    """
    def number(key):
        m = re.fullmatch(r"chapter(\d+)", key)
        return int(m.group(1)) if m else None

    in_format = {n for n in (number(k) for k in sections) if n}
    whole_document = bool(in_format) and set(chapters) >= in_format
    keep = {}
    for key, label in sections.items():
        n = number(key)
        if n is not None:
            if n in chapters:
                keep[key] = label
        elif whole_document:
            keep[key] = label
    return keep


def resolve_format(name):
    """Accept 'four-chapter', a folder next to this skill's templates/, or a real path."""
    if os.path.isdir(name):
        return name
    candidate = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates", name)
    if os.path.isdir(candidate):
        return candidate
    sys.exit(f"Format folder not found: {name} (also looked in {candidate})")


def docx_lines(path):
    """Every line of text the saved document really contains, tables included."""
    from docx import Document
    doc = Document(path)
    lines = [p.text for p in doc.paragraphs]
    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                lines.append(cell.text)
    return [line for line in lines if line.strip()]


def plain(text):
    """Text without markdown dressing or spacing, so a draft line and the same line inside Word match.

    '**Business Model Canvas** - [STUDENT: ...]' arrives in the document as plain text, and a
    numbered item gains a space where the builder pads its number. Either difference made every
    styled paragraph look like a new, undocumented blank.
    """
    return " ".join(re.sub(r"[*_`]+", " ", text).split()).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--survey", default=None)
    ap.add_argument("--preset", default=None, help="school preset JSON; its \"chapters\" setting chooses what is required")
    ap.add_argument("--chapters", default=None, help="override the preset: 1-3, 1,2,3, or 3 for Chapters 1 to 3")
    ap.add_argument("--format", default=None, help="school template folder, e.g. four-chapter - the folder's own files become the required parts")
    ap.add_argument("--docx", default=None, help="the built .docx to check as well (default: any .docx in the folder)")
    ap.add_argument("--dry-run", action="store_true", help="list sample prose as claims to verify instead of treating it as unwritten")
    ap.add_argument("--out", default=None)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.folder, "*.md")))
    if not files:
        sys.exit(f"No .md files in {args.folder}")
    out = args.out or os.path.join(args.folder, "GAPS.md")

    if args.chapters:
        chapters = parse(args.chapters, origin="--chapters")
    elif args.preset:
        chapters = from_preset(args.preset)
    else:
        chapters = resolve(default=DEFAULT_CHAPTERS)
    if args.format:
        expected = scoped_sections(format_sections(resolve_format(args.format)), chapters)
    else:
        expected = required_sections(chapters)

    student, braces, instr, dry, shots = [], [], [], [], 0
    present = set()
    refs_found = False
    md_blob = ""
    for f in files:
        base = os.path.basename(f).lower()
        if base == "gaps.md" or base == "auto_sections.md":
            continue
        for key in expected:
            if key in base:
                present.add(key)
        text = open(f, encoding="utf-8").read()
        md_blob += text
        if "references" in base:
            refs_found = True
        for n, line in enumerate(text.splitlines(), 1):
            for m in STUDENT.finditer(line):
                student.append((os.path.basename(f), n, m.group(0)))
                if "screenshot" in m.group(0).lower():
                    shots += 1
            for m in DRY_RUN.finditer(line):
                dry.append((os.path.basename(f), n, line.strip()[:200]))
            for m in BRACES.finditer(line):
                braces.append((os.path.basename(f), n, m.group(0)))
            if line.strip().startswith("```mermaid-placeholder"):
                instr.append((os.path.basename(f), n, "diagram placeholder: replace with a real diagram"))
            if INSTRUCTION.match(line):
                instr.append((os.path.basename(f), n, line.strip()[:100]))

    lines = ["# What you still need to do", ""]
    lines += ["Checking these parts only: " + ", ".join(expected.values()) + ".", ""]
    todo = 0

    missing = [label for key, label in expected.items() if key not in present]
    if missing:
        lines += ["## Missing sections", ""] + [f"- {m}" for m in missing] + [""]
        todo += len(missing)
    if 2 in chapters and not refs_found:
        lines += ["## References", "",
                  "- No references file found. Find real sources (Google Scholar, IEEE Xplore, ScienceDirect, your school library), "
                  "put them in a CSV, and run `format_refs.py`. Ask your adviser how many are required.", ""]
        todo += 1

    if 4 in chapters:
        if args.survey:
            try:
                from openpyxl import load_workbook
                ws = load_workbook(args.survey, data_only=False)["Responses"]
                filled = sum(1 for row in ws.iter_rows(min_row=2, min_col=2, max_row=202) for c in row if c.value is not None)
            except Exception as e:  # noqa: BLE001
                filled = 0
                lines += [f"(Could not read the survey file: {e})", ""]
            if filled == 0:
                lines += ["## Survey", "", "- The survey spreadsheet has no responses yet. Chapter 4.4 cannot be written until you collect real answers.", ""]
                todo += 1
        else:
            lines += ["## Survey", "", "- Check that you have conducted the survey and entered real answers in Survey_Results.xlsx before writing Chapter 4.4.", ""]

    # The saved document holds things no markdown file does - the title page among them.
    docx = args.docx
    if not docx:
        candidates = sorted(glob.glob(os.path.join(args.folder, "*.docx")))
        docx = candidates[0] if candidates else None
    if docx:
        try:
            found_lines = docx_lines(docx)
        except Exception as e:  # noqa: BLE001
            found_lines = []
            lines += [f"(Could not read the built document {os.path.basename(docx)}: {e})", ""]
        md_plain = plain(md_blob)
        only_docx = []
        for line in found_lines:
            marks = STUDENT.findall(line) + BRACES.findall(line)
            if marks and plain(line) not in md_plain:
                only_docx.append((line, marks))
        if only_docx:
            lines += [f"## Still blank in the saved .docx ({len(only_docx)})", "",
                      "These are in the built file but not in any draft, so build_docx.py wrote them - "
                      "usually the title page. Pass --school --college --degree --authors --date, or fill them in Word:", ""]
            lines += [f"- `{os.path.basename(docx)}`: {line[:120]} ({', '.join(marks)})" for line, marks in only_docx[:20]]
            lines += [""]
            todo += len(only_docx)

    if shots:
        lines += ["## Screenshots", "", f"- {shots} screenshot placeholder(s) to replace with real images.", ""]
        todo += shots

    others = [s for s in student if "screenshot" not in s[2].lower()]
    if others:
        lines += [f"## Notes for you to write or confirm ({len(others)})", ""]
        lines += [f"- `{f}` line {n}: {t}" for f, n, t in others]
        lines += [""]
        todo += len(others)
    if braces:
        lines += [f"## Unfilled fields ({len(braces)})", "", "These {{...}} fields were never replaced with project details:", ""]
        lines += [f"- `{f}` line {n}: {t}" for f, n, t in braces]
        lines += [""]
        todo += len(braces)
    if instr:
        lines += [f"## Leftover draft instructions ({len(instr)})", "", "Delete these bracketed instruction lines once done:", ""]
        lines += [f"- `{f}` line {n}: {t}" for f, n, t in instr]
        lines += [""]
        todo += len(instr)
    if dry:
        heading = "## Sentences you wrote yourself in this dry run" if args.dry_run else \
                  "## Sample prose marked as a dry run"
        lines += [f"{heading} ({len(dry)})", "",
                  "This text was not collected, observed or tested by you. Keep it only if you can prove every claim "
                  "in it; otherwise delete it. Say so plainly if your adviser wants a real draft:", ""]
        lines += [f"- `{f}` line {n}: {t}" for f, n, t in dry]
        lines += [""]
        todo += len(dry)

    if todo == 0:
        lines += ["Nothing flagged. Re-read everything once more, and make sure you can explain every sentence at your defense.", ""]
    lines += ["---", "Also confirm: your school's AI-use policy, your adviser's format, and that every number and claim in the paper is real."]

    open(out, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    headings = [line[3:].strip() for line in lines if line.startswith("## ")]
    if headings:
        print("Sections: " + ", ".join(headings))
    print("\n".join(lines[:40]))
    if len(lines) > 40:
        print(f"... {len(lines) - 40} more lines - the whole list is in {out}")
    print(f"\nWrote {out}  ({todo} item(s) left)")
    if args.strict and todo:
        sys.exit(1)


if __name__ == "__main__":
    main()
