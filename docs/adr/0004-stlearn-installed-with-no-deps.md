# stlearn is installed with --no-deps, against its declared numpy floor

Tutorial 02b runs [stLearn](https://stlearn.readthedocs.io/)'s spatially-constrained
ligand–receptor test. `stlearn==1.4.1` declares `numpy>=2.4.0`. `constraints-colab.txt`
pins `numpy==2.0.2`, because Colab preinstalls 2.0.2 and imports it before the first
cell runs, so moving numpy swaps files under a live kernel and forces a mid-Tutorial
session restart for a whole room (ADR-0003 records the same reasoning for pandas).

No stlearn release resolves against numpy 2.0.2: 1.4.x requires `numpy>=2.4.0`, 1.3.0
requires `numpy<2.0`, 1.2.2 requires `scikit-image<0.23`, and 1.1.x pins
`scipy==1.11.4`. The resolver cannot help. So 02b installs stlearn on its own with
dependency resolution switched off, and holds numpy where Colab put it:

    pip install -q -c constraints-colab.txt scanpy seaborn bokeh leidenalg
    pip install -q --no-deps stlearn

The alternative considered and rejected was a second pin set for this notebook alone,
resolved at `numpy==2.5.2` / `pandas==2.3.3` (which does resolve cleanly — stlearn
1.4.1, spatialdata 0.8.0 and scanpy 1.12.3 coexist there), plus `00_setup_check`'s
restart banner. It costs a Participant one forced restart and the Workshop a second pin
set to maintain and re-verify. It remains the documented fallback if the override below
ever stops holding.

## Why the override is safe enough here

`stlearn-1.4.1-py3-none-any.whl` is 217 KB of pure Python. Every third party it imports
at module level is already installed by the constrained line above except **bokeh** and
**leidenalg**, which are therefore named explicitly in `requirements-colab.txt` and
pinned in Section A of `constraints-colab.txt`, and **torchvision**, which Colab
preinstalls (`stlearn/pp.py` → `image_preprocessing.model_zoo` imports it
unconditionally for a feature extractor 02b never calls). `plotly`, `rpy2` and
`IPython` are imported inside functions only.

The numpy 2.4 floor appears to be conservative rather than load-bearing: the whole of
`st.tl.cci.run`, `st.tl.cci.run_cci` and every plotting function 02b uses was verified
to run correctly on numpy 2.0.2.

## Consequences

The guarantee is narrow and should be stated as such: **stlearn works on the code paths
`verify/run_notebooks.sh` executes end to end, and nothing wider.** A Participant who
takes stlearn somewhere else should resolve its dependencies properly.

`stlearn` must never be added to `constraints-colab.txt`. A constraint on a package
installed with `--no-deps` is never consulted, so the pin would be inert while reading
as a guarantee. It lives in its own file, `requirements-colab-stlearn.txt`, whose header
says it is only ever installed with `--no-deps`, and `verify/make_env.sh` builds the
verification venv the same way — including an `import stlearn` smoke test, so a missing
leaf dependency fails at env-build time rather than in the room.

Re-check the floor whenever stlearn is bumped. If a future release genuinely uses a
numpy ≥ 2.4 API, `import stlearn` or the CCI cells will fail in the verification run;
switch to the second-pin-set fallback above rather than pinning stlearn backwards.

## A separate wart, recorded here because it surfaced with this one

`st.tl.cci.run` calls `numba.set_num_threads(os.cpu_count())`. Where a process is capped
below the machine's core count — any Slurm job, any container with a CPU limit — that
overshoots numba's ceiling and raises `ValueError: The number of threads must be between
1 and N`. Colab is unaffected (both numbers are 2). Tutorial 02b reconciles the two
before importing stlearn, and says why in the notebook.
