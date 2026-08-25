#!/usr/bin/env python
"""Step 04 -- build the Crop Staged dataset ``atera_crop.zarr.zip``.

A single SpatialData object holding the 2000 um window chosen at gate 2:

    images["he"]              H&E overview of the whole Crop, ~1.1 um/px
    images["he_zoom"]         a 300 um square at native 0.2738 um/px
    shapes["cell_boundaries"] one polygon per cell, in micrometres
    tables["table"]           obs + the ~60-gene marker panel, annotating the shapes

Everything lives in ONE coordinate system, ``"global"``, whose units are
micrometres. Shapes and table centroids are already in micrometres so they carry
an identity transform; the two images carry Scale-then-Translate. The point is
that a Tutorial can plot image and boundaries together with no transform work.

WHY THIS IS BUILT BY HAND rather than with ``spatialdata_io.xenium()``:
the RAW bundle declares ``analysis_sw_version: "xenium-9.9.9.9"``. The reader
parses that as >= 2.0.0 and takes the modern branch, which demands a real
``polygon_sets`` zarr that this pre-release Atera bundle does not have. Calling
the reader on Atera fails; ``Image2DModel`` / ``ShapesModel`` / ``TableModel``
are used directly instead.

The zip is written with ``-0`` (store, no deflate) because zarr chunks are
already compressed -- re-deflating them costs time and buys nothing.

Runs on Bunya, never in Colab.  ~3 min.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import anndata as ad
import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shapely
import spatialdata as sd
import tifffile
import zarr
from spatialdata.models import Image2DModel, ShapesModel, TableModel
from spatialdata.transformations import Identity, Scale, Sequence, Translation

import config as C
import atera_io as io

CS = C.COORD_SYSTEM


# --------------------------------------------------------------------------- #
# Image tiles
# --------------------------------------------------------------------------- #


def _window_with_built_counts(win, table):
    """Stamp the AS-BUILT cell counts onto the window metadata.

    ``win`` comes from prep/02_pick_crop.py, whose scan runs before the table is
    assembled, so its ``n_cells`` can drift from what was actually written (it has
    read 15,606 vs 16,006 for the Crop, and 331 vs 337 for the zoom). Keep the
    predicted values for provenance but add the truth beside them, so anything
    reading these attrs gets a number that matches the object.
    """
    import numpy as _np

    out = {**win, "n_cells_built": int(table.n_obs)}
    zoom = win.get("he_zoom")
    if zoom:
        xy = table.obsm["spatial"]
        inside = (
            (xy[:, 0] >= zoom["x0_um"])
            & (xy[:, 0] < zoom["x0_um"] + zoom["size_um"])
            & (xy[:, 1] >= zoom["y0_um"])
            & (xy[:, 1] < zoom["y0_um"] + zoom["size_um"])
        )
        out["he_zoom"] = {**zoom, "n_cells_built": int(_np.count_nonzero(inside))}
    return out


def read_he_tile(
    x0_um: float, y0_um: float, size_um: float, level: int
) -> tuple[np.ndarray, float, float, float]:
    """Read a square H&E region at a pyramid level.

    Returns ``(cyx uint8 array, um_per_px, x_origin_um, y_origin_um)``. The origin
    is snapped to the level's own pixel grid so the Scale/Translate transform is
    exact rather than carrying a sub-pixel resampling error.
    """
    ds = 2**level
    um_px = C.HE_PX_UM * ds
    px0 = int(round(x0_um / um_px))
    py0 = int(round(y0_um / um_px))
    n = int(round(size_um / um_px))

    tf = tifffile.TiffFile(C.HE_PYRAMID_TIF)
    series = tf.series[0]
    if level >= len(series.levels):
        raise SystemExit(f"pyramid has no level {level}")
    z = zarr.open(series.aszarr(level=level), mode="r")  # (c, y, x)
    ny, nx = z.shape[1], z.shape[2]
    px1, py1 = min(px0 + n, nx), min(py0 + n, ny)
    t0 = time.time()
    tile = np.asarray(z[:, py0:py1, px0:px1])
    print(
        f"  he level {level}: {tile.shape} at {um_px:.4f} um/px "
        f"in {time.time() - t0:.1f}s"
    )
    return tile, um_px, px0 * um_px, py0 * um_px


def image_element(tile: np.ndarray, um_px: float, x_um: float, y_um: float):
    tr = Sequence(
        [
            Scale([um_px, um_px], axes=("x", "y")),
            Translation([x_um, y_um], axes=("x", "y")),
        ]
    )
    return Image2DModel.parse(
        tile,
        dims=("c", "y", "x"),
        c_coords=["r", "g", "b"],
        transformations={CS: tr},
        chunks=(3, 512, 512),
    )


# --------------------------------------------------------------------------- #
# Boundaries
# --------------------------------------------------------------------------- #


def read_boundaries(cell_ids: pd.Index) -> gpd.GeoDataFrame:
    """One polygon per cell, built by grouping the aligned vertex table.

    ``cell_boundaries.parquet`` is 4.25M vertex rows of (cell_id, vertex_x,
    vertex_y) -- no label_id, no geometry column. Polygons are assembled with
    ``shapely.polygons(..., indices=...)`` rather than a per-cell Python loop.
    """
    t0 = time.time()
    bnd = pd.read_parquet(
        io.stage(C.ALIGNED_BOUNDARIES_PARQUET),
        columns=["cell_id", "vertex_x", "vertex_y"],
    )
    bnd["cell_id"] = bnd["cell_id"].astype(str)
    bnd = bnd[bnd["cell_id"].isin(set(cell_ids))]
    # Vertices ship in ring order; a stable sort keeps that order within a cell.
    bnd = bnd.sort_values("cell_id", kind="stable")

    codes, uniq = pd.factorize(bnd["cell_id"], sort=False)
    n_per = np.bincount(codes)
    keep_cell = n_per >= 4
    if not keep_cell.all():
        print(f"  dropped {int((~keep_cell).sum())} cells with < 4 boundary vertices")
        keep_row = keep_cell[codes]
        bnd, codes = bnd[keep_row], codes[keep_row]
        codes, uniq = pd.factorize(bnd["cell_id"], sort=False)

    coords = np.column_stack(
        [bnd["vertex_x"].to_numpy(np.float64), bnd["vertex_y"].to_numpy(np.float64)]
    )
    rings = shapely.linearrings(coords, indices=codes)
    polys = shapely.polygons(rings)
    gdf = gpd.GeoDataFrame({"cell_id": uniq}, geometry=polys, index=pd.Index(uniq, name="cell_id"))
    bad = ~shapely.is_valid(gdf.geometry.values)
    if bad.any():
        gdf.loc[bad, "geometry"] = shapely.make_valid(gdf.geometry.values[bad])
        print(f"  repaired {int(bad.sum())} invalid polygons")

    # make_valid() can turn a self-intersecting ring into a MultiPolygon or a
    # GeometryCollection. A mixed-geometry GeoDataFrame breaks spatialdata-plot's
    # default datashader path ("Geometry type combination is not supported"), so
    # reduce every repaired cell to its largest constituent Polygon. Measured on
    # this Crop: 45 of 16,006 cells, 0.127% of total cell area, of which ~10% of
    # those cells' own area is discarded -- i.e. ~0.013% overall.
    mixed = gdf.geometry.geom_type != "Polygon"
    if mixed.any():
        def _largest_polygon(g):
            parts = [p for p in getattr(g, "geoms", []) if p.geom_type == "Polygon"]
            if not parts:
                raise ValueError(f"no polygonal part in {g.geom_type}")
            return max(parts, key=lambda p: p.area)

        lost = gdf.loc[mixed, "geometry"].area.sum()
        gdf.loc[mixed, "geometry"] = gdf.loc[mixed, "geometry"].apply(_largest_polygon)
        kept = gdf.loc[mixed, "geometry"].area.sum()
        print(
            f"  reduced {int(mixed.sum())} multi-part geometries to their largest "
            f"polygon ({100 * (1 - kept / lost):.1f}% of those cells' area dropped, "
            f"{100 * (lost - kept) / gdf.geometry.area.sum():.3f}% of total)"
        )
    assert (gdf.geometry.geom_type == "Polygon").all(), "mixed geometry survived"
    print(
        f"  {len(gdf):,} polygons from {len(bnd):,} vertices in {time.time() - t0:.1f}s"
    )
    return gdf


# --------------------------------------------------------------------------- #
# Table
# --------------------------------------------------------------------------- #


def build_table(cells: pd.DataFrame, cell_ids: list[str]) -> ad.AnnData:
    X, genes, barcodes = io.read_panel_matrix(cache=C.WORK_DIR / "panel_matrix.npz")
    pos = pd.Series(np.arange(len(barcodes)), index=pd.Index(barcodes.astype(str)))
    take = pos.loc[cell_ids].to_numpy()

    sub = cells.set_index("cell_id").loc[cell_ids]
    obs = pd.DataFrame(index=pd.Index(cell_ids, name="cell_id"))
    for col in [
        "transcript_counts",
        "total_counts",
        "cell_area",
        "nucleus_area",
        "nucleus_count",
    ]:
        if col in sub:
            obs[col] = sub[col].to_numpy()
    obs[C.GRAPHCLUST_KEY] = pd.Categorical(
        sub[C.GRAPHCLUST_KEY].astype("Int16").astype(str).replace("<NA>", None)
    )
    obs[C.KMEANS_KEY] = pd.Categorical(
        sub[C.KMEANS_KEY].astype("Int16").astype(str).replace("<NA>", None)
    )
    present = C.cell_type_order(sub["cell_type"])
    obs["cell_type"] = pd.Categorical(sub["cell_type"], categories=present)
    obs["region"] = pd.Categorical(["cell_boundaries"] * len(obs))
    obs["cell_id"] = cell_ids

    marker_for = {g: t for t, gs in C.CELL_TYPE_MARKERS.items() for g in gs}
    var = pd.DataFrame(
        {"gene": genes, "marker_for": [marker_for.get(g, "panel extra") for g in genes]},
        index=pd.Index(genes, name="gene_name"),
    )

    table = ad.AnnData(X=np.ascontiguousarray(X[take], dtype=np.float32), obs=obs, var=var)
    table.obsm["spatial"] = np.ascontiguousarray(
        sub[["x_centroid", "y_centroid"]].to_numpy(np.float32)
    )
    table.uns["cell_type_colors"] = [C.cell_type_color(t) for t in present]
    return TableModel.parse(
        table, region="cell_boundaries", region_key="region", instance_key="cell_id"
    )


# --------------------------------------------------------------------------- #
# Assembly
# --------------------------------------------------------------------------- #


def build(win: dict) -> tuple[sd.SpatialData, pd.DataFrame]:
    cells = io.cell_annotation_table()
    x0, y0, x1, y1 = win["x0_um"], win["y0_um"], win["x1_um"], win["y1_um"]
    inside = (
        cells["x_centroid"].between(x0, x1) & cells["y_centroid"].between(y0, y1)
    )
    sub = cells[inside].copy()
    print(f"{len(sub):,} cells inside the Crop [{x0:.0f},{x1:.0f}] x [{y0:.0f},{y1:.0f}] um")

    gdf = read_boundaries(pd.Index(sub["cell_id"]))
    # Keep only cells that have both a polygon and a table row, in one order.
    cell_ids = [c for c in sub["cell_id"] if c in gdf.index]
    n_lost = len(sub) - len(cell_ids)
    if n_lost:
        print(f"  {n_lost} cells have no usable boundary polygon and are dropped")
    gdf = gdf.loc[cell_ids]
    shapes = ShapesModel.parse(gdf, transformations={CS: Identity()})

    table = build_table(cells, cell_ids)

    he_tile, he_um_px, he_x, he_y = read_he_tile(
        x0, y0, C.CROP_SIZE_UM, C.CROP_OVERVIEW_LEVEL
    )
    zoom = win["he_zoom"]
    zoom_tile, zoom_um_px, zx, zy = read_he_tile(
        zoom["x0_um"], zoom["y0_um"], zoom["size_um"], 0
    )

    sdata = sd.SpatialData(
        images={
            "he": image_element(he_tile, he_um_px, he_x, he_y),
            "he_zoom": image_element(zoom_tile, zoom_um_px, zx, zy),
        },
        shapes={"cell_boundaries": shapes},
        tables={"table": table},
    )
    sdata.attrs["atera"] = {
        "dataset": "Atera whole-transcriptome Xenium, human breast cancer (FFPE)",
        "chemistry_version": "Atera v1",
        "frame": "aligned (VALIS-warped Xenium geometry in H&E space)",
        "units": "micrometre",
        "he_px_um": C.HE_PX_UM,
        "coordinate_system": CS,
        # `win` is what prep/02_pick_crop.py predicted; n_cells there can drift from
        # the built object, so record the truth alongside it.
        "crop_window": _window_with_built_counts(win, table),
        "he_overview_um_px": he_um_px,
        "he_zoom_um_px": zoom_um_px,
        "panel_genes": list(table.var_names),
        "cell_type_markers": {k: list(v) for k, v in C.CELL_TYPE_MARKERS.items()},
        "cell_type_colors": C.CELL_TYPE_COLORS,
        "read_instructions": (
            "Download atera_crop.zarr.zip, unzip it, then "
            "spatialdata.read_zarr('atera_crop.zarr'). Reading the .zip in place "
            "is not supported by spatialdata 0.7.3 -- retest on 0.8.x."
        ),
        "built_by": "prep/04_build_crop.py",
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    return sdata, sub.set_index("cell_id").loc[cell_ids]


def write_zip(sdata: sd.SpatialData, out: Path) -> Path:
    tmp_zarr = C.WORK_DIR / "atera_crop.zarr"
    if tmp_zarr.exists():
        shutil.rmtree(tmp_zarr)
    sdata.write(tmp_zarr, overwrite=True)
    size = sum(p.stat().st_size for p in tmp_zarr.rglob("*") if p.is_file())
    print(f"  zarr store {size / 1e6:.1f} MB in {tmp_zarr}")

    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    # -0 = store only; zarr chunks are already compressed. Entries must sit at the
    # archive root or zarr's ZipStore cannot find `zarr.json` / `.zgroup`.
    subprocess.run(
        ["zip", "-0", "-r", "-q", str(out.resolve()), "."],
        cwd=tmp_zarr,
        check=True,
    )
    return out


# --------------------------------------------------------------------------- #
# Verification
# --------------------------------------------------------------------------- #


def overlay_png(sdata: sd.SpatialData, path: Path, win: dict) -> None:
    """H&E with cell boundaries coloured by cell type -- the registration eyeball."""
    he = sdata.images["he"]
    tab = sdata.tables["table"]
    gdf = sdata.shapes["cell_boundaries"]
    arr = np.moveaxis(np.asarray(he.data), 0, -1)
    um_px = float(sdata.attrs["atera"]["he_overview_um_px"])
    tr = sd.transformations.get_transformation(he, CS)
    ox, oy = win["x0_um"], win["y0_um"]
    extent = (ox, ox + arr.shape[1] * um_px, oy + arr.shape[0] * um_px, oy)

    ct = tab.obs["cell_type"].astype(str).to_numpy()
    colours = np.array([C.cell_type_color(t) for t in ct])

    zoom = win["he_zoom"]
    fig, axes = plt.subplots(1, 2, figsize=(20, 10))

    axes[0].imshow(arr, extent=extent)
    gpd.GeoDataFrame(geometry=gdf.geometry.values).plot(
        ax=axes[0], facecolor="none", edgecolor=colours, linewidth=0.35
    )
    axes[0].add_patch(
        plt.Rectangle(
            (zoom["x0_um"], zoom["y0_um"]),
            zoom["size_um"],
            zoom["size_um"],
            fill=False,
            ec="#00ff00",
            lw=2,
        )
    )
    axes[0].set_xlim(ox, ox + C.CROP_SIZE_UM)
    axes[0].set_ylim(oy + C.CROP_SIZE_UM, oy)
    axes[0].set_title(
        f"Crop {C.CROP_SIZE_UM:.0f} um, {len(gdf):,} cells "
        f"(green box = he_zoom)"
    )

    zarr_img = np.moveaxis(np.asarray(sdata.images["he_zoom"].data), 0, -1)
    zpx = float(sdata.attrs["atera"]["he_zoom_um_px"])
    zext = (
        zoom["x0_um"],
        zoom["x0_um"] + zarr_img.shape[1] * zpx,
        zoom["y0_um"] + zarr_img.shape[0] * zpx,
        zoom["y0_um"],
    )
    axes[1].imshow(zarr_img, extent=zext)
    gpd.GeoDataFrame(geometry=gdf.geometry.values).plot(
        ax=axes[1], facecolor="none", edgecolor=colours, linewidth=1.0
    )
    axes[1].set_xlim(zoom["x0_um"], zoom["x0_um"] + zoom["size_um"])
    axes[1].set_ylim(zoom["y0_um"] + zoom["size_um"], zoom["y0_um"])
    axes[1].set_title(f"he_zoom {zoom['size_um']:.0f} um at {zpx:.4f} um/px")

    handles = [
        plt.Line2D([], [], color=C.cell_type_color(t), lw=3, label=t)
        for t in C.cell_type_order(ct)
    ]
    axes[1].legend(handles=handles, fontsize=8, loc="upper right", framealpha=0.9)
    for ax in axes:
        ax.set_xlabel("x (um)")
    axes[0].set_ylabel("y (um)")
    fig.tight_layout()
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {path}")


def try_direct_zip_read(path: Path) -> bool:
    """Can `sd.read_zarr` open the .zarr.zip in place, without unzipping?

    As of spatialdata 0.7.3 / zarr 3.1.6: no. ``_resolve_zarr_store`` only handles
    LocalStore and FsspecStore, and the reader then wants ``store.root``, which a
    ZipStore does not have. Probed rather than assumed, because the Tutorials pin
    spatialdata 0.8.x and this may start working.
    """
    try:
        sd.read_zarr(path)
        return True
    except Exception as exc:  # noqa: BLE001 - the point is to report, not to raise
        print(f"  direct .zarr.zip read unsupported here ({type(exc).__name__}) "
              "-- unzip first, as the README documents")
        return False


def verify(path: Path, win: dict) -> sd.SpatialData:
    print(f"\nround trip: sd.read_zarr({path.name})")
    direct = try_direct_zip_read(path)
    unpacked = C.WORK_DIR / "roundtrip" / "atera_crop.zarr"
    if unpacked.parent.exists():
        shutil.rmtree(unpacked.parent)
    unpacked.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["unzip", "-q", str(path), "-d", str(unpacked)], check=True)
    back = sd.read_zarr(unpacked)
    print(f"  read back from {'the zip directly' if direct else 'the unzipped store'}")
    print(back)
    assert set(back.images) == {"he", "he_zoom"}, back.images
    assert set(back.shapes) == {"cell_boundaries"}, back.shapes
    assert set(back.tables) == {"table"}, back.tables

    for name, elem in list(back.images.items()) + list(back.shapes.items()):
        cs = sd.transformations.get_transformation(elem, get_all=True)
        assert set(cs) == {CS}, f"{name} coordinate systems {set(cs)}"
    ext = sd.get_extent(back, coordinate_system=CS)
    print(
        "extent in 'global' (um):",
        {k: (round(v[0], 1), round(v[1], 1)) for k, v in ext.items()},
    )

    # images and shapes must land on the same micrometre window
    ix = ext["x"]
    assert ix[0] <= win["x0_um"] + 5 and ix[1] >= win["x1_um"] - 5, ix
    tab = back.tables["table"]
    assert tab.n_obs == len(back.shapes["cell_boundaries"]), "table/shape count mismatch"
    assert list(tab.obs["cell_id"]) == list(back.shapes["cell_boundaries"].index)
    print("images/shapes/table overlay in one coordinate system: OK")
    return back


# --------------------------------------------------------------------------- #


def main() -> int:
    C.ensure_dirs()
    if not C.CROP_WINDOW_JSON.exists():
        raise SystemExit("run 02_pick_crop.py first (human gate 2)")
    win = json.loads(C.CROP_WINDOW_JSON.read_text())

    sdata, sub = build(win)
    print(sdata)

    out = write_zip(sdata, C.CROP_ZARR_ZIP)
    mb = out.stat().st_size / 1e6
    print(f"\nwrote {out}  ({mb:.1f} MB, target <= 45 MB)")
    if mb > 45:
        print("!! over the 45 MB budget -- drop CROP_ZOOM_UM or raise CROP_OVERVIEW_LEVEL")

    back = verify(out, win)
    overlay_png(back, C.CROP_OVERLAY_PNG, win)

    print("\ncrop composition")
    vc = back.tables["table"].obs["cell_type"].value_counts()
    for t, v in vc.items():
        if v:
            print(f"  {t:20s} {v:>6,}  ({100 * v / vc.sum():5.1f}%)")
    print(f"  {'TOTAL':20s} {vc.sum():>6,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
