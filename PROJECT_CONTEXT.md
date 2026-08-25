# Project Overview

`ASI_FIMSA_workshop` holds the material for a two-hour hands-on spatial-omics session at
the ASI-FIMSA meeting, delivered as three Google Colab notebooks plus a setup check.
The audience is immunologists with minimal Python. Material is deliberately
over-authored and trimmed to the slot before delivery.

Vocabulary is defined in `CONTEXT.md`; the three decisions that shape everything else
are in `docs/adr/`.

# Current Goal / Focus

Build the four notebooks and the `prep/` scripts that produce their Staged datasets.
Nothing is built yet — the design was settled in a grilling session on 2026-08-25.

# Scientific / Analysis Context

One disease, human breast carcinoma, seen three ways. NOTE: these are three DIFFERENT
FFPE specimens, not serial sections of one block — matched by disease and preservation,
not by tissue. Say "one disease, three technologies", never "the same tissue"; a difference
between two panels can be a difference between two tumours:

- **Visium** `V1_Breast_Cancer_Block_A_Section_1` — 55 µm spots, whole transcriptome
- **Xenium** public 10x human breast, 313-gene pre-designed panel — single cell, targeted
- **Atera** whole-transcriptome Xenium (`chemistry_version: "Atera v1"`, 18,028 targets,
  170,057 cells, Gen2 prototype) — single cell, whole transcriptome

Immunology lands through the tumour microenvironment: Tutorial 2's niches are immune
infiltration, tumour boundary and stroma; Tutorial 3's per-gene accuracy chart shows
stromal/epithelial genes predicting well from morphology and sparse immune markers
(`PTPRC`, `CD3D`, `CD68`, `MS4A1`) not — a real limitation worth discussing.

The three Tutorials:

1. **Read and visualise** — `visium_sge()` download+read, `spatialdata_io.xenium()` on a
   small public bundle, Atera as a prepared `.zarr` Crop.
2. **Niche analysis** — squidpy `spatial_neighbors` + `nhood_enrichment` → neighbourhood
   composition kNN + KMeans (derived from the parent course's `3.2_neighborhood.ipynb`)
   → sopa `vectorize_niches` / `niches_geometry_stats` / `cells_to_groups`. Runs on the
   Atera Crop (~20–30k cells), not the full slide.
3. **ViT for gene expression** — from-scratch Vision Transformer on per-spot H&E tiles
   from the Visium sample, regressing 16 breast/immune markers, with attention rollout.
   Derived from the parent course's `Deep_learning_04_vit_HE_spatial.ipynb`.

# Tech Stack

- Google Colab, Python 3.12 (2026.07 runtime: numpy 2.0.2, torch 2.11.0 preinstalled)
- `spatialdata` 0.8.x + `spatialdata-io` 0.7.x + `spatialdata-plot` 0.4.x + `squidpy`
  1.8.x + `sopa` 2.2.x + `scanpy` 1.12.x — bumped together, see ADR-0003
- Pin set: `constraints-colab.txt` (two-tier — exact pins for the stack and every
  compatibility-critical transitive; floors only for what Colab already ships, so pip does
  not replace working preinstalled copies). `requirements-colab.txt` is the union set.
- Verification venv: `/scratch/project_mnt/S0010/Xiao/envs/colab312` (Python 3.12.9),
  rebuildable with `bash verify/make_env.sh`; run notebooks with `bash verify/run_notebooks.sh`
  then `python verify/check_outputs.py`
- Install with `uv pip install --system`, not pip — measured ~5x faster (union set 7.9 s vs
  45.4 s cold against a simulated Colab base)
- Python only, no R — see ADR-0002
- CPU-first; Tutorial 3 uses CUDA opportunistically via
  `device = "cuda" if torch.cuda.is_available() else "cpu"`
- Prep scripts run on Bunya against RDM

# Key Input and Output Paths

- Atera raw bundle (RDM): `/QRISdata/Q1851/Xiao/Atera_dataset/BreastCancer/RAW/WTA_Preview_FFPE_Breast_Cancer`
  (~65 G; H&E 17.7 G, `morphology.ome.tif` 14.8 G, `transcripts.parquet` 10 G)
- Atera aligned/processed (RDM): `.../BreastCancer/PROCESSED/WTA_Preview_FFPE_Breast_Cancer`
  (~29 G; `xenium_HE_aligned/`, `he_sections/`, `qc/`)
- Staged datasets: Hugging Face dataset repo `xiao233333/asi-fimsa-workshop-2026`,
  fetched in Colab with `hf_hub_download` (primary — CDN-backed, no download quota).
  Google Drive `ASI-FIMSA-workshop-2026` (`1ELxQjcswMcO7w4N6Z74u_2Yt3F5UWHbm`) is kept as
  a mirror and `gdown` fallback. Drive is not primary because its per-file download quota
  trips under the load pattern of a whole room fetching at once.
- Parent course material: `/scratch/user/uqxtan9/analysis_project/gml-teaching-2026`
- Notebooks: `notebooks/`; dataset builders: `prep/`; pin set: `requirements-colab.txt`
- Prep pipeline (Bunya only, never Colab): `prep/config.py` + `prep/atera_io.py` shared by
  `00_extract_analysis.py` -> `01_annotate_clusters.py` -> `02_pick_crop.py` ->
  `03_build_wholeslide.py` -> `04_build_crop.py`
- Two human sign-off gates, both committed: `prep/atera_cluster_annotation.csv`
  (34 vendor clusters -> named cell types) and `prep/crop_window.json` (the Crop)
- Vendored helper: `notebooks/voronoi.py` (from the parent course, patched — see Known issues)

# Conventions that are easy to get wrong

- **Always work in the ALIGNED Atera frame** (`PROCESSED/.../xenium_HE_aligned/`), never RAW.
  RAW is Xenium instrument space at 0.2125 um/px; aligned is H&E space at 0.27377667386671845
  um/px and is rotated ~90 degrees. The VALIS transform was never saved, so the two frames are
  **not interconvertible** — mixing them silently misplaces every cell. The aligned frame is
  also the only one where the H&E lines up. Pixel size is absent from the TIFF tags; take it
  from `qc/align_meta.json`.
- The 10x clustering CSVs have 170,045 rows against 170,057 cells — **join on `Barcode`**,
  never positionally.
- `cell_feature_matrix.h5` is CSC with shape `[features, cells]` — transpose for AnnData.

# Known issues

- **Installing the stack upgrades `pandas`** (2.2.x -> 2.3.x; `scanpy` 1.12.3 requires
  `>=2.3`), and Colab imports pandas at startup — so a Participant may be told to restart the
  runtime. Every install cell must snapshot `sys.modules` and print a restart banner if a
  watched module's version changed. See ADR-0003. Only three packages are replaced in total
  (pandas, tifffile, gdown); numpy and torch are left alone.

- **`sd.read_zarr()` cannot open a `.zarr.zip` in place** on spatialdata 0.7.3 — a Tutorial
  must unzip the Crop first. `_resolve_zarr_store` handles only LocalStore/FsspecStore and
  then wants `store.root`, which ZipStore lacks. Re-test on the 0.8.x Colab pins; the
  incantation is in `prep/README.md` and in the object's own `attrs["read_instructions"]`.
- **B cells are not resolved as their own cluster.** 9.75% of cells detect at least one of
  MS4A1/CD79A/CD79B/BANK1, but they sit inside cluster 11 (labelled T cell, 22% positive for
  any of the four) rather than forming their own. Genuinely uncommon here AND unresolved by
  graphclust at k=34. No label was forced; all four genes are in the shipped 69-gene panel so
  a Participant can re-ask the question. This is teaching material, not a defect.

- **NumPy 2.0 removed APIs are a live hazard.** Colab ships numpy 2.0.2, where
  `ndarray.ptp()` no longer exists. This bit twice in unrelated code inherited from the
  parent course (`voronoi.py`, and a coordinate assertion in the ViT Tutorial) and only
  surfaced on execution. Grep new code for `.ptp()`, `.newbyteorder()`, `np.float_`,
  `np.NaN`, `np.in1d` before trusting it.
- `gdown` 6.x **removed the `--fuzzy` flag** (it is the default now). Any snippet copied from
  older tutorials that passes `--fuzzy` will fail with "unrecognized arguments". No notebook
  here uses it.

# Change Log

- 2026-08-25: Design settled by grilling session. Established the Workshop glossary
  (`CONTEXT.md`) and ADRs 0001–0003. Key decisions: rewrite rather than fork
  `gml-teaching-2026`; public 10x data plus the Atera preview bundle; matched-disease
  breast carcinoma across all three Tutorials; Python-only; Staged datasets in Google Drive
  as trimmed artifacts rather than raw bundles; from-scratch ViT rather than a
  pretrained backbone.
- 2026-08-25: Build started. Repo scaffolded (README, .gitignore, branch renamed to
  `main`, first commit). Staging host settled on Hugging Face with Drive as mirror.
  Atera confirmed as the public 10x preview dataset, 170,057 cells x 18,028 genes; its
  redistribution licence is reported CC BY 4.0 but is NOT yet verified first-hand, so no
  Atera-derived artifact may be published until it is.
- 2026-08-25: Tutorial 3 (ViT) built and verified end to end on CPU — 3,798 spots, tiles
  (3798, 64, 64, 3), 118,160 parameters, 203 s wall, final mean Pearson r 0.325. The crop
  window is derived from the sample's own scalefactors (`spot_diameter_fullres` x
  `tissue_hires_scalef` x 2.2 ~= 32 px), not the parent course's hard-coded 40, which was
  tuned for a different sample. Per-gene accuracy confirms the intended teaching point:
  stromal/epithelial genes (DCN 0.48, KRT8 0.46, COL1A1 0.44) predict from morphology while
  every immune marker (PTPRC 0.31, CD68 0.30, CD3D 0.25, MS4A1 0.19) ranks last.
- 2026-08-25: Crop selected in the aligned frame — 2000 um square at (3000, 9000) um,
  **16,006 cells across all 12 cell types**, 43% tumour / 7% proliferating tumour /
  10% fibroblast / 10% T cell / 6% dendritic cell / 3% macrophage. Chosen by maximum cell
  count subject to a Shannon-entropy floor on composition. The densest window on the slide
  holds 20,779 cells but at entropy 0.54 and is solid tumour — the floor rejected it, which
  is the point. Density and diversity anti-correlate here, so the Crop is smaller than the
  20-30k first estimated; smaller is also faster in Colab.
- 2026-08-25: Staged datasets built and verified (published later the same day, see below):
  `atera_wholeslide_cells.h5ad` **19.9 MB** and `atera_crop.zarr.zip` **18.0 MB**, both at
  `/scratch/project_mnt/S0010/Xiao/asi_fimsa_workshop/staged/`. Round trip confirmed:
  `he` (3, 1826, 1826), `he_zoom` (3, 1096, 1096), 16,006 polygons, table (16006, 69), one
  `"global"` coordinate system, polygon centroids matching `obsm['spatial']` to 0.00 um.
  The 34 vendor clusters resolve to 12 named types plus Unassigned; 14 of 34 are marked
  `low_confidence`. Total Participant download is now ~110 MB, not the ~300 MB planned.
- 2026-08-25: **Atera licence confirmed CC BY 4.0** and the Staged datasets published to
  `https://huggingface.co/datasets/xiao233333/asi-fimsa-workshop-2026` with a dataset card
  carrying the required attribution, the derivation, and the caveats. Round-tripped from the
  public URL: both artifacts download with matching sha256 (10.2 s and 4.2 s). `DATA_LICENCE.md`
  records sources and attribution for all three datasets. Drive mirror still pending.
- 2026-08-25: Code licensed **MIT** (`LICENSE`), with one documented exception —
  `voronoi_finite_polygons_2d()` in `notebooks/voronoi.py` derives from a 2013 Stack
  Overflow answer and is CC BY-SA 3.0, a copyleft licence that cannot be absorbed into MIT.
  The carve-out is recorded in `LICENSE`, in the module docstring, and in the README.
- 2026-08-25: Rebuilt the Crop to fix mixed geometry. `shapely.make_valid()` in
  `prep/04_build_crop.py` could turn a self-intersecting cell boundary into a MultiPolygon
  or GeometryCollection (45 of 16,006 cells), and a mixed-geometry GeoDataFrame breaks
  `spatialdata-plot`'s default datashader path with "Geometry type combination is not
  supported" — i.e. the obvious `render_shapes("cell_boundaries", color="cell_type")` call
  in two Tutorials. Each repaired cell is now reduced to its largest constituent polygon
  (0.013% of total cell area discarded). Published Crop is all-Polygon and the default
  render path is verified working. `voronoi.py` is now also shipped in the Hugging Face
  dataset repo, so the Tutorials do not depend on the GitHub repo existing to fetch it.
- 2026-08-25: All four Tutorials built and passing the headless suite in the Colab-target
  venv — 0 errors, 32 figures, 3m50s total (00 11.9s, 01 43.3s, 02 21.3s, 03 124.3s, whose
  single slowest cell is the 104s ViT training loop). The riskiest design bet paid off:
  `spatialdata_io.xenium()` accepts a 182-byte placeholder `cells.zarr.zip` for bundles
  declaring analysis_sw_version < 1.3.0, so Tutorial 1 runs the real reader on the real 10x
  vendor directory for 33 MB instead of the 9.86 GB bundle.
- 2026-08-25: Corrected a factual claim in public docs. The three datasets are three
  DIFFERENT FFPE breast-carcinoma specimens, not serial sections of one block — README and
  this file said "one tissue". Framing is now "one disease, three technologies".
- 2026-08-25: `sopa.spatial.prepare_network` returns a square adjacency DataFrame that
  `netgraph.Graph()` rejects; convert with `networkx.from_pandas_adjacency` and threshold
  the edges (the raw graph is complete — 21 nodes, 210 edges — and unreadable). This only
  surfaced after netgraph was added to Tutorial 2's install line, because the cell had been
  written for the netgraph-absent path and its real branch had never executed.
- 2026-08-25: Google Drive mirror populated and verified. Both artifacts download
  **unauthenticated** via `gdown` with matching sha256, so link-sharing is inherited from the
  folder and a Participant's Colab session can reach them; per-file ids are recorded in
  `prep/manifest.json`. Hugging Face remains the primary origin. Note the rclone remote had
  `service_account_file` pointing at an OAuth client-secret JSON (`{"installed": ...}`)
  rather than a service-account key, which blocked the OAuth path until removed.
- 2026-08-25: Repo published at https://github.com/xiao233333/ASI-FIMSA-workshop-2026
  (public, default branch `main`). All four Colab badge targets resolve, as does
  `notebooks/voronoi.py`, which the Tutorials fetch at run time.
