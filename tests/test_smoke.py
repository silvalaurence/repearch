"""Smoke tests: run the whole pipeline on the example project. Run with: pytest -q"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
SAMPLE = ROOT / "examples" / "sample-project"
LARAVEL_SAMPLE = ROOT / "examples" / "laravel-project"
TEMPLATES = ("chapter1.md", "chapter2.md", "chapter3.md", "chapter4.md", "chapter5.md",
             "appendices.md", "survey_iso25010.md")


def run(*args, check=True):
    return subprocess.run([sys.executable, "-I", *map(str, args)], capture_output=True, text=True, check=check)


def missing_section(gaps_text):
    """The '## Missing sections' list only, so mentions elsewhere in the report do not count."""
    m = re.search(r"## Missing sections\n\n(.*?)(?=\n## |\Z)", gaps_text, re.S)
    return m.group(1) if m else ""


def test_scan_finds_real_facts(tmp_path):
    out = tmp_path / "scan.json"
    run(SCRIPTS / "scan_repo.py", SAMPLE, "--out", out)
    d = json.loads(out.read_text())
    assert set(d["tables"]) == {"residents", "staff", "tickets"}
    fks = {c["name"]: c["ref"] for c in d["tables"]["tickets"] if c.get("ref")}
    assert fks == {"resident_id": "residents", "called_by": "staff"}
    assert {r["path"] for r in d["routes"]} >= {"/queue", "/residents"}
    assert set(d["folders"]) == {"db", "routes", "tests"}
    assert {r["file"] for r in d["routes"]} >= {"routes/queue.js"}  # forward slashes on Windows too
    assert set(d["env_vars"]) >= {"DB_HOST", "JWT_SECRET"}
    assert d["test_files"]


def test_scanner_never_reads_env_files(tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    (proj / ".env").write_text("DB_PASSWORD=supersecret123\n")
    (proj / "app.py").write_text("print('hi')\n")
    out = tmp_path / "scan.json"
    run(SCRIPTS / "scan_repo.py", proj, "--out", out)
    assert "supersecret123" not in out.read_text()


def test_full_pipeline(tmp_path):
    scan, outdir = tmp_path / "scan.json", tmp_path / "output"
    run(SCRIPTS / "scan_repo.py", SAMPLE, "--out", scan)
    run(SCRIPTS / "gen_sections.py", scan, "--out", outdir)
    auto = (outdir / "auto_sections.md").read_text()
    assert "erDiagram" in auto and "residents ||--o{ tickets" in auto
    assert "Express.js" in auto
    for t in TEMPLATES:
        (outdir / t).write_text((ROOT / "templates" / t).read_text())
    docx = tmp_path / "out.docx"
    r = run(SCRIPTS / "build_docx.py", outdir, "--title", "Test", "--out", docx, "--no-render")
    assert docx.exists() and docx.stat().st_size > 10_000
    assert "placeholders left" in r.stdout
    from docx import Document
    texts = [p.text for p in Document(docx).paragraphs]
    assert texts.index("CHAPTER 4") < texts.index("CHAPTER 5") < texts.index("APPENDICES")
    x = tmp_path / "s.xlsx"
    run(SCRIPTS / "likert_sheet.py", "--questions", outdir / "survey_iso25010.md", "--out", x)
    assert x.exists()
    g = run(SCRIPTS / "gaps_report.py", outdir, "--survey", x)
    gaps = (outdir / "GAPS.md").read_text()
    assert "What you still need to do" in gaps and "no responses yet" in gaps
    s = run(SCRIPTS / "gaps_report.py", outdir, "--strict", check=False)
    assert s.returncode == 1  # unfinished drafts must fail strict mode


def test_refs_formatter_rejects_incomplete_and_example_rows(tmp_path):
    csvp = tmp_path / "r.csv"
    run(SCRIPTS / "format_refs.py", "--template", csvp)
    r = run(SCRIPTS / "format_refs.py", csvp, "--out", tmp_path / "o.md", check=False)
    assert r.returncode == 1  # the untouched example row must be refused
    csvp.write_text("type,authors,year,title,source,volume,issue,pages,publisher,doi,url,institution\n"
                    "journal,\"Reyes, A.; Cruz, B.\",2022,A real-looking title,Some Journal,5,2,10-20,,10.1234/abc,,\n"
                    "book,,2020,No author,,,,,Pub,,,\n")
    r = run(SCRIPTS / "format_refs.py", csvp, "--out", tmp_path / "o.md", check=False)
    out = (tmp_path / "o.md").read_text()
    assert "Reyes, A., & Cruz, B. (2022)" in out and "https://doi.org/10.1234/abc" in out
    assert "missing authors" in r.stdout


def test_er_figure_is_relations_and_detail_is_valid_mermaid(tmp_path):
    scan, outdir = tmp_path / "scan.json", tmp_path / "output"
    run(SCRIPTS / "scan_repo.py", SAMPLE, "--out", scan)
    run(SCRIPTS / "gen_sections.py", scan, "--out", outdir)
    er = (outdir / "diagrams" / "er.mmd").read_text()
    # The printed figure carries entities and relationships only, never a column list.
    assert "username" not in er and '"resident_id"' in er
    detail = (outdir / "diagrams" / "er_detail.mmd").read_text()
    assert "UNIQUE" not in detail and "username UK" in detail  # Mermaid only accepts PK, FK, UK
    import shutil
    exe = shutil.which("mmdc")
    if exe:
        cfg = tmp_path / "pp.json"
        cfg.write_text('{"args": ["--no-sandbox"]}')
        # On Windows 'mmdc' is a .CMD shim; the bare name is not resolvable by
        # CreateProcess, so pass the full path (exactly what render_mermaid does).
        subprocess.run([exe, "-i", str(outdir / "diagrams" / "er.mmd"), "-o", str(tmp_path / "er.png"), "-p", str(cfg)],
                       check=True, capture_output=True)
        assert (tmp_path / "er.png").exists()


def test_laravel_migrations_are_parsed(tmp_path):
    """Regression: an undefined regex killed the whole scan on any Laravel project."""
    scan = tmp_path / "scan.json"
    r = run(SCRIPTS / "scan_repo.py", LARAVEL_SAMPLE, "--out", scan, check=False)
    assert r.returncode == 0, r.stderr
    d = json.loads(scan.read_text())
    assert set(d["tables"]) == {"patients", "appointments"}
    fk = {c["name"]: c.get("ref") for c in d["tables"]["appointments"]}
    assert fk["patient_id"] == "patients"
    assert {rt["path"] for rt in d["routes"]} >= {"/dashboard", "/appointments"}
    outdir = tmp_path / "output"
    run(SCRIPTS / "gen_sections.py", scan, "--out", outdir)
    auto = (outdir / "auto_sections.md").read_text()
    assert "patients ||--o{ appointments" in auto
    assert "| Laravel | backend |" in auto
    assert "varchar(150)" in auto


def test_postgres_schema_qualified_tables_and_multword_types(tmp_path):
    """Regression for two SQL bugs: 'public.users' was dropped entirely (so a Postgres
    dump produced zero tables), and 'character varying(255)' was truncated to 'character'."""
    proj = tmp_path / "pg"
    (proj / "db").mkdir(parents=True)
    (proj / "db" / "schema.sql").write_text(
        "CREATE TABLE public.users (\n"
        "  id SERIAL PRIMARY KEY,\n"
        "  full_name character varying(255) NOT NULL,\n"
        "  balance double precision,\n"
        "  created_at timestamp without time zone\n"
        ");\n"
        "CREATE TABLE public.orders (\n"
        "  id bigint PRIMARY KEY,\n"
        "  user_id bigint REFERENCES public.users(id)\n"
        ");\n")
    out = tmp_path / "scan.json"
    run(SCRIPTS / "scan_repo.py", proj, "--out", out)
    d = json.loads(out.read_text())
    assert set(d["tables"]) == {"users", "orders"}, d["tables"]
    by_name = {c["name"]: c for c in d["tables"]["users"]}
    assert by_name["full_name"]["type"] == "character varying(255)"
    assert by_name["balance"]["type"] == "double precision"
    assert by_name["created_at"]["type"] == "timestamp without time zone"
    order_cols = {c["name"]: c for c in d["tables"]["orders"]}
    assert order_cols["user_id"].get("ref") == "users"
    assert "FK" in order_cols["user_id"]["flags"]


def test_prisma_relation_fields_are_not_columns_and_give_fk(tmp_path):
    """Regression: 'posts Post[]' and 'author User @relation(...)' were emitted as fake
    columns, and @relation produced no foreign key at all (so the ER diagram had no links)."""
    proj = tmp_path / "p"
    proj.mkdir()
    (proj / "schema.prisma").write_text(
        "model User {\n"
        "  id    Int    @id\n"
        "  email String @unique\n"
        "  posts Post[]\n"
        "}\n"
        "model Post {\n"
        "  id       Int  @id\n"
        "  authorId Int\n"
        "  author   User @relation(fields: [authorId], references: [id])\n"
        "}\n")
    out = tmp_path / "scan.json"
    run(SCRIPTS / "scan_repo.py", proj, "--out", out)
    d = json.loads(out.read_text())
    assert set(d["tables"]) == {"User", "Post"}, d["tables"]
    user_cols = {c["name"]: c for c in d["tables"]["User"]}
    assert "posts" not in user_cols, "list relation must not become a column"
    assert "UNIQUE" in user_cols["email"]["flags"]
    post_cols = {c["name"]: c for c in d["tables"]["Post"]}
    assert "author" not in post_cols, "relation field must not become a column"
    assert post_cols["authorId"].get("ref") == "User"
    assert "FK" in post_cols["authorId"]["flags"]


def test_one_package_is_not_reported_as_two_technologies(tmp_path):
    """mysql2 must not also match the 'mysql' key: the stack table is pasted straight into Chapter 3."""
    scan, outdir = tmp_path / "scan.json", tmp_path / "output"
    run(SCRIPTS / "scan_repo.py", SAMPLE, "--out", scan)
    run(SCRIPTS / "gen_sections.py", scan, "--out", outdir)
    auto = (outdir / "auto_sections.md").read_text()
    assert "MySQL (mysql2 driver)" in auto
    assert "MySQL (driver)" not in auto


def test_python_manifest_packages_are_recognised(tmp_path):
    scan = tmp_path / "scan.json"
    reqs = "fastapi==0.110\nSQLAlchemy==2.0\nredis==5.0\npasslib[bcrypt]==1.7\ncelery==5.3\nstreamlit==1.32\n"
    scan.write_text(json.dumps({"manifests": {"requirements.txt": reqs}, "languages": {"Python": 4},
                                "routes": [], "tables": {}, "env_vars": [], "test_files": [], "todos": []}))
    outdir = tmp_path / "output"
    run(SCRIPTS / "gen_sections.py", scan, "--out", outdir)
    auto = (outdir / "auto_sections.md").read_text()
    for label in ("FastAPI", "SQLAlchemy ORM", "Redis", "Passlib password hashing", "Celery", "Streamlit"):
        assert label in auto, f"{label} is missing from the tech stack table"


def test_gaps_report_flags_a_missing_chapter5(tmp_path):
    """A Chapter 1-5 paper with no Chapter 5 must not pass the check."""
    for name in ("chapter1", "chapter2", "chapter3", "chapter4", "appendices", "references"):
        (tmp_path / f"{name}.md").write_text("# Done\n\nAll real here.\n")
    run(SCRIPTS / "gaps_report.py", tmp_path)
    gaps = (tmp_path / "GAPS.md").read_text()
    assert "Chapter 5" in missing_section(gaps)

    (tmp_path / "chapter5.md").write_text("# CHAPTER 5\n# SUMMARY, FINDINGS, CONCLUSION AND RECOMMENDATION\n")
    run(SCRIPTS / "gaps_report.py", tmp_path)
    gaps = (tmp_path / "GAPS.md").read_text()
    assert "Chapter 5" not in missing_section(gaps)


def test_preset_chapters_limit_what_is_required(tmp_path):
    """A school that only submits Chapter 3 must not be nagged about the other four."""
    preset = tmp_path / "school.json"
    preset.write_text(json.dumps({"font": "Arial", "chapters": [3]}))
    out = tmp_path / "output"
    out.mkdir()
    (out / "chapter3.md").write_text("# CHAPTER 3\n\nReal methodology content here.\n")
    (out / "notes.md").write_text("# Notes\n")

    run(SCRIPTS / "gaps_report.py", out, "--preset", preset)
    gaps = (out / "GAPS.md").read_text()
    assert "Checking these parts only: Chapter 3." in gaps
    assert missing_section(gaps) == ""
    for part in ("Appendices", "References", "Survey"):
        assert f"## {part}" not in gaps, f"{part} was required even though this school only wants Chapter 3"


def test_preset_chapters_as_a_number_means_one_through_that_number(tmp_path):
    preset = tmp_path / "school.json"
    preset.write_text(json.dumps({"chapters": 3}))
    out = tmp_path / "output"
    out.mkdir()
    (out / "chapter3.md").write_text("# CHAPTER 3\n\nReal methodology content here.\n")

    run(SCRIPTS / "gaps_report.py", out, "--preset", preset)
    missing = missing_section((out / "GAPS.md").read_text())
    assert "Chapter 1" in missing and "Chapter 2" in missing
    assert "Chapter 3" not in missing and "Chapter 4" not in missing


def test_bad_chapters_setting_gives_a_plain_message(tmp_path):
    preset = tmp_path / "school.json"
    preset.write_text(json.dumps({"chapters": ["one"]}))
    out = tmp_path / "output"
    out.mkdir()
    (out / "chapter1.md").write_text("# CHAPTER 1\n")
    r = run(SCRIPTS / "gaps_report.py", out, "--preset", preset, check=False)
    assert r.returncode != 0 and "not readable" in r.stderr and "Traceback" not in r.stderr


def test_a_template_the_student_added_is_copied_and_ordered(tmp_path):
    """build_docx orders by the chapter number in the file name, so a school-specific
    template keeps its own name and still lands in the right place."""
    out = tmp_path / "output"
    out.mkdir()
    for name in TEMPLATES:
        (out / name).write_text((ROOT / "templates" / name).read_text())
    (out / "conceptual_framework.md").write_text("# CONCEPTUAL FRAMEWORK\n\nInput-Process-Output model.\n")
    docx = tmp_path / "custom.docx"
    run(SCRIPTS / "build_docx.py", out, "--title", "Custom", "--out", docx, "--no-render")
    from docx import Document
    texts = [p.text for p in Document(docx).paragraphs]
    assert texts.index("CHAPTER 5") < texts.index("CONCEPTUAL FRAMEWORK") < texts.index("APPENDICES")


def test_school_format_variant_is_checked_and_ordered(tmp_path):
    """A school with front matter, four chapters and back matter is checked as its own
    template folder reads, never against the default 1-5 list."""
    out = tmp_path / "output"
    out.mkdir()
    variant = ROOT / "templates" / "four-chapter"
    for name in ("00-front-matter.md", "chapter1.md", "chapter2.md", "chapter3.md",
                 "chapter4.md", "90-back-matter.md"):
        (out / name).write_text((variant / name).read_text())
    preset = ROOT / "presets" / "four-chapter.json"

    run(SCRIPTS / "gaps_report.py", out, "--format", "four-chapter", "--preset", preset)
    gaps = (out / "GAPS.md").read_text()
    assert "Checking these parts only: FRONT MATTER, BACK MATTER, CHAPTER 1, CHAPTER II, CHAPTER III, CHAPTER IV." in gaps
    assert missing_section(gaps) == "", "this school has no Chapter 5 and no separate Appendices part"

    docx = tmp_path / "variant.docx"
    run(SCRIPTS / "build_docx.py", out, "--title", "Variant", "--preset", preset, "--out", docx, "--no-render")
    from docx import Document
    doc = Document(docx)
    texts = [p.text for p in doc.paragraphs]
    assert texts.index("FRONT MATTER") < texts.index("CHAPTER 1") < texts.index("CHAPTER IV") < texts.index("BACK MATTER")
    assert doc.styles["Normal"].font.name == "Arial" and doc.styles["Normal"].font.size.pt == 12

    (out / "00-front-matter.md").unlink()
    run(SCRIPTS / "gaps_report.py", out, "--format", "four-chapter")
    assert "FRONT MATTER" in missing_section((out / "GAPS.md").read_text())
