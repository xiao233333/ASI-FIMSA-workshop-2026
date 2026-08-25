"""Shared readers for the Atera bundle, used by more than one Prep script.

Kept separate from ``config.py`` so config stays a declarative source of truth.
Nothing here is imported by a Tutorial -- Prep scripts only.
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path

import h5py
import numpy as np
import pandas as pd

import config as C

# --------------------------------------------------------------------------- #
# Staging
# --------------------------------------------------------------------------- #


def stage(src: Path, dest_dir: Path | None = None, force: bool = False) -> Path:
    """Copy an RDM file into scratch and return the local path.

    RDM is NFS (~495 MB/s); /scratch is GPFS (~10 GB/s). Anything read more than
    once, or read with random access, is staged first.
    """
    dest_dir = Path(dest_dir or C.WORK_DIR / "staged")
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / Path(src).name
    if dest.exists() and not force and dest.stat().st_size == Path(src).stat().st_size:
        return dest
    t0 = time.time()
    shutil.copy2(src, dest)
    mb = dest.stat().st_size / 1e6
    print(f"  staged {Path(src).name}: {mb:,.0f} MB in {time.time() - t0:.1f}s")
    return dest


# --------------------------------------------------------------------------- #
# Cell table
# --------------------------------------------------------------------------- #


def read_aligned_cells() -> pd.DataFrame:
    """The aligned cell table: same schema and row order as RAW, x/y in H&E space."""
    df = pd.read_parquet(C.ALIGNED_CELLS_PARQUET)
    df["cell_id"] = df["cell_id"].astype(str)
    # `segmentation_method` is one long repeated string per row -- categorical or the
    # h5ad balloons.
    if "segmentation_method" in df:
        df["segmentation_method"] = df["segmentation_method"].astype("category")
    return df


# --------------------------------------------------------------------------- #
# Feature matrix
# --------------------------------------------------------------------------- #


def read_feature_names(h5_path: Path | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Return (all feature names, feature_type) from the CellRanger v2 HDF5."""
    with h5py.File(h5_path or C.FEATURE_MATRIX_H5, "r") as f:
        names = f["matrix/features/name"][:].astype(str)
        ftype = f["matrix/features/feature_type"][:].astype(str)
    return names, ftype


def read_panel_matrix(
    panel_genes: list[str] | None = None,
    h5_path: Path | None = None,
    cache: Path | None = None,
    block: int = 20_000,
    keep_cells: np.ndarray | None = None,
) -> tuple[np.ndarray, list[str], np.ndarray]:
    """Extract a dense (n_cells, n_panel) float32 counts matrix for `panel_genes`.

    The HDF5 is CSC with ``shape = [n_features, n_cells]`` -- ``indptr`` walks
    *cells*, ``indices`` are *feature* rows -- so this streams cell blocks rather
    than trying to row-slice a 307M-nnz matrix.

    Returns ``(X, genes_found, barcodes)``. Column order follows `panel_genes`
    minus anything absent from the panel.

    ``keep_cells`` is an optional boolean mask over the 170,057 cells. The stream
    still walks every block -- the file is CSC, so there is no cheaper way to find
    a cell's non-zeros -- but only the kept rows are materialised, and ``X`` and
    ``barcodes`` come back restricted to them, in file order. This exists because
    06_build_cci_table.py asks for 1,675 genes: dense over all cells that is 1.1 GB,
    against 107 MB over the 16,006 Crop cells. Leave it None and nothing changes.
    """
    panel_genes = list(panel_genes or C.PANEL_GENES)
    h5_path = Path(h5_path or C.FEATURE_MATRIX_H5)

    if cache is not None and Path(cache).exists():
        npz = np.load(cache, allow_pickle=False)
        genes = [str(g) for g in npz["genes"]]
        print(f"  panel matrix from cache {cache} {npz['X'].shape}")
        return npz["X"], genes, npz["barcodes"].astype(str)

    # 307M non-zeros read in blocks: stage off NFS first.
    h5_path = stage(h5_path)

    t0 = time.time()
    with h5py.File(h5_path, "r") as f:
        n_feat, n_cells = (int(v) for v in f["matrix/shape"][:])
        names = f["matrix/features/name"][:].astype(str)
        barcodes = f["matrix/barcodes"][:].astype(str)
        indptr = f["matrix/indptr"][:]

        name_to_row = {n: i for i, n in enumerate(names)}
        genes = [g for g in panel_genes if g in name_to_row]
        missing = [g for g in panel_genes if g not in name_to_row]
        if missing:
            print(f"  WARNING: panel genes absent from the matrix: {missing}")

        # feature row -> panel column, -1 for everything else
        lut = np.full(n_feat, -1, dtype=np.int16)
        for col, g in enumerate(genes):
            lut[name_to_row[g]] = col

        # Global cell index -> output row, or -1 for a cell that is not kept.
        # With keep_cells=None this is the identity and costs one int32 array.
        if keep_cells is None:
            row_out = np.arange(n_cells, dtype=np.int64)
            n_out = n_cells
        else:
            keep_cells = np.asarray(keep_cells, dtype=bool)
            if keep_cells.shape != (n_cells,):
                raise ValueError(
                    f"keep_cells must be a boolean mask over {n_cells} cells, "
                    f"got shape {keep_cells.shape}"
                )
            row_out = np.full(n_cells, -1, dtype=np.int64)
            n_out = int(keep_cells.sum())
            row_out[keep_cells] = np.arange(n_out, dtype=np.int64)
            barcodes = barcodes[keep_cells]

        X = np.zeros((n_out, len(genes)), dtype=np.float32)
        d_data = f["matrix/data"]
        d_idx = f["matrix/indices"]

        for a in range(0, n_cells, block):
            b = min(a + block, n_cells)
            lo, hi = int(indptr[a]), int(indptr[b])
            idx = d_idx[lo:hi]
            col = lut[idx]
            keep = col >= 0
            if not keep.any():
                continue
            dat = d_data[lo:hi][keep]
            col = col[keep].astype(np.int64)
            # nnz position -> cell index within this block
            # Global nnz position -> global cell row. Do NOT rebase to the block
            # (`- a`): X is indexed globally, and subtracting the block offset
            # folds every block onto rows 0..block, which silently inflates the
            # first cells and empties the rest.
            pos = np.flatnonzero(keep) + lo
            row = np.searchsorted(indptr, pos, side="right") - 1
            assert a <= row.min() and row.max() < b, "row index escaped its block"
            # Drop non-zeros belonging to cells we are not keeping, then map the
            # survivors onto their output rows.
            out = row_out[row]
            if keep_cells is not None:
                sel = out >= 0
                if not sel.any():
                    continue
                out, col, dat = out[sel], col[sel], dat[sel]
            np.add.at(X, (out, col), dat.astype(np.float32))

    print(
        f"  panel matrix {X.shape} in {time.time() - t0:.1f}s "
        f"(mean counts/cell {X.sum(1).mean():.1f})"
    )
    if cache is not None:
        Path(cache).parent.mkdir(parents=True, exist_ok=True)
        np.savez(cache, X=X, genes=np.array(genes), barcodes=barcodes)
    return X, genes, barcodes


# --------------------------------------------------------------------------- #
# Analysis tables (written by 00_extract_analysis.py)
# --------------------------------------------------------------------------- #


def read_analysis(name: str) -> pd.DataFrame:
    p = C.ANALYSIS_DIR / f"{name}.parquet"
    if not p.exists():
        raise FileNotFoundError(f"{p} missing -- run 00_extract_analysis.py first")
    return pd.read_parquet(p)


def cell_annotation_table() -> pd.DataFrame:
    """Aligned cells joined to graphclust / kmeans / UMAP / PCA / cell_type.

    Joins are ON BARCODE, never positional: the clustering CSVs carry 170,045 rows
    against 170,057 cells, so 12 cells legitimately end up NaN.
    """
    cells = read_aligned_cells()
    gc = read_analysis("graphclust_clusters").rename(
        columns={"Cluster": C.GRAPHCLUST_KEY}
    )
    km = read_analysis("kmeans_clusters")
    umap = read_analysis("umap")
    pca = read_analysis("pca")

    out = cells.merge(gc, left_on="cell_id", right_on="Barcode", how="left")
    out = out.merge(km[["Barcode", C.KMEANS_KEY]], on="Barcode", how="left")
    out = out.merge(umap, on="Barcode", how="left")
    out = out.merge(pca, on="Barcode", how="left")
    out = out.drop(columns=["Barcode"])

    if C.CLUSTER_ANNOTATION_CSV.exists():
        ann = pd.read_csv(C.CLUSTER_ANNOTATION_CSV)
        final = ann["manual_override"].fillna("").astype(str).str.strip()
        ann["cell_type"] = np.where(final != "", final, ann["assigned_type"])
        out = out.merge(
            ann[["cluster", "cell_type"]],
            left_on=C.GRAPHCLUST_KEY,
            right_on="cluster",
            how="left",
        ).drop(columns=["cluster"])
        out["cell_type"] = out["cell_type"].fillna("Unassigned")
    return out


def he_um_to_px(v: float) -> float:
    return v / C.HE_PX_UM
