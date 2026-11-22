<img src="site/logo.svg" alt="repearch" width="370">

repearch turns your real project code into honest, editable capstone documentation for IT / CS / IS students, in the common Philippine Chapter 1–5 format. It reads your code, draws the ER diagram, builds the data dictionary, lists modules and endpoints, and formats the Word file. You still write the problem, the literature review, and the conclusions, because you are the one who defends them.

It is a portable agent skill — a `SKILL.md` plus plain-Python scripts — that works with any AI coding harness. There is no vendor lock-in: the scripts depend only on `python-docx` and `openpyxl`, and there is no SDK, API key, model call, or harness-specific code. Every script also runs by hand from a terminal.

repearch will not invent survey results, respondents, test results, papers, authors, or DOIs, and will not write your problem statement or conclusions as finished text.

## Run

1. Clone into wherever your agent discovers skills: `git clone https://github.com/silvalaurence/repearch <skills-dir>/repearch`, then `pip install -r <skills-dir>/repearch/requirements.txt`. WorkBuddy reads `~/.workbuddy-ai/skills/`.
2. Inside your project, tell the agent: "Use the repearch skill on this project." It asks a few questions, runs the scripts, fills the templates, and produces `Capstone_Draft.docx` plus a "what you still need to do" list.
3. Without an agent, run the scripts directly:
   - `python scripts/scan_repo.py ./my-project --out output/scan.json`
   - `python scripts/gen_sections.py output/scan.json --out output/`
   - `cp templates/*.md output/` and fill the `{{...}}` and `[STUDENT: ...]` parts
   - `python scripts/build_docx.py output/ --title "..." --out Capstone_Draft.docx`
   - `python scripts/gaps_report.py output/`
4. Match your school's format with `templates/four-chapter/`, a preset in `presets/`, `--chapters` to submit part of the paper, `--split` for one file per chapter, and `strip_numbering.py` to remove dotted labels. `check_consistency.py` reports sentences in Chapters I and II that contradict the design statement in Chapter III.

Optional: `npm i -g @mermaid-js/mermaid-cli` renders diagrams as pictures in the Word file; otherwise they stay as code blocks.

## Files

- `SKILL.md` — agent instructions
- `scripts/` — scanner, section generator, Word builder, gaps report, and helpers
- `templates/` — chapter layouts, including `four-chapter/`
- `presets/` — school-specific formatting presets
- `references/` — document and section outlines
- `examples/` — sample input and output
- `site/logo.svg` — README logo

MIT licensed. Not affiliated with any school; you are responsible for your own capstone content and your institution's rules.
