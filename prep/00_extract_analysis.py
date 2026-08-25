#!/usr/bin/env python
"""Step 00 -- unpack the vendor `analysis.tar.gz` and convert its CSVs to parquet.

The Atera bundle ships CellRanger-style secondary analysis (graph clustering,
k-means, UMAP, PCA, differential expression) inside a 76 MB tarball. Nothing
downstream should parse CSV, so this is done once into $TMPDIR and everything else
reads the parquet.

Writes five tables into ``config.ANALYSIS_DIR``:

    graphclust_clusters.parquet       Barcode, Cluster            (34 clusters)
    kmeans_clusters.parquet           Barcode, kmeans_2 .. kmeans_10
    umap.parquet                      Barcode, UMAP-1, UMAP-2
    pca.parquet                       Barcode, PC-1 .. PC-10
    differential_expression.parquet   one row per gene, 34 clusters wide

GOTCHA the whole pipeline turns on: the clustering CSVs have 170,045 rows against
170,057 cells. Downstream joins are on Barcode, never positional; 12 cells are
legitimately unclustered.

Runs on Bunya, never in Colab.  ~1 min.
"""

from __future__ import annotations

import shutil
import sys
import tarfile
import time
from pathlib import Path

import pandas as pd

import config as C
import atera_io as io

EXTRACT_DIR_NAME = "analysis_raw"


def extract(force: bool = False) -> Path:
    dest = C.WORK_DIR / EXTRACT_DIR_NAME
    marker = dest / ".complete"
    if marker.exists() and not force:
        print(f"already extracted -> {dest}")
        return dest
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    local_tar = io.stage(C.ANALYSIS_TARBALL)
    t0 = time.time()
    with tarfile.open(local_tar, "r:gz") as tf:
        # `filter="data"` refuses absolute paths / symlink escapes (py>=3.12 default)
        try:
            tf.extractall(dest, filter="data")
        except TypeError:  # pragma: no cover - python < 3.12
            tf.extractall(dest)
    marker.touch()
    print(f"extracted {C.ANALYSIS_TARBALL.name} in {time.time() - t0:.1f}s -> {dest}")
    return dest


def _find(root: Path, rel: str) -> Path:
    hits = sorted(root.glob(f"**/{rel}"))
    if not hits:
        raise FileNotFoundError(f"{rel} not found under {root}")
    return hits[0]


def convert(root: Path) -> dict[str, pd.DataFrame]:
    C.ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    out: dict[str, pd.DataFrame] = {}

    # -- graph-based clustering ------------------------------------------------ #
    gc = pd.read_csv(_find(root, "clustering/gene_expression_graphclust/clusters.csv"))
    gc["Barcode"] = gc["Barcode"].astype(str)
    gc["Cluster"] = gc["Cluster"].astype("int16")
    out["graphclust_clusters"] = gc

    # -- k-means 2..10, one wide table ---------------------------------------- #
    km = None
    for k in range(2, 11):
        p = root.glob(f"**/clustering/gene_expression_kmeans_{k}_clusters/clusters.csv")
        p = next(iter(sorted(p)), None)
        if p is None:
            print(f"  WARNING: kmeans_{k} missing")
            continue
        d = pd.read_csv(p).rename(columns={"Cluster": f"kmeans_{k}"})
        d["Barcode"] = d["Barcode"].astype(str)
        d[f"kmeans_{k}"] = d[f"kmeans_{k}"].astype("int16")
        km = d if km is None else km.merge(d, on="Barcode", how="outer")
    out["kmeans_clusters"] = km

    # -- UMAP ------------------------------------------------------------------ #
    um = pd.read_csv(_find(root, "umap/gene_expression_2_components/projection.csv"))
    um["Barcode"] = um["Barcode"].astype(str)
    out["umap"] = um

    # -- PCA ------------------------------------------------------------------- #
    pca = pd.read_csv(_find(root, "pca/gene_expression_10_components/projection.csv"))
    pca["Barcode"] = pca["Barcode"].astype(str)
    out["pca"] = pca

    # -- differential expression ---------------------------------------------- #
    de = pd.read_csv(
        _find(root, "diffexp/gene_expression_graphclust/differential_expression.csv")
    )
    out["differential_expression"] = de

    for name, df in out.items():
        p = C.ANALYSIS_DIR / f"{name}.parquet"
        df.to_parquet(p, index=False)
        print(f"  {name:32s} {df.shape[0]:>7,} x {df.shape[1]:<4} -> {p.name}")
    return out


def main() -> int:
    C.ensure_dirs()
    print(C.describe())
    print()
    root = extract(force="--force" in sys.argv)
    tables = convert(root)

    n_cells_clustered = tables["graphclust_clusters"]["Barcode"].nunique()
    n_clusters = tables["graphclust_clusters"]["Cluster"].nunique()
    print()
    print(f"graphclust: {n_clusters} clusters over {n_cells_clustered:,} barcodes")
    if n_cells_clustered != C.N_CELLS:
        print(
            f"NOTE (expected): {C.N_CELLS - n_cells_clustered} of {C.N_CELLS:,} cells "
            "carry no cluster. Join on Barcode, never positionally."
        )
    de = tables["differential_expression"]
    print(f"diffexp: {de.shape[0]:,} genes x {(de.shape[1] - 2) // 3} clusters")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
