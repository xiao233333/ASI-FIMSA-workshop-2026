#!/usr/bin/env python3
"""Generate (or verify) notebooks/00_setup_check.ipynb.

00_setup_check is the one notebook a Participant opens with nothing else to
hand -- a Colab link in an email, days before the Workshop, on their own laptop.
It therefore cannot fetch constraints-colab.txt from the repo; the pin set has to
be embedded in the notebook itself.

Embedded copies drift. So the notebook is generated: the pin block is derived
from constraints-colab.txt here, and `--check` re-derives it and diffs against
what is actually in the notebook. Edit constraints-colab.txt and re-run this;
never hand-edit the pins inside the notebook.

    python verify/build_setup_check.py            # write the notebook
    python verify/build_setup_check.py --check    # fail if it is stale
"""

from __future__ import annotations

import argparse
import pathlib
import sys

import nbformat as nbf

REPO = pathlib.Path(__file__).resolve().parent.parent
CONSTRAINTS = REPO / "constraints-colab.txt"
NOTEBOOK = REPO / "notebooks" / "00_setup_check.ipynb"

PIN_START = "# --- BEGIN PINS (generated from constraints-colab.txt) ---"
PIN_END = "# --- END PINS ---"

# The union set, matching requirements-colab.txt. torch is absent on purpose:
# Colab preinstalls 2.11.0 built for its own driver.
PACKAGES = [
    "spatialdata", "spatialdata-io", "spatialdata-plot", "squidpy", "sopa",
    "scanpy", "netgraph", "huggingface_hub", "gdown", "tifffile",
    "imagecodecs", "seaborn",
]


def pin_block() -> str:
    """The constraint lines only -- comments and blanks stripped."""
    lines = []
    for raw in CONSTRAINTS.read_text().splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            lines.append(line)
    return "\n".join(lines)


def install_cell() -> str:
    pins = pin_block()
    pkgs = "\n".join(f'    "{p}",' for p in PACKAGES)
    return f'''# ============================================================================
# Step 1 of 4  --  install the software the Workshop uses
# ----------------------------------------------------------------------------
# This usually takes under a minute. Colab wipes everything you install when a
# session ends, so you will run a cell like this again at the start of each
# Tutorial on the day. That is expected, not a mistake.
#
# You do not need to read or understand anything below. Just run the cell.
# ============================================================================
import importlib
import pathlib
import subprocess
import sys
import time

IN_COLAB = "google.colab" in sys.modules

# Exact versions we have tested together. Pinning them means everyone in the
# room is running the same software, so a problem on your screen is a problem
# we can reproduce on ours.
{PIN_START}
PINS = """\\
{pins}
"""
{PIN_END}

PACKAGES = [
{pkgs}
]

# Packages Colab has already loaded into memory before you ran anything. If the
# install replaces one of these on disk, Python keeps using the old copy and
# things break in confusing ways later. We check for that at the end.
WATCH = ["numpy", "pandas", "scipy", "matplotlib", "sklearn", "PIL", "numba"]
DIST = {{"sklearn": "scikit-learn", "PIL": "pillow"}}


def _version(mod):
    from importlib.metadata import PackageNotFoundError, version
    try:
        return version(DIST.get(mod, mod))
    except PackageNotFoundError:
        return None


def _run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout[-1500:])
        print(result.stderr[-1500:])
    return result.returncode


started = time.time()
preloaded = {{m: _version(m) for m in WATCH if m in sys.modules}}
INSTALL_OK = True

if IN_COLAB:
    constraints = pathlib.Path("/content/constraints-colab.txt")
    constraints.write_text(PINS)

    # uv is a much faster drop-in for pip. Installing uv itself costs a couple
    # of seconds and saves roughly half a minute, which matters when forty
    # people install at once on conference wifi. If anything about it goes
    # wrong we fall straight back to pip.
    rc = _run([sys.executable, "-m", "pip", "install", "-q", "uv"])
    if rc == 0:
        rc = _run([sys.executable, "-m", "uv", "pip", "install", "--system", "-q",
                   "-c", str(constraints), *PACKAGES])
    if rc != 0:
        print("Falling back to pip (this is slower but works just as well)...")
        rc = _run([sys.executable, "-m", "pip", "install", "-q",
                   "-c", str(constraints), *PACKAGES])
    INSTALL_OK = rc == 0
    importlib.invalidate_caches()
else:
    print("Not running in Google Colab, so nothing was installed.")
    print("This is the expected path when we test the notebook ourselves.")

# Did the install replace a package Python had already loaded?
STALE = [m for m, before in preloaded.items()
         if before is not None and _version(m) != before]

print(f"\\nStep 1 finished in {{time.time() - started:.0f}} seconds.")
if not INSTALL_OK:
    print("The install reported an error. Keep going -- the checks below will")
    print("tell us exactly what is missing, and that is what we need from you.")
if STALE:
    print()
    print("=" * 70)
    print("PLEASE RESTART THE SESSION, THEN RUN THIS NOTEBOOK AGAIN FROM THE TOP.")
    print("Use the menu: Runtime -> Restart session.")
    print("Reason: these were updated while Python was already using them:")
    print("  " + ", ".join(STALE))
    print("Restarting takes a few seconds and is completely normal.")
    print("=" * 70)
'''


def cells():
    md = nbf.v4.new_markdown_cell
    code = nbf.v4.new_code_cell
    return [
        md(
            "# Setup check -- please run this before the Workshop\n"
            "\n"
            "This short notebook checks that your Google Colab session can run the "
            "ASI-FIMSA spatial-omics Tutorials. It installs the software we use, "
            "downloads one tiny test file, and draws one small figure. It takes "
            "about two minutes and it changes nothing on your own computer.\n"
            "\n"
            "**What to do:** click *Runtime -> Run all* in the menu, then wait. "
            "The last cell tells you either that you are ready, or exactly what to "
            "send us.\n"
            "\n"
            "**You do not need a graphics card (GPU).** Everything in the Workshop "
            "runs on an ordinary free Colab session. One Tutorial trains a small "
            "neural network, and it is a few minutes faster with a GPU, but it is "
            "designed to finish comfortably without one.\n"
            "\n"
            "**If something goes wrong, nothing is broken.** Colab sessions are "
            "disposable. You can always close the tab, open the notebook again and "
            "start over."
        ),
        code(install_cell()),
        md(
            "## Step 2 -- check the software loaded correctly\n"
            "\n"
            "The next cell imports each package and prints its version, then reports "
            "your Python version and whether this session happens to have a GPU. "
            "A row marked `MISSING` is the useful kind of failure: it tells us "
            "precisely what did not install."
        ),
        code(setup_check_cell()),
        md(
            "## Step 3 -- check this session can reach the Workshop data\n"
            "\n"
            "The Tutorials download prepared datasets while they run, so your Colab "
            "session needs to be able to reach the internet. This downloads one very "
            "small file to prove it can.\n"
            "\n"
            "The Workshop dataset is still being uploaded, so it is completely normal "
            "for the first attempt below to say it cannot find it. In that case we "
            "fall back to a small public file, which tests the same thing."
        ),
        code(connectivity_cell()),
        code(figure_cell()),
        md(
            "## Step 4 -- the verdict\n"
            "\n"
            "Run the last cell. It collects the results of everything above into one "
            "answer."
        ),
        code(verdict_cell()),
    ]


def setup_check_cell() -> str:
    return '''# ============================================================================
# Step 2 of 4  --  what is installed, what Python we have, and is there a GPU
# ============================================================================
import platform
import sys
from importlib.metadata import PackageNotFoundError, version

# import name -> the name it is installed under, where they differ
CHECKS = [
    ("numpy", "numpy"), ("pandas", "pandas"), ("scipy", "scipy"),
    ("matplotlib", "matplotlib"), ("skimage", "scikit-image"),
    ("anndata", "anndata"), ("scanpy", "scanpy"), ("squidpy", "squidpy"),
    ("spatialdata", "spatialdata"), ("spatialdata_io", "spatialdata-io"),
    ("spatialdata_plot", "spatialdata-plot"), ("sopa", "sopa"),
    ("netgraph", "netgraph"), ("zarr", "zarr"), ("dask", "dask"),
    ("tifffile", "tifffile"), ("imagecodecs", "imagecodecs"),
    ("seaborn", "seaborn"), ("huggingface_hub", "huggingface_hub"),
    ("gdown", "gdown"), ("torch", "torch"),
]

print(f"Python {platform.python_version()}")
print()
print("{:<22}{:<16}{}".format("package", "version", "status"))
print("-" * 52)

MISSING = []
for import_name, dist_name in CHECKS:
    try:
        __import__(import_name)
        try:
            found = version(dist_name)
        except PackageNotFoundError:
            found = "installed"
        status = "ok"
    except Exception as exc:                      # noqa: BLE001
        found, status = "-", f"MISSING ({type(exc).__name__})"
        MISSING.append(dist_name)
    print(f"{dist_name:<22}{found:<16}{status}")

# numpy is the one version we care about exactly. Colab ships 2.0.2 and loads it
# before your first cell runs, so anything that quietly upgrades it forces a
# session restart in the middle of a Tutorial. If this line disagrees, tell us.
import numpy
NUMPY_OK = numpy.__version__ == "2.0.2"
print()
print(f"numpy is {numpy.__version__}"
      + ("" if NUMPY_OK else "  <-- we expected 2.0.2; please mention this to us"))

# A GPU is a bonus, never a requirement.
try:
    import torch
    HAS_GPU = torch.cuda.is_available()
    GPU_NAME = torch.cuda.get_device_name(0) if HAS_GPU else None
except Exception:                                 # noqa: BLE001
    HAS_GPU, GPU_NAME = False, None

print()
if HAS_GPU:
    print(f"GPU: yes ({GPU_NAME}). The neural-network Tutorial will run faster.")
else:
    print("GPU: no. That is completely fine -- everything is built to run without one.")
    print("If you would like one anyway: Runtime -> Change runtime type -> T4 GPU.")

IMPORTS_OK = not MISSING
print()
print("Step 2:", "all packages loaded" if IMPORTS_OK
      else f"{len(MISSING)} package(s) missing: {', '.join(MISSING)}")
'''


def connectivity_cell() -> str:
    return '''# ============================================================================
# Step 3 of 4  --  can this session download data?
# ============================================================================
from huggingface_hub import hf_hub_download

WORKSHOP_REPO = "xiao233333/asi-fimsa-workshop-2026"
DOWNLOAD_OK = False
downloaded_from = None

try:
    path = hf_hub_download(repo_id=WORKSHOP_REPO, filename="README.md",
                           repo_type="dataset")
    DOWNLOAD_OK, downloaded_from = True, "the Workshop dataset"
    print(f"Downloaded a file from {WORKSHOP_REPO}.")
except Exception as exc:                          # noqa: BLE001
    # Expected until the Workshop dataset is published. Deliberately no
    # traceback: a wall of red text reads like something you did wrong.
    print(f"Could not reach {WORKSHOP_REPO} yet ({type(exc).__name__}).")
    print("That is expected before the Workshop -- the dataset is still being")
    print("uploaded. Trying a small public file instead, which tests the same")
    print("thing: whether this session can download data at all.")
    try:
        path = hf_hub_download(repo_id="bert-base-uncased", filename="config.json")
        DOWNLOAD_OK, downloaded_from = True, "a public test file"
        print("That worked.")
    except Exception as exc2:                     # noqa: BLE001
        print(f"That did not work either ({type(exc2).__name__}: {exc2}).")
        print("This usually means a firewall or proxy is blocking the session.")
        print("Trying again on a different network often fixes it.")

if DOWNLOAD_OK:
    import os
    print(f"\\nStep 3: downloads work ({downloaded_from}, "
          f"{os.path.getsize(path)} bytes).")
else:
    print("\\nStep 3: downloads are blocked. Please tell us -- see the last cell.")
'''


def figure_cell() -> str:
    return '''# ============================================================================
# Step 3b  --  can this session draw a figure?
# ============================================================================
# Most of the Workshop is looking at pictures of tissue, so a session that
# cannot draw is a session that cannot follow along.
import matplotlib.pyplot as plt
import numpy as np

PLOT_OK = False
try:
    rng = np.random.default_rng(0)
    centres = np.array([[2.0, 2.0], [8.0, 3.0], [5.0, 8.0]])
    which = rng.integers(0, 3, 400)
    xy = centres[which] + rng.normal(0, 0.9, size=(400, 2))

    fig, ax = plt.subplots(figsize=(4, 4))
    ax.scatter(xy[:, 0], xy[:, 1], c=which, cmap="viridis", s=14, edgecolor="none")
    ax.set_title("If you can see three blobs, plotting works")
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_aspect("equal")
    plt.show()
    PLOT_OK = True
except Exception as exc:                          # noqa: BLE001
    print(f"Plotting failed ({type(exc).__name__}: {exc})")

print("Step 3b:", "figure drawn" if PLOT_OK else "figure FAILED")
'''


def verdict_cell() -> str:
    return '''# ============================================================================
# Step 4 of 4  --  are you ready?
# ============================================================================
checks = {
    "software installed": IMPORTS_OK,
    "numpy is the expected version": NUMPY_OK,
    "downloads work": DOWNLOAD_OK,
    "figures draw": PLOT_OK,
}

print("=" * 70)
for label, passed in checks.items():
    print(f"  {'PASS' if passed else 'FAIL'}   {label}")
print("=" * 70)
print()

if all(checks.values()):
    print("YOU ARE READY.")
    print()
    print("Nothing else to do before the Workshop. You do not need to keep this")
    print("session open -- each Tutorial installs what it needs when you open it.")
    if not HAS_GPU:
        print()
        print("You have no GPU, and that is fine. Everything is built to run without one.")
else:
    failed = [label for label, passed in checks.items() if not passed]
    print("NOT READY YET -- and this is usually quick for us to fix.")
    print()
    print("Please email us BEFORE the Workshop with:")
    print("  1. Which lines above say FAIL:")
    for label in failed:
        print(f"       - {label}")
    print("  2. A screenshot of this whole notebook, or the text of any red error.")
    print("  3. Your Python version, printed in Step 2 above:")
    import platform
    print(f"       Python {platform.python_version()}")
    print()
    print("Things worth trying yourself first, in order:")
    print("  a. Runtime -> Restart session, then Runtime -> Run all.")
    print("  b. Open the notebook again in a brand-new Colab session.")
    print("  c. Try a different network (a phone hotspot rules out a firewall).")
    print()
    print("Please do not spend more than ten minutes on this. Send us the")
    print("screenshot and we will sort it out on the day.")
'''


def build():
    nb = nbf.v4.new_notebook()
    nb.cells = cells()
    nb.metadata = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.12"},
        "colab": {"provenance": [], "toc_visible": True},
    }
    # No stored outputs, no execution counts: the notebook is source, and a
    # Participant should see it run in their own session, not ours.
    for cell in nb.cells:
        if cell.cell_type == "code":
            cell.outputs = []
            cell.execution_count = None
    return nb


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="fail if the notebook on disk is stale")
    args = ap.parse_args()

    nb = build()
    if args.check:
        if not NOTEBOOK.exists():
            print(f"{NOTEBOOK} does not exist -- run this script without --check")
            return 1
        current = nbf.read(NOTEBOOK, as_version=4)
        want = [c.source for c in nb.cells]
        have = [c.source for c in current.cells]
        if want == have:
            print(f"{NOTEBOOK.name} is up to date with constraints-colab.txt")
            return 0
        print(f"{NOTEBOOK.name} is STALE relative to constraints-colab.txt")
        for i, (a, b) in enumerate(zip(want, have)):
            if a != b:
                print(f"  cell {i} differs")
        if len(want) != len(have):
            print(f"  cell count {len(have)} on disk vs {len(want)} generated")
        print("Regenerate with: python verify/build_setup_check.py")
        return 1

    NOTEBOOK.parent.mkdir(parents=True, exist_ok=True)
    nbf.write(nb, NOTEBOOK)
    print(f"wrote {NOTEBOOK}  ({len(nb.cells)} cells, "
          f"{sum(c.cell_type == 'code' for c in nb.cells)} code)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
