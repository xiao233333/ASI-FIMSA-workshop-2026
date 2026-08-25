---
license: cc-by-4.0
pretty_name: ASI-FIMSA 2026 spatial omics workshop data
tags:
  - spatial-transcriptomics
  - single-cell
  - xenium
  - spatialdata
  - breast-cancer
  - teaching
size_categories:
  - 100K<n<1M
---

# ASI-FIMSA 2026 spatial omics workshop — staged data

Small, Colab-sized artifacts derived from the public **10x Genomics Atera whole-transcriptome
Xenium preview** dataset of FFPE human breast cancer, prepared for a two-hour hands-on
workshop at the ASI-FIMSA meeting.

Notebooks and build scripts: https://github.com/xiao233333/ASI-FIMSA-workshop-2026

## Attribution

Derived from [Preview Data: Atera In Situ Gene Expression, FFPE Human Breast
Cancer](https://www.10xgenomics.com/datasets/atera-wta-ffpe-human-breast-cancer).
**Data © 10x Genomics, used under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).**
These files are modified from the original — see *What changed* below.

## Files

| file | size | contents |
|---|---|---|
| `atera_wholeslide_cells.h5ad` | 19.9 MB | All 170,057 cells. Aligned centroids in `obsm['spatial']`, vendor `graphclust` and `kmeans_10`, `obsm['X_umap']`, `obsm['X_pca']`, our `cell_type` labels, and a 69-gene marker counts matrix. No images. |
| `atera_crop.zarr.zip` | 18.0 MB | A `SpatialData` store for a 2,000 µm window: `he` (3, 1826, 1826), `he_zoom` (3, 1096, 1096) at native 0.2738 µm/px, 16,006 cell boundary polygons, and a (16006, 69) table. One `"global"` coordinate system, in micrometres. |
| `atera_crop_lr.h5ad` | 5.4 MB | The **same 16,006 Crop cells** as `atera_crop.zarr.zip`, with the same `cell_type` labels and the same `obsm['spatial']`, but carrying a different panel: raw sparse counts for 1,673 connectomeDB2020 ligands and receptors that Atera measures. Built for ligand–receptor analysis, which the 69-gene panel cannot support. No images. |
| `cci_panel_genes.txt` | — | The 1,673 gene symbols in that panel, and how many complete ligand–receptor pairs each database contributes. |
| `atera_cluster_annotation.csv` | — | The 34 vendor clusters → 12 named cell types, with scores, margins and `low_confidence` flags. |
| `crop_window.json` | — | Exactly which window was chosen and why, including its cell-type composition. |
| `manifest.json` | — | Sizes, sha256 checksums and origins. |

## Loading

```python
from huggingface_hub import hf_hub_download
import anndata as ad, spatialdata as sd, zipfile, pathlib

REPO = "xiao233333/asi-fimsa-workshop-2026"

adata = ad.read_h5ad(hf_hub_download(REPO, "atera_wholeslide_cells.h5ad", repo_type="dataset"))

z = hf_hub_download(REPO, "atera_crop.zarr.zip", repo_type="dataset")
with zipfile.ZipFile(z) as f:          # unzip first -- see the note below
    f.extractall("atera_crop")
sdata = sd.read_zarr(next(pathlib.Path("atera_crop").glob("*.zarr")))

# The ligand-receptor view of the same cells.
lr = ad.read_h5ad(hf_hub_download(REPO, "atera_crop_lr.h5ad", repo_type="dataset"))
lr.obs["imagecol"] = lr.obsm["spatial"][:, 0]   # stlearn reads positions from
lr.obs["imagerow"] = lr.obsm["spatial"][:, 1]   # these, not from obsm["spatial"]
```

**`spatialdata.read_zarr()` cannot open a `.zarr.zip` in place** (its store resolver handles
LocalStore/FsspecStore and then wants `store.root`, which `ZipStore` lacks). Extract first.

### Why there are two views of the same 16,006 cells

`atera_crop.zarr.zip` carries a 69-gene panel chosen to name cell types. Intersected with
connectomeDB2020 that leaves **four** complete literature-supported ligand–receptor pairs, so
no interaction analysis is possible on it. Atera is whole-transcriptome, so the genes were
measured all along — `atera_crop_lr.h5ad` carries 1,673 of them and supports **2,168** pairs.
The two files describe identical cells in identical coordinates and can be joined on
`obs['cell_id']`.

## What changed from the original

The original bundle is ~65 GB. From it we produced ~38 MB by: subsetting to one 2,000 µm
spatial window for the imaging artifact; restricting the expression matrix to a 69-gene
marker panel; downsampling the H&E overview; and adding cell-type labels. Coordinates are
in the **H&E-aligned frame** (0.27377667386671845 µm/px), not the Xenium instrument frame —
the two differ in scale and by roughly a 90° rotation, and are not interconvertible.

## Caveats — please read before reusing

- **This is pre-release data.** 18,028-target "Human WTA (pre-release)" panel, `Atera v1`
  chemistry, Gen2 prototype instrument. 10x notes preview data may be superseded.
- **The cell-type labels are ours, not 10x's**, and they are teaching material rather than
  a reference annotation. They were derived automatically from the vendor's per-cluster
  differential expression and then reviewed. 14 of 34 clusters carry `low_confidence`; one
  is `Mixed (plasma+mast)` and three are `Unassigned` because the evidence did not support
  a call.
- **B cells are not resolved as their own population.** 9.75% of cells express at least one
  of `MS4A1`/`CD79A`/`CD79B`/`BANK1`, but they sit inside the large lymphocyte cluster
  labelled `T cell` rather than forming their own. All four genes are in the panel, so the
  question can be re-asked.
- The 69-gene panel is a *marker* panel chosen for teaching. For anything quantitative, go
  back to the full 18,028-gene matrix in the original dataset.
