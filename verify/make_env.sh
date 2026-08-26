#!/bin/bash
# Rebuild the local Python 3.12 verification environment from the pin set.
#
#   bash verify/make_env.sh              # create/refresh the venv
#   COLAB312_VENV=/some/other/path bash verify/make_env.sh
#
# Why a venv and not a conda env: every environment under
# /home/uqxtan9/micromamba/envs is Python 3.11 or older, and spatialdata 0.8,
# scanpy 1.12.3 and squidpy 1.8.3 all require >=3.12. uv 0.5.31's newest
# CPython is 3.12.9, close enough to Colab's 3.12.13 for this purpose.
#
# Why /scratch/project_mnt and not $HOME: the env is ~2.3 GB and $HOME has
# roughly 2 GB free. Do not move this to $HOME.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${COLAB312_VENV:-/scratch/project_mnt/S0010/Xiao/envs/colab312}"
UV="${UV_BIN:-/home/uqxtan9/.local/bin/uv}"

# uv's default interpreter store is under $HOME, which has no room. UV_LINK_MODE
# is set to copy in the user profile on purpose -- the uv cache and these targets
# are on different filesystems -- so it is left alone here.
export UV_PYTHON_INSTALL_DIR="${UV_PYTHON_INSTALL_DIR:-/scratch/project_mnt/S0010/Xiao/uv-python}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-/scratch/project_mnt/S0010/Xiao/.cache/uv}"

echo "repo:   $REPO"
echo "venv:   $VENV"
echo "uv:     $($UV --version)"

mkdir -p "$UV_PYTHON_INSTALL_DIR" "$(dirname "$VENV")"
"$UV" python install 3.12
"$UV" venv --python 3.12 "$VENV"

cd "$REPO"

# The Colab-facing union set, held to the tested resolution.
"$UV" pip install --python "$VENV/bin/python" \
  -c constraints-colab.txt -r requirements-colab.txt

# Local-only extras: a kernel to execute with, and the torch Colab preinstalls.
# The CPU index keeps torch to ~200 MB instead of dragging in the CUDA stack.
"$UV" pip install --python "$VENV/bin/python" \
  --extra-index-url https://download.pytorch.org/whl/cpu \
  --index-strategy unsafe-best-match \
  -c constraints-colab.txt -r verify/requirements-verify.txt

# nbconvert resolves --ExecutePreprocessor.kernel_name=python3 through the
# kernelspec search path. Registering into the venv's own share/jupyter keeps it
# self-contained; run_notebooks.sh then points JUPYTER_PATH at it so a stale
# kernelspec in ~/.local/share/jupyter cannot shadow it and silently execute the
# notebooks against a different interpreter.
"$VENV/bin/python" -m ipykernel install --prefix "$VENV" \
  --name python3 --display-name "Python 3 (colab312)"

echo
echo "--- installed ---"
"$VENV/bin/python" - <<'PY'
import sys
from importlib.metadata import version
print("python", sys.version.split()[0])
for p in ["numpy","torch","scanpy","squidpy","spatialdata","spatialdata-io",
          "spatialdata-plot","sopa","netgraph","anndata","zarr","dask",
          "imagecodecs","tifffile","huggingface-hub","gdown",
          "liana","mudata","plotnine"]:
    print(f"  {p:20s} {version(p)}")
assert version("numpy") == "2.0.2", "numpy drifted off the Colab pin"
print("\nnumpy holds at 2.0.2")

# Tutorial 3's dependency, checked at build time rather than discovered in the
# room: that liana imports under the numpy hold and its resource actually loads.
import liana
res = liana.rs.select_resource("consensus")
print(f"liana {version('liana')}: consensus resource loads, {len(res):,} interactions")
PY
echo
echo "Done. Verify notebooks with:  bash verify/run_notebooks.sh"
