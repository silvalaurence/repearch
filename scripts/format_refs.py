#!/usr/bin/env python3
"""Format references (APA 7th) from sources YOU found and typed in. Nothing is looked up or invented.

Usage:
  python format_refs.py --template refs.csv         # writes an empty CSV with the right columns
  python format_refs.py refs.csv --out references.md # formats the list, sorted A-Z

CSV columns: type, authors, year, title, source, volume, issue, pages, publisher, doi, url, institution
type: journal | book | web | conference | thesis
authors: "Last, F.; Last, F.; Last, F." (use ; between authors; for an organization write its name once)
Rows missing authors, year or title are rejected with a message. A reference without a DOI or URL gets a
warning so you can check it is findable.
"""
import argparse
import csv
import sys

COLUMNS = ["type", "authors", "year", "title", "source", "volume", "issue", "pages", "publisher", "doi", "url", "institution"]


def fmt_authors(raw):
    names = [a.strip() for a in raw.split(";") if a.strip()]
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]}, & {names[1]}"
    return ", ".join(names[:-1]) + f", & {names[-1]}"


def link(row):
    doi = row.get("doi", "").strip()
    if doi:
        return doi if doi.startswith("http") else f"https://doi.org/{doi}"
    return row.get("url", "").strip()


def fmt(row):
    t = row["type"].strip().lower()
    a, y, title = fmt_authors(row["authors"]), row["year"].strip(), row["title"].strip().rstrip(".")
    src, vol, iss, pp = (row.get(k, "").strip() for k in ("source", "volume", "issue", "pages"))
    pub, inst = row.get("publisher", "").strip(), row.get("institution", "").strip()
    end = link(row)
    a = a if a.endswith(".") else a + "."
    if t == "journal":
        s = f"{a} ({y}). {title}. *{src}*"
        if vol:
            s += f", *{vol}*"
        if iss:
            s += f"({iss})"
        if pp:
            s += f", {pp}"
        s += "."
    elif t == "book":
        s = f"{a} ({y}). *{title}*." + (f" {pub}." if pub else "")
    elif t == "conference":
        s = f"{a} ({y}). {title}. In *{src}*" + (f" (pp. {pp})" if pp else "") + "." + (f" {pub}." if pub else "")
    elif t == "thesis":
        s = f"{a} ({y}). *{title}* [Undergraduate capstone project" + (f", {inst}" if inst else "") + "]."
    elif t == "web":
        s = f"{a} ({y}). *{title}*." + (f" {src}." if src else "")
    else:
        raise ValueError(f"unknown type '{row['type']}' (use journal, book, web, conference or thesis)")
    return s + (f" {end}" if end else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="?")
    ap.add_argument("--template", metavar="FILE")
    ap.add_argument("--out", default="references.md")
    args = ap.parse_args()

    if args.template:
        with open(args.template, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(COLUMNS)
            w.writerow(["journal", "Dela Cruz, J.; Santos, M.", "2023", "Example only: replace with a real article",
                        "Journal Name", "12", "3", "45-60", "", "10.xxxx/replace-me", "", ""])
        print(f"Wrote template {args.template}. Delete the example row and add REAL sources only.")
        return
    if not args.csv:
        ap.error("give a CSV file or use --template")

    out, problems, warnings = [], [], []
    with open(args.csv, newline="", encoding="utf-8-sig") as f:
        for n, row in enumerate(csv.DictReader(f), start=2):
            if not any((v or "").strip() for v in row.values()):
                continue
            missing = [k for k in ("type", "authors", "year", "title") if not (row.get(k) or "").strip()]
            if missing:
                problems.append(f"row {n}: missing {', '.join(missing)}")
                continue
            if "replace" in (row["title"] + row.get("doi", "")).lower():
                problems.append(f"row {n}: still looks like the example row")
                continue
            try:
                out.append((row["authors"].strip().lower(), row["year"], fmt(row)))
            except ValueError as e:
                problems.append(f"row {n}: {e}")
                continue
            if not link(row) and row["type"].strip().lower() in ("journal", "web", "conference"):
                warnings.append(f"row {n}: no DOI or URL, make sure readers can find it")

    out.sort()
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("# REFERENCES\n\n")
        for _a, _y, line in out:
            f.write(line + "\n\n")
    print(f"Formatted {len(out)} reference(s) -> {args.out}")
    for w in warnings:
        print("warning:", w)
    for p in problems:
        print("skipped:", p)
    if problems:
        sys.exit(1)


if __name__ == "__main__":
    main()
