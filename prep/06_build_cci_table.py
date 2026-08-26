#!/usr/bin/env python
"""Step 06 -- build the ligand-receptor Staged dataset ``atera_crop_lr.h5ad``.

The SAME 16,006 cells as the Crop built by 04, carrying a different panel: every
connectomeDB2020 gene the Atera run measures, instead of the 69 genes chosen to
name cell types.

WHY THIS EXISTS AS A SEPARATE ARTIFACT
--------------------------------------
``atera_crop.zarr.zip`` carries ``config.PANEL_GENES``. Intersected with
connectomeDB2020 that is exactly FOUR complete literature ligand-receptor pairs
(CXCL12-CD4, EPCAM-EPCAM, MRC1-PTPRC, PTPRC-MRC1), so a cell-cell interaction
Tutorial cannot be run on it at all. The genes are not missing from the
experiment -- Atera is whole-transcriptome, 18,028 targets -- they were simply
not carried into the Crop.

They are carried into a NEW file rather than into a widened Crop because the Crop
is published, its sha256 is recorded in prep/manifest.json, and Tutorials 01 and
02 both read it. A sibling artifact costs ~14 MB of download and leaves all of
that alone.

Layout:

    X                float32 CSR (16006, ~1670)   raw counts, ~6.7% dense
    obs              taken VERBATIM from the Crop's own table, so cell_id order,
                     cell_type and its category order cannot drift apart
    var              gene, role (ligand / receptor / both), n_cells_detected,
                     mean_counts
    obsm['spatial']  aligned centroids in micrometres, identical to the Crop's
    uns              provenance, palette, connectomeDB counts, read instructions

NOT written: ``obs['imagerow']`` / ``obs['imagecol']``. stlearn reads cell
positions from those two columns rather than from ``obsm['spatial']``, and
deriving them is a teaching beat in the Tutorial -- shipping them pre-made would
hide the one adaptation a Participant has to make to run a Visium-era tool on
single cells.

DEPENDS ON STEP 04. The cell list is read from the built Crop, not re-derived
from the window, because 04 also drops cells with no usable boundary polygon.
Re-deriving would silently produce a slightly different cell set.

Runs on Bunya, never in Colab.  ~2 min.
"""

from __future__ import annotations

import csv
import io as _io
import json
import shutil
import sys
import time
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import anndata as ad
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy.sparse as sp
import spatialdata as sd

import config as C
import atera_io as io


# --------------------------------------------------------------------------- #
# connectomeDB2020
# --------------------------------------------------------------------------- #


def read_connectomedb() -> dict[str, list[tuple[str, str]]]:
    """Download the connectomeDB2020 pair tables and return them per database.

    Fetched rather than vendored: this repo is MIT and redistributing a curated
    third-party database under it is not ours to do. Only the resolved GENE LIST
    is committed (CCI_PANEL_GENES_TXT) -- a list of HGNC symbols, which is a fact
    about the Atera panel, not the database.
    """
    out: dict[str, list[tuple[str, str]]] = {}
    for name, url in C.CONNECTOMEDB_FILES.items():
        t0 = time.time()
        with urllib.request.urlopen(url, timeout=60) as fh:
            text = fh.read().decode("utf8")
        rows = list(csv.reader(_io.StringIO(text), delimiter="\t"))
        header = rows[0]
        if "Ligand" not in header[0]:
            raise SystemExit(f"{name}: unexpected header {header!r}")
        pairs = [(r[0].strip(), r[1].strip()) for r in rows[1:] if len(r) >= 2]
        out[name] = pairs
        print(f"  {name}: {len(pairs):,} pairs in {time.time() - t0:.1f}s")
    return out


def pair_coverage(pairs: list[tuple[str, str]], genes: set[str]) -> int:
    """How many pairs have BOTH members inside `genes`."""
    return sum(1 for lig, rec in pairs if lig in genes and rec in genes)


# --------------------------------------------------------------------------- #
# The Crop's own cells
# --------------------------------------------------------------------------- #


def read_crop_table() -> ad.AnnData:
    """Return the published Crop's table -- the authority on which cells these are.

    ``sd.read_zarr`` cannot open a ``.zarr.zip`` in place on the versions this
    repo pins, so the zip is unpacked into WORK_DIR first. That is the same dance
    the Tutorials do, and the reason is recorded in prep/README.md.
    """
    if not C.CROP_ZARR_ZIP.exists():
        raise SystemExit(
            f"{C.CROP_ZARR_ZIP} is missing -- run 04_build_crop.py first. "
            "Step 06 takes its cell list from the built Crop rather than "
            "re-deriving it from crop_window.json, because 04 also drops cells "
            "with no usable boundary polygon."
        )
    dest = C.WORK_DIR / "atera_crop.zarr"
    if dest.exists():
        shutil.rmtree(dest)
    t0 = time.time()
    with zipfile.ZipFile(C.CROP_ZARR_ZIP) as zf:
        zf.extractall(dest)
    sdata = sd.read_zarr(dest)
    table = sdata["table"]
    print(
        f"  Crop table {table.shape} read in {time.time() - t0:.1f}s "
        f"({table.n_obs:,} cells, {table.n_vars} teaching-panel genes)"
    )
    return table


# --------------------------------------------------------------------------- #
# Build
# --------------------------------------------------------------------------- #


def build() -> tuple[ad.AnnData, dict]:
    crop = read_crop_table()
    cell_ids = crop.obs["cell_id"].astype(str).to_numpy()

    print("\nconnectomeDB2020:")
    dbs = read_connectomedb()
    pairs_all = [p for name in C.CCI_USE_DATABASES for p in dbs[name]]
    db_genes = sorted({g for p in pairs_all for g in p})

    names, ftype = io.read_feature_names()
    atera_genes = {n for n, t in zip(names, ftype) if t == "Gene Expression"}
    candidates = [g for g in db_genes if g in atera_genes]
    print(
        f"\n{len(db_genes):,} connectomeDB genes, {len(candidates):,} of them "
        f"among the {len(atera_genes):,} Atera targets"
    )

    # Which of the 170,057 cells are the Crop's, in file order.
    all_cells = io.read_aligned_cells()
    pos = pd.Series(np.arange(len(all_cells)), index=all_cells["cell_id"].astype(str))
    take = pos.loc[cell_ids].to_numpy()
    mask = np.zeros(len(all_cells), dtype=bool)
    mask[take] = True
    if mask.sum() != len(cell_ids):
        raise SystemExit("Crop cell ids are not unique within the aligned cell table")

    print(f"\nstreaming counts for {len(candidates):,} genes over {mask.sum():,} cells:")
    X, genes, barcodes = io.read_panel_matrix(
        candidates, cache=C.WORK_DIR / "cci_matrix.npz", keep_cells=mask
    )

    # read_panel_matrix returns rows in FILE order; the Crop is in its own order.
    # Reindex by barcode -- never positionally.
    order = pd.Series(np.arange(len(barcodes)), index=pd.Index(barcodes.astype(str)))
    X = X[order.loc[cell_ids].to_numpy()]

    # -- detection filter ----------------------------------------------------- #
    n_det = (X > 0).sum(axis=0)
    keep = n_det >= C.CCI_MIN_CELLS_DETECTED
    dropped = [g for g, k in zip(genes, keep) if not k]
    print(
        f"  {int(keep.sum()):,} genes detected in >= {C.CCI_MIN_CELLS_DETECTED} "
        f"Crop cells; dropping {len(dropped)}"
        + (f" ({', '.join(dropped[:8])}{' ...' if len(dropped) > 8 else ''})" if dropped else "")
    )
    X = X[:, keep]
    genes = [g for g, k in zip(genes, keep) if k]
    n_det = n_det[keep]
    gene_set = set(genes)

    # -- var ------------------------------------------------------------------ #
    ligands = {lig for lig, _ in pairs_all}
    receptors = {rec for _, rec in pairs_all}
    role = [
        "both" if g in ligands and g in receptors else "ligand" if g in ligands else "receptor"
        for g in genes
    ]
    var = pd.DataFrame(
        {
            "gene": genes,
            "role": pd.Categorical(role, categories=["ligand", "receptor", "both"]),
            "n_cells_detected": n_det.astype(np.int32),
            "mean_counts": X.mean(axis=0).astype(np.float32),
        },
        index=pd.Index(genes, name="gene_name"),
    )

    # -- obs, taken verbatim from the Crop ------------------------------------ #
    obs = crop.obs.copy()
    obs["lr_panel_counts"] = X.sum(axis=1).astype(np.float32)

    Xs = sp.csr_matrix(X) if C.CCI_STORE_SPARSE else np.ascontiguousarray(X)
    adata = ad.AnnData(X=Xs, obs=obs, var=var)
    adata.obsm["spatial"] = np.ascontiguousarray(crop.obsm["spatial"], dtype=np.float32)
    adata.uns["cell_type_colors"] = list(crop.uns["cell_type_colors"])

    coverage = {
        name: {
            "pairs_in_database": len(pairs),
            "pairs_in_atera": pair_coverage(pairs, atera_genes),
            "pairs_in_this_panel": pair_coverage(pairs, gene_set),
            "pairs_in_teaching_panel": pair_coverage(pairs, set(C.PANEL_GENES)),
        }
        for name, pairs in dbs.items()
    }

    crop_attrs = dict(crop.uns.get("spatialdata_attrs", {}))
    adata.uns["atera"] = {
        "dataset": "Atera whole-transcriptome Xenium, human breast cancer (FFPE)",
        "chemistry_version": "Atera v1",
        "frame": "aligned (VALIS-warped Xenium geometry in H&E space)",
        "units": "micrometre",
        "he_px_um": C.HE_PX_UM,
        "n_targets_full_panel": C.N_GENES,
        "crop_window": json.loads(C.CROP_WINDOW_JSON.read_text()),
        "same_cells_as": C.CROP_ZARR_ZIP.name,
        "panel": "connectomeDB2020 ligands and receptors measured by Atera",
        "n_panel_genes": len(genes),
        "min_cells_detected": C.CCI_MIN_CELLS_DETECTED,
        "lr_source": {
            "database": "connectomeDB2020",
            "obtained_from": C.CONNECTOMEDB_FILES,
            "retrieved_on": datetime.now(timezone.utc).date().isoformat(),
            "note": (
                "Only the resolved gene list is redistributed here; the pair "
                "tables themselves ship inside the stlearn wheel and are loaded "
                "with stlearn.tl.cci.load_lrs()."
            ),
            "coverage": coverage,
        },
        "read_instructions": (
            "adata = anndata.read_h5ad('atera_crop_lr.h5ad'). stlearn reads cell "
            "positions from obs['imagerow'] and obs['imagecol'], which are "
            "deliberately absent: set them from obsm['spatial'] (col = x, row = y) "
            "and pass an explicit distance in micrometres to stlearn.tl.cci.run, "
            "because its automatic distance expects Visium scalefactors."
        ),
        "built_by": "prep/06_build_cci_table.py",
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "spatialdata_attrs_of_source": {k: str(v) for k, v in crop_attrs.items()},
    }
    return adata, coverage


# --------------------------------------------------------------------------- #
# Gate file + QC figure
# --------------------------------------------------------------------------- #


def write_gate(adata: ad.AnnData, coverage: dict) -> None:
    lines = [
        "# Ligand-receptor gene panel carried by atera_crop_lr.h5ad.",
        "# Generated by prep/06_build_cci_table.py -- do not hand-edit; change",
        "# config.CCI_USE_DATABASES or CCI_MIN_CELLS_DETECTED and re-run.",
        "#",
        "# Every connectomeDB2020 ligand or receptor that the Atera run measures",
        f"# and that is detected in >= {C.CCI_MIN_CELLS_DETECTED} of the "
        f"{adata.n_obs:,} Crop cells.",
        "#",
    ]
    for name, cov in coverage.items():
        lines.append(
            f"# {name}: {cov['pairs_in_database']:,} pairs in the database, "
            f"{cov['pairs_in_atera']:,} measurable by Atera, "
            f"{cov['pairs_in_this_panel']:,} in this panel, "
            f"{cov['pairs_in_teaching_panel']} in the 69-gene teaching panel."
        )
    lines.append("#")
    lines.extend(sorted(adata.var_names))
    C.CCI_PANEL_GENES_TXT.write_text("\n".join(lines) + "\n")
    print(f"wrote {C.CCI_PANEL_GENES_TXT}  ({adata.n_vars:,} genes)")


def qc_figure(adata: ad.AnnData, coverage: dict) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(16.5, 5.2))

    ax = axes[0]
    types = list(adata.obs["cell_type"].cat.categories)
    palette = dict(zip(types, adata.uns["cell_type_colors"]))
    xy = adata.obsm["spatial"]
    for t in types:
        m = (adata.obs["cell_type"] == t).to_numpy()
        ax.scatter(xy[m, 0], xy[m, 1], s=1.2, lw=0, c=palette[t], label=f"{t} ({m.sum():,})")
    ax.set_aspect("equal")
    ax.invert_yaxis()
    ax.set_xlabel("x (um)")
    ax.set_ylabel("y (um)")
    ax.set_title(f"the same {adata.n_obs:,} Crop cells")
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=6, markerscale=6)

    ax = axes[1]
    names = list(coverage)
    teach = [coverage[n]["pairs_in_teaching_panel"] for n in names]
    lr = [coverage[n]["pairs_in_this_panel"] for n in names]
    y = np.arange(len(names))
    ax.barh(y - 0.2, teach, height=0.38, color="#bdbdbd", label="69-gene teaching panel")
    ax.barh(y + 0.2, lr, height=0.38, color="#1f6fb4", label=f"{adata.n_vars:,}-gene LR panel")
    for yi, v in zip(y - 0.2, teach):
        ax.text(v + 40, yi, str(v), va="center", fontsize=8)
    for yi, v in zip(y + 0.2, lr):
        ax.text(v + 40, yi, f"{v:,}", va="center", fontsize=8)
    ax.set_yticks(y, names, fontsize=8)
    ax.set_xlabel("complete ligand-receptor pairs")
    ax.set_title("what each panel can even ask")
    ax.legend(fontsize=8, loc="lower right")

    ax = axes[2]
    ax.hist(adata.var["n_cells_detected"], bins=60, color="#2e8b57")
    ax.axvline(20, color="#c1272d", lw=1.2, ls="--", label="stlearn min_spots=20")
    ax.set_xlabel("cells detecting the gene")
    ax.set_ylabel("genes")
    ax.set_title(f"detection over {adata.n_vars:,} LR genes")
    ax.legend(fontsize=8)

    fig.tight_layout()
    out = C.PREP_DIR / "cci_panel_qc.png"
    fig.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out}")


def main() -> int:
    C.ensure_dirs()
    adata, coverage = build()
    print()
    print(adata)

    write_gate(adata, coverage)
    qc_figure(adata, coverage)

    C.CCI_LR_H5AD.parent.mkdir(parents=True, exist_ok=True)
    adata.write_h5ad(C.CCI_LR_H5AD, compression="gzip")
    mb = C.CCI_LR_H5AD.stat().st_size / 1e6
    print(f"\nwrote {C.CCI_LR_H5AD}  ({mb:.1f} MB)")

    # -- round trip ----------------------------------------------------------- #
    back = ad.read_h5ad(C.CCI_LR_H5AD)
    assert back.shape == adata.shape, "shape changed on round trip"
    assert sp.issparse(back.X) == C.CCI_STORE_SPARSE
    a1 = back.X.toarray() if sp.issparse(back.X) else back.X
    a0 = adata.X.toarray() if sp.issparse(adata.X) else adata.X
    assert np.array_equal(a1, a0), "counts changed on round trip"
    assert np.allclose(back.obsm["spatial"], adata.obsm["spatial"])

    crop_ids = list(adata.obs["cell_id"].astype(str))
    assert list(back.obs["cell_id"].astype(str)) == crop_ids
    dens = 100 * a0.astype(bool).sum() / a0.size
    print(
        f"round trip OK: {back.shape}, {dens:.2f}% dense, "
        f"{a0.sum(1).mean():.0f} LR-panel counts per cell"
    )
    for name, cov in coverage.items():
        print(
            f"  {name}: {cov['pairs_in_this_panel']:,} complete pairs in this panel "
            f"(teaching panel: {cov['pairs_in_teaching_panel']})"
        )
    print(
        "\ncell types:\n" + back.obs["cell_type"].value_counts().to_string()
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
