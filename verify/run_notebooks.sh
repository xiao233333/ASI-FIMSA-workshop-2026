#!/bin/bash
# Execute the Workshop notebooks headlessly and report PASS/FAIL per notebook.
#
# Adapted from the parent course's scripts/run_all_notebooks.slurm -- the same
# nbconvert loop and thread/cache hygiene, with the Apptainer, Slurm and R-kernel
# machinery dropped. These notebooks are meant to run in Colab, so the closest
# honest local check is a plain venv with the pinned stack, not a container.
#
# Usage
#   bash verify/run_notebooks.sh                       # every notebook, in order
#   bash verify/run_notebooks.sh notebooks/00_setup_check.ipynb
#   COLAB312_VENV=/other/venv bash verify/run_notebooks.sh
#   VERIFY_OUT=/somewhere/else bash verify/run_notebooks.sh
#
# Environment
#   COLAB312_VENV   verification venv        (default /scratch/project_mnt/S0010/Xiao/envs/colab312)
#   VERIFY_OUT      output directory         (default <repo>/verify/output)
#   VERIFY_THREADS  BLAS/OMP/numba threads   (default 4)
#   WORKSHOP_NOTEBOOKS  space- or newline-separated notebook list, overridden by argv
#
# Exits non-zero if any notebook raised in any cell.
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${COLAB312_VENV:-/scratch/project_mnt/S0010/Xiao/envs/colab312}"
OUT="${VERIFY_OUT:-$REPO/verify/output}"
THREADS="${VERIFY_THREADS:-4}"

if [ ! -x "$VENV/bin/python" ]; then
  echo "No verification venv at $VENV -- build it with: bash verify/make_env.sh" >&2
  exit 2
fi

# Notebook list: argv wins, then $WORKSHOP_NOTEBOOKS, then every notebook in the
# repo in filename order (the 00/01/02/03 prefixes are the teaching order).
if [ "$#" -gt 0 ]; then
  NOTEBOOKS=("$@")
elif [ -n "${WORKSHOP_NOTEBOOKS:-}" ]; then
  read -r -a NOTEBOOKS <<< "$WORKSHOP_NOTEBOOKS"
else
  # LC_ALL=C on purpose. Under a UTF-8 locale, sort ignores punctuation in the
  # primary comparison, so a suffixed notebook name can sort ahead of the plain
  # one at the same number and the run order stops matching the teaching order.
  # Byte order puts '_' (0x5F) first, which is what the numbering means.
  mapfile -t NOTEBOOKS < <(find "$REPO/notebooks" -maxdepth 1 -name '*.ipynb' \
                             -not -name '*-checkpoint.ipynb' | LC_ALL=C sort)
fi
if [ "${#NOTEBOOKS[@]}" -eq 0 ]; then
  echo "No notebooks found under $REPO/notebooks" >&2
  exit 2
fi

# Everything scratch-like goes under $TMPDIR, which on Bunya is
# /scratch/temp/$SLURM_JOB_ID and is cleaned up with the job. Nothing here is
# allowed to write into $HOME: it has ~2 GB free and a numba or matplotlib cache
# will silently fill it.
export TMPDIR="${TMPDIR:-/scratch/temp/${SLURM_JOB_ID:-$USER-manual}}"
export XDG_CACHE_HOME="$TMPDIR/.cache"
export MPLCONFIGDIR="$TMPDIR/.cache/matplotlib"
export NUMBA_CACHE_DIR="$TMPDIR/.cache/numba"
export JUPYTER_RUNTIME_DIR="$TMPDIR/jupyter-runtime"
export JUPYTER_DATA_DIR="$TMPDIR/jupyter-data"
# huggingface_hub and torch ignore XDG_CACHE_HOME and default to $HOME/.cache.
# A single Staged dataset would exhaust the ~2 GB free there, so redirect both.
export HF_HOME="$TMPDIR/.cache/huggingface"
export TORCH_HOME="$TMPDIR/.cache/torch"
mkdir -p "$XDG_CACHE_HOME" "$MPLCONFIGDIR" "$NUMBA_CACHE_DIR" \
         "$JUPYTER_RUNTIME_DIR" "$JUPYTER_DATA_DIR" "$HF_HOME" "$TORCH_HOME" "$OUT"

# Resolve the kernelspec from the venv, not from ~/.local/share/jupyter. A stale
# kernelspec named python3 in $HOME would otherwise win and execute every
# notebook against some other interpreter, which looks like a pass until an
# import fails for reasons that make no sense.
export JUPYTER_PATH="$VENV/share/jupyter"
export PATH="$VENV/bin:$PATH"

# Keep BLAS/OMP/numba modest. scanpy, squidpy and sopa each spawn their own
# workers; left alone they oversubscribe the node and the notebooks get slower,
# not faster.
export OMP_NUM_THREADS="$THREADS"
export MKL_NUM_THREADS="$THREADS"
export OPENBLAS_NUM_THREADS="$THREADS"
export NUMEXPR_NUM_THREADS="$THREADS"
export NUMBA_NUM_THREADS="$THREADS"

# NOT Agg. Agg is headless-safe but it makes plt.show() a no-op, so the executed
# notebook comes back with no image/png outputs and check_outputs.py cannot tell
# a working figure from a silently blank one. The inline backend is what Colab
# itself uses and it embeds the PNGs we need to inspect.
export MPLBACKEND="module://matplotlib_inline.backend_inline"

echo "==================================================================="
echo "venv:    $VENV  ($("$VENV/bin/python" -V 2>&1))"
echo "host:    $(hostname)    start: $(date)"
echo "output:  $OUT"
echo "threads: $THREADS    MPLBACKEND=$MPLBACKEND"
echo "notebooks: ${#NOTEBOOKS[@]}"

declare -a RESULTS
TIMINGS="$OUT/timings.tsv"
: > "$TIMINGS"

for nb in "${NOTEBOOKS[@]}"; do
  # Accept both absolute paths and paths relative to the repo root.
  [ -f "$nb" ] || nb="$REPO/$nb"
  if [ ! -f "$nb" ]; then
    echo ">> MISSING $nb"
    RESULTS+=("FAIL  $(basename "$nb")  (not found)")
    continue
  fi
  base="$(basename "$nb" .ipynb)"
  log="$OUT/$base.log"
  echo "==================================================================="
  echo ">> $base"

  # nbconvert starts the kernel in the INPUT notebook's directory and ignores
  # the shell's cwd, so executing notebooks/*.ipynb in place lets a Tutorial
  # download its dataset straight into the repo -- Tutorial 3 drops ~47 MB of
  # Visium data that way. Copy each notebook into a scratch workdir first and
  # execute the copy: the kernel's cwd is then that workdir, which is where the
  # downloads land, and the repo stays clean. The executed notebook is still
  # written to the top of $OUT so check_outputs.py finds it.
  work="$OUT/$base"
  mkdir -p "$work"
  cp -f "$nb" "$work/$base.ipynb"

  t0=$(date +%s)
  jupyter nbconvert --to notebook --execute \
      --ExecutePreprocessor.timeout=-1 \
      --ExecutePreprocessor.kernel_name=python3 \
      --output-dir "$OUT" \
      --output "$base.ipynb" \
      "$work/$base.ipynb" > "$log" 2>&1
  rc=$?
  t1=$(date +%s)
  secs=$(( t1 - t0 ))
  printf '%s\t%s\n' "$base" "$secs" >> "$TIMINGS"

  if [ $rc -eq 0 ]; then
    echo "   PASS  ${secs}s  -> $OUT/$base.ipynb"
    RESULTS+=("PASS  $base  ${secs}s")
  else
    echo "   FAIL (rc=$rc)  ${secs}s  -- full log: $log"
    tail -n 15 "$log" | sed 's/^/       /'
    RESULTS+=("FAIL  $base  ${secs}s")
  fi
done

echo "==================================================================="
echo "SUMMARY ($(date)):"
fail=0
for r in "${RESULTS[@]}"; do
  echo "  $r"
  [[ "$r" == FAIL* ]] && fail=$((fail+1))
done
echo
echo "Executed notebooks under: $OUT"
echo "Failures: $fail / ${#RESULTS[@]}"

# Cell-level check: nbconvert exits 0 on a notebook whose cells all "ran" but
# produced nothing, so the exit code alone is not enough evidence.
if [ $fail -eq 0 ]; then
  echo
  "$VENV/bin/python" "$REPO/verify/check_outputs.py" "$OUT"
  fail=$(( fail + $? ))
fi

exit $(( fail > 0 ))
