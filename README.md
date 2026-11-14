# repearch

A portable **agent skill** — a `SKILL.md` plus plain-Python scripts — that works with **any AI coding harness**, and turns **your real project code** into honest, editable capstone documentation for IT / CS / IS students (built around the common Philippine Chapter 1-5 format).

It does the boring documentation work: reading your code, drawing the ER diagram, building the data dictionary, listing modules and endpoints, formatting the Word file. **You** still write the problem, the literature review, and the conclusions, because you are the one who defends them.

**No vendor lock-in.** `SKILL.md` is just an instruction sheet in the open Agent Skills format (a folder with YAML frontmatter and Markdown); the scripts are ordinary Python 3 depending only on `python-docx` and `openpyxl`. There is no SDK, API key, model call, or harness-specific code anywhere in this repo. Any agent that can discover a skills folder can drive it — and every script also runs by hand from a terminal with no agent at all.

## What it does

| Step | Tool | Result |
|------|------|--------|
| Scan your repo | `scan_repo.py` | Languages, packages, routes, DB tables and foreign keys, migrations, env var names, tests, TODOs. Skips build output, backups, tool folders and vendored skill packs (`--ignore DIR`, `--keep-vendored`), and never reads `.env` files |
| Pull out the facts | `gen_sections.py` | Tech stack table, architecture diagram, endpoints per module, **ER diagram**, **data dictionary**, env table |
| Draft chapters | `templates/` | Chapter 1, 2 (worksheet), 3, 4, 5, appendices, ISO 25010 survey — copy only the ones your school needs |
| Format sources | `format_refs.py` | APA 7 list from sources **you** found (it never makes any up) |
| Build the paper | `build_docx.py` | Word file: title page, TOC, page numbers, diagrams as images, your school's font and margins via presets. `--split` also writes one file per chapter |
| Renumber, or stop numbering | `strip_numbering.py` | Drops `2.1` and `Table 2.1` labels when your manual wants plain names, and refuses to save while a cross-reference still points at a number you just deleted |
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

repearch is a **folder, not a package**. Put it wherever your AI harness discovers skills; the folder itself needs no changes from one harness to another.

```bash
# <skills-dir> is wherever your agent looks for skills.
git clone https://github.com/silvalaurence/repearch <skills-dir>/repearch
pip install -r <skills-dir>/repearch/requirements.txt
```

For example, WorkBuddy reads `~/.workbuddy-ai/skills/`, so there the command is
`git clone https://github.com/silvalaurence/repearch ~/.workbuddy-ai/skills/repearch`.
Most harnesses also accept a project-local skills folder, and any agent can simply be pointed at this repo's `SKILL.md` directly — frontmatter (`name`, `description`) plus instructions is all the format requires. If your harness uses a different directory, just clone there instead.

Then, inside your project folder, tell your agent:

> Use the repearch skill on this project.

It will ask a few questions (school, title, users, problem), run the scripts, fill the templates, and give you a `Capstone_Draft.docx` and a "What you still need to do" list.

**Without any agent**, the scripts work on their own:

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

Only those chapters are built and only those are checked: front matter, back matter and appendices are then out of scope, not "missing". A lone number is still the 1-through-N shortcut, so `--chapters 3` means Chapters 1 to 3 and `--chapters 3-3` means Chapter 3 alone. `--chapters 2,3` and `--chapters 2-3` both mean the same two chapters.

If each chapter is handed in as its own file, add `--split`. One document is written per chapter, and each carries only the references that chapter actually cites, so Chapter II does not arrive stapled to sources it never mentions:

```bash
python scripts/build_docx.py output/ --title "..." --chapters 2,3 --split --out Chapters_2-3.docx
# Chapters_2-3.docx, Chapters_2-3 - Chapter 2.docx, Chapters_2-3 - Chapter 3.docx
```

Split files need a `references.md` in the folder (`format_refs.py` writes one); without it the builder says so instead of shipping chapters with no bibliography. An entry whose author line cannot be read is kept rather than guessed at - leaving out a source the chapter did cite is the worse mistake.

## Sections without numbers

Some manuals want `2.1 Theoretical Background` and `Table 2.1 Summary of studies`; others want the same pages with plain names. `strip_numbering.py` removes the labels from headings and captions, and then stops:

```bash
python scripts/strip_numbering.py output/              # what would change, and what would break
python scripts/strip_numbering.py output/ --write      # apply it, once nothing dangles
```

The moment a number disappears, every sentence that said "see Table 2.1" or "discussed in Section 3.4" points at nothing. The script lists each of those with its file and line, suggests a rewrite, and refuses to save until they are fixed - or until you pass `--allow-dangling` and accept them. Only dotted labels are touched, so a chapter numeral like `II.` survives; that is the number the manual uses to find the chapter. Rewriting the sentences themselves stays your job, because only you know what "the Research Instrument section" should say.

The title page is written by `build_docx.py`, so its blanks are filled by flags, not by editing markdown:

```bash
python scripts/build_docx.py output/ --title "PickleHub" --school "St. Rose College" \
  --college "College of Computing Studies" --degree "BS Information Technology" \
  --authors "A. Reyes, B. Cruz" --date "November 2026"
```

Anything you leave out stays marked `[STUDENT: School name]` and yellow. Put the same keys under `"title_page"` in your preset to keep them for every build. The placeholder count it prints is counted in the saved .docx, so it includes that title page - and `gaps_report.py` reads the .docx too (any .docx in the folder, or `--docx path`).

## Figures

- **Caption above the figure**, on its own bold line: `**Figure 3.1 The system architecture**`. `build_docx.py` uses that as the printed caption and invents nothing otherwise.
- **A caption does not need a number.** `**Summary of related studies**` directly above a table becomes that table's caption, printed bold and centred above it; the same line above a diagram or image becomes the figure caption. A bold line that ends in a full stop is read as an emphasised sentence, not a title, so `**Treatment of data.**` stays in the body where it belongs. With no caption line at all, the figure simply gets none - the gaps report is where that shows up.
- **Ticks and crosses get a font that can draw them.** Neither Arial nor Times New Roman has `✓` or `✗`, so a comparative matrix built from them prints as empty boxes. `build_docx.py` moves only those glyphs to a symbol font and leaves the prose in your school's typeface.
- **Draw for the page.** mermaid.live returns whatever shape the graph wants; a wide tree at page width prints as a strip nobody can read, and the builder warns you when that happens. The check is on the width-to-height ratio, not just on height: a 3.4:1 chart still prints 1.6 in tall and still loses every label, so anything past about 2.4:1 is flagged. Group nodes into row-wise subgraphs, and split any tree with more than ~15 leaves into two captioned figures.
- **Big schemas are already split.** `diagrams/er.mmd` is the printable figure (entities and relationships only), `diagrams/er_detail.mmd` keeps every column for the data dictionary, and `diagrams/er_part1.mmd`, `er_part2.mmd` ... follow the foreign-key lines into page-sized groups.

## Tables

A pipe table in the markdown becomes a bordered table that fills the text block exactly, header row shaded and repeated if the table runs onto a second page, and no row split across a page break.

- **Columns follow the content.** Widths come from the 90th percentile of each column's cell length, so one long cell cannot starve the rest, compressed with a 0.75 power so a 105-character cell does not take four times the room of a 29-character label.
- **No header breaks mid-word.** Each column has a floor taken from the longest word in its header.
- **Ticks and counts share one width and are centred.** A column that is mostly `✓`, `✗` or a single number is treated as a scale: every such column in a table gets the same width, and its cells are centred rather than ragged left.
- **Not everything belongs in a grid.** A table earns its place when several items share the same attributes. A block of label-and-one-paragraph items - a Business Model Canvas, a software specification - reads better as a bulleted list with the label in bold, which is also how Chapter I usually states its objectives and definitions. Write `- **Key Partners.** ...` and it prints as a hanging-indent bullet.

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
