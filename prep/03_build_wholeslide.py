#!/usr/bin/env python
"""Step 03 -- build the whole-slide Staged dataset ``atera_wholeslide_cells.h5ad``.

All 170,057 Atera cells with their aligned centroids, the vendor clustering /
UMAP / PCA, the merged cell types from gate 1, and a ~60-gene marker panel as a
dense float32 X. Deliberately NOT the full 18,028-target matrix: that is 307M
non-zeros and nothing a Tutorial does on the whole slide needs it. Target ~35 MB
so a Participant on conference wifi is not waiting on a download.

Layout:

    X                float32 (170057, 60)   dense marker-panel counts
    obs              counts, areas, segmentation_method, graphclust, kmeans_10,
                     cell_type  (all categoricals kept categorical)
    var              gene name, marker_for (which cell type the gene marks)
    obsm['spatial']  aligned centroids in micrometres  -- x, y
    obsm['X_umap']   vendor 2-component UMAP
    obsm['X_pca']    vendor 10-component PCA
    uns              provenance, palette, panel definition

The 12 cells with no cluster keep NaN cluster labels and cell_type "Unassigned".

Runs on Bunya, never in Colab.  ~3 min, dominated by streaming the HDF5.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import anndata as ad
import numpy as np
import pandas as pd

import config as C
import atera_io as io

PANEL_CACHE = None  # set in main(); WORK_DIR/panel_matrix.npz

OBS_NUMERIC = [
    "transcript_counts",
    "control_probe_counts",
    "genomic_control_counts",
    "control_codeword_counts",
    "unassigned_codeword_counts",
    "deprecated_codeword_counts",
    "total_counts",
    "cell_area",
    "nucleus_area",
    "nucleus_count",
]


def build() -> ad.AnnData:
    cells = io.cell_annotation_table()
    if len(cells) != C.N_CELLS:
        print(f"WARNING: {len(cells):,} cells, expected {C.N_CELLS:,}")

    X, genes, barcodes = io.read_panel_matrix(cache=PANEL_CACHE)

    # The HDF5 barcodes and cells.parquet cell_ids are in the same order, but
    # assert it rather than trust it -- a silent mis-order would be invisible.
    if not np.array_equal(np.asarray(barcodes), cells["cell_id"].to_numpy()):
        raise SystemExit(
            "cell_feature_matrix barcodes do not match cells.parquet cell_id order"
        )

    obs = pd.DataFrame(index=pd.Index(cells["cell_id"].astype(str), name="cell_id"))
    for col in OBS_NUMERIC:
        if col in cells:
            obs[col] = cells[col].to_numpy()
    if "segmentation_method" in cells:
        obs["segmentation_method"] = pd.Categorical(cells["segmentation_method"])

    obs[C.GRAPHCLUST_KEY] = pd.Categorical(
        cells[C.GRAPHCLUST_KEY].astype("Int16").astype(str).replace("<NA>", None),
        categories=[str(i) for i in sorted(cells[C.GRAPHCLUST_KEY].dropna().unique().astype(int))],
    )
    obs[C.KMEANS_KEY] = pd.Categorical(
        cells[C.KMEANS_KEY].astype("Int16").astype(str).replace("<NA>", None),
        categories=[str(i) for i in sorted(cells[C.KMEANS_KEY].dropna().unique().astype(int))],
    )
    present = C.cell_type_order(cells["cell_type"])
    obs["cell_type"] = pd.Categorical(cells["cell_type"], categories=present)
    obs["panel_counts"] = X.sum(axis=1).astype(np.float32)

    marker_for = {g: t for t, gs in C.CELL_TYPE_MARKERS.items() for g in gs}
    var = pd.DataFrame(
        {
            "gene": genes,
            "marker_for": [marker_for.get(g, "panel extra") for g in genes],
        },
        index=pd.Index(genes, name="gene_name"),
    )

    umap_cols = [c for c in cells.columns if c.upper().startswith("UMAP")]
    pca_cols = [c for c in cells.columns if c.upper().startswith("PC-")]

    adata = ad.AnnData(X=np.ascontiguousarray(X, dtype=np.float32), obs=obs, var=var)
    adata.obsm["spatial"] = np.ascontiguousarray(
        cells[["x_centroid", "y_centroid"]].to_numpy(np.float32)
    )
    if len(umap_cols) == 2:
        adata.obsm["X_umap"] = cells[umap_cols].to_numpy(np.float32)
    if len(pca_cols) == 10:
        adata.obsm["X_pca"] = cells[pca_cols].to_numpy(np.float32)

    crop = json.loads(C.CROP_WINDOW_JSON.read_text()) if C.CROP_WINDOW_JSON.exists() else None
    adata.uns["atera"] = {
        "dataset": "Atera whole-transcriptome Xenium, human breast cancer (FFPE)",
        "chemistry_version": "Atera v1",
        "frame": "aligned (VALIS-warped Xenium geometry in H&E space)",
        "frame_note": (
            "Coordinates are in the ALIGNED frame, micrometres. The RAW instrument "
            "frame is rotated ~90 degrees relative to this one and the VALIS "
            "transform was not saved -- the two are not interconvertible."
        ),
        "he_px_um": C.HE_PX_UM,
        "n_targets_full_panel": C.N_GENES,
        "panel_genes": list(genes),
        "cell_type_markers": {k: list(v) for k, v in C.CELL_TYPE_MARKERS.items()},
        "clustering": "vendor CellRanger graph-based clustering (34 clusters)",
        "cell_type_source": "prep/atera_cluster_annotation.csv (human gate 1)",
        "crop_window": crop,
        "built_by": "prep/03_build_wholeslide.py",
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    adata.uns["cell_type_colors"] = [C.cell_type_color(t) for t in present]
    return adata


def main() -> int:
    global PANEL_CACHE
    C.ensure_dirs()
    PANEL_CACHE = C.WORK_DIR / "panel_matrix.npz"

    adata = build()
    print(adata)

    C.WHOLESLIDE_H5AD.parent.mkdir(parents=True, exist_ok=True)
    adata.write_h5ad(C.WHOLESLIDE_H5AD, compression="gzip")
    mb = C.WHOLESLIDE_H5AD.stat().st_size / 1e6
    print(f"\nwrote {C.WHOLESLIDE_H5AD}  ({mb:.1f} MB, target ~35 MB)")

    # -- round trip ----------------------------------------------------------- #
    back = ad.read_h5ad(C.WHOLESLIDE_H5AD)
    assert back.shape == adata.shape
    assert np.allclose(back.X, adata.X)
    assert np.allclose(back.obsm["spatial"], adata.obsm["spatial"])
    print("round trip OK:", back.shape, sorted(back.obsm))
    print(
        "cell_type counts:\n"
        + back.obs["cell_type"].value_counts().to_string()
    )
    print(
        f"spatial extent x {back.obsm['spatial'][:, 0].min():.1f}-"
        f"{back.obsm['spatial'][:, 0].max():.1f} um, "
        f"y {back.obsm['spatial'][:, 1].min():.1f}-"
        f"{back.obsm['spatial'][:, 1].max():.1f} um"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
