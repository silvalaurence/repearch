#!/usr/bin/env python3
"""Turn scan.json into ready-to-paste, fact-based sections and diagrams.

Usage: python gen_sections.py scan.json --out output/
Writes:
  output/auto_sections.md      tech stack, modules/routes, data dictionary, env table, tests, limitations
  output/diagrams/er.mmd       ER entities and relationships only, readable as a printed figure
  output/diagrams/er_detail.mmd   the same model with every column, as reference material
  output/diagrams/er_partN.mmd    large schemas split along foreign-key lines, one figure per sheet
  output/diagrams/architecture.mmd  tiers the client demonstrably reaches

Everything comes from the scan. Nothing is guessed: where meaning is unknown it writes a
[STUDENT: ...] placeholder. Foreign keys without an explicit REFERENCES are only suggested, never drawn.
A tier is only drawn when the code shows the client using it.
"""
import argparse
import json
import os
import re
from collections import OrderedDict

FRAMEWORKS = OrderedDict([
    # (key in dependency text) -> (label, layer). More specific names come before the
    # shorter names they contain, so the first hit is always the precise product.
    ("expo", ("Expo", "frontend")), ("react-native", ("React Native", "frontend")),
    ("react", ("React", "frontend")), ("vue", ("Vue", "frontend")), ("svelte", ("Svelte", "frontend")),
    ("angular", ("Angular", "frontend")), ("next", ("Next.js", "frontend")), ("flutter", ("Flutter", "frontend")),
    ("tailwindcss", ("Tailwind CSS", "frontend")), ("bootstrap", ("Bootstrap", "frontend")),
    ("streamlit", ("Streamlit", "frontend")),
    ("express", ("Express.js", "backend")), ("laravel/framework", ("Laravel", "backend")),
    ("django", ("Django", "backend")), ("flask", ("Flask", "backend")), ("fastapi", ("FastAPI", "backend")),
    ("spring-boot", ("Spring Boot", "backend")), ("nestjs", ("NestJS", "backend")), ("codeigniter", ("CodeIgniter", "backend")),
    ("celery", ("Celery", "backend")),
    ("mysql2", ("MySQL (mysql2 driver)", "database")), ("mysql", ("MySQL (driver)", "database")), ("pg", ("PostgreSQL (pg driver)", "database")),
    ("psycopg", ("PostgreSQL (psycopg driver)", "database")), ("sqlite", ("SQLite", "database")), ("mongodb", ("MongoDB", "database")),
    ("mongoose", ("MongoDB (Mongoose)", "database")), ("firebase", ("Firebase", "database")),
    ("supabase-js", ("Supabase", "database")), ("supabase", ("Supabase", "database")),
    ("prisma", ("Prisma ORM", "database")), ("sequelize", ("Sequelize ORM", "database")),
    ("sqlalchemy", ("SQLAlchemy ORM", "database")), ("redis", ("Redis", "database")),
    ("jsonwebtoken", ("JSON Web Tokens", "security")), ("bcrypt", ("bcrypt password hashing", "security")),
    ("passlib", ("Passlib password hashing", "security")), ("python-jose", ("JOSE token signing", "security")),
    ("passport", ("Passport.js", "security")), ("jest", ("Jest", "testing")), ("pytest", ("pytest", "testing")),
    ("phpunit", ("PHPUnit", "testing")), ("mocha", ("Mocha", "testing")), ("vitest", ("Vitest", "testing")),
])
LOCAL_URL = re.compile(r"^https?://(localhost|127\.0\.0\.1|0\.0\.0\.0|10\.0\.2\.2|host\.docker\.internal|"
                       r"[^\s/`'\"]+:\d{2,5})", re.I)


def clean_ident(s):
    return re.sub(r"[^A-Za-z0-9_]", "_", s)


def clean_type(t):
    t = re.sub(r"[^A-Za-z0-9_\[\]()]", "", t)
    return t or "TEXT"


def deps_from_manifests(manifests):
    """Return {name: version} from package.json / composer.json / requirements.txt where parseable."""
    deps = {}
    for path, text in manifests.items():
        base = os.path.basename(path)
        if base in ("package.json", "composer.json"):
            try:
                data = json.loads(text)
            except ValueError:
                # file was cut at 4000 chars; fall back to regex
                for k, v in re.findall(r'"([@\w./-]+)"\s*:\s*"([\^~>=<\d][^"]*)"', text):
                    deps[k] = v
                continue
            for key in ("dependencies", "devDependencies", "require", "require-dev"):
                for k, v in (data.get(key) or {}).items():
                    deps[k] = v
        elif base == "requirements.txt":
            for line in text.splitlines():
                m = re.match(r"\s*([A-Za-z0-9_.-]+)\s*(?:[=<>~!]=?\s*([\w.*]+))?", line)
                if m and not line.strip().startswith("#"):
                    deps[m.group(1)] = m.group(2) or ""
    return deps


def dep_name(name):
    """'@supabase/supabase-js' -> 'supabase-js'. A scope is packaging, not product name,
    and leaving it in makes @react-native-anything look like React."""
    low = name.lower()
    return low.split("/", 1)[1] if low.startswith("@") else low


def match_framework(name):
    """Find the FRAMEWORKS entry for a dependency, as (label, layer, version_is_mine).

    One label per package, and the version is only trustworthy when the package *is* that
    product. Reporting React at the version of @react-native-async-storage puts a number
    in the paper that no one can defend, so a substring hit never carries a version.
    """
    low = dep_name(name)
    for key, (label, layer) in FRAMEWORKS.items():
        if low == key:
            return label, layer, True
    for key, (label, layer) in FRAMEWORKS.items():
        if low.startswith(key + "-") or low.startswith(key + "/") or (len(key) > 4 and key in low):
            return label, layer, False
    return None


def detect_stack(scan):
    """{label: (layer, declared version)} - version blank unless the package itself matched."""
    deps = deps_from_manifests(scan.get("manifests", {}))
    found = OrderedDict()
    for name, ver in deps.items():
        match = match_framework(name)
        if not match:
            continue
        label, layer, exact = match
        slot = found.setdefault(label, [layer, ""])
        if exact and not slot[1]:
            slot[1] = ver
    return deps, OrderedDict((label, (layer, ver)) for label, (layer, ver) in found.items())


def md_escape(s):
    return str(s).replace("|", "\\|")


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(md_escape(c) for c in r) + " |")
    return "\n".join(out)


def suggested_fks(tables):
    """Columns named *_id that match a table name but have no explicit REFERENCES (suggestion only)."""
    names = {t.lower(): t for t in tables}
    out = []
    for t, cols in tables.items():
        for c in cols:
            if c.get("ref") or not c["name"].lower().endswith("_id"):
                continue
            stem = c["name"].lower()[:-3]
            for cand in (stem, stem + "s", stem + "es"):
                if cand in names and names[cand] != t:
                    out.append((t, c["name"], names[cand]))
                    break
    return out


def er_relations(tables):
    """(parent, child, column) for every declared foreign key whose target table exists."""
    names = {t.lower(): t for t in tables}
    rels = []
    for t, cols in tables.items():
        for c in cols:
            ref = c.get("ref")
            if ref and ref.lower() in names:
                rels.append((names[ref.lower()], t, c["name"]))
    return rels


def er_attributes(tables, entities):
    lines = []
    for t in entities:
        lines.append(f"  {clean_ident(t)} {{")
        for c in tables[t]:
            keys = ["UK" if k == "UNIQUE" else k for k in c.get("flags", []) if k in ("PK", "FK", "UNIQUE")]
            lines.append(f"    {clean_type(c['type'])} {clean_ident(c['name'])}" + (f" {','.join(keys)}" if keys else ""))
        lines.append("  }")
    return lines


def er_figure(tables, rels):
    """The figure artifact: entities and relationships, no attribute lists.

    A real schema drawn with every column is twenty tables by fifteen rows, which prints
    as an unreadable strip at page width. Columns belong in the data dictionary table.
    A table that takes part in no relationship gets its key column so it still appears.
    """
    lines = ["erDiagram"]
    drawn = set()
    for parent, child, col in rels:
        lines.append(f'  {clean_ident(parent)} ||--o{{ {clean_ident(child)} : "{clean_ident(col)}"')
        drawn.add(parent)
        drawn.add(child)
    for t, cols in tables.items():
        if t in drawn:
            continue
        lines.append(f"  {clean_ident(t)} {{")
        key_col = next((c for c in cols if "PK" in c.get("flags", [])), cols[0] if cols else None)
        if key_col:
            lines.append(f"    {clean_type(key_col['type'])} {clean_ident(key_col['name'])} PK")
        lines.append("  }")
    return "\n".join(lines) + "\n"


def er_detail(tables, rels):
    """The full ER block, attributes and all: reference material, not a printed figure."""
    lines = ["erDiagram"]
    for parent, child, col in rels:
        lines.append(f'  {clean_ident(parent)} ||--o{{ {clean_ident(child)} : "{clean_ident(col)}"')
    lines.extend(er_attributes(tables, list(tables)))
    return "\n".join(lines) + "\n"


def components(tables, rels):
    """Tables grouped into foreign-key connected clusters, biggest first."""
    adj = {t: set() for t in tables}
    for parent, child, _col in rels:
        adj.setdefault(parent, set()).add(child)
        adj.setdefault(child, set()).add(parent)
    seen, groups = set(), []
    for t in tables:
        if t in seen:
            continue
        stack, group = [t], []
        seen.add(t)
        while stack:
            node = stack.pop()
            group.append(node)
            for nxt in adj[node]:
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        groups.append(sorted(group))
    return sorted(groups, key=len, reverse=True)


def er_sheets(tables, rels, per_sheet=12):
    """Cluster tables into figures of at most per_sheet entities, so each one fits a page."""
    sheets, current = [], []
    for group in components(tables, rels):
        for start in range(0, len(group), per_sheet):
            chunk = group[start:start + per_sheet]
            if current and len(current) + len(chunk) > per_sheet:
                sheets.append(current)
                current = []
            current.extend(chunk)
        if len(current) >= per_sheet:
            sheets.append(current)
            current = []
    if current:
        sheets.append(current)
    return sheets


def architecture(scan, found):
    """A flowchart of the tiers the code actually shows, plus notes on what was left out.

    A backend box is only honest if the client talks to something. server.ts sitting in the
    repo proves nothing on its own - it is often a first-sprint prototype nobody deleted.
    """
    by_layer = {}
    for label, (layer, _v) in found.items():
        by_layer.setdefault(layer, []).append(label)
    langs = list(scan.get("languages", {}))
    fe = ", ".join(by_layer.get("frontend", [])) or ("HTML/CSS/JS" if any("HTML" in l for l in langs) else "Client interface")
    db = ", ".join(by_layer.get("database", [])) or ("Database" if scan.get("tables") else "")
    backend = ", ".join(by_layer.get("backend", []))
    calls = scan.get("api_calls", [])
    routes = scan.get("routes", [])
    reaches_server = [c for c in calls if c["target"].startswith("/") or LOCAL_URL.match(c["target"])]
    notes = []

    lines = ["flowchart LR", "  U([Users])", f'  F["Frontend<br/>{fe}"]']
    if backend and (reaches_server or routes):
        lines.append(f'  B["Backend<br/>{backend}"]')
        lines.append("  U --> F --> B")
        if not reaches_server:
            notes.append("The server tier is drawn because " +
                         (f"{len(routes)} route(s) are registered in this repo" if routes else "a backend package is declared") +
                         ", not because a client URL points at it. Server-rendered apps look like this; "
                         "if your client never reaches this code, say so and take the box out.")
        if db:
            lines.append(f'  D[("Database<br/>{db}")]')
            lines.append("  B --> D")
    else:
        if backend:
            notes.append(f"A backend package is declared ({backend}) but no client code calls a server URL and "
                         "no routes are registered here. Confirm whether it is actually used before drawing it.")
        elif scan.get("server_files"):
            notes.append("Server files exist (" + ", ".join(f"`{f}`" for f in scan["server_files"][:3]) +
                         ") but no client call reaches a server and no backend package is declared. "
                         "They read as a legacy prototype, not wired - so no server tier is drawn.")
        if db:
            lines.append(f'  D[("Database<br/>{db}")]')
            lines.append("  U --> F --> D")
        else:
            lines.append("  U --> F")
    if calls and not reaches_server:
        hosts = sorted({c["target"] for c in calls})[:4]
        notes.append("The client only calls these addresses: " + ", ".join(f"`{h}`" for h in hosts) +
                     ". Draw the tier they actually point at.")
    return "\n".join(lines) + "\n", notes


def module_name(path):
    stem = os.path.splitext(os.path.basename(path))[0]
    return stem if stem.lower() not in ("index", "routes", "web", "api", "urls") else os.path.basename(os.path.dirname(path)) or stem


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scan")
    ap.add_argument("--out", default="output")
    args = ap.parse_args()

    scan = json.load(open(args.scan, encoding="utf-8"))
    os.makedirs(os.path.join(args.out, "diagrams"), exist_ok=True)
    deps, found = detect_stack(scan)
    tables = scan.get("tables", {})
    S = []

    S.append("# AUTO-GENERATED FROM THE CODE\n\nThese sections come straight from the scan. Copy what you need into your chapters. "
             "Facts here were found in the repo; anything marked [STUDENT: ...] needs your input.\n")

    # Tech stack
    S.append("## Technology Stack (for Section 3.3)\n")
    rows = [(lang, "-", f"{n} source file(s)", "[STUDENT: purpose]") for lang, n in scan.get("languages", {}).items()]
    S.append(table(["Technology", "Version", "Evidence in repo", "Purpose"], rows) if rows else "No source languages detected.")
    S.append("")
    if found:
        S.append(table(["Framework / library", "Layer", "Package version (as declared)"],
                       [(label, layer, ver or "-") for label, (layer, ver) in found.items()]))
    else:
        S.append("No known frameworks detected from manifests. [STUDENT: list them from your package files.]")
    S.append("")

    # Architecture
    arch, arch_notes = architecture(scan, found)
    open(os.path.join(args.out, "diagrams", "architecture.mmd"), "w", encoding="utf-8", newline="\n").write(arch)
    S.append("## System Architecture (for Section 3.2)\n\n```mermaid\n" + arch + "```\n")
    if arch_notes:
        S.append("What the scan could not confirm about the tiers:\n")
        S.extend(f"- {n}" for n in arch_notes)
        S.append("")
    S.append("The layer names above come from packages the project declares, and a tier is only drawn when the "
             "client actually reaches it. [STUDENT: correct them if your system differs.]\n")

    # Modules / routes
    S.append("## Modules and Endpoints (for Section 3.4)\n")
    routes = scan.get("routes", [])
    if routes:
        grouped = OrderedDict()
        for r in routes:
            grouped.setdefault(module_name(r["file"]), []).append(r)
        for mod, rs in grouped.items():
            S.append(f"### {mod}\n")
            S.append(table(["Method", "Path", "File"], [(r["method"] or "-", r["path"], r["file"]) for r in rs]))
            S.append("\n[STUDENT: describe what this module does for the user.]\n")
    else:
        S.append("No routes were detected. [STUDENT: list your modules by looking at your menu or pages.]\n")
    if scan.get("folders"):
        S.append("Top-level folders: " + ", ".join(f"`{f}`" for f in scan["folders"]) + "\n")

    # Database
    S.append("## Database Design (for Section 3.7)\n")
    if tables:
        rels = er_relations(tables)
        figure = er_figure(tables, rels)
        diagram_dir = os.path.join(args.out, "diagrams")
        open(os.path.join(diagram_dir, "er.mmd"), "w", encoding="utf-8", newline="\n").write(figure)
        open(os.path.join(diagram_dir, "er_detail.mmd"), "w", encoding="utf-8", newline="\n").write(er_detail(tables, rels))
        S.append("### Entity-Relationship Diagram\n\n```mermaid\n" + figure + "```\n")
        S.append(f"{len(tables)} table(s) and {len(rels)} declared foreign-key relationship(s) were found. "
                 "This figure shows entities and relationships only; every column is listed in the Data Dictionary "
                 "below, which is the artifact your adviser grades. `diagrams/er_detail.mmd` keeps the full version "
                 "in case you are asked for one.\n")
        sheets = er_sheets(tables, rels)
        if len(sheets) > 1:
            for n, group in enumerate(sheets, 1):
                part = er_figure({t: tables[t] for t in group},
                                 [r for r in rels if r[0] in group and r[1] in group])
                open(os.path.join(diagram_dir, f"er_part{n}.mmd"), "w", encoding="utf-8", newline="\n").write(part)
            S.append(f"{len(tables)} tables will not fit one readable figure. `diagrams/er_part1.mmd` through "
                     f"`er_part{len(sheets)}.mmd` follow the foreign-key lines and split them into {len(sheets)} "
                     "page-shaped groups. Caption them as separate figures instead of shrinking one large one.\n")
        sug = suggested_fks(tables)
        if sug:
            S.append("Possible relationships not declared in the schema (check, then add to your diagram only if true):\n")
            S.extend(f"- `{t}.{c}` may refer to `{p}`" for t, c, p in sug)
            S.append("")
        S.append("### Data Dictionary\n")
        rows = []
        for t, cols in tables.items():
            for c in cols:
                key = "/".join(k for k in c.get("flags", []) if k in ("PK", "FK", "UNIQUE")) or "-"
                if c.get("ref"):
                    key += f" -> {c['ref']}"
                rows.append((t, c["name"], c["type"], key, "[STUDENT: meaning]"))
        S.append(table(["Table", "Column", "Type", "Key", "Description"], rows))
        S.append("")
    else:
        S.append("No SQL schema, Prisma models or Laravel migrations were found. "
                 "[STUDENT: export your schema (mysqldump --no-data or pg_dump --schema-only) into a .sql file in the project and scan again.]\n")

    # Migration history
    migrations = scan.get("migrations", [])
    if migrations:
        S.append("### Schema Change History (evidence for an iterative model, Section 3.11)\n")
        S.append("These migration files are numbered or dated in order, so they are real evidence the database grew "
                 "a sprint at a time:\n")
        S.extend(f"- `{m}`" for m in migrations)
        S.append("\n[STUDENT: match each one to the sprint or release it belongs to.]\n")

    # Environment
    S.append("## Environment Settings (for Appendix B)\n")
    declared = scan.get("env_declared", [])
    referenced = scan.get("env_vars", [])
    if declared:
        S.append(table(["Variable", "Purpose"], [(e, "[STUDENT: purpose]") for e in declared]))
        S.append("\nNames only - never the values. These are the settings the project declares in its example env file.\n")
    if referenced:
        S.append("Read somewhere in the code but not declared in the example env file. A dependency or a build tool "
                 "may be the one reading these, so check before listing them as your system's settings: "
                 + ", ".join(f"`{e}`" for e in referenced) + "\n")
    if not declared and not referenced:
        S.append("No application environment variables were found.\n")

    # Tests
    S.append("## Tests Found (for Section 4.3.2)\n")
    tf = scan.get("test_files", [])
    other = scan.get("other_test_files", [])
    if tf:
        S.append(f"{len(tf)} file(s) inside the project's own test folders:\n")
        S.extend(f"- `{t}`" for t in tf)
        S.append("\nThese files exist. Run them yourself and paste the real output; do not report results you have not seen.\n")
    else:
        S.append("No test files were found in a tests/, test/, __tests__/ or spec/ folder.\n")
    if other:
        S.append(f"A further {len(other)} file(s) are named like tests but sit outside those folders - co-located "
                 "specs, or files that came bundled with a tool. Count them only if you actually run them:\n")
        S.extend(f"- `{t}`" for t in other)
        S.append("")

    # Limitations
    S.append("## Limitations Visible in the Code (for Section 4.5)\n")
    todos = scan.get("todos", [])
    if todos:
        S.extend(f"- `{t['file']}:{t['line']}` {t['text']}" for t in todos)
    else:
        S.append("No TODO/FIXME/HACK comments found.")
    S.append("")

    path = os.path.join(args.out, "auto_sections.md")
    open(path, "w", encoding="utf-8", newline="\n").write("\n".join(S))
    print(f"Wrote {path}")
    print(f"Tables: {len(tables)}  Frameworks: {len(found)}  Routes: {len(routes)}  "
          f"Env vars: {len(declared)} declared  Tests: {len(tf)} own + {len(other)} elsewhere")
    for n in arch_notes:
        print("Note: " + n)


if __name__ == "__main__":
    main()
