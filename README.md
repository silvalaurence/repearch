# repearch

A WorkBuddy skill that turns **your real project code** into honest, editable capstone documentation for IT / CS / IS students (built around the common Philippine Chapter 1-5 format).

It does the boring documentation work: reading your code, drawing the ER diagram, building the data dictionary, listing modules and endpoints, formatting the Word file. **You** still write the problem, the literature review, and the conclusions, because you are the one who defends them.

## What it does

| Step | Tool | Result |
|------|------|--------|
| Scan your repo | `scan_repo.py` | Languages, packages, routes, DB tables and foreign keys, migrations, env var names, tests, TODOs. Skips build output, backups, tool folders and vendored skill packs (`--ignore DIR`, `--keep-vendored`), and never reads `.env` files |
| Pull out the facts | `gen_sections.py` | Tech stack table, architecture diagram, endpoints per module, **ER diagram**, **data dictionary**, env table |
| Draft chapters | `templates/` | Chapter 1, 2 (worksheet), 3, 4, 5, appendices, ISO 25010 survey — copy only the ones your school needs |
| Format sources | `format_refs.py` | APA 7 list from sources **you** found (it never makes any up) |
| Build the paper | `build_docx.py` | Word file: title page, TOC, page numbers, diagrams as images, your school's font and margins via presets |
| Survey math | `likert_sheet.py` | Excel sheet that computes weighted means and Strongly Agree/Agree labels from real responses |
| Check what's left | `gaps_report.py` | A to-do list of everything unfinished in the chapters your preset requires, including the title page written by `build_docx.py` (`--strict` fails until it's clean) |

See `examples/sample-output/` for what comes out of a tiny example project.

## What it will NOT do (on purpose)

- Invent survey results, respondents, or test results
- Invent papers, authors, or DOIs
- Write your problem statement, significance, or conclusions as finished text
- Claim your system has features or security it doesn't

Panels check these things, and AI-written fake data can get a capstone failed. Check your school's AI-use policy and your adviser's format before you use any tool like this.

## Install

**WorkBuddy (skill):**

```bash
git clone https://github.com/silvalaurence/repearch ~/.workbuddy-ai/skills/repearch
pip install -r ~/.workbuddy-ai/skills/repearch/requirements.txt
```

Then, inside your project folder, tell WorkBuddy:

> Use the repearch skill on this project.

It will ask a few questions (school, title, users, problem), run the scripts, fill the templates, and give you a `Capstone_Draft.docx` and a "What you still need to do" list.

**Without an AI assistant**, the scripts work on their own:

```bash
python scripts/scan_repo.py ./my-project --out output/scan.json
python scripts/gen_sections.py output/scan.json --out output/
cp templates/*.md output/            # fill in the {{...}} and [STUDENT: ...] parts
python scripts/build_docx.py output/ --title "My Capstone Title" --out Capstone_Draft.docx
python scripts/gaps_report.py output/
```

Optional: `npm i -g @mermaid-js/mermaid-cli` makes diagrams appear as pictures in the Word file. Without it they stay as marked code blocks you can render at [mermaid.live](https://mermaid.live).

## Match your school's format

Two things describe a college's format: the **layout** (which parts the paper has) and the **preset** (how it looks, and how many chapters you submit).

**Layout.** `templates/` is the common Chapters 1-5 layout. `templates/four-chapter/` is a front-matter / four-chapter / back-matter layout: Approval Sheet, Abstract, Acknowledgment, Dedication, List of Tables and List of Figures in front; Chapters 1-4 with the Conclusion, Recommendations and Translational Research inside Chapter IV; Curriculum Vitae and Appendices at the end. Copy the folder your college uses:

```bash
cp templates/four-chapter/*.md output/
```

**Preset.** Copy `presets/four-chapter.json` (or `default.json`), edit it, and pass it in:

```bash
python scripts/build_docx.py output/ --title "..." --preset my-school.json
python scripts/gaps_report.py output/ --preset my-school.json --format four-chapter
```

```json
{"font": "Arial", "size": 12, "line_spacing": 1.5, "left_margin": 1.5, "other_margin": 1.0,
 "chapters": [1, 2, 3, 4]}
```

`chapters` says which chapters your college actually requires, so `gaps_report.py` stops nagging about the rest. Use `"chapters": [3]` if you only submit Chapter 3, or `"chapters": 3` as a shortcut for Chapters 1 to 3.

`--format` tells the checklist to read that layout folder's own files as the list of required parts. A missing Abstract or Curriculum Vitae is then caught, and a part your college never asks for is not.

**Page order comes from the file name:** `00-front-matter.md` goes first, `chapter1.md` through `chapterN.md` follow in order, a file with no number lands after the chapters, and `90-back-matter.md` goes last. Copy the questionnaire as `output/95-questionnaire.md` if you want it printed after the appendices.

If your college uses a section that is not in any folder, add a file to the layout folder - or put `your-name.md` straight in `output/` - and both scripts will treat it as a real part of the paper.

Chapter titles and section numbers live in `templates/`. Edit them to match your college's manual.

## Handing in part of the paper

`--chapters 1-3` works on both scripts and overrides a preset, so a mid-term submission needs no hand-copied JSON file:

```bash
python scripts/build_docx.py output/ --title "..." --chapters 1-3 --out Chapters_1-3.docx
python scripts/gaps_report.py output/ --chapters 1-3 --format four-chapter
```

Only those chapters are built and only those are checked: front matter, back matter and appendices are then out of scope, not "missing". A lone number is still the 1-through-N shortcut, so `--chapters 3` means Chapters 1 to 3 and `--chapters 3-3` means Chapter 3 alone.

The title page is written by `build_docx.py`, so its blanks are filled by flags, not by editing markdown:

```bash
python scripts/build_docx.py output/ --title "PickleHub" --school "St. Rose College" \
  --college "College of Computing Studies" --degree "BS Information Technology" \
  --authors "A. Reyes, B. Cruz" --date "November 2026"
```

Anything you leave out stays marked `[STUDENT: School name]` and yellow. Put the same keys under `"title_page"` in your preset to keep them for every build. The placeholder count it prints is counted in the saved .docx, so it includes that title page - and `gaps_report.py` reads the .docx too (any .docx in the folder, or `--docx path`).

## Figures

- **Caption above the figure**, on its own bold line: `**Figure 3.1 The system architecture**`. `build_docx.py` uses that as the printed caption and invents nothing otherwise.
- **Draw for the page.** mermaid.live returns whatever shape the graph wants; a wide tree at page width prints as a strip nobody can read, and the builder warns you when that happens. Group nodes into row-wise subgraphs, and split any tree with more than ~15 leaves into two captioned figures.
- **Big schemas are already split.** `diagrams/er.mmd` is the printable figure (entities and relationships only), `diagrams/er_detail.mmd` keeps every column for the data dictionary, and `diagrams/er_part1.mmd`, `er_part2.mmd` ... follow the foreign-key lines into page-sized groups.

## A dry run, in the open

Asking what the paper would look like before the work exists is fine, as long as it is marked. Put sample sentences inside `[DRY-RUN: ...]` - a test date, a number of respondents, a place where sessions were "observed". They print bright green, `gaps_report.py --dry-run` lists each one under "Sentences you wrote yourself in this dry run", and `--strict` fails until you have proven or deleted them.

## What it understands

SQL files with `CREATE TABLE` (inline or table-level foreign keys), Prisma schemas, Laravel migrations, and routes from Express, Flask/FastAPI-style decorators, Laravel `Route::`, and Django `path()`. Package detection reads `package.json`, `composer.json`, and `requirements.txt`. Other stacks still work: the assistant reads the code directly, and the scan just finds less.

## Limits

- The table of contents rebuilds itself when Word opens the file. A reader that ignores that instruction shows the placeholder line instead, so right-click the list and choose **Update Field > Update entire table**.
- Use case and data flow diagrams are drawn from the roles and modules the assistant finds. Always check them against your real system.
- Tested on small sample projects. Please open an issue if it chokes on yours.

## Tests

```bash
pip install -r requirements.txt pytest
pytest -q
```

## Contributing

Ideas that would help: presets for specific schools' manuals, more stacks in the scanner, a Filipino-language survey template. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT. See [LICENSE](LICENSE). Not affiliated with any school. You are responsible for your own capstone's content and for following your institution's rules.
