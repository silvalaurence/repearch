#!/usr/bin/env python3
"""Create Survey_Results.xlsx: paste real Likert responses, get weighted means and interpretations.

Usage: python likert_sheet.py --out Survey_Results.xlsx [--questions survey_iso25010.md]
The sheet starts EMPTY. It never contains made-up responses.
"""
import argparse
import re

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

DEFAULT = {
    "A. Functional Suitability": ["A1", "A2", "A3"],
    "B. Performance Efficiency": ["B1", "B2"],
    "C. Usability": ["C1", "C2", "C3", "C4"],
    "D. Reliability": ["D1", "D2"],
    "E. Security": ["E1", "E2"],
    "F. Maintainability / Compatibility": ["F1", "F2"],
}
MAX_RESPONDENTS = 200


def parse_questions(path):
    groups, current = {}, None
    for line in open(path, encoding="utf-8"):
        h = re.match(r"^##\s+([A-Z]\.\s+.*)", line)
        if h:
            current = re.sub(r"\s*\(.*\)", "", h.group(1)).strip()
            groups[current] = []
            continue
        q = re.match(r"^\|\s*([A-Z]\d+)\s*\|", line)
        if q and current:
            groups[current].append(q.group(1))
    return {k: v for k, v in groups.items() if v} or DEFAULT


def interp_formula(cell):
    return (f'=IF({cell}="","",IF({cell}>=4.21,"Strongly Agree",IF({cell}>=3.41,"Agree",'
            f'IF({cell}>=2.61,"Neutral",IF({cell}>=1.81,"Disagree","Strongly Disagree")))))')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="Survey_Results.xlsx")
    ap.add_argument("--questions", default=None)
    args = ap.parse_args()
    groups = parse_questions(args.questions) if args.questions else DEFAULT

    wb = Workbook()
    ws = wb.active
    ws.title = "Responses"
    head_fill = PatternFill("solid", fgColor="1F3864")
    ws["A1"] = "Respondent #"
    items = [q for qs in groups.values() for q in qs]
    for j, q in enumerate(items, start=2):
        ws.cell(row=1, column=j, value=q)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = head_fill
        c.alignment = Alignment(horizontal="center")
    for r in range(2, MAX_RESPONDENTS + 2):
        ws.cell(row=r, column=1, value=r - 1)
    ws.freeze_panes = "B2"
    ws["A" + str(MAX_RESPONDENTS + 4)] = "Enter each respondent's answers (1 to 5) in their row. Leave blank if not answered."
    for j in range(1, len(items) + 2):
        ws.column_dimensions[get_column_letter(j)].width = 8 if j > 1 else 14

    sm = wb.create_sheet("Summary")
    sm.append(["Item", "Group", "Responses", "Mean", "Interpretation"])
    for c in sm[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = head_fill
    row = 2
    col_of = {q: get_column_letter(j) for j, q in enumerate(items, start=2)}
    item_rows = {}
    for g, qs in groups.items():
        for q in qs:
            col = col_of[q]
            rng = f"Responses!{col}2:{col}{MAX_RESPONDENTS + 1}"
            sm.cell(row=row, column=1, value=q)
            sm.cell(row=row, column=2, value=g)
            sm.cell(row=row, column=3, value=f"=COUNT({rng})")
            sm.cell(row=row, column=4, value=f'=IF(C{row}=0,"",ROUND(AVERAGE({rng}),2))')
            sm.cell(row=row, column=5, value=interp_formula(f"D{row}"))
            item_rows.setdefault(g, []).append(row)
            row += 1

    row += 1
    sm.cell(row=row, column=1, value="Weighted mean per group").font = Font(bold=True)
    row += 1
    for c, h in enumerate(["Group", "", "", "Weighted mean", "Interpretation"], start=1):
        sm.cell(row=row, column=c, value=h).font = Font(bold=True)
    row += 1
    for g, rows in item_rows.items():
        refs = ",".join(f"D{r}" for r in rows)
        sm.cell(row=row, column=1, value=g)
        sm.cell(row=row, column=4, value=f'=IF(COUNT({refs})=0,"",ROUND(AVERAGE({refs}),2))')
        sm.cell(row=row, column=5, value=interp_formula(f"D{row}"))
        row += 1
    sm.column_dimensions["A"].width = 34
    sm.column_dimensions["B"].width = 34
    sm.column_dimensions["D"].width = 14
    sm.column_dimensions["E"].width = 20

    sc = wb.create_sheet("Scale")
    for r in [["Mean range", "Verbal interpretation"], ["4.21 - 5.00", "Strongly Agree"],
              ["3.41 - 4.20", "Agree"], ["2.61 - 3.40", "Neutral"], ["1.81 - 2.60", "Disagree"],
              ["1.00 - 1.80", "Strongly Disagree"]]:
        sc.append(r)
    sc["A1"].font = sc["B1"].font = Font(bold=True)
    sc.column_dimensions["A"].width = 16
    sc.column_dimensions["B"].width = 24

    wb.save(args.out)
    print(f"Wrote {args.out} (empty, ready for real responses)")


if __name__ == "__main__":
    main()
