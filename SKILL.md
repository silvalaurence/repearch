---
name: repearch
description: Drafts the documentation parts of a Philippine IT/CS/IS capstone (Chapters 1-5 scaffolding, data dictionary, ER and architecture diagrams, appendices, ISO 25010 survey, APA references) from the student's real project code, and builds a formatted .docx. Use when a student asks to turn their project into capstone or thesis documentation.
---

# repearch

Turns a student's real codebase into honest, editable capstone drafts. The code is the source of truth. The student stays the author.

## Hard rules (never break these)

1. **Never invent survey data, respondents, interview answers, or test results.** If it was not run or collected, it is a placeholder.
2. **Never invent citations or references.** Chapter 2 is a worksheet, not a draft. Only suggest search keywords and databases (Google Scholar, IEEE Xplore, ScienceDirect, Philippine E-Journals, school library). References come only from sources the student gives you, formatted with `format_refs.py`.
3. **Never write the student's problem statement, gap, significance, or conclusions as finished text.** Offer guiding questions and a rough starter marked `[STUDENT: rewrite in your own words]`.
4. **Mark every unfinished part.** `[STUDENT: ...]` for a part only the student can fill in, `[DRY-RUN: ...]` for sample prose written because a dry run was asked for (see "Sanctioned dry run"). Both are highlighted in the .docx and both fail `--strict`, so nothing slips into the final paper unnoticed.
5. **Only describe what the code actually does.** If a feature is not in the repo, do not list it as implemented. Do not claim security features (encryption, hashing, role checks) you did not see in the code.
6. **Never read or quote secrets.** Skip `.env` files, keys, and passwords. Env var names only.
7. Remind the student once to check their school's AI-use policy and their adviser's required format.

## Workflow

Scripts live in `scripts/` next to this file. Python 3 with `pip install python-docx openpyxl`. Work in an `output/` folder inside the student's project (or a scratch folder). Do not modify the student's code.

### Step 1: Intake (one short batch, max 11 questions)
- School, course, and the manual or template their college follows (chapter layout, SDLC model)
- **How many chapters does your college require, and which ones?** Some want Chapters 1-5, some only Chapter 3. Ask this even when the student already sent a format manual, then record it as `chapters` in the preset: `"chapters": [3]` for that chapter alone, or `"chapters": 3` for Chapters 1 through 3. Pass the same preset to `build_docx.py` and `gaps_report.py`. Copy only those chapter templates, and never nag the student about a chapter their school does not want.
- **Which layout does your college use?** `templates/` holds the default Chapters 1-5 layout; `templates/four-chapter/` holds a front-matter / four-chapter / back-matter layout. Use the matching folder and pass its name to `gaps_report.py` with `--format four-chapter`, so the checklist reads that folder's own files instead of the default list. If the student's college uses a layout nobody has added yet, build it as a new folder of templates and the checklist will follow it automatically.
- **Any section name you do not recognise, ask about - do not fill it in.** For example some colleges require "Translational Research" and mean different things by it. Write the guiding questions into the template and leave the content to the student.
- Project title and one-sentence purpose
- Who the users are (e.g., barangay staff, students, clinic patients)
- The real-world problem being solved
- Adviser's format if different from default (Times New Roman 12, double spaced, left margin 1.5 in). If so, copy `presets/default.json`, edit it, and pass it with `--preset`.
- Whether the system has been tested with real users yet
- Dev model used (Agile, Waterfall, Prototyping, etc.)

If the student is unavailable or does not answer, use defaults, say which were used, and mark them `[STUDENT: confirm]`.

### Step 2: Scan the repo
```
python scripts/scan_repo.py <project> --out output/scan.json
python scripts/gen_sections.py output/scan.json --out output/
```
`gen_sections.py` writes `output/auto_sections.md` (tech stack, endpoints per module, ER diagram, data dictionary, env table, tests found, TODO limitations) and `output/diagrams/*.mmd`. These are facts from the code. Read key source files directly when the scan is not enough (auth, main modules, what each screen does). If the scan found no tables, ask whether there is a schema to export, instead of guessing.

The scanner already skips dot-folders, build output (`dist`, `out`, `build`, `.expo`, `.vercel`), backups, and any vendored skill or agent pack, and reports how many folders it skipped. If a folder it kept is not the student's code, add `--ignore <dir>`; if the repo *is* a skill pack, pass `--keep-vendored`.

What the scan separates, because a paper cannot afford to blur them:
- **Tests in the project's own test folders** versus files that merely look like tests. Only the first count belongs in Chapter 3.
- **Env variables the app reads** versus names merely declared in `.env.example`. Never a value, and never shell noise (`COLORTERM`, `npm_*`, `REMOTION_*`).
- **Server files the client demonstrably calls** versus a leftover prototype. `gen_sections.py` draws a backend tier only when a client call reaches one and a backend package is declared; otherwise it says so in the notes. Repeat that note to the student instead of drawing the box they expected.
- **Declared dependency versions** per exact package. A version is printed for a technology only when that package *is* the technology; otherwise the column shows `-`.

### Step 3: Draft chapters
Copy the templates for the parts the school asked for, from the layout folder chosen in Step 1, into `output/` and fill the `{{...}}` fields using the intake answers, `auto_sections.md`, and the code. Page order comes from the file name: a leading number like `00-front-matter.md` places the page first, `chapterN.md` places the chapter, and anything else falls after the chapters and before the back matter. In the four-chapter layout, copy the questionnaire as `output/95-questionnaire.md` so it prints after the appendices. If the student brought their own template file (a school format this folder does not have), copy it into `output/` under its own name and fill it the same way: `build_docx.py` still orders it and `gaps_report.py` treats it as an extra section rather than a missing one. Ask the student where their template's headings should go if it is not obvious.

| File | Content |
|------|---------|
| `chapter1.md` | Background, objectives (from real modules), scope and delimitations, conceptual framework outline |
| `chapter2.md` | Worksheet only: search plan, reading log. Leave as the student's to write |
| `chapter3.md` | Architecture, stack, modules, use cases, DFD, database, data dictionary, security (only what exists), evaluation method |
| `chapter4.md` | Screens, test cases (results blank until run), evaluation results (blank until survey done) |
| `chapter5.md` | Summary of findings, conclusions, recommendations. Each one must trace to a real Chapter 4 result; leave the wording to the student |
| `appendices.md` | User manual, install guide from README/manifests, env table |
| `survey_iso25010.md` | Questionnaire (edit items to fit the system) |

The default layout above. `templates/four-chapter/` holds the other layout: front matter, Chapters 1-4 named the way that manual names them, and back matter.

Diagrams: replace each ```` ```mermaid-placeholder ```` block in the templates with a real ```` ```mermaid ```` block. Use the architecture and ER blocks from `auto_sections.md`. For use case and data flow diagrams, write Mermaid from the roles and modules you actually found. If the student has screenshots, reference them as `![Figure 4.1. Login page](screenshots/login.png)`.

**Caption a figure on the line above it**, as `**Figure 3.1 The system flowchart**`. `build_docx.py` uses that line as the printed caption and invents nothing; a diagram with no caption simply gets none.

**A caption does not have to carry a number.** If the manual numbers nothing, write `**Summary of related studies**` on the line above the table or diagram and it becomes the caption - bold and centred above a table, below a figure. A bold line ending in a full stop is treated as an emphasised sentence, so `**Treatment of data.**` stays in the body. Never add a number the student's manual does not use just to make the builder happy.

**Draw for the page, not for the screen.** mermaid.live returns whatever shape the graph wants, and a wide tree comes back 18:1 - at page width that prints as a strip nobody can read, and `build_docx.py` warns when it happens. The warning is on the width-to-height ratio, so a 3.4:1 chart is flagged even though it clears 1.6 in tall. Group nodes into row-wise subgraphs, and split any tree with more than about fifteen leaves into two figures. `gen_sections.py` already does this for large schemas: `diagrams/er.mmd` holds entities and relationships only (the printable figure), `diagrams/er_detail.mmd` keeps every column (the data dictionary source), and `diagrams/er_partN.mmd` follows foreign-key lines into page-sized groups. Caption the parts as separate figures instead of shrinking one large one.

### Step 4: References (only if the student has sources)
```
python scripts/format_refs.py --template refs.csv      # student fills with REAL sources
python scripts/format_refs.py refs.csv --out output/references.md
```
If the student has no sources yet, help them build a search plan in `chapter2.md` instead. Do not make up papers, authors, or DOIs.

### Step 5: Build outputs
```
python scripts/build_docx.py output/ --title "<Project title>" --preset <school preset> \
  --chapters 1-3 --school "..." --college "..." --degree "..." --authors "..." --date "November 2026" \
  --out Capstone_Draft.docx
python scripts/likert_sheet.py --questions output/survey_iso25010.md --out Survey_Results.xlsx
```
Skip `likert_sheet.py` when Chapter 4 is not part of this school's format; there is no evaluation chapter to fill.
Mermaid blocks become images automatically when `mmdc` is installed (`npm i -g @mermaid-js/mermaid-cli`); otherwise they stay as a highlighted block to render at mermaid.live.

`--chapters 1-3` builds only what this run hands in; front and back matter join in only for a whole-paper run, and the skipped files are listed so nothing vanishes silently. The comma form works too: `--chapters 2,3` and `--chapters 2-3` are the same two chapters. `--school/--college/--degree/--authors/--date` fill the title page - the same keys also work under `"title_page"` in the preset, so a group that builds the paper weekly does not retype them. Ask for them at intake; a title page left as `[STUDENT: School name]` is a blank page in the printed draft. The counts the builder prints are read back out of the saved .docx, so they include the title page it wrote.

**When the student hands in one chapter at a time**, add `--split`. Each chapter gets its own file and its own reference list, cut down to the sources that chapter actually cites. It needs `output/references.md`; without one the builder says so rather than shipping a chapter with no bibliography. If the student says "I only need to pass Chapter 2 and Chapter 3", this is the flag - do not write a bespoke splitting script.

**When the manual wants no section numbers**, run `strip_numbering.py` before the build:
```
python scripts/strip_numbering.py output/            # shows the edits and every reference that would break
python scripts/strip_numbering.py output/ --write    # applies them, once nothing dangles
```
It removes `2.1` from headings and `Table 2.1`/`Figure 2.1` from captions, keeps chapter numerals like `II.`, and refuses to save while a sentence still says "Section 3.4". Rewriting those sentences is yours to do - name the part instead ("the Research Instrument section", "the interpretation table below"). Never pass `--allow-dangling` just to get past the check; a draft full of dead cross-references is what the panel notices.

### Step 6: Gaps report
```
python scripts/gaps_report.py output/ --preset <school preset> --format <layout folder> \
  --chapters 1-3 --survey Survey_Results.xlsx --dry-run
```
Pass the same preset used in Step 5, plus `--format` when the student's college uses a layout folder other than the default. `--chapters 1-3` overrides a preset on the command line, so a partial submission needs no hand-copied JSON file; a part outside the scope - front matter, back matter, appendices - is then not reported missing, only out of scope. Show the student the result under the title **"What you still need to do"**. Read the .docx once (convert to PDF and look at a few pages) before handing it over.

The report reads the built .docx too (any .docx in the folder, or `--docx <path>`), because the title page is written by `build_docx.py` and appears in no markdown draft. Use `--strict` before a hand-in: it exits 1 while anything is unfinished.

## Sanctioned dry run

When a student asks to see what the paper would look like before the work exists, that is allowed - but only in the open. Write the sample sentences and wrap each one in `[DRY-RUN: ...]`; they print bright green, `gaps_report.py --dry-run` lists every one under "Sentences you wrote yourself in this dry run", and `--strict` fails on them. Each listed sentence is a claim the student must personally verify, prove, or delete: a test date, a number of respondents, a place where sessions were observed. Never let a `[DRY-RUN: ...]` sentence survive into a submission, and never turn one into plain text just to make the draft read better.

## Proven in the field - keep these

A real run (Expo + Supabase, Agile, Chapters 1-3 only) confirmed these behave correctly. They look like inefficiency; they are the point. Do not "optimise" them away.

- **The layout folder is the checklist.** `templates/four-chapter/` matched the school manual's headings one for one, so `--format` needed no extra configuration and reported nothing the manual does not require. A new college layout is a new folder of templates, never a new code path.
- **Sprint-numbered migration files are printed as Schema Change History.** They are the student's real evidence for an iterative model in Section 3.11, and they cost nothing to keep. Do not fold them into the ER diagram.
- **Chapter 2 stays a worksheet when the student has no sources.** The no-invented-citations rule forcing an unfinished Chapter 2 is the tool protecting the student from a defense question they cannot answer. A full-looking Chapter 2 with unverifiable citations is a failure, not a convenience.
- **A blank is reported as a blank.** Title-page fields, unread diagrams, and empty survey sheets all show up in the gaps report even though they make the output look less finished.
- **A tier with no evidence behind it is not drawn.** Saying "these server files read as a legacy prototype, not wired" is more useful to the student than the diagram they expected.

## Tone
Be a helpful assistant, not a ghostwriter. Short, plain language. The student must be able to explain every sentence at their defense.
