#!/usr/bin/env python3
"""Scan a project folder and write a JSON summary the agent drafts capstone chapters from.

Usage: python scan_repo.py <project_path> --out scan.json
Only reads files. Never executes project code. Never records secret values.
"""
import argparse
import json
import os
import re
import sys

# Build output, tool folders and dependency trees are not the student's code, so they
# never count as project files. Any folder starting with "." is also skipped; that alone
# removes .expo, .vercel, .opencode, .agents and friends.
SKIP_DIRS = {".git", "node_modules", "vendor", "venv", ".venv", "__pycache__", "dist", "build",
             ".next", ".idea", ".vscode", "storage", "coverage", ".gradle", "bin", "obj",
             "out", "target", "web-build", "backups", "backup", ".cache", ".turbo", ".output",
             ".parcel-cache", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".svelte-kit",
             "bower_components", "Pods", ".expo", ".vercel", ".netlify", ".serverless"}
# A top-level folder of these names is usually a downloaded skill or agent pack, not the
# project. It is skipped only when it actually looks like one (see is_vendored).
VENDORED_NAMES = {"agent", "agents", "skill", "skills", ".agents", "plugins"}
SKILL_MARKER = "SKILL.md"
LANG_BY_EXT = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript (React)", ".ts": "TypeScript",
    ".tsx": "TypeScript (React)", ".php": "PHP", ".java": "Java", ".kt": "Kotlin", ".cs": "C#",
    ".dart": "Dart (Flutter)", ".go": "Go", ".rb": "Ruby", ".vue": "Vue", ".svelte": "Svelte",
    ".html": "HTML", ".css": "CSS", ".sql": "SQL", ".swift": "Swift", ".c": "C", ".cpp": "C++",
}
MANIFESTS = ["package.json", "composer.json", "requirements.txt", "pyproject.toml", "pom.xml",
             "build.gradle", "pubspec.yaml", "Gemfile", "go.mod", "Dockerfile", "docker-compose.yml",
             "docker-compose.yaml"]
ROUTE_PATTERNS = [
    re.compile(r"""(?:app|router|Router|api)\.(get|post|put|patch|delete)\(\s*['"]([^'"]+)['"]"""),
    re.compile(r"""@(?:\w+\.)?(get|post|put|patch|delete|route)\(\s*['"]([^'"]+)['"]""", re.I),
    re.compile(r"""Route::(get|post|put|patch|delete|resource)\(\s*['"]([^'"]+)['"]"""),
    re.compile(r"""path\(\s*['"]([^'"]*)['"]"""),
]
ENV_PATTERNS = [
    re.compile(r"process\.env\.([A-Z0-9_]+)"),
    re.compile(r"os\.environ(?:\.get)?\(?\[?\s*['\"]([A-Z0-9_]+)['\"]"),
    re.compile(r"os\.getenv\(\s*['\"]([A-Z0-9_]+)['\"]"),
    re.compile(r"\benv\(\s*['\"]([A-Z0-9_]+)['\"]"),
    re.compile(r"getenv\(\s*['\"]([A-Z0-9_]+)['\"]"),
]
CREATE_TABLE_HEAD = re.compile(
    r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:TEMP(?:ORARY)?\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
    r"((?:[`\"\[]?\w+[`\"\]]?\s*\.\s*)?[`\"\[]?\w+[`\"\]]?)\s*\(",
    re.I)
# A column definition ends its type at the first constraint keyword. Types like
# "character varying(255)", "double precision" and "timestamp without time zone"
# contain spaces, so the type cannot be taken as a single whitespace token.
TYPE_STOP = re.compile(
    r"\b(?:NOT\s+NULL|NULL|PRIMARY\s+KEY|UNIQUE|DEFAULT|REFERENCES|CHECK|COLLATE|"
    r"GENERATED|AUTO_INCREMENT|AUTOINCREMENT|IDENTITY|COMMENT|CONSTRAINT|"
    r"ON\s+UPDATE|ON\s+DELETE)\b", re.I)
LARAVEL_TABLE = re.compile(
    r"Schema::create\(\s*['\"](\w+)['\"]\s*,\s*function\s*\([^)]*\)\s*\{(.*?)^\s*\}\);",
    re.S | re.M)
LARAVEL_CALL = re.compile(r"\$table->(\w+)\(\s*(?:['\"]([^'\"]*)['\"])?([^)]*)\)")
PRISMA_MODEL = re.compile(r"model\s+(\w+)\s*\{([^}]*)\}", re.S)
PRISMA_RELATION = re.compile(r"@relation\(([^)]*)\)")
PRISMA_FIELDS = re.compile(r"fields\s*:\s*\[([^\]]*)\]")
SKIP_LINE_START = ("PRIMARY", "FOREIGN", "KEY", "UNIQUE", "CONSTRAINT", "INDEX", "CHECK")
# Files sitting under a real test folder are the project's own tests. A file merely named
# like a test somewhere else (.spec.ts inside a bundled library, for instance) is counted
# separately so the paper never claims twenty tests the student did not write.
TEST_DIR = re.compile(r"(^|/)(tests?|__tests__|spec|specs|e2e|features)(/|$)", re.I)
TEST_NAME = re.compile(r"(\.test\.|\.spec\.|_test\.|test_[^/]*\.py$|Test\.php$|_test\.go$)", re.I)
# Variables the operating system or the terminal sets for itself. Finding them in a
# script does not make them settings of the student's application.
ENV_NOISE = re.compile(
    r"^(COLORTERM|TERM|TERM_PROGRAM|SHELL|PWD|OLDPWD|HOME|USER|USERNAME|USERPROFILE|PATH|PATHEXT|"
    r"LANG|LANGUAGE|LC_|EDITOR|PAGER|DISPLAY|TMPDIR|TMP|TEMP|SHLVL|HOSTNAME|OS$|MACHTYPE|PS1|"
    r"COMSPEC|SYSTEMROOT|WINDIR|PROGRAMDATA|PROGRAMFILES|APPDATA|LOCALAPPDATA|ALLUSERSPROFILE|"
    r"PYTHON|PIP_|NODE|NPM_|npm_|YARN_|BUN_|CI$|GIT_|SSH_|BASH_|ZSH_|VSCODE|QODER|GOPATH|GOROOT)")
SERVER_DIR = re.compile(r"(^|/)(server|servers|backend|api-server)(/|$)", re.I)
MIGRATION_HINT = re.compile(r"(^|/)(migrations?|supabase/migrations|database/migrations|flyway|liquibase)(/|$)", re.I)
CLIENT_CALL = [
    re.compile(r"""(?:fetch|axios\.(?:get|post|put|patch|delete|request)|XMLHttpRequest)\s*[(:]?\s*\.?open?\s*\(?\s*[`'"]([^`'"\s]+)[`'"]""", re.I),
    re.compile(r"""baseURL\s*[:=]\s*[`'"]([^`'"]+)[`'"]""", re.I),
    re.compile(r"""(?:createClient|supabase)\(\s*[`'"]([^`'"]+)[`'"]""", re.I),
    re.compile(r"""[`'"](/(?:api|rpc|v\d)/[^`'"\s]+)[`'"]""", re.I),
]
LOCAL_BACKEND = re.compile(r"^https?://(localhost|127\.0\.0\.1|0\.0\.0\.0|10\.0\.2\.2|host\.docker\.internal|[^\s/]+:(\d{4}|\[\d+\]))", re.I)


def read(path, limit=400_000):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read(limit)
    except OSError:
        return ""


def is_vendored(dirpath, name_suggests_pack=False):
    """True when this folder is a copied-in skill/agent pack rather than the student's code.

    A folder holding a SKILL.md is a skill package by definition. A bare top-level folder
    named agent/ or skills/ only counts when its immediate children look like skill packs,
    so a real src/agent module is never thrown away.
    """
    if os.path.exists(os.path.join(dirpath, SKILL_MARKER)):
        return True
    if not name_suggests_pack:
        return False
    try:
        kids = os.listdir(dirpath)
    except OSError:
        return False
    return any(os.path.exists(os.path.join(dirpath, k, SKILL_MARKER)) for k in kids)


def walk(root, stats, keep_vendored=False, extra_ignore=()):
    """Yield project files, pruning build output, tool folders, dependencies and vendored packs."""
    root_abs = os.path.abspath(root)
    extra = {e.lower() for e in extra_ignore}
    for dirpath, dirnames, filenames in os.walk(root):
        at_root = os.path.abspath(dirpath) == root_abs
        kept = []
        for d in dirnames:
            child = os.path.join(dirpath, d)
            low = d.lower()
            if low.startswith(".") or low in SKIP_DIRS or low in extra:
                stats["ignored_dirs"] += 1
                continue
            if not keep_vendored and is_vendored(child, at_root and low in VENDORED_NAMES):
                stats["ignored_dirs"] += 1
                stats["vendored"] += 1
                continue
            kept.append(d)
        dirnames[:] = kept
        for name in filenames:
            yield os.path.join(dirpath, name)


IDENT = r"(?:[`\"\[]?\w+[`\"\]]?\s*\.\s*)?[`\"\[]?\w+[`\"\]]?"
REF_INLINE = re.compile(r"REFERENCES\s+(" + IDENT + ")", re.I)
FK_TABLE_LEVEL = re.compile(
    r"FOREIGN\s+KEY\s*\(\s*[`\"\[]?(\w+)[`\"\]]?\s*\)\s*REFERENCES\s+(" + IDENT + ")", re.I)
PK_TABLE_LEVEL = re.compile(r"PRIMARY\s+KEY\s*\(([^)]*)\)", re.I)


def bare(identifier):
    """'public."Users"' -> 'Users'. Drops any schema qualifier and quoting."""
    return identifier.split(".")[-1].strip().strip("`\"[]")


def match_paren(text, start):
    """Given the index of an opening '(' return the index just past its match, or None.

    Ignores parentheses inside quotes and comments, so DEFAULT 'a(b' and
    CHECK (x IN ('y)')) do not truncate the table body.
    """
    depth, i, quote, n = 0, start, None, len(text)
    while i < n:
        ch = text[i]
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                if i + 1 < n and text[i + 1] == quote:
                    i += 2
                    continue
                quote = None
        elif ch in "'\"`":
            quote = ch
        elif ch == "-" and text.startswith("--", i):
            j = text.find("\n", i)
            i = n if j == -1 else j
            continue
        elif ch == "/" and text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j == -1 else j + 2
            continue
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return None


def iter_create_tables(text):
    """Yield (table_name, body) for every CREATE TABLE, schema qualifier stripped."""
    for m in CREATE_TABLE_HEAD.finditer(text):
        end = match_paren(text, m.end() - 1)
        if end is None:
            continue
        yield bare(m.group(1)), text[m.end():end - 1]


def split_column(defn):
    """'full_name character varying(255) NOT NULL' -> ('full_name', 'character varying(255)', 'NOT NULL')."""
    m = re.match(r"\s*([`\"\[]?[\w$]+[`\"\]]?)\s+(.*)$", defn, re.S)
    if not m:
        return None
    name, rest = m.group(1).strip("`\"[]"), m.group(2).strip()
    stop = TYPE_STOP.search(rest)
    coltype, tail = (rest[:stop.start()], rest[stop.start():]) if stop else (rest, "")
    coltype = re.sub(r"\s+", " ", coltype).strip().rstrip(",")
    return name, coltype, tail


def parse_sql_tables(text):
    tables = {}
    for name, body in iter_create_tables(text):
        cols = []
        for raw in body.split("\n"):
            line = raw.strip().rstrip(",")
            if not line or line.startswith("--") or line.startswith("/*"):
                continue
            if line.upper().startswith(SKIP_LINE_START):
                continue
            parts = split_column(line)
            if not parts:
                continue
            cname, ctype, _tail = parts
            up = line.upper()
            col = {"name": cname, "type": ctype or "TEXT", "flags": []}
            if "PRIMARY KEY" in up:
                col["flags"].append("PK")
            ref = REF_INLINE.search(line)
            if ref:
                col["flags"].append("FK")
                col["ref"] = bare(ref.group(1))
            if "NOT NULL" in up:
                col["flags"].append("NOT NULL")
            if re.search(r"\bUNIQUE\b", up):
                col["flags"].append("UNIQUE")
            cols.append(col)
        # table-level constraints
        by_name = {c["name"]: c for c in cols}
        for fk in FK_TABLE_LEVEL.finditer(body):
            c = by_name.get(fk.group(1))
            if c is not None:
                if "FK" not in c["flags"]:
                    c["flags"].append("FK")
                c["ref"] = bare(fk.group(2))
        for pk in PK_TABLE_LEVEL.finditer(body):
            for col_name in re.split(r"[,\s]+", pk.group(1)):
                c = by_name.get(col_name.strip("`\"[]"))
                if c is not None and "PK" not in c["flags"]:
                    c["flags"].append("PK")
        tables[name] = cols
    return tables


def parse_prisma(text):
    """Prisma models -> tables. Relation fields are not columns; @relation gives the FK."""
    tables = {}
    for m in PRISMA_MODEL.finditer(text):
        model, body = m.group(1), m.group(2)
        cols, pending = [], []
        for raw in body.splitlines():
            line = raw.split("//")[0].strip()
            if not line or line.startswith("@@"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            fname, ftype, attrs = parts[0], parts[1], " ".join(parts[2:])
            if ftype.endswith("[]"):
                continue  # list relation, not a column
            rel = PRISMA_RELATION.search(attrs)
            if rel:
                fields = PRISMA_FIELDS.search(rel.group(1))
                if fields:
                    pending.append((fields.group(1), ftype.rstrip("?")))
                continue  # the relation field itself is not a column
            col = {"name": fname, "type": ftype.rstrip("?").split(".")[0], "flags": []}
            if re.search(r"@id\b", attrs):
                col["flags"].append("PK")
            if re.search(r"@unique\b", attrs):
                col["flags"].append("UNIQUE")
            cols.append(col)
        by_name = {c["name"]: c for c in cols}
        for field_list, target in pending:
            for fname in re.split(r"[,\s]+", field_list.strip()):
                c = by_name.get(fname.strip())
                if c is not None:
                    if "FK" not in c["flags"]:
                        c["flags"].append("FK")
                    c["ref"] = target
        tables[model] = cols
    return tables


LARAVEL_TYPES = {
    "id": "bigint", "foreignId": "bigint", "foreignUuid": "char(36)", "foreignUlid": "char(26)",
    "unsignedBigInteger": "bigint", "bigInteger": "bigint", "unsignedInteger": "int",
    "integer": "int", "tinyInteger": "tinyint", "smallInteger": "smallint",
    "mediumInteger": "mediumint", "unsignedSmallInteger": "smallint",
    "string": "varchar(255)", "char": "char(1)", "text": "text", "mediumText": "mediumtext",
    "longText": "longtext", "tinyText": "tinytext",
    "boolean": "boolean", "decimal": "decimal(8,2)", "float": "float", "double": "double",
    "date": "date", "dateTime": "datetime", "time": "time", "timestamp": "timestamp", "year": "year",
    "json": "json", "jsonb": "jsonb", "uuid": "char(36)", "ulid": "char(26)",
    "binary": "blob", "enum": "enum", "ipAddress": "varchar(45)", "macAddress": "varchar(17)",
}
LARAVEL_SKIP = {"timestamps", "nullableTimestamps", "softDeletes", "morphs", "nullableMorphs",
                "rememberToken", "index", "unique", "primary", "dropColumn", "dropForeign"}


def plural(word):
    if word.endswith("y") and len(word) > 1 and word[-2] not in "aeiou":
        return word[:-1] + "ies"
    if word.endswith(("s", "x", "ch", "sh")):
        return word + "es"
    return word + "s"


def parse_laravel(text):
    """Schema::create(...) migrations -> tables, with Laravel's implicit PK/FK conventions."""
    tables = {}
    for m in LARAVEL_TABLE.finditer(text):
        table, body = m.group(1), m.group(2)
        cols, pending_fk = [], []
        for raw in body.splitlines():
            line = raw.strip()
            if "$table->" not in line:
                continue
            call = LARAVEL_CALL.search(line)
            if not call:
                continue
            method, arg0, extra = call.group(1), call.group(2), call.group(3) or ""
            if method == "foreign":
                on = re.search(r"->on\(\s*['\"]([^'\"]+)['\"]", line)
                if arg0 and on:
                    pending_fk.append((arg0, on.group(1)))
                continue
            if method in LARAVEL_SKIP:
                continue
            ctype = LARAVEL_TYPES.get(method)
            if ctype is None:
                continue
            nums = re.findall(r"\d+", extra)
            if method == "string" and nums:
                ctype = f"varchar({nums[0]})"
            elif method == "char" and nums:
                ctype = f"char({nums[0]})"
            elif method == "decimal" and len(nums) >= 2:
                ctype = f"decimal({nums[0]},{nums[1]})"
            col = {"name": arg0 or method, "type": ctype, "flags": []}
            if method == "id" or "->primary()" in line:
                col["flags"].append("PK")
            if "->nullable()" not in line:
                col["flags"].append("NOT NULL")
            if "->unique()" in line:
                col["flags"].append("UNIQUE")
            if method == "foreignId" or method == "foreignUuid" or method == "foreignUlid":
                con = re.search(r"->constrained\(\s*(?:['\"]([^'\"]+)['\"])?", line)
                stem = arg0[:-3] if arg0.endswith("_id") else arg0
                ref = (con.group(1) if con and con.group(1) else plural(stem)) if con else plural(stem)
                col["flags"].append("FK")
                col["ref"] = ref
            cols.append(col)
        by_name = {c["name"]: c for c in cols}
        for fk_col, ref_table in pending_fk:
            c = by_name.get(fk_col)
            if c is not None:
                if "FK" not in c["flags"]:
                    c["flags"].append("FK")
                c["ref"] = ref_table
        tables[table] = cols
    return tables


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--out", default="scan.json")
    ap.add_argument("--ignore", action="append", default=[], metavar="DIR",
                    help="extra folder name to skip (repeatable)")
    ap.add_argument("--keep-vendored", action="store_true",
                    help="scan vendored skill/agent packs too (off by default: they are not your code)")
    args = ap.parse_args()

    root = os.path.abspath(args.project)
    if not os.path.isdir(root):
        sys.exit(f"Not a folder: {root}")

    result = {"project_folder": os.path.basename(root), "languages": {}, "manifests": {}, "folders": [],
              "routes": [], "tables": {}, "env_vars": [], "env_declared": [], "test_files": [],
              "other_test_files": [], "server_files": [], "api_calls": [], "migrations": [],
              "todos": [], "readme": "", "file_count": 0}
    env_vars, env_declared, routes, todos, calls, servers, migrations = set(), set(), [], [], [], [], []
    other_tests = []
    top_dirs = set()
    stats = {"ignored_dirs": 0, "vendored": 0}

    for path in walk(root, stats, keep_vendored=args.keep_vendored, extra_ignore=args.ignore):
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        result["file_count"] += 1
        parts = rel.split("/")
        if len(parts) > 1:
            top_dirs.add(parts[0])
        name = os.path.basename(path)
        ext = os.path.splitext(name)[1].lower()

        if ext in LANG_BY_EXT:
            lang = LANG_BY_EXT[ext]
            result["languages"][lang] = result["languages"].get(lang, 0) + 1
        if name in MANIFESTS:
            result["manifests"][rel] = read(path, 20_000)[:4000]
        if name.lower().startswith("readme") and not result["readme"]:
            result["readme"] = read(path, 20_000)[:6000]
        if MIGRATION_HINT.search(rel):
            migrations.append(rel)
        in_server = bool(SERVER_DIR.search(rel))
        if in_server and ext in (".ts", ".js", ".mjs", ".cjs", ".py", ".php"):
            servers.append(rel)
        # never read real secret files; only the example one for var names
        if name in (".env.example", ".env.sample", ".env.dist"):
            for line in read(path, 20_000).splitlines():
                m = re.match(r"\s*([A-Z0-9_]+)\s*=", line)
                if m and not ENV_NOISE.match(m.group(1)):
                    env_declared.add(m.group(1))
            continue
        if name.startswith(".env"):
            continue

        if ext in (".sql",):
            result["tables"].update(parse_sql_tables(read(path)))
        if ext in (".prisma",):
            result["tables"].update(parse_prisma(read(path)))
        if ext in (".php", ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".cs", ".vue", ".rb", ".go", ".dart"):
            text = read(path)
            if "migrations" in rel.lower() and ext == ".php":
                result["tables"].update(parse_laravel(text))
            for pat in ENV_PATTERNS:
                for var in pat.findall(text):
                    if not ENV_NOISE.match(var):
                        env_vars.add(var)
            for pat in ROUTE_PATTERNS:
                for method, route in pat.findall(text) if pat.groups == 2 else [("", r) for r in pat.findall(text)]:
                    if len(routes) < 300:
                        routes.append({"method": method.upper(), "path": route, "file": rel})
            if not in_server and ext in (".ts", ".tsx", ".js", ".jsx") and not TEST_NAME.search(rel):
                for pat in CLIENT_CALL:
                    for target in pat.findall(text):
                        if len(calls) < 60:
                            calls.append({"target": target[:120], "file": rel})
            for i, line in enumerate(text.splitlines(), 1):
                if re.search(r"\b(TODO|FIXME|HACK)\b", line) and len(todos) < 40:
                    todos.append({"file": rel, "line": i, "text": line.strip()[:160]})
        if TEST_DIR.search(rel):
            result["test_files"].append(rel)
        elif TEST_NAME.search(rel):
            other_tests.append(rel)

    result["folders"] = sorted(top_dirs)
    result["env_declared"] = sorted(env_declared)
    result["env_vars"] = sorted(env_vars - env_declared)
    result["routes"] = routes
    result["todos"] = todos
    result["server_files"] = sorted(servers)[:20]
    result["api_calls"] = calls
    result["migrations"] = sorted(migrations)[:80]
    result["other_test_files"] = sorted(other_tests)[:40]
    result["test_files"] = sorted(result["test_files"])[:60]
    result["ignored_folders"] = stats["ignored_dirs"]
    result["vendored_packs"] = stats["vendored"]
    result["languages"] = dict(sorted(result["languages"].items(), key=lambda kv: -kv[1]))

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"Scanned {result['file_count']} files -> {args.out} "
          f"({result['ignored_folders']} folders ignored"
          f"{', ' + str(result['vendored_packs']) + ' vendored pack(s)' if result['vendored_packs'] else ''})")
    print(f"Languages: {', '.join(result['languages']) or 'none found'}")
    print(f"Tables: {len(result['tables'])}  Routes: {len(routes)}  "
          f"Env vars: {len(env_declared)} declared + {len(result['env_vars'])} referenced only")
    print(f"Tests: {len(result['test_files'])} in the project's test folders"
          f" ({len(other_tests)} test-named files elsewhere are not counted)")
    if servers:
        wired = sum(1 for c in calls if LOCAL_BACKEND.match(c["target"]) or c["target"].startswith("/"))
        print(f"Server-looking files: {len(servers)}; client calls that reach one: {wired}")


if __name__ == "__main__":
    main()
