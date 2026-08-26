# Project Overview

`ASI_FIMSA_workshop` holds the material for a two-hour hands-on spatial-omics session at
the ASI-FIMSA meeting, delivered as four Google Colab notebooks plus a setup check.
The audience is immunologists with minimal Python. Material is deliberately
over-authored and trimmed to the slot before delivery.

Vocabulary is defined in `CONTEXT.md`; the three decisions that shape everything else
are in `docs/adr/`.

# Current Goal / Focus

All five notebooks are built and passing the headless suite (00, 01, 02, 03, 04 -- 0 errors,
40 figures). Remaining before delivery: run every Tutorial once in a real free-tier Colab
session, which is the only test that proves the pin set survives contact with Colab's own
numpy and torch.

**The stLearn Tutorial was retired on 2026-08-26.** The cell-cell interaction slot is now
Tutorial 3, LIANA+ only. See the Change Log entry for what that removed.

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

The four Tutorials:

1. **Read and visualise** — `visium_sge()` download+read, `spatialdata_io.xenium()` on a
   small public bundle, Atera as a prepared `.zarr` Crop.
2. **Niche analysis** — squidpy `spatial_neighbors` + `nhood_enrichment` → neighbourhood
   composition kNN + KMeans (derived from the parent course's `3.2_neighborhood.ipynb`)
   → sopa `vectorize_niches` / `niches_geometry_stats` / `cells_to_groups`. Runs on the
   Atera Crop (~20–30k cells), not the full slide.
3. **Cell–cell interaction** (`03_cell_cell_interaction_liana`) — LIANA+ on the
   `atera_crop_lr.h5ad` cells: `rank_aggregate` consensus run twice (expression-only, then
   spatially weighted) as a measured A/B, plus `bivariate` per-cell local scores with Moran's
   R on the H&E. Opens on the panel argument: the 69-gene Crop supports a handful of literature
   LR pairs, the 1,673-gene panel supports thousands.
4. **ViT for gene expression** — from-scratch Vision Transformer on per-spot H&E tiles
   cut from the Visium sample's **full-resolution** H&E TIFF, regressing 16 breast/immune
   markers, with attention rollout.
   Derived from the parent course's `Deep_learning_04_vit_HE_spatial.ipynb`.

# Tech Stack

- Google Colab, Python 3.12 (2026.07 runtime: numpy 2.0.2, torch 2.11.0 preinstalled)
- `spatialdata` 0.8.x + `spatialdata-io` 0.7.x + `spatialdata-plot` 0.4.x + `squidpy`
  1.8.x + `sopa` 2.2.x + `scanpy` 1.12.x — bumped together, see ADR-0003
- Pin set: `constraints-colab.txt` (two-tier — exact pins for the stack and every
  compatibility-critical transitive; floors only for what Colab already ships, so pip does
  not replace working preinstalled copies). `requirements-colab.txt` is the union set.
- `liana` 1.9.0 for Tutorial 3, installed **normally**. It declares no numpy floor, so it
  resolves against the pin set with nothing switched off — verified 2026-08-26 with
  `uv pip compile -c constraints-colab.txt scanpy seaborn liana` → numpy 2.0.2, pandas 2.3.3.
  Pinned in `constraints-colab.txt`. Brings mudata + plotnine + mizani; the Tutorial uses none
  of them directly. **stlearn is no longer installed anywhere** — see ADR-0004, superseded.
- Verification venv: `/scratch/project_mnt/S0010/Xiao/envs/colab312-stlearn` (Python 3.12.9),
  rebuildable with `COLAB312_VENV=... bash verify/make_env.sh`; run notebooks with
  `bash verify/run_notebooks.sh` then `python verify/check_outputs.py`. The venv name is
  historical: it still carries a stlearn install, which nothing now uses.
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
  `03_build_wholeslide.py` -> `04_build_crop.py` -> `06_build_cci_table.py` ->
  `05_make_manifest.py`. **06 runs before 05** (05 must see every artifact) and after 04
  (06 takes its cell list from the built Crop rather than re-deriving the window).
- Two human sign-off gates, both committed: `prep/atera_cluster_annotation.csv`
  (34 vendor clusters -> named cell types) and `prep/crop_window.json` (the Crop).
  `prep/cci_panel_genes.txt` is committed too but is a generated record, not a gate.
- Vendored helper: `notebooks/voronoi.py` (from the parent course, patched — see Known issues)

# Conventions that are easy to get wrong

- **Always work in the ALIGNED Atera frame** (`PROCESSED/.../xenium_HE_aligned/`), never RAW.
  RAW is Xenium instrument space at 0.2125 um/px; aligned is H&E space at 0.27377667386671845
  um/px and is rotated ~90 degrees. The VALIS transform was never saved, so the two frames are
  **not interconvertible** — mixing them silently misplaces every cell. The aligned frame is
  also the only one where the H&E lines up. Pixel size is absent from the TIFF tags; take it
  from `qc/align_meta.json`.
- **Tutorial 3 tiles from the full-resolution Visium H&E TIFF, memory-mapped.** Four rules
  that are easy to break: (a) never `np.pad` the full-res image — padding 24240 x 24240 x 3
  materialises 1.9 GB and kills the Colab session; clip per tile instead (no spot on this
  slide is within half a window of an edge anyway). (b) `tifffile` is **already preinstalled
  on Colab** via scikit-image, so it must NOT be added to Tutorial 3's install cell, which
  deliberately installs scanpy alone (`constraints-colab.txt:21-22`). (c) `adata.obsm["spatial"]`
  is already in full-res pixels — tiling needs no scale factor; it is the 2000 px thumbnail
  that is the rescaled frame. (d) never hand matplotlib the 24240² array; overviews use the
  thumbnail, tiles use the TIFF.
- **Tiles must be cut in `adata.obs_names` order, not `tissue_positions_list.csv` order.**
  Getting this wrong mismatches every tile to the wrong spot's expression, and the only
  symptom is that the model trains to r ≈ 0.00 while every figure still looks plausible.
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


- **liana 1.9.0 breaks on a NAMED `var` index.** `li.mt.bivariate` builds an internal table
  with `pd.DataFrame(...).reset_index().rename(columns={"index": "gene"})`, which only produces
  a `gene` column when the index has no name. `atera_crop_lr.h5ad` names its index `gene_name`,
  so the rename no-ops and the implicit merge dies several frames deep with
  `pandas.errors.MergeError: No common columns to perform merge on`. Fix is one line —
  `adata.var.index.name = None` (Tutorial 3 also clears `obs.index.name`) — and it does this in
  Section 1 with a comment. Anything else here that calls `li.mt.bivariate` must do the same.
- **`li.ut.spatial_neighbors` leaves explicit zeros in the graph.** It applies the cutoff as
  `dist.data = dist.data * (dist.data > cutoff)`, multiplying rather than pruning, so below-
  cutoff weights stay stored as `0.0`. Two consequences: `W.nnz` reports `max_neighbours`
  per cell regardless of bandwidth and is **not** the edge count (count `(W > 0).sum(axis=1)`
  instead), and `li.mt.bivariate` then walks all those stored zeros. On the Crop at
  bandwidth 15 that is 3,217,206 stored against 269,630 real edges, and one
  `W.eliminate_zeros()` cut Tutorial 3's local-analysis cell from 114.7 s to 27.0 s with an
  identical answer. The published LIANA+ tutorial notebook has this same wrong per-cell
  edge count in its output.
- **LIANA+'s `bandwidth` is not a radius, and there are two different ones.** With a Gaussian
  kernel the furthest cell still above `cutoff` sits at `bandwidth * sqrt(2*ln(1/cutoff))`
  = **2.146 × bandwidth** at the default `cutoff=0.1`. A 30 µm hard radius (median 14
  neighbours) corresponds to a **15 µm** LIANA bandwidth (median 16), not 30 µm (median 60).
  Separately, `spatial_pair_proximity` applies its bandwidth to *between-population* mean
  distances, which on the Crop span 9–224 µm: at 15 µm the median proximity is 0.003 and the
  weighting annihilates nearly every cross-population score, so Tutorial 3 uses **30 µm** there.
  Two scales, two bandwidths, and Tutorial 3 Section 4 explains why.

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
  window is derived from the sample's own scalefactors, not the parent course's hard-coded
  40, which was tuned for a different sample. (The window derivation was superseded later the
  same day — it is now computed in the full-resolution frame, `spot_diameter_fullres` x 2.2
  = 390 px; see the full-res H&E entry at the end of this log.) Per-gene accuracy confirms the intended teaching point:
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
- 2026-08-25: Added Tutorial **02b, cell–cell interaction** (stLearn ligand–receptor), between
  the niche and ViT Tutorials; the ViT keeps its `03` number and Colab badge. Two blockers had
  to be designed around. **(a) The published Crop cannot support the analysis**: its 69-gene
  panel yields exactly 4 complete connectomeDB2020 literature pairs (CXCL12–CD4, EPCAM–EPCAM,
  MRC1–PTPRC, PTPRC–MRC1). New Staged artifact `atera_crop_lr.h5ad` (5.4 MB) carries the same
  16,006 cells with 1,673 connectomeDB genes Atera measures → **2,168 pairs**; 6.7% dense, 226
  counts/cell. `atera_crop.zarr.zip` is untouched, so Tutorials 01 and 02 needed no
  re-verification. **(b) No stlearn release resolves against numpy 2.0.2** — 1.4.x wants
  `numpy>=2.4.0`, 1.3.0 wants `<2.0`, 1.2.2 wants `scikit-image<0.23`, 1.1.x pins
  `scipy==1.11.4`. Resolved by installing stlearn `--no-deps` (ADR-0004) and adding its two
  uncovered eager imports, bokeh and leidenalg, to the pin set; torchvision is the third and
  Colab preinstalls it. Verified: `import stlearn`, `load_lrs`, `cci.run` and `run_cci` all run
  correctly on numpy 2.0.2.
- 2026-08-25: 02b's analysis parameters, chosen by benchmark rather than by taste: neighbourhood
  **30 µm** (median 14 neighbours, 0.13% of cells isolated), `min_spots=20`, pairs pre-filtered
  to both genes detected in ≥5% of cells (402 of 2,168, leaving 1,368 genes for the null),
  `n_pairs=200` for `cci.run` and `n_perms=100` for `run_cci`. ~195 s at 4 threads. The result
  is worth knowing before re-tuning: the ranking is dominated by matrix–integrin pairs (22 of
  the top 25) because it tracks abundance, while the immune signal concentrates on
  **T cell ↔ dendritic cell** — top or runner-up for six of eight watched pairs. Cells carrying
  significant scores are strongly immune-enriched and tumour-depleted (Tumour epithelial 42.7%
  of the Crop but 3.5% of significant `B2M_HLA-F` cells; macrophages 3.9× enriched for
  `CD47_SIRPA`), which independently reproduces Tutorial 02's immune-exclusion picture.
- 2026-08-25: `atera_io.read_panel_matrix` gained an optional `keep_cells` boolean mask. Asking
  for 1,675 genes over all 170,057 cells is 1.1 GB dense; restricted to the Crop it is 107 MB.
  Default `None` preserves the old behaviour for steps 03 and 04.
- 2026-08-25: **Tutorial 3 now tiles from the full-resolution Visium H&E TIFF**
  (`V1_Breast_Cancer_Block_A_Section_1_image.tif`, 1.76 GB, 24240 x 24240 x 3, uncompressed,
  one strip per row and contiguous from byte 8, single page, no pyramid), instead of the
  2000 px `tissue_hires_image.png`. The old choice was defensible on download size and
  nothing else: a tile was 32 real px at 3.76 um/px, so an 8 um nucleus was 2 px and the
  Tutorial's "infer from morphology" framing rested on morphology the model never received.
  A tile is now 390 px at 0.31 um/px, downsampled (not upsampled) into the same 64 x 64
  tensor — 5.3x the edge energy over all 3,798 tiles. Measured: download 10 s at 175 MB/s;
  `tifffile.memmap` opens in 0.02 s at 0.04 GB RSS; tiling all 3,798 spots takes ~12 s at
  1.06 GB peak RSS. `WIN` moves from 32 to 390, `OUT` stays 64 and `patch` stays 8, so the
  model is byte-identical at 118,160 parameters; notebook wall 179 s (was ~131 s), the
  difference being download plus tiling.
  A 4-config x 3-seed sweep justified keeping `OUT = 64`: hires 64/p8 (the old design)
  0.3003 +/- 0.0233, **full-res 64/p8 0.3198 +/- 0.0060**, full-res 128/p16 0.2897,
  hires 128/p16 0.2974. The full-res tiles win on mean r, on immune markers
  (0.206 -> 0.230) and on structural markers (0.374 -> 0.390) at no extra training cost,
  and the **4x drop in seed-to-seed spread matters most for a live session** — the old
  design had a seed landing at 0.267. 128/p16 loses for both sources, so that is a patch-
  granularity effect rather than a resolution one; it became Exercise 4 with a known answer.
  The teaching point is unchanged: best DCN/KRT8/COL1A1, worst IGLC7/IGHA2/MS4A1.
  The hires-PNG path survives only as a download-failure fallback and as the source for the
  overview figure; **the fallback branch was executed and verified**, not just written
  (stub the `wget` to fail: warns, degrades to WIN 32, finishes with 0 errors), because this
  repo has previously shipped an unexercised branch. `tifffile` needed no install — Colab
  ships it via scikit-image — so Tutorial 3 still installs scanpy alone. No licence change:
  the TIFF is fetched from 10x's CDN and never redistributed, like the `.h5` and `.tar.gz`.
- 2026-08-26: **Public release forked off to a second repo.** This tree stays the authoring
  repo (`xiao233333/ASI-FIMSA-workshop-2026`); the Participant-facing release now lives at
  `/scratch/user/uqxtan9/analysis_project/ASI_FIMSA_2026` → `GenomicsMachineLearning/ASI_FIMSA_2026`.
  It carries the notebooks, `prep/`, `verify/`, `docs/adr/`, the pin sets and the licence/context
  docs, minus `AGENTS.md`, `CLAUDE.md` and `docs/agents/`. **Edits to Participant-facing material
  must reach both trees** — in particular the Colab badges in `README.md` and `REPO_RAW` in
  Tutorials 02 and 02b differ between them by design, because each points at its own repo.
  The Hugging Face dataset repo is shared and unchanged.
- 2026-08-26: **Tutorial prose trimmed and de-AI'd; Exercises removed.** Markdown across the five
  notebooks went 144,021 -> 99,175 characters (~24,000 -> ~16,500 words, 69%). **Code cells were not
  touched at all**, including their comments, and the headless suite still passes 5/5 with 0 errors
  and 44 figures. What was cut, as categories worth keeping cut: install and pin rationale (the numpy
  2.0.2 essay, the pin-file callout, `--no-deps`/ADR-0004, the numba thread guard, "do not upgrade
  torch"); vendor-format archaeology (the `cells.zarr.zip` placeholder essay, the `.zarr.zip`
  unzip-first explanation, the sopa `geometrize_niches` rename, the `.ptp()`/NumPy 2.0 note, the
  netgraph adjacency conversion, the stlearn `imagerow`/`uns["spatial"]` essays); and authoring
  provenance (the CosMx multi-FOV "what we dropped" callout, the `voronoi.py` history). Those facts
  now live **only here and in `docs/adr/`**, which is the right place for them. Style rules applied,
  worth keeping if the notebooks are edited again: **no `&mdash;`/`&ndash;` in prose** (280 -> 0; use
  a comma, colon, parenthesis or full stop), no rhetorical "honest/honesty" (16 -> 0), no forced
  punchlines or inflated-importance claims. Blockquote callouts 36 -> 21. Tutorial 3's Section 4
  Transformer explainer was **kept and shortened** (6,806 -> ~4,000), so Section 5's reference to it
  still resolves. Tutorial 1's title was corrected from "One tissue, three technologies" to "one
  disease, three technologies", which the Scientific Context section has required since 2026-08-25.
- 2026-08-26: **Both trees are now byte-identical apart from three URL strings.** The release tree's
  earlier hand-trim had diverged and lost real content: `03_vit_gene_expression.ipynb` no longer
  installed scanpy (the `%pip install -q scanpy` cell had been deleted while scanpy was still imported
  downstream, so it would fail on a fresh Colab), `00_setup_check.ipynb` had lost its final verdict
  cell, and Tutorial 3's Section 5 referred to a Section 4 that had been deleted. Copying the
  authoring notebooks over repaired all three. Propagation is now mechanical: `cp` the five notebooks,
  then `sed` `githubusercontent.com/xiao233333/ASI-FIMSA-workshop-2026` ->
  `githubusercontent.com/GenomicsMachineLearning/ASI_FIMSA_2026` (exactly 3 occurrences, all
  `REPO_RAW`, in Tutorials 02 and 02b). Verified afterwards that every markdown cell matches and only
  those three code lines differ.

- 2026-08-26: Added **Tutorial 02c, cell–cell interaction with LIANA+** (`notebooks/02c_cell_cell_interaction_liana.ipynb`),
  an optional companion to 02b on the same `atera_crop_lr.h5ad` cells. Written because 02b's
  `--no-deps stlearn` install (ADR-0004) is the Workshop's largest untested risk and 02c is a
  drop-in replacement that does not need it: **liana declares no numpy floor**, so
  `-c constraints-colab.txt scanpy seaborn liana` resolves with numpy held at 2.0.2 and nothing
  switched off. Verified headless: 0 errors, 8 figures, **103 s** (02b's two analysis cells
  alone are 216 s). Coverage on this panel is **3,738 of LIANA's 4,620 consensus interactions**.
  Teaching content 02b does not have: an expression-only vs spatially-weighted A/B of the same
  consensus (53.7% of unsaturated rows promoted, 46.3% demoted — spatial weighting is a
  constraint, not an accuracy), per-cell `bivariate` local scores with Moran's R drawn on the
  H&E, and the receptor-complex story (`ICAM1→ITGAL_ITGB2`, `TGFB1→TGFBR1_TGFBR2`; `CSF1_CSF1R`
  and 02b's number-one `B2M_HLA-F` are **absent from LIANA's consensus resource entirely**).
  **The cross-tutorial result is the payoff:** 02b's T cell ↔ dendritic cell axis reproduces
  under a different tool, database and statistic — top for 4 of the 8 surviving watched pairs.
  `Plasma cell → T cell` tops 3 more and is flagged in the notebook as a 91-cell artefact
  candidate, not a finding. Repo plumbing done alongside: liana/mudata/plotnine/mizani pinned
  in `constraints-colab.txt`, `liana` added to `requirements-colab.txt`, `verify/make_env.sh`
  now imports liana and loads its resource at build time, README badge row added. **Not yet
  run in real Colab** — see Current Goal.
- 2026-08-26: 02c propagated to the public tree, and the propagation rule is now wider than
  the earlier entry says. Copying the notebooks and `sed`-ing `REPO_RAW` is **not sufficient**
  when a Tutorial adds a dependency: 02c's install cell fetches `constraints-colab.txt` from
  the *public* repo's raw URL, so the pin set has to travel with it or the public Tutorial
  installs unpinned. First attempt moved notebook + badge only and left the public
  `constraints-colab.txt` without a liana pin. **Propagation checklist is now: notebooks
  (sed `REPO_RAW`), README badges, `constraints-colab.txt`, `requirements-colab.txt`,
  `verify/`.** None of those four support files contain an org reference, so they copy verbatim.
- 2026-08-26: A house-style pass (em-dash entities stripped, titles lower-cased, prose
  rewrapped to ~100 cols) was run over every notebook including 02c, in both trees. It touched
  **markdown only** — all 24 of 02c's code cells are byte-identical across the two trees, and
  the suite still passes. `verify/build_02c.py`, a builder used to author 02c, was **deleted**:
  it embedded the pre-pass prose and would have silently reverted the restyle if anyone ran it.
  Prose notebooks here are hand-authored and have no builders; only `00_setup_check` does,
  because it is genuinely generated. Do not reintroduce a builder for a hand-edited notebook.
- 2026-08-26: **Tutorial 02c (LIANA+) given the same trim.** Markdown 28,522 -> 21,229 characters
  (74%), same rules as the other five: no `&mdash;`/`&ndash;` in prose (57 -> 0), no rhetorical
  "honest" (4 -> 0), Exercises section deleted, and the `--no-deps`-versus-LIANA+ install comparison
  cut from Section 0.1 (that contrast is an ADR-0004 fact, not Participant material). Code untouched;
  02c passes headless on its own in 104 s with 8 figures and 0 errors. Its Section 4 bandwidth trap
  was kept but the LaTeX formula was replaced by the multiplier it evaluates to (~2.15 x bandwidth),
  which is the part a Participant acts on. The one surviving cross-notebook reference is to **02b's**
  Section 7.2, and it is written with the `02b` prefix so it does not read as a local section.
  02c was also **added to the release tree**, which did not have it: the notebook plus its Colab badge
  row in `README.md` (inserted after 02b) and the blurb's "Four Tutorials" -> "Four Tutorials plus an
  optional fifth". Note the two `README.md` files have otherwise diverged a long way (authoring 159
  lines, release 27) and were left that way; only the 02c row was synced.
- 2026-08-26: **stLearn Tutorial retired; notebooks renumbered.** A human decision, taken
  after the 02b-vs-02c question recorded above: the release ships **one** cell-cell interaction
  Tutorial, and it is LIANA+. `notebooks/02b_cell_cell_interaction.ipynb` was deleted from both
  trees, `02c_cell_cell_interaction_liana.ipynb` became **`03_cell_cell_interaction_liana.ipynb`**
  and `03_vit_gene_expression.ipynb` became **`04_vit_gene_expression.ipynb`**. The teaching order
  is now 00, 01, 02, 03, 04, and `verify/run_notebooks.sh` picks it up from the filenames.
  **What this removed from the dependency surface**, which is the real win: `stlearn` is no longer
  installed anywhere, so ADR-0004's `--no-deps` override is gone, and with it `bokeh`, `leidenalg`
  and their leaves (`xyzservices`, `narwhals`, `tornado`). `requirements-colab-stlearn.txt` was
  deleted. `texttable` stays, re-attributed to python-igraph, which Tutorial 1 genuinely needs.
  **`00_setup_check` gained a real gap-fix in the process:** it installed and version-checked
  `stlearn` but never `liana`, so it had been passing while failing to test the one dependency
  Tutorial 3 needs. It now installs and checks `liana` instead. Note 00's markdown lives in
  `verify/build_setup_check.py`, not in the notebook — regenerating overwrites hand edits, so
  edit the generator and re-run it (`--check` fails if the notebook is stale).
  **Tutorial 3 was rewritten to stand alone.** It was written as "a second opinion" whose spine
  was a comparison against 02b; the cross-tutorial check (old Section 7.1), the stLearn headline
  quote and the hard-radius translation are gone, its Section 9 now carries the full limitations
  list it used to defer to 02b, and five **code** cells were edited for the first time in this
  effort — a plot legend, two print blocks, the `receptor_02b` variable and two comments. Logic
  and outputs are unchanged; the notebook passes headless in 101 s.
  Also updated: both READMEs, `constraints-colab.txt`, `requirements-colab.txt`, all four
  `verify/` scripts, `DATA_LICENCE.md` (connectomeDB2020 is now credited to the prep pipeline
  that fetches it, not to a Tutorial that loaded it through stlearn), `prep/README.md` and
  `prep/06_build_cci_table.py`. ADR-0004 is marked **superseded** rather than deleted.
  **Known stale, deliberately not chased:** the published `atera_crop_lr.h5ad` on Hugging Face
  carries `read_instructions` telling the reader to set `obs['imagerow']`/`obs['imagecol']` for
  stlearn. No Tutorial reads that field any more, so the dataset was not rebuilt or re-uploaded.
  Full suite after the change: 5/5 PASS, 0 errors, 40 figures.

- 2026-08-26: **Notebook 00 trimmed, and Tutorial 2 now actually installs `netgraph`.** Two
  Participant-facing changes, both propagated to the release tree.
  **Notebook 00** lost its "please run this before the Workshop" framing and its whole Step 4
  ("the verdict" — the PASS/FAIL table plus the "email us BEFORE the Workshop" block). Steps 1-3
  renumbered `of 4` -> `of 3`; Step 3b (the figure check) is untouched and is still what satisfies
  `check_outputs.py`'s at-least-one-image rule. Every edit went into
  `verify/build_setup_check.py`, never the `.ipynb` — the notebook is generated, and `--check`
  catches hand edits. Three collateral fixes were forced by the deletion: the intro's "The last
  cell tells you either that you are ready" sentence, the blocked-downloads branch's "see the last
  cell" pointer (caught in review, not in drafting), and the phrase "before the Workshop" in the
  generator docstring and in one `check_outputs.py` comment. Notebook 00 is now 7 cells / 4 code,
  runs headless in 17 s against a 120 s budget.
  **Tutorial 2** had `netgraph` missing from its install line — `PACKAGES` read
  `["squidpy", "sopa", "scanpy", "seaborn"]` — even though `constraints-colab.txt:16` and
  `requirements-colab.txt:46-50` both already asserted it was there and `netgraph==4.13.2` was
  already pinned. Section 5.6 (`sopa.spatial.prepare_network` + `netgraph.Graph`) was therefore
  silently skipped for **every Colab Participant**; it only ever ran locally, where the
  verification venv happens to have netgraph. Adding the one name makes the existing docs true.
  The try/except guard in 5.6 stays — it is what protects a non-Colab reader. No pin file changed.
  **New gotcha for propagation:** `nbformat >= 4.5` assigns each cell a **random `id`**, so
  regenerating `00_setup_check.ipynb` independently in both trees can never produce byte-identical
  files (7 `id` lines differ). Regenerate in one tree and `cp` to the other. This is safe because
  `--check` compares only cell `source`, and `cp` is already the documented propagation method.
  **Deliberately not chased:** `README.md` still says "Start with the setup check **before** you
  arrive" (lines 15-16, 20, 29-41, 52) — its Colab badge points at the right file, so nothing is
  broken. And the two stale tracked duplicates at the repo root, `00_setup_check.ipynb` and
  `03_cell_cell_interaction_LIANAplus_breast_cancer_Xenium.ipynb`, are unreferenced dead weight
  older than the current `notebooks/` copies; the root 00 still carries the removed phrase.
  Suite after the change: 00 and 02 both PASS, 0 errors, 1 + 14 figures.
