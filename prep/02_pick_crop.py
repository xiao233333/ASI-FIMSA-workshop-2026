#!/usr/bin/env python
"""Step 02 -- choose the Crop: one 2000 um square window of the aligned slide.

HUMAN GATE 2. Writes ``prep/crop_window.json`` (committed) plus
``prep/crop_candidates.png``, a whole-slide H&E with the shortlisted boxes drawn
on it so a person can see what was picked and why.

Everything here is in the ALIGNED frame -- Xenium geometry warped by VALIS into
H&E space. The RAW frame is rotated ~90 degrees relative to this one and the VALIS
transform was never saved, so a window chosen in RAW coordinates cannot be carried
across. A pure-density scan in RAW found 20,589 cells in a 2000 um window; this
scan is redone from scratch here and its numbers are not comparable.

Selection rule: **maximise cell count subject to a Shannon-entropy floor on the
cell-type composition.** Density alone lands on solid tumour, which would gut the
niche Tutorial -- the whole point of Tutorial 2 is immune infiltration, tumour
boundary and stroma, and you cannot teach a neighbourhood if there is only one
neighbour type.

The scan itself is a sliding-window sum over a 250 um histogram, so the whole
grid is evaluated at once rather than looping over windows.

Runs on Bunya, never in Colab.  ~1 min (dominated by reading the H&E overview).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import tifffile
import zarr

import config as C
import atera_io as io


# --------------------------------------------------------------------------- #
# Sliding-window scan
# --------------------------------------------------------------------------- #


def _window_sums(counts: np.ndarray, k: int) -> np.ndarray:
    """Sum every k x k block of `counts` (ny, nx, ntypes) at stride 1 in bins."""
    cs = np.cumsum(np.cumsum(counts, axis=0), axis=1)
    cs = np.pad(cs, ((1, 0), (1, 0), (0, 0)))
    return (
        cs[k:, k:] - cs[:-k, k:] - cs[k:, :-k] + cs[:-k, :-k]
    )  # (ny-k+1, nx-k+1, ntypes)


def _entropy(counts: np.ndarray, min_per_type: int, n_types: int) -> np.ndarray:
    """Shannon entropy of composition, normalised by log(n_types)."""
    c = np.where(counts >= min_per_type, counts, 0).astype(np.float64)
    tot = c.sum(axis=-1, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        p = np.where(tot > 0, c / np.maximum(tot, 1e-9), 0.0)
        h = -np.sum(np.where(p > 0, p * np.log(p), 0.0), axis=-1)
    return h / np.log(n_types)


def scan(cells: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    size, stride = C.CROP_SIZE_UM, C.CROP_STRIDE_UM
    k = int(round(size / stride))
    if not np.isclose(k * stride, size):
        raise SystemExit("CROP_SIZE_UM must be an integer multiple of CROP_STRIDE_UM")

    # Composition spans every label the annotation actually produced -- including a
    # "Mixed (...)" cluster, which is real cells -- but never Unassigned, which is
    # an absence of evidence rather than a population.
    types = [
        t
        for t in C.cell_type_order(cells["cell_type"])
        if t != C.UNASSIGNED_LABEL
    ]
    n_types = len(types)
    tcode = cells["cell_type"].map({t: i for i, t in enumerate(types)}).values
    ok = ~pd.isna(tcode)
    x = cells.loc[ok, "x_centroid"].to_numpy(float)
    y = cells.loc[ok, "y_centroid"].to_numpy(float)
    tcode = tcode[ok].astype(int)

    x0g = np.floor(x.min() / stride) * stride
    y0g = np.floor(y.min() / stride) * stride
    nx = int(np.ceil((x.max() - x0g) / stride)) + 1
    ny = int(np.ceil((y.max() - y0g) / stride)) + 1

    ix = ((x - x0g) / stride).astype(int)
    iy = ((y - y0g) / stride).astype(int)
    counts = np.zeros((ny, nx, n_types), dtype=np.int32)
    np.add.at(counts, (iy, ix, tcode), 1)

    win = _window_sums(counts, k)  # (ny-k+1, nx-k+1, n_types)
    n_cells = win.sum(axis=-1)
    ent = _entropy(win, C.CROP_MIN_CELLS_PER_TYPE, n_types)

    jj, ii = np.mgrid[0 : win.shape[0], 0 : win.shape[1]]
    cand = pd.DataFrame(
        {
            "x0_um": x0g + ii.ravel() * stride,
            "y0_um": y0g + jj.ravel() * stride,
            "n_cells": n_cells.ravel(),
            "entropy": ent.ravel(),
        }
    )
    for i, t in enumerate(types):
        cand[t] = win[:, :, i].ravel()

    meta = {
        "types": types,
        "n_types": n_types,
        "grid": (ny, nx),
        "n_windows": len(cand),
        "grid_origin_um": (float(x0g), float(y0g)),
    }
    return cand, meta


def shortlist(cand: pd.DataFrame, meta: dict) -> tuple[pd.DataFrame, float]:
    floor = C.CROP_ENTROPY_FLOOR
    elig = cand[cand["n_cells"] >= C.CROP_MIN_CELLS]
    passing = elig[elig["entropy"] >= floor]
    if passing.empty:
        floor = float(elig["entropy"].quantile(C.CROP_ENTROPY_FALLBACK_Q))
        print(
            f"!! no window reached the entropy floor {C.CROP_ENTROPY_FLOOR:.2f}; "
            f"falling back to the q{C.CROP_ENTROPY_FALLBACK_Q:.2f} entropy "
            f"= {floor:.3f}. Revisit config.CROP_ENTROPY_FLOOR."
        )
        passing = elig[elig["entropy"] >= floor]

    # Non-maximum suppression so the top-N are distinct regions, not one region
    # reported N times at one-stride offsets.
    ranked = passing.sort_values("n_cells", ascending=False)
    picked: list[int] = []
    for idx, row in ranked.iterrows():
        if all(
            max(
                abs(row["x0_um"] - ranked.loc[j, "x0_um"]),
                abs(row["y0_um"] - ranked.loc[j, "y0_um"]),
            )
            >= C.CROP_NMS_UM
            for j in picked
        ):
            picked.append(idx)
        if len(picked) >= C.CROP_TOP_N:
            break
    return ranked.loc[picked], floor


# --------------------------------------------------------------------------- #
# he_zoom sub-window
# --------------------------------------------------------------------------- #


def pick_zoom(cells: pd.DataFrame, win: pd.Series, types: list[str]) -> dict:
    """Most cell-type-diverse CROP_ZOOM_UM square inside the Crop."""
    size = C.CROP_ZOOM_UM
    stride = C.CROP_ZOOM_SEARCH_STRIDE_UM
    x0, y0 = float(win["x0_um"]), float(win["y0_um"])
    sub = cells[
        cells["x_centroid"].between(x0, x0 + C.CROP_SIZE_UM)
        & cells["y_centroid"].between(y0, y0 + C.CROP_SIZE_UM)
    ]
    best, best_key = None, (-1.0, -1)
    n_steps = int((C.CROP_SIZE_UM - size) / stride) + 1
    codes = sub["cell_type"].map({t: i for i, t in enumerate(types)})
    sub = sub.assign(_t=codes).dropna(subset=["_t"])
    xs, ys, ts = (
        sub["x_centroid"].to_numpy(),
        sub["y_centroid"].to_numpy(),
        sub["_t"].to_numpy(int),
    )
    for i in range(n_steps):
        for j in range(n_steps):
            zx, zy = x0 + i * stride, y0 + j * stride
            m = (
                (xs >= zx) & (xs < zx + size) & (ys >= zy) & (ys < zy + size)
            )
            if m.sum() < 50:
                continue
            c = np.bincount(ts[m], minlength=len(types)).astype(float)
            p = c / c.sum()
            h = float(-(p[p > 0] * np.log(p[p > 0])).sum() / np.log(len(types)))
            key = (round(h, 3), int(m.sum()))
            if key > best_key:
                best_key, best = key, (zx, zy, int(m.sum()), h, c)
    if best is None:
        zx, zy = x0 + (C.CROP_SIZE_UM - size) / 2, y0 + (C.CROP_SIZE_UM - size) / 2
        return {"x0_um": zx, "y0_um": zy, "size_um": size, "n_cells": 0, "entropy": 0.0}
    zx, zy, n, h, c = best
    return {
        "x0_um": float(zx),
        "y0_um": float(zy),
        "size_um": float(size),
        "n_cells": int(n),
        "entropy": round(float(h), 4),
        "composition": {t: int(v) for t, v in zip(types, c) if v},
    }


# --------------------------------------------------------------------------- #
# Figure
# --------------------------------------------------------------------------- #


def whole_slide_figure(
    cells: pd.DataFrame, top: pd.DataFrame, chosen: pd.Series, zoom: dict, path
) -> None:
    tf = tifffile.TiffFile(C.HE_PYRAMID_TIF)
    series = tf.series[0]
    level = min(5, len(series.levels) - 1)
    img = np.moveaxis(np.asarray(series.levels[level].asarray()), 0, -1)
    ds = C.HE_FULL_WH[1] / img.shape[0]
    um_px = C.HE_PX_UM * ds
    extent = (0, img.shape[1] * um_px, img.shape[0] * um_px, 0)

    fig, axes = plt.subplots(1, 2, figsize=(16, 11))
    for ax in axes:
        ax.imshow(img, extent=extent, interpolation="bilinear")
        ax.set_xlabel("x (um, aligned frame)")
    axes[0].set_ylabel("y (um, aligned frame)")

    # -- left: cells coloured by type ---------------------------------------- #
    for t in C.cell_type_order(cells["cell_type"]):
        s = cells[cells["cell_type"] == t]
        if s.empty:
            continue
        axes[0].scatter(
            s["x_centroid"],
            s["y_centroid"],
            s=0.05,
            c=C.cell_type_color(t),
            linewidths=0,
            label=f"{t} ({len(s):,})",
            rasterized=True,
        )
    axes[0].legend(
        markerscale=40, fontsize=7, loc="upper right", framealpha=0.9, title="cell type"
    )
    axes[0].set_title("Aligned cells over the H&E")

    # -- right: candidate boxes ---------------------------------------------- #
    for rank, (_, r) in enumerate(top.iterrows(), start=1):
        is_best = (r["x0_um"] == chosen["x0_um"]) and (r["y0_um"] == chosen["y0_um"])
        axes[1].add_patch(
            mpatches.Rectangle(
                (r["x0_um"], r["y0_um"]),
                C.CROP_SIZE_UM,
                C.CROP_SIZE_UM,
                fill=False,
                ec="#00ff00" if is_best else "#ffcc00",
                lw=2.5 if is_best else 1.2,
            )
        )
        axes[1].text(
            r["x0_um"] + 40,
            r["y0_um"] + 220,
            f"{rank}\n{int(r['n_cells']):,}\nH={r['entropy']:.2f}",
            color="#00ff00" if is_best else "#ffcc00",
            fontsize=7,
            weight="bold",
        )
    axes[1].add_patch(
        mpatches.Rectangle(
            (zoom["x0_um"], zoom["y0_um"]),
            zoom["size_um"],
            zoom["size_um"],
            fill=False,
            ec="#ff00ff",
            lw=1.8,
        )
    )
    axes[1].set_title(
        f"Top {len(top)} candidate Crops (green = chosen, magenta = he_zoom)\n"
        f"{C.CROP_SIZE_UM:.0f} um windows, {C.CROP_STRIDE_UM:.0f} um stride, "
        f"entropy floor {C.CROP_ENTROPY_FLOOR}"
    )
    fig.tight_layout()
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {path}")


# --------------------------------------------------------------------------- #


def main() -> int:
    C.ensure_dirs()
    if not C.CLUSTER_ANNOTATION_CSV.exists():
        raise SystemExit("run 01_annotate_clusters.py first (human gate 1)")

    cells = io.cell_annotation_table()
    print(
        f"{len(cells):,} aligned cells, extent "
        f"x {cells['x_centroid'].min():.1f}-{cells['x_centroid'].max():.1f} um, "
        f"y {cells['y_centroid'].min():.1f}-{cells['y_centroid'].max():.1f} um"
    )
    n_unassigned = int((cells["cell_type"] == "Unassigned").sum())
    if n_unassigned:
        print(f"{n_unassigned} cells carry no cluster and are excluded from the scan")

    cand, meta = scan(cells)
    print(
        f"scanned {meta['n_windows']:,} windows over a {meta['grid'][0]}x"
        f"{meta['grid'][1]} bin grid, {meta['n_types']} cell types"
    )
    print(
        f"cell count  : max {cand['n_cells'].max():,} "
        f"(entropy there {cand.loc[cand['n_cells'].idxmax(), 'entropy']:.3f})"
    )
    print(
        f"entropy     : max {cand['entropy'].max():.3f}, "
        f"median {cand['entropy'].median():.3f}"
    )

    top, floor = shortlist(cand, meta)
    chosen = top.iloc[0]

    print()
    print(f"top {len(top)} candidates (entropy floor {floor:.3f}, "
          f"{C.CROP_NMS_UM:.0f} um non-max suppression):")
    show = top[["x0_um", "y0_um", "n_cells", "entropy"] + meta["types"]].copy()
    show.insert(0, "rank", range(1, len(show) + 1))
    print(show.to_string(index=False))

    zoom = pick_zoom(cells, chosen, meta["types"])
    comp = {t: int(chosen[t]) for t in meta["types"]}
    total = sum(comp.values())

    payload = {
        "frame": "aligned (VALIS-warped Xenium geometry in H&E space)",
        "units": "micrometre",
        "he_px_um": C.HE_PX_UM,
        "size_um": C.CROP_SIZE_UM,
        "stride_um": C.CROP_STRIDE_UM,
        "x0_um": float(chosen["x0_um"]),
        "y0_um": float(chosen["y0_um"]),
        "x1_um": float(chosen["x0_um"]) + C.CROP_SIZE_UM,
        "y1_um": float(chosen["y0_um"]) + C.CROP_SIZE_UM,
        "he_px": {
            "x0": int(round(chosen["x0_um"] / C.HE_PX_UM)),
            "y0": int(round(chosen["y0_um"] / C.HE_PX_UM)),
            "x1": int(round((chosen["x0_um"] + C.CROP_SIZE_UM) / C.HE_PX_UM)),
            "y1": int(round((chosen["y0_um"] + C.CROP_SIZE_UM) / C.HE_PX_UM)),
        },
        "n_cells": int(total),
        "entropy": round(float(chosen["entropy"]), 4),
        "entropy_floor_used": round(float(floor), 4),
        "entropy_floor_config": C.CROP_ENTROPY_FLOOR,
        "n_types": meta["n_types"],
        "composition": comp,
        "composition_frac": {t: round(v / total, 4) for t, v in comp.items()},
        "he_zoom": zoom,
        "selection_rule": (
            "argmax cell count over 2000 um windows at 250 um stride, subject to "
            "normalised Shannon entropy of cell-type composition >= floor"
        ),
        "n_windows_scanned": int(meta["n_windows"]),
        "n_windows_passing_floor": int(
            (
                (cand["entropy"] >= floor) & (cand["n_cells"] >= C.CROP_MIN_CELLS)
            ).sum()
        ),
        "generated_by": "prep/02_pick_crop.py",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    C.CROP_WINDOW_JSON.write_text(json.dumps(payload, indent=2) + "\n")
    print()
    print(f"wrote {C.CROP_WINDOW_JSON}")

    cand.to_parquet(C.WORK_DIR / "crop_scan.parquet", index=False)
    whole_slide_figure(cells, top, chosen, zoom, C.CROP_CANDIDATES_PNG)

    print()
    print("chosen Crop composition")
    for t, v in sorted(comp.items(), key=lambda kv: -kv[1]):
        print(f"  {t:20s} {v:>7,}  ({100 * v / total:5.1f}%)")
    print(
        f"  {'TOTAL':20s} {total:>7,}   entropy {chosen['entropy']:.3f} "
        f"(normalised, {meta['n_types']} types)"
    )
    print()
    print(
        "HUMAN GATE 2: review prep/crop_candidates.png, then commit "
        "prep/crop_window.json."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
