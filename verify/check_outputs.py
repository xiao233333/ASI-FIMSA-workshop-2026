#!/usr/bin/env python3
"""Inspect executed notebooks for the failures nbconvert's exit code misses.

`jupyter nbconvert --execute` exits 0 as long as no cell raised. That is a weak
signal for teaching material: a notebook whose plotting silently produced
nothing, or whose figures were swallowed by a headless matplotlib backend, still
exits 0 and still ruins the Tutorial. This checks the executed notebooks
themselves:

  * zero error outputs   -- a traceback anywhere is a failure
  * >=1 embedded image   -- proof that at least one figure actually rendered
  * wall time            -- read back from the per-cell execution timestamps
                            nbclient records, so it reflects the notebook, not
                            the harness

Usage
    python verify/check_outputs.py verify/output
    python verify/check_outputs.py verify/output/00_setup_check.ipynb
    python verify/check_outputs.py verify/output --budget 00_setup_check=120

Exits 1 if any notebook fails a check.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys

IMAGE_MIMES = ("image/png", "image/jpeg", "image/svg+xml")

# A Participant runs 00_setup_check before the Workshop, on Colab, possibly on
# hotel wifi. If it stops being a two-minute notebook it stops being run at all.
DEFAULT_BUDGETS = {"00_setup_check": 120}


def parse_ts(value):
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def inspect(path: pathlib.Path) -> dict:
    nb = json.loads(path.read_text(encoding="utf-8"))
    cells = [c for c in nb.get("cells", []) if c.get("cell_type") == "code"]

    errors, images, executed = [], 0, 0
    starts, ends, per_cell = [], [], []

    for idx, cell in enumerate(cells, 1):
        for out in cell.get("outputs", []):
            if out.get("output_type") == "error":
                errors.append(
                    (idx, out.get("ename", "?"), (out.get("evalue") or "").splitlines()[:1])
                )
            data = out.get("data") or {}
            if any(m in data for m in IMAGE_MIMES):
                images += 1

        meta = (cell.get("metadata") or {}).get("execution") or {}
        start = parse_ts(meta.get("iopub.execute_input") or meta.get("shell.execute_reply.started"))
        end = parse_ts(meta.get("shell.execute_reply"))
        if start and end:
            executed += 1
            starts.append(start)
            ends.append(end)
            per_cell.append((idx, (end - start).total_seconds()))
        elif cell.get("execution_count") is not None:
            executed += 1

    wall = (max(ends) - min(starts)).total_seconds() if starts and ends else None
    return {
        "path": path,
        "name": path.stem,
        "code_cells": len(cells),
        "executed": executed,
        "errors": errors,
        "images": images,
        "wall": wall,
        "per_cell": sorted(per_cell, key=lambda t: -t[1]),
    }


def load_harness_timings(root: pathlib.Path) -> dict:
    """Fallback wall times written by run_notebooks.sh, for notebooks executed
    without per-cell timing metadata."""
    tsv = root / "timings.tsv" if root.is_dir() else root.parent / "timings.tsv"
    out = {}
    if tsv.exists():
        for line in tsv.read_text().splitlines():
            parts = line.split("\t")
            if len(parts) == 2 and parts[1].strip().isdigit():
                out[parts[0]] = float(parts[1])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("targets", nargs="+",
                    help="executed .ipynb files, or a directory containing them")
    ap.add_argument("--budget", action="append", default=[], metavar="NAME=SECONDS",
                    help="fail a notebook that exceeds this wall time "
                         "(default: 00_setup_check=120)")
    ap.add_argument("--allow-no-images", action="store_true",
                    help="do not require an embedded figure (for notebooks that "
                         "legitimately plot nothing)")
    ap.add_argument("--slowest", type=int, default=3,
                    help="how many slow cells to list per notebook (default 3)")
    args = ap.parse_args()

    budgets = dict(DEFAULT_BUDGETS)
    for item in args.budget:
        name, _, secs = item.partition("=")
        budgets[name.strip()] = float(secs)

    paths: list[pathlib.Path] = []
    timings: dict[str, float] = {}
    for target in args.targets:
        p = pathlib.Path(target)
        if p.is_dir():
            paths.extend(sorted(q for q in p.glob("*.ipynb")
                                if not q.name.endswith("-checkpoint.ipynb")))
        else:
            paths.append(p)
        timings.update(load_harness_timings(p))

    if not paths:
        print("check_outputs: no executed notebooks found", file=sys.stderr)
        return 1

    print("=" * 79)
    print("OUTPUT CHECK")
    print(f"{'notebook':<34}{'cells':>6}{'imgs':>6}{'errs':>6}{'wall':>10}   verdict")
    print("-" * 79)

    failures = 0
    reports = []
    for path in paths:
        if not path.exists():
            print(f"{path.name:<34}{'':>6}{'':>6}{'':>6}{'':>10}   FAIL (missing)")
            failures += 1
            continue
        r = inspect(path)
        wall = r["wall"] if r["wall"] is not None else timings.get(r["name"])

        problems = []
        if r["errors"]:
            problems.append(f"{len(r['errors'])} error output(s)")
        if r["images"] == 0 and not args.allow_no_images:
            problems.append("no embedded image output")
        if r["executed"] == 0:
            problems.append("no cell was executed")
        budget = budgets.get(r["name"])
        if budget is not None and wall is not None and wall > budget:
            problems.append(f"wall {wall:.0f}s over budget {budget:.0f}s")

        verdict = "PASS" if not problems else "FAIL"
        failures += bool(problems)
        wall_s = f"{wall:.1f}s" if wall is not None else "n/a"
        print(f"{r['name']:<34}{r['code_cells']:>6}{r['images']:>6}"
              f"{len(r['errors']):>6}{wall_s:>10}   {verdict}")
        reports.append((r, problems))

    print("-" * 79)

    for r, problems in reports:
        if not problems and not r["per_cell"]:
            continue
        print()
        print(f"{r['name']}: {'; '.join(problems) if problems else 'ok'}")
        for idx, ename, evalue in r["errors"][:5]:
            detail = evalue[0] if evalue else ""
            print(f"    code cell {idx}: {ename}: {detail}")
        if args.slowest and r["per_cell"]:
            slow = ", ".join(f"cell {i} {s:.1f}s" for i, s in r["per_cell"][:args.slowest])
            print(f"    slowest: {slow}")

    print()
    print(f"Notebooks checked: {len(reports)}    Failures: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
