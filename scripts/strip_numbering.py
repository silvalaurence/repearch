#!/usr/bin/env python3
"""Drop the numeric labels from section headings and table/figure captions.

Some colleges want "2.1 Theoretical Background" and "Table 2.1 Summary of studies"; others
want the same pages with no numbers at all. The content does not change, so this is a
mechanical edit - except for one thing. The moment a label is removed, every sentence that
said "see Table 2.1" or "discussed in Section 3.4" points at nothing, and a draft full of
dead cross-references is worse than a draft with numbers. So the script does the stripping
and then refuses to write until those sentences have been rewritten, or until the student
says out loud that they are leaving them.

Usage:
  python strip_numbering.py drafts/                    # show what would change, and what breaks
  python strip_numbering.py drafts/ --write            # apply it, if nothing dangles
  python strip_numbering.py drafts/ --chapters 2,3     # only Chapters II and III
  python strip_numbering.py drafts/ --write --allow-dangling

Only dotted labels are touched: 2.1 and 3.4.2 go, while a chapter numeral like "II." or a
lone "2." stays, because the chapter number is what the manual uses to find the chapter.
"""
import argparse
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _chapters import parse  # noqa: E402

SKIP_FILES = {"auto_sections.md", "gaps.md", "readme.md"}
LABEL = r"\d+(?:\.\d+)+"          # 2.1, 3.4.2 - at least one dot, so chapter numerals survive

HEADING = re.compile(rf"^(?P<lead>#{{1,6}}\s+)(?P<num>{LABEL})\.?\s+(?P<name>\S.*)$")
# **Table 2.1 Summary of studies** - the number inside the bold run
CAPTION_IN = re.compile(
    rf"^\*\*\s*(?P<kind>Table|Figure|Fig\.)\s+(?P<num>{LABEL})\.?\s*[:.\u2013\u2014-]?\s*"
    r"(?P<name>[^*]*?)\s*\*\*\s*$")
# **Table 2.1** Summary of studies - bold number, plain title after it
CAPTION_OUT = re.compile(
    rf"^\*\*\s*(?P<kind>Table|Figure|Fig\.)\s+(?P<num>{LABEL})\s*\*\*\s*(?P<name>\S.*)$")
REF = re.compile(rf"\b(?P<kind>Section|Sec\.|Table|Figure|Fig\.)\s+(?P<num>{LABEL})")
SIGN_REF = re.compile(rf"§\s*(?P<num>{LABEL})")

HINT = {
    "Section": 'Name the part instead, e.g. "the Research Instrument section"',
    "Sec.": 'Name the part instead, e.g. "the Research Instrument section"',
    "Table": 'Point at it in words, e.g. "the interpretation table below"',
    "Figure": 'Point at it in words, e.g. "the Gantt chart"',
    "Fig.": 'Point at it in words, e.g. "the Gantt chart"',
}


def strip_heading(line):
    m = HEADING.match(line)
    if not m:
        return None
    return m.group("lead") + m.group("name").strip()


def strip_caption(line):
    m = CAPTION_IN.match(line)
    if m:
        name = m.group("name").strip().lstrip(".:\u2013\u2014- ").strip()
        return f"**{name}**" if name else None      # a caption that was only a number disappears
    m = CAPTION_OUT.match(line)
    if m:
        return f"**{m.group('name').strip()}**"
    return None


def references(text):
    """Every sentence that points at a label, with the line it sits on."""
    found = []
    for n, line in enumerate(text.splitlines(), 1):
        for pattern in (REF, SIGN_REF):
            for m in pattern.finditer(line):
                kind = m.groupdict().get("kind", "§")
                found.append((n, m.group(0), kind))
    return found


def chapter_of(path):
    m = re.search(r"chapter[-_ ]?(\d+)", os.path.basename(path).lower())
    return int(m.group(1)) if m else None


def in_scope(files, chapters):
    if not chapters:
        return files
    return [f for f in files if chapter_of(f) in chapters]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--chapters", default=None, help="only these chapters, e.g. 2,3 or 2-3")
    ap.add_argument("--write", action="store_true", help="apply the edit instead of only showing it")
    ap.add_argument("--allow-dangling", action="store_true",
                    help="write even though some cross-references no longer resolve")
    args = ap.parse_args()

    files = sorted(f for f in glob.glob(os.path.join(args.folder, "*.md"))
                   if os.path.basename(f).lower() not in SKIP_FILES)
    if not files:
        sys.exit(f"No .md files in {args.folder}")
    files = in_scope(files, parse(args.chapters, origin="--chapters") if args.chapters else None)
    if not files:
        sys.exit(f"--chapters {args.chapters} matched no chapter file in {args.folder}")

    stripped_headings = stripped_captions = 0
    dangling = []
    rewritten = {}

    for path in files:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        out = []
        for line in text.splitlines(keepends=True):
            body = line.rstrip("\n")
            new = strip_heading(body)
            if new is not None:
                stripped_headings += 1
                out.append(new + ("\n" if line.endswith("\n") else ""))
                continue
            new = strip_caption(body)
            if new is not None:
                stripped_captions += 1
                out.append(new + ("\n" if line.endswith("\n") else ""))
                continue
            out.append(line)
        new_text = "".join(out)
        rewritten[path] = new_text
        for n, token, kind in references(new_text):
            dangling.append((path, n, token, kind))

    for path, n, token, kind in dangling:
        print(f"{os.path.basename(path)}:{n}: {token} - no such label any more. "
              f"{HINT.get(kind, 'Rewrite this reference in words')}.")
    if dangling:
        print(f"\n{len(dangling)} cross-reference(s) would point at nothing.")

    print(f"Headings to unnumber: {stripped_headings}")
    print(f"Captions to unnumber: {stripped_captions}")

    if not args.write:
        print("\nNothing written. Add --write to apply this.")
        return 0
    if dangling and not args.allow_dangling:
        print("\nNothing written: rewrite the cross-references above first, or pass "
              "--allow-dangling if you are keeping them as they are.")
        return 1
    for path, text in rewritten.items():
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
    print(f"\nWrote {len(rewritten)} file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
