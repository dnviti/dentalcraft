#!/usr/bin/env python3
"""Generate THIRD-PARTY-NOTICES.md for the binaries shipped by a Cargo workspace.

    scripts/third-party-notices.py [WORKSPACE_DIR] [-o OUT.md] [--report REPORT.md]
                                   [--roots dc-app,dc-cli] [--target TRIPLE ...]

WORKSPACE_DIR  directory with the workspace Cargo.toml (default: dentalcraft-app).
-o             output file (default: THIRD-PARTY-NOTICES.md in the current directory).
--report       write the compliance report (copyleft / problematic licences, missing
               texts, per-binary pull-in paths) to this file as well as stdout.
--roots        shipped binary packages (default: dc-app,dc-cli, as in binaries.yml).
--target       target triple to resolve for (repeatable). Default: the release
               targets of binaries.yml, x86_64-unknown-linux-gnu and
               x86_64-pc-windows-gnu. The closure is the union over the targets.

What it does
  * Copies the workspace to a scratch directory outside any enclosing repository, so
    the superproject .cargo/config.toml [patch] does not apply (dependencies resolve
    to the pinned tags, as in CI) and the real Cargo.lock is never rewritten.
  * Runs `cargo metadata --format-version 1 --locked` per target and takes the
    closure of the roots over normal dependency edges (no dev or build-only deps:
    build dependencies are not linked into the shipped binaries).
  * Drops the project's own crates (dc-*, dca-*; path or dnviti-personal-org git
    sources) and lists every other crate with name, version, SPDX expression,
    repository and the licence/notice files shipped in its source directory
    (LICENSE*, COPYING*, NOTICE*, ...), identical texts printed once.
  * Adds the fonts and icons bundled under assets/ of the project's crates (the
    OFL / MIT files next to them).
  * Crates without a licence file get the text of their Apache-2.0 licence taken
    from another crate of the tree (that text is not holder specific); other
    licences are never filled in with someone else's copyright line and are
    reported as missing instead.

Python 3 standard library only. Needs cargo on PATH and the crates already in the
cargo cache or network access.
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

# Licences whose text has no copyright holder line: a crate without licence file may
# use the text found in another crate (Apache-2.0 first, as the usual dual choice).
STANDARD_TEXT_IDS = ("Apache-2.0", "BSL-1.0", "CC0-1.0", "MPL-2.0")
DEFAULT_ROOTS = ["dc-app", "dc-cli"]
DEFAULT_TARGETS = ["x86_64-unknown-linux-gnu", "x86_64-pc-windows-gnu"]
OWN_SOURCE_MARKER = "dnviti-personal-org"

LICENCE_FILE = re.compile(
    r"^(licen[cs]es?|copying|copyright|notice|unlicen[cs]e|authors?|patents)([-_.].*)?$", re.I
)
# Files that look like licence files by name but are not (code, metadata).
LICENCE_FILE_SKIP_EXT = {".rs", ".toml", ".py", ".sh", ".c", ".h", ".json", ".yml", ".yaml", ".lock"}
NOTICE_NAME = re.compile(r"^notice([-_.].*)?$", re.I)
AUTHORS = re.compile(r"^authors?([-_.].*)?$", re.I)

# SPDX handling ---------------------------------------------------------------
PERMISSIVE = {
    "MIT", "MIT-0", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "0BSD",
    "Zlib", "Unlicense", "CC0-1.0", "BSL-1.0", "Unicode-3.0", "Unicode-DFS-2016",
    "OFL-1.1", "NCSA", "BlueOak-1.0.0", "WTFPL", "CDLA-Permissive-2.0",
    "LLVM-exception", "Apache-2.0 WITH LLVM-exception", "Libpng", "OpenSSL",
}
# Not copyleft for the app, but with conditions to honour (ship the text; no
# modified-font renaming): flagged for a human look, severity "notice".
NOTICE_ONLY = {"Ubuntu-font-1.0"}
WEAK_COPYLEFT = ("MPL-", "LGPL-", "EPL-", "CDDL-", "CPL-", "EUPL-", "OSL-", "Artistic-")
SEV_LABEL = {
    1: "notice",
    2: "weak copyleft (LGPL/EPL/CDDL: linking constraints)",
    3: "strong copyleft, non-commercial or unknown",
}


def sev_label(e) -> str:
    if e["sev"] != 1:
        return SEV_LABEL[e["sev"]]
    ids = spdx_ids(e["spdx"])
    hints = []
    if any(i.startswith("MPL-") for i in ids):
        hints.append("MPL-2.0: source of modified files only")
    if "Ubuntu-font-1.0" in ids:
        hints.append("Ubuntu font licence: keep the text, no renaming of modified fonts")
    return "notice (" + "; ".join(hints) + ")"


def term_severity(term: str) -> int:
    base = term.rstrip("+")
    if term in PERMISSIVE or base in PERMISSIVE:
        return 0
    if base.startswith("MPL-") or base in NOTICE_ONLY:
        return 1
    if base.startswith(WEAK_COPYLEFT):
        return 2
    return 3


def tokenize(expr: str):
    return re.findall(r"\(|\)|[^\s()]+", expr)


def severity(expr: str | None) -> int:
    """Lowest severity a licensee can choose from an SPDX expression (OR = choice)."""
    if not expr or not expr.strip():
        return 3
    toks = tokenize(expr.replace("/", " OR "))  # legacy "MIT/Apache-2.0"
    pos = 0

    def parse_or():
        nonlocal pos
        vals = [parse_and()]
        while pos < len(toks) and toks[pos].upper() == "OR":
            pos += 1
            vals.append(parse_and())
        return min(vals)

    def parse_and():
        nonlocal pos
        vals = [parse_atom()]
        while pos < len(toks) and toks[pos].upper() == "AND":
            pos += 1
            vals.append(parse_atom())
        return max(vals)

    def parse_atom():
        nonlocal pos
        if pos >= len(toks):
            return 3
        t = toks[pos]
        if t == "(":
            pos += 1
            v = parse_or()
            if pos < len(toks) and toks[pos] == ")":
                pos += 1
            return v
        pos += 1
        sev = term_severity(t)
        # "X WITH exception"
        if pos < len(toks) and toks[pos].upper() == "WITH":
            pos += 2
        return sev

    try:
        return parse_or()
    except Exception:
        return 3


def satisfiable_with(expr: str | None, spdx_id: str) -> bool:
    """True if choosing only `spdx_id` satisfies the expression (OR = any, AND = all)."""
    if not expr:
        return False
    toks = tokenize(expr.replace("/", " OR "))
    pos = 0

    def parse_or():
        nonlocal pos
        v = parse_and()
        while pos < len(toks) and toks[pos].upper() == "OR":
            pos += 1
            v = parse_and() or v
        return v

    def parse_and():
        nonlocal pos
        v = parse_atom()
        while pos < len(toks) and toks[pos].upper() == "AND":
            pos += 1
            v = parse_atom() and v
        return v

    def parse_atom():
        nonlocal pos
        if pos >= len(toks):
            return False
        t = toks[pos]
        pos += 1
        if t == "(":
            v = parse_or()
            if pos < len(toks) and toks[pos] == ")":
                pos += 1
            return v
        ok = t == spdx_id
        if pos < len(toks) and toks[pos].upper() == "WITH":
            pos += 2
            ok = False
        return ok

    try:
        return parse_or()
    except Exception:
        return False


def spdx_ids(expr: str | None):
    if not expr:
        return []
    return [t for t in tokenize(expr.replace("/", " OR "))
            if t not in "()" and t.upper() not in ("AND", "OR", "WITH")]


# Licence text classification (fingerprints) ----------------------------------
def classify_text(text: str) -> str | None:
    """Primary licence of a text (first fingerprint that matches), or None."""
    ids = classify_all(text)
    return ids[0] if ids else None


def classify_all(text: str) -> list:
    """Every licence fingerprint found in a text (a LICENSE file may hold several)."""
    t = " ".join(text.split()).lower()
    ids = []
    if "boost software license" in t:
        ids.append("BSL-1.0")
    if "sil open font license" in t:
        ids.append("OFL-1.1")
    if "data files and any associated documentation" in t and "unicode" in t:
        ids.append("Unicode-3.0")
    if "apache license" in t and "version 2.0" in t:
        ids.append("Apache-2.0")
    # BSL, OFL and Unicode reuse the MIT grant sentence: not an MIT text by itself
    grant = "permission is hereby granted, free of charge" in t
    if grant and (not {"BSL-1.0", "OFL-1.1", "Unicode-3.0"} & set(ids) or "mit license" in t):
        ids.append("MIT")
    if "cc0 1.0 universal" in t:
        ids.append("CC0-1.0")
    if "ubuntu font licence" in t:
        ids.append("Ubuntu-font-1.0")
    if "mozilla public license" in t and "2.0" in t:
        ids.append("MPL-2.0")
    if "gnu lesser general public" in t:
        ids.append("LGPL")
    if "gnu general public license" in t:
        ids.append("GPL")
    if "redistribution and use in source and binary forms" in t:
        ids.append("BSD-3-Clause" if "neither the name" in t else "BSD-2-Clause")
    if "permission to use, copy, modify, and/or distribute" in t:
        ids.append("ISC")
    if "this is free and unencumbered software" in t:
        ids.append("Unlicense")
    if "zlib" in t and "altered source versions" in t:
        ids.append("Zlib")
    return ids


# Election of one licence per crate -------------------------------------------
# Preference when a crate offers a choice (SPDX OR); the first alternative with all
# its texts available wins, after the severity (a permissive choice beats any other).
PREFERENCE = ["MIT", "Apache-2.0", "BSD-3-Clause", "BSD-2-Clause", "ISC", "Zlib", "BSL-1.0", "Unicode-3.0"]
FAMILY = {"0BSD": "ISC", "MIT-0": "MIT", "BSD-2-Clause": "BSD", "BSD-3-Clause": "BSD",
          "Apache-2.0 WITH LLVM-exception": "Apache-2.0"}


def family(spdx_id: str) -> str:
    return FAMILY.get(spdx_id, spdx_id.rstrip("+"))


def alternatives(expr: str | None):
    """Disjunctive normal form of an SPDX expression: list of lists of ids
    (OR = choice between lists, AND = every id of a list applies)."""
    if not expr or not expr.strip():
        return []
    toks = tokenize(expr.replace("/", " OR "))
    pos = 0

    def parse_or():
        nonlocal pos
        alts = parse_and()
        while pos < len(toks) and toks[pos].upper() == "OR":
            pos += 1
            alts = alts + parse_and()
        return alts

    def parse_and():
        nonlocal pos
        alts = parse_atom()
        while pos < len(toks) and toks[pos].upper() == "AND":
            pos += 1
            rhs = parse_atom()
            alts = [a + b for a in alts for b in rhs]
        return alts

    def parse_atom():
        nonlocal pos
        t = toks[pos]
        pos += 1
        if t == "(":
            v = parse_or()
            if pos < len(toks) and toks[pos] == ")":
                pos += 1
            return v
        if pos < len(toks) and toks[pos].upper() == "WITH":
            t = f"{t} WITH {toks[pos + 1]}"
            pos += 2
        return [[t]]

    try:
        return parse_or()
    except Exception:
        return []


def alt_cost(alt):
    return (max(term_severity(i) for i in alt),
            max((PREFERENCE.index(family(i)) if family(i) in PREFERENCE else len(PREFERENCE)) for i in alt),
            len(alt))


def elect(expr, file_ids, standard):
    """Pick the alternative to use: best cost among those whose texts can be shown
    (found in the crate or available as a standard text); else the best by cost."""
    alts = sorted(alternatives(expr), key=alt_cost)
    if not alts:
        return None
    have = {family(i) for ids in file_ids for i in ids} | {family(i) for i in standard}
    for alt in alts:
        if all(family(i) in have for i in alt):
            return alt
    return alts[0]


# Cargo -----------------------------------------------------------------------
def run(cmd, cwd, env=None, check=True):
    return subprocess.run(cmd, cwd=cwd, env=env, check=check, capture_output=True, text=True)


def metadata(workdir: Path, target: str) -> dict:
    base = ["cargo", "metadata", "--format-version", "1", "--locked", "--filter-platform", target]
    for extra in (["--offline"], []):  # cache first, then the network
        p = run(base + extra, workdir, check=False)
        if p.returncode == 0:
            return json.loads(p.stdout)
        last = p.stderr
        # --locked fails when the lock lags the manifest: handled by the caller.
        if "cannot update the lock file" in last:
            raise LockStale(last)
    raise SystemExit(f"cargo metadata failed for {target}:\n{last}")


class LockStale(Exception):
    pass


def lock_third_party(lock: Path) -> set:
    """(name, version, source) of the registry/git packages in a Cargo.lock."""
    out = set()
    for block in lock.read_text().split("[[package]]")[1:]:
        name = re.search(r'^name = "(.*)"', block, re.M)
        ver = re.search(r'^version = "(.*)"', block, re.M)
        src = re.search(r'^source = "(.*)"', block, re.M)
        if name and ver and src and OWN_SOURCE_MARKER not in src.group(1):
            out.add((name.group(1), ver.group(1), src.group(1)))
    return out


def stage_workspace(ws: Path, scratch: Path) -> Path:
    """Copy of the workspace outside the enclosing repo (no parent .cargo/config.toml)."""
    dst = scratch / "ws"
    shutil.copytree(ws, dst, ignore=shutil.ignore_patterns("target", ".git"))
    return dst


def resolve(workdir: Path, targets):
    """Run cargo metadata per target; returns (packages by id, {target: nodes by id})."""
    lock = workdir / "Cargo.lock"
    before = lock_third_party(lock) if lock.exists() else set()
    packages, nodes = {}, {}
    stale = False
    for tgt in targets:
        try:
            md = metadata(workdir, tgt)
        except LockStale:
            # The committed lock lags the workspace manifest (release-please bumps
            # the workspace version without refreshing Cargo.lock). Refresh it in
            # the scratch copy only, then require that no third-party pin moved.
            stale = True
            p = run(["cargo", "metadata", "--format-version", "1", "--offline",
                     "--filter-platform", tgt], workdir, check=False)
            if p.returncode != 0:
                p = run(["cargo", "metadata", "--format-version", "1",
                         "--filter-platform", tgt], workdir)
            md = json.loads(p.stdout)
        for pkg in md["packages"]:
            packages[pkg["id"]] = pkg
        nodes[tgt] = {n["id"]: n for n in md["resolve"]["nodes"]}
        md_root = md
    if stale:
        after = lock_third_party(lock)
        if before != after:
            moved = sorted(before ^ after)
            raise SystemExit("Cargo.lock refresh moved third-party pins; refusing:\n"
                             + "\n".join(map(str, moved[:20])))
        print("note: Cargo.lock lags the workspace manifest (workspace member versions "
              "only); refreshed in the scratch copy, third-party pins unchanged",
              file=sys.stderr)
    return packages, nodes, md_root


def closure(roots, nodes_by_target):
    """Normal-dependency closure from the roots, per root, union over targets."""
    reach = {}
    for rid in roots:
        seen = set()
        stack = [rid]
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            for nodes in nodes_by_target.values():
                node = nodes.get(cur)
                if not node:
                    continue
                for dep in node["deps"]:
                    if any(k["kind"] is None for k in dep["dep_kinds"]):
                        stack.append(dep["pkg"])
        reach[rid] = seen
    return reach


def is_own(pkg) -> bool:
    src = pkg.get("source")
    return src is None or OWN_SOURCE_MARKER in src


# Licence file collection -----------------------------------------------------
def read_text(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\0" in data[:4096]:
        return None
    return data.decode("utf-8", "replace").replace("\r\n", "\n").strip("\n") + "\n"


def licence_files(src_dir: Path, license_file: str | None):
    """Licence/notice files of a crate source dir (top level, LICENSES/ and license-file)."""
    found = {}

    def consider(p: Path):
        if p.is_file() and p.suffix.lower() not in LICENCE_FILE_SKIP_EXT and not AUTHORS.match(p.name):
            found[p.resolve()] = p

    for p in sorted(src_dir.iterdir()):
        if p.is_file() and LICENCE_FILE.match(p.name):
            consider(p)
        elif p.is_dir() and p.name.lower() in ("licenses", "license", "licences", "licence"):
            for q in sorted(p.rglob("*")):
                consider(q)
        elif p.is_dir() and p.name.lower() in ("fonts", "assets"):
            # bundled fonts/icons keep their licence next to them (OFL.txt, UFL.txt, ...)
            for q in sorted(p.rglob("*.txt")):
                consider(q)
    if license_file:
        consider(src_dir / license_file)
    out = []
    for p in found.values():
        text = read_text(p)
        if text and text.strip():
            out.append((p.relative_to(src_dir).as_posix() if p.is_relative_to(src_dir) else p.name, text))
    return out


def bundled_assets(own_pkgs):
    """Licence files under assets/ of the project's own crates (fonts, icons)."""
    entries = {}
    for pkg in own_pkgs:
        root = Path(pkg["manifest_path"]).parent
        assets = root / "assets"
        if not assets.is_dir():
            continue
        for p in sorted(assets.rglob("*")):
            if p.is_file() and (LICENCE_FILE.match(p.name) or re.match(r"^ofl([-_.].*)?$", p.name, re.I)):
                text = read_text(p)
                if not text:
                    continue
                rel = p.parent.relative_to(assets).as_posix()
                entries.setdefault((pkg["name"], rel), []).append((p.name, text))
    return entries


def first_copyright(text: str) -> str:
    for line in text.splitlines():
        if re.search(r"copyright|\(c\)|©", line, re.I):
            return line.strip()
    return ""


def fence_for(text: str) -> str:
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    return "`" * max(3, longest + 1)


def digest(text: str) -> str:
    return hashlib.sha256(" ".join(text.split()).encode()).hexdigest()


# Main ------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workspace", nargs="?", default="dentalcraft-app")
    ap.add_argument("-o", "--output", default="THIRD-PARTY-NOTICES.md")
    ap.add_argument("--report")
    ap.add_argument("--roots", default=",".join(DEFAULT_ROOTS))
    ap.add_argument("--target", action="append")
    args = ap.parse_args()

    ws = Path(args.workspace).resolve()
    if not (ws / "Cargo.toml").is_file():
        sys.exit(f"{ws}: no Cargo.toml")
    targets = args.target or DEFAULT_TARGETS
    root_names = [r for r in args.roots.split(",") if r]
    env_path = os.path.expanduser("~/.cargo/bin")
    os.environ["PATH"] = env_path + os.pathsep + os.environ.get("PATH", "")
    if shutil.which("cargo") is None:
        sys.exit("cargo not found on PATH")

    with tempfile.TemporaryDirectory(prefix="dc-notices-") as tmp:
        workdir = stage_workspace(ws, Path(tmp))
        packages, nodes, md = resolve(workdir, targets)
        members = set(md["workspace_members"])
        root_ids = [pid for pid in members if packages[pid]["name"] in root_names]
        missing_roots = set(root_names) - {packages[r]["name"] for r in root_ids}
        if missing_roots:
            sys.exit(f"root packages not in the workspace: {sorted(missing_roots)}")
        reach = closure(root_ids, nodes)
        in_closure = set().union(*reach.values())

        own = [packages[i] for i in in_closure if is_own(packages[i])]
        third = sorted((packages[i] for i in in_closure if not is_own(packages[i])),
                       key=lambda p: (p["name"].lower(), p["version"]))

        # which shipped binary pulls each crate in
        pulled_by = {}
        for pkg in third:
            pulled_by[pkg["id"]] = sorted(packages[r]["name"] for r in root_ids if pkg["id"] in reach[r])

        # collect texts
        info = []
        for pkg in third:
            src_dir = Path(pkg["manifest_path"]).parent
            files = licence_files(src_dir, pkg.get("license_file"))
            info.append({"pkg": pkg, "files": files, "spdx": pkg.get("license"),
                         "sev": severity(pkg.get("license") or None)})

        # Reference texts that carry no holder specific line, taken from the tree
        standard = {}
        for sid in STANDARD_TEXT_IDS:
            counts = defaultdict(int)
            for e in info:
                for _, text in e["files"]:
                    if classify_all(text)[:1] == [sid] and text.count("\n") > 5:
                        counts[text] += 1
            if counts:
                standard[sid] = max(counts, key=counts.get)

        # Elect one licence per crate (OR = choice; AND keeps every text) and keep
        # only the texts of the elected licence, plus NOTICE files.
        missing = []
        for e in info:
            file_ids = [classify_all(t) for _, t in e["files"]]
            alt = elect(e["spdx"], file_ids, standard)
            e["elected"] = alt
            if alt is None:  # no usable SPDX expression: keep whatever is shipped
                if not e["files"]:
                    missing.append(e)
                continue
            fams = {family(i) for i in alt}
            kept = [(n, t) for (n, t), ids in zip(e["files"], file_ids)
                    if not ids or fams & {family(i) for i in ids} or NOTICE_NAME.match(Path(n).name)]
            if not kept:
                kept = list(e["files"])
            covered = {family(i) for (n, t) in kept for i in classify_all(t)}
            borrowed = []
            for i in alt:
                if family(i) not in covered and i in standard:
                    kept.append((f"(standard {i} text, taken from another crate of the tree)", standard[i]))
                    borrowed.append(i)
                    covered.add(family(i))
            if not kept:
                missing.append(e)
            if borrowed:
                e["borrowed"] = " + ".join(borrowed)
            e["files"] = kept

        assets = bundled_assets(own)

        # group texts
        texts = {}      # digest -> {"text":..., "users":[...]}
        order = []
        def add_text(label, text, user):
            d = digest(text)
            if d not in texts:
                texts[d] = {"text": text, "users": [], "label": label}
                order.append(d)
            if user not in texts[d]["users"]:
                texts[d]["users"].append(user)
            return d

        for e in info:
            e["refs"] = [add_text(n, t, f"{e['pkg']['name']} {e['pkg']['version']}") for n, t in e["files"]]
        asset_rows = []
        for (crate, rel), files in sorted(assets.items()):
            refs = [add_text(n, t, f"{rel} ({crate})") for n, t in files]
            asset_rows.append((rel, crate, refs, files))

        write_notices(Path(args.output), info, asset_rows, texts, order, root_names, targets)

        write_report(args, info, missing, third, pulled_by, packages, root_ids, workdir, targets,
                     len(texts), len(asset_rows))


def spdx_for_asset(files):
    ids = {classify_text(t) for _, t in files}
    ids.discard(None)
    return " AND ".join(sorted(ids)) or "see text"


def write_notices(out: Path, info, asset_rows, texts, order, roots, targets):
    lines = []
    w = lines.append
    w("# Third-party notices")
    w("")
    w("DentalCraft is source-available under the PolyForm Noncommercial License 1.0.0 (see `LICENSE.md`).")
    w("It includes the third-party components listed below, each under its own licence. This file")
    w("reproduces the copyright and licence notices that those licences require.")
    w("")
    w("Generated by `scripts/third-party-notices.py` (superproject) from the dependency")
    w(f"closure of {' and '.join('`' + r + '`' for r in roots)} (normal dependencies, targets: "
      f"{', '.join(targets)}), on {datetime.date.today().isoformat()}.")
    w("To regenerate, from the superproject root:")
    w("`scripts/third-party-notices.py dentalcraft-app -o dentalcraft-app/THIRD-PARTY-NOTICES.md`.")
    w("Do not edit by hand.")
    w("")
    w(f"Rust crates: {len(info)}. Bundled fonts and icons: {len(asset_rows)}.")
    w("")
    w("## Bundled fonts and icons")
    w("")
    for rel, crate, refs, files in asset_rows:
        name = rel if rel != "." else f"assets of {crate}"
        w(f"- **{name}**: {spdx_for_asset(files)}. Licence text: "
          + ", ".join(f"[text {order.index(r) + 1}](#text-{order.index(r) + 1})" for r in refs))
    w("")
    w("## Rust crates")
    w("")
    w("| Crate | Version | Licence (SPDX) | Used under | Repository | Text |")
    w("|---|---|---|---|---|---|")
    for e in info:
        p = e["pkg"]
        repo = p.get("repository") or p.get("homepage") or ""
        refs = ", ".join(f"[{order.index(r) + 1}](#text-{order.index(r) + 1})" for r in dict.fromkeys(e["refs"]))
        spdx = (p.get("license") or "none").replace("|", "\\|")
        used = " AND ".join(e["elected"]) if e.get("elected") else (p.get("license") or "none")
        w(f"| {p['name']} | {p['version']} | {spdx} | {used} | {repo} | {refs or 'none'} |")
    w("")
    w("## Licence texts")
    w("")
    w("Each distinct text is printed once, followed by the components it applies to.")
    w("Where a crate offers a choice of licences (`OR`), DentalCraft uses it under the one")
    w("named in the \"Used under\" column and only that text is reproduced. Where a crate")
    w("combines licences (`AND`), all of them apply and all texts are reproduced.")
    w("")
    for i, d in enumerate(order, 1):
        t = texts[d]
        w(f'<a id="text-{i}"></a>')
        w(f"### Text {i}")
        w("")
        w("Applies to: " + ", ".join(t["users"]))
        w("")
        f = fence_for(t["text"])
        w(f + "text")
        w(t["text"].rstrip("\n"))
        w(f)
        w("")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines))


def write_report(args, info, missing, third, pulled_by, packages, root_ids, workdir, targets,
                 ntexts, nassets):
    r = []
    w = r.append
    w(f"# Licence compliance report ({', '.join(targets)})")
    w("")
    w(f"Crates (third party): {len(third)}; unique licence texts: {ntexts}; bundled assets: {nassets}")
    w("")
    by_lic = defaultdict(int)
    for e in info:
        by_lic[e["spdx"] or "NONE"] += 1
    w("## Licences by count (SPDX expression as declared)")
    w("")
    for lic, n in sorted(by_lic.items(), key=lambda kv: (-kv[1], kv[0])):
        w(f"- {n:4d}  {lic}")
    w("")
    by_used = defaultdict(int)
    for e in info:
        by_used[" AND ".join(e["elected"]) if e.get("elected") else (e["spdx"] or "NONE")] += 1
    w("## Licences by count (as used: one licence elected per OR choice)")
    w("")
    for lic, n in sorted(by_used.items(), key=lambda kv: (-kv[1], kv[0])):
        w(f"- {n:4d}  {lic}")
    w("")
    w("## Problematic for a closed-source binary")
    w("")
    flagged = [e for e in info if e["sev"] > 0]
    if not flagged:
        w("none")
    for e in sorted(flagged, key=lambda e: (-e["sev"], e["pkg"]["name"])):
        p = e["pkg"]
        w(f"- {p['name']} {p['version']}: {e['spdx'] or 'NONE'}; {sev_label(e)}; "
          f"pulled in by: {', '.join(pulled_by[p['id']])}")
        # cargo tree -i evidence
        spec = f"{p['name']}@{p['version']}"
        for tgt in targets:
            t = run(["cargo", "tree", "-i", spec, "-e", "normal", "--target", tgt, "--locked", "--offline"],
                    workdir, check=False)
            first = [l for l in (t.stdout or t.stderr).splitlines() if l.strip()][:12]
            w(f"  - cargo tree -i {spec} --target {tgt}:")
            for l in first:
                w(f"    {l}")
    w("")
    w("## Missing licence text")
    w("")
    if not missing:
        w("none")
    for e in missing:
        p = e["pkg"]
        w(f"- {p['name']} {p['version']}: {e['spdx'] or 'NONE'} ({p.get('repository') or 'no repository'})")
    w("")
    borrowed = [e for e in info if e.get("borrowed")]
    w("## Standard text borrowed from another crate")
    w("")
    if not borrowed:
        w("none")
    for e in borrowed:
        w(f"- {e['pkg']['name']} {e['pkg']['version']}: {e['spdx']} (used {e['borrowed']})")
    w("")
    text = "\n".join(r)
    print(text)
    if args.report:
        Path(args.report).write_text(text)


if __name__ == "__main__":
    main()
