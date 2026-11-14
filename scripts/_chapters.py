#!/usr/bin/env python3
"""Chapter scope, parsed the same way by every script.

Kept separate because gaps_report.py, build_docx.py and the school presets all need the
same answer to "which chapters does this college want", and two copies of that rule is
how a tool ends up nagging about a chapter the school never asks for.
"""
import json
import sys

DEFAULT_CHAPTERS = [1, 2, 3, 4, 5]
MAX_CHAPTER = 5


def _fail(spec, origin):
    sys.exit(f"{origin} '{spec}' is not readable. Use 1-3 for a range, 1,2,3 for a set, "
             "or 3 alone for Chapters 1 to 3 (write 3-3 for Chapter 3 only).")


def _expand(item, origin, lone_is_range):
    text = str(item).replace(" ", "")
    if "-" in text:
        low, _, high = text.partition("-")
        if not (low.isdigit() and high.isdigit() and int(low) <= int(high)):
            _fail(item, origin)
        return range(int(low), int(high) + 1)
    if not text.isdigit():
        _fail(item, origin)
    n = int(text)
    return range(1, n + 1) if lone_is_range else [n]


def parse(spec, origin="chapters"):
    """Which chapters the school wants, as a sorted list.

    '1-3' is a range and '1,2,3' (or a JSON list) is that set. A lone number means 1
    through that number, the same shortcut the presets already document, so "chapters": 3
    and --chapters 3 both give Chapters 1 to 3. Write 3-3 when only Chapter 3 is submitted.

    The comma form has to be split here, not left to the caller: --chapters arrives from
    argparse as the single string '2,3', and the previous code passed it through whole and
    then rejected it as unreadable, telling the student to use the very form it refused.
    """
    if spec is None:
        return None
    if isinstance(spec, (list, tuple)):
        items = [str(i) for i in spec]
        lone_is_range = False
    else:
        text = str(spec).replace(" ", "")
        items = [part for part in text.split(",") if part] or [text]
        lone_is_range = len(items) == 1  # only a genuinely lone '3' means 1-3
    found = set()
    for item in items:
        found.update(_expand(item, origin, lone_is_range))
    bad = sorted(c for c in found if not 1 <= c <= MAX_CHAPTER)
    if bad or not found:
        sys.exit(f"{origin} must stay within chapters 1 to {MAX_CHAPTER}, not {sorted(found) or spec!r}")
    return sorted(found)


def from_preset(path):
    """The preset's own 'chapters' setting."""
    with open(path, encoding="utf-8") as fh:
        return parse(json.load(fh).get("chapters", DEFAULT_CHAPTERS), origin=f"chapters in {path}")


def resolve(preset=None, chapters=None, default=None):
    """The flag wins over the preset, the preset wins over the default."""
    if chapters:
        return parse(chapters, origin="--chapters")
    if preset:
        return from_preset(preset)
    return default if default is not None else DEFAULT_CHAPTERS
