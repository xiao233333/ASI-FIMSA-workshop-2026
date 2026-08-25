#!/usr/bin/env python
"""Step 05 -- write ``prep/manifest.json``: what was built, and where to get it.

One entry per Staged dataset with its sha256, its byte size, and its origin URLs
in the order a Tutorial should try them: Hugging Face first (primary), Google
Drive second (mirror). A Tutorial downloads by manifest entry and verifies the
hash, so a truncated download fails loudly at the start of the session rather
than as a confusing error twenty cells later.

Deliberately written to ``prep/manifest.json``, not ``notebooks/manifest.json``:
this file is the build's own output. Wiring it into the notebooks is a separate,
downstream decision.

Also records the sha256 of the two committed human-gate files. If those change
without the artifacts being rebuilt, the manifest and the gates disagree and the
mismatch is visible instead of silent.

NOTE: nothing is uploaded here, and the origin URLs do not resolve until
``upload_to_origins.sh`` has been run. That upload is blocked on the Atera
redistribution licence -- see the header of that script.

Runs on Bunya, never in Colab.  ~10 s.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import config as C

CHUNK = 8 << 20


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


DESCRIPTIONS = {
    C.WHOLESLIDE_H5AD.name: (
        "All 170,057 Atera cells: aligned centroids, vendor graphclust / kmeans / "
        "UMAP / PCA, merged cell types, and a marker-panel counts matrix. No images."
    ),
    C.CROP_ZARR_ZIP.name: (
        "SpatialData Crop: a 2000 um window with an H&E overview, a native-resolution "
        "he_zoom, per-cell boundary polygons and the annotated table, all in one "
        "micrometre coordinate system. Unzip before spatialdata.read_zarr()."
    ),
}


def entry(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"{path} missing -- run the build steps first")
    return {
        "name": path.name,
        "bytes": path.stat().st_size,
        "megabytes": round(path.stat().st_size / 1e6, 2),
        "sha256": sha256(path),
        "description": DESCRIPTIONS.get(path.name, ""),
        # Ordered: try the primary first, fall back to the mirror.
        "origins": [
            {
                "kind": "huggingface",
                "role": "primary",
                "repo_id": C.HF_REPO_ID,
                "revision": C.HF_REVISION,
                "url": C.hf_url(path.name),
            },
            {
                "kind": "gdrive",
                "role": "mirror",
                "folder_id": C.GDRIVE_FOLDER_ID,
                "folder_url": C.gdrive_folder_url(),
                # Filled in by upload_to_origins.sh; gdown needs the per-file id.
                "file_id": None,
                "url": None,
            },
        ],
        "built_by": "prep/",
        "local_path": str(path),
    }


def main() -> int:
    artifacts = [entry(p) for p in C.STAGED_ARTIFACTS]

    gates = {}
    for p in (C.CLUSTER_ANNOTATION_CSV, C.CROP_WINDOW_JSON):
        if p.exists():
            gates[p.name] = {"bytes": p.stat().st_size, "sha256": sha256(p)}

    payload = {
        "schema_version": 1,
        "workshop": "ASI-FIMSA 2026",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generated_by": "prep/05_make_manifest.py",
        # The Atera licence was confirmed CC BY 4.0 on 2026-08-25, so the gate that
        # used to live here is gone. `uploaded` reflects whether THIS manifest's
        # checksums are the ones live at the origins -- rebuilding an artifact makes
        # it False again until upload_to_origins.sh (or an equivalent) has run.
        "uploaded": False,
        "licence": {
            "atera_source": "CC BY 4.0",
            "verified_on": "2026-08-25",
            "attribution": (
                "Data (c) 10x Genomics, used under CC BY 4.0. Derived: spatially "
                "subset, marker-panel restricted, image downsampled, cell types added."
            ),
            "source_url": "https://www.10xgenomics.com/datasets/atera-wta-ffpe-human-breast-cancer",
        },
        "artifacts": artifacts,
        "human_gates": gates,
        "notes": [
            "Origin URLs are the intended locations; they 404 until the upload runs.",
            "Coordinates in every artifact are the ALIGNED (H&E) frame, micrometres.",
            f"H&E pixel size {C.HE_PX_UM} um/px is pinned, not read from a TIFF tag.",
        ],
    }
    C.MANIFEST_JSON.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {C.MANIFEST_JSON}")
    for a in artifacts:
        print(f"  {a['name']:32s} {a['megabytes']:>7.2f} MB  {a['sha256'][:16]}...")
    total = sum(a["bytes"] for a in artifacts)
    print(f"  {'TOTAL':32s} {total / 1e6:>7.2f} MB  (what a Participant downloads)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
