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

One tissue, breast cancer, seen three ways, so that every difference on screen is the
technology rather than the sample:

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
- Python only, no R — see ADR-0002
- CPU-first; Tutorial 3 uses CUDA opportunistically via
  `device = "cuda" if torch.cuda.is_available() else "cpu"`
- Prep scripts run on Bunya against RDM

# Key Input and Output Paths

- Atera raw bundle (RDM): `/QRISdata/Q1851/Xiao/Atera_dataset/BreastCancer/RAW/WTA_Preview_FFPE_Breast_Cancer`
  (~65 G; H&E 17.7 G, `morphology.ome.tif` 14.8 G, `transcripts.parquet` 10 G)
- Atera aligned/processed (RDM): `.../BreastCancer/PROCESSED/WTA_Preview_FFPE_Breast_Cancer`
  (~29 G; `xenium_HE_aligned/`, `he_sections/`, `qc/`)
- Staged datasets: Google Drive `ASI-FIMSA-workshop-2026`
  (`1ELxQjcswMcO7w4N6Z74u_2Yt3F5UWHbm`), fetched in Colab with `gdown`
- Parent course material: `/scratch/user/uqxtan9/analysis_project/gml-teaching-2026`
- Notebooks: `notebooks/`; dataset builders: `prep/`; pin set: `requirements-colab.txt`

# Change Log

- 2026-08-25: Design settled by grilling session. Established the Workshop glossary
  (`CONTEXT.md`) and ADRs 0001–0003. Key decisions: rewrite rather than fork
  `gml-teaching-2026`; public 10x data plus the Atera preview bundle; matched-tissue
  breast cancer across all three Tutorials; Python-only; Staged datasets in Google Drive
  as trimmed artifacts rather than raw bundles; from-scratch ViT rather than a
  pretrained backbone.
