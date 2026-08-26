#!/usr/bin/env python
"""Build the H&E backdrop asset Tutorial 3 draws its Section 6 maps on.

Not part of the numbered ``00``--``06`` pipeline, and deliberately unnumbered: it
writes a **repo asset**, not a Staged dataset, so it has no place in the
"06 before 05, 05 last" ordering and nothing about it belongs in ``manifest.json``.

Why it exists. Tutorial 3 used to read the H&E straight out of ``atera_crop.zarr.zip``
with ``spatialdata``. That works locally and never works in Colab: Tutorial 3's install
line is ``scanpy seaborn liana``, Colab does not ship spatialdata, so the import failed,
the backdrop was skipped and every Participant got the maps on white. Reading one image
also cost an 18 MB download and an unzip.

So the image is flattened here, once, into two files a Tutorial can fetch from the repo
over ``REPO_RAW`` with nothing but ``matplotlib`` and ``json``:

    notebooks/assets/atera_crop_he.jpg    the H&E overview, native 1826 px, JPEG q92
    notebooks/assets/atera_crop_he.json   its matplotlib extent, in micrometres

JPEG rather than PNG on purpose. The backdrop is desaturated to greyscale, percentile-
stretched, alpha-blended under a scatter and rendered at roughly 600 px, so compression
artefacts are not observable; PNG lands near the zarr's own 7.7 MB, JPEG under 1 MB. The
lossless original stays published inside ``atera_crop.zarr.zip``.

The extent is computed from the element's own transformation, exactly as
``02_niche_analysis``'s ``image_and_extent`` does, so the pixel size is never hand-typed.

Runs on Bunya in the verification venv (it needs spatialdata), never in Colab. ~5 s.

    cd prep
    /scratch/project_mnt/S0010/Xiao/envs/colab312-stlearn/bin/python build_he_backdrop.py
    /scratch/.../python build_he_backdrop.py --crop /path/to/atera_crop.zarr   # or a .zip
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

import numpy as np
import spatialdata as sd
from PIL import Image
from spatialdata.transformations import get_transformation

import config as C

ELEMENT = "he"
JPEG_QUALITY = 92
ASSET_DIR = C.REPO_DIR / "notebooks" / "assets"
JPG_PATH = ASSET_DIR / "atera_crop_he.jpg"
JSON_PATH = ASSET_DIR / "atera_crop_he.json"


def open_crop(crop: Path, workdir: Path):
    """Return a SpatialData for `crop`, unzipping into `workdir` if it is a .zip.

    spatialdata still cannot read a .zarr.zip in place (see prep/README.md), so a
    zip has to be unpacked first -- the same two lines a Tutorial used to carry.
    """
    if crop.is_dir():
        return sd.read_zarr(crop)
    if crop.suffix != ".zip":
        sys.exit(f"not a .zarr directory or a .zarr.zip: {crop}")
    target = workdir / crop.name.replace(".zip", "")
    print(f"unzipping {crop.name} -> {target}")
    with zipfile.ZipFile(crop) as zf:
        zf.extractall(target)
    return sd.read_zarr(target)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--crop", type=Path,
                    default=C.CROP_ZARR_ZIP,
                    help="the built Crop, as a .zarr directory or a .zarr.zip")
    ap.add_argument("--quality", type=int, default=JPEG_QUALITY)
    args = ap.parse_args()

    if not args.crop.exists():
        sys.exit(f"Crop not found: {args.crop}\n"
                 "Build it with prep/04_build_crop.py, or pass --crop.")

    C.WORK_DIR.mkdir(parents=True, exist_ok=True)
    workdir = Path(tempfile.mkdtemp(prefix="he_backdrop_", dir=C.WORK_DIR))
    try:
        sdata = open_crop(args.crop, workdir)
        el = sdata[ELEMENT]
        rgb = np.asarray(el.transpose("y", "x", "c").data)
        if rgb.dtype != np.uint8:                       # every Crop so far is uint8
            sys.exit(f"expected a uint8 image, got {rgb.dtype}")

        # The element's own transformation to "global", so the micrometre extent is
        # derived rather than typed. Same idiom as the Tutorials.
        M = get_transformation(el, C.COORD_SYSTEM).to_affine_matrix(
            input_axes=("x", "y"), output_axes=("x", "y"))
        h, w = rgb.shape[:2]
        (x0, x1), (y0, y1) = (M @ np.array([[0, 0, 1], [w, h, 1]]).T)[:2]
        extent = (float(x0), float(x1), float(y1), float(y0))   # y flipped for imshow

        px_x, px_y = float(M[0, 0]), float(M[1, 1])
        if not np.isclose(px_x, px_y):
            sys.exit(f"non-square pixels ({px_x} x {px_y}); the extent below would lie")

        ASSET_DIR.mkdir(parents=True, exist_ok=True)
        Image.fromarray(rgb).save(JPG_PATH, quality=args.quality,
                                  subsampling=0, optimize=True)
        JSON_PATH.write_text(json.dumps({
            "element": ELEMENT,
            "source": f"{args.crop.name} images/{ELEMENT}",
            "coordinate_system": C.COORD_SYSTEM,
            "shape": list(rgb.shape),
            "pixel_size_um": px_x,
            "extent_um": list(extent),
            "note": "matplotlib extent (x0, x1, y1, y0); y already flipped for imshow",
            "built_by": "prep/build_he_backdrop.py",
            "licence": "Data (c) 10x Genomics, used under CC BY 4.0. "
                       "Derived: spatially subset, image downsampled, JPEG encoded.",
        }, indent=2) + "\n", encoding="utf-8")

        print(f"{JPG_PATH.relative_to(C.REPO_DIR)}  "
              f"{rgb.shape[1]} x {rgb.shape[0]} px, q{args.quality}, "
              f"{JPG_PATH.stat().st_size / 1e6:.2f} MB")
        print(f"{JSON_PATH.relative_to(C.REPO_DIR)}  "
              f"{px_x:.6f} um/px, extent {tuple(round(v) for v in extent)}")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    main()
