# Contributing

Thanks for helping other students. A few ground rules keep this tool useful and honest.

## Non-negotiable
- **No fabricated content.** Nothing in this repo may generate fake survey data, fake respondents, fake citations, or fake test results. Pull requests that do will be closed.
- **Facts from code only.** If the scanner can't see it, the output must say `[STUDENT: ...]`, not guess.
- **A diagram states only what the code shows.** A tier is drawn where a client demonstrably reaches it or the repo registers the routes; leftover prototype folders are named as such instead of becoming a box in Figure 3.1.
- **Sample prose is marked, never smuggled.** A sanctioned dry run writes `[DRY-RUN: ...]`, the builder prints those passages separately from the blanks, and `--strict` fails on them.
- **Never read secrets.** The scanner must not open `.env` files or record key values.

## Behaviours that are intentional - please do not "fix" them
- A layout folder **is** the checklist. `templates/four-chapter/` matches one school's manual heading for heading, and `gaps_report.py --format` reads that folder instead of a list kept in code. A new college format is a new folder, not a new branch of logic.
- Migration files are printed as **Schema Change History**. They are the student's real evidence for an iterative development model.
- **Chapter 2 stays a worksheet** until the student supplies sources. An unfinished-looking chapter is the tool doing its job.
- A blank is reported as a blank, including the ones `build_docx.py` writes on the title page.
- A version number is printed for a technology **only** when the package that supplied it is that technology; otherwise the column shows `-`.

## Good first contributions
- A preset in `presets/` for a school's manual (add the school name and where the rule is stated)
- Scanner support for another stack (Django models, Spring entities, Room/Flutter, ASP.NET)
- Templates in Filipino or for other capstone formats
- Better edge cases for foreign keys and schema parsing

## Setup
```bash
pip install -r requirements.txt pytest
pytest -q
```
Add a test for new behavior: `tests/test_field_feedback.py` holds one test per real-world failure that got fixed, `tests/test_smoke.py` covers the pipeline as a whole. If you add a scanner feature, extend `examples/sample-project`, or add a small fixture folder that reproduces the junk a real repo contains - `examples/scan-noise-project` is the model for that. Use placeholder names, never a student's actual project.

## Style
Plain Python 3.9+, standard library where possible, short functions, clear messages for students (not stack traces).
