#!/usr/bin/env python
"""Pull the deck's figures out of the verified headless run.

Source: verify/output_he_pushed/ -- the clean 2026-08-27 suite (5/5 PASS, 0 errors,
40 embedded PNGs). Figures are identified by (notebook, cell index) and written to
slides/figures/ as optimised PNG, because qimr_master.js's pngSize() parses the IHDR
header and throws on anything that is not a PNG.
"""
import base64
import io
import json
import os
import re
import sys

from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, "verify", "output_he_pushed")
OUT = os.path.join(REPO, "slides", "figures")

# (notebook stem, cell index) -> slug. Cell indices read off the executed notebooks.
WANTED = {
    "00_setup_check": {6: "blobs"},
    "01_read_and_visualise": {
        15: "visium_genes", 37: "xenium_dotplot", 39: "xenium_boundaries",
        47: "atera_wholeslide", 49: "atera_umap", 51: "atera_markers", 56: "atera_crop_he",
        58: "atera_zoom", 65: "triptych",
    },
    "02_niche_analysis": {
        13: "crop_overview", 17: "crop_cellres", 23: "demo_neighbourhood",
        28: "delaunay", 30: "nhood_enrichment", 38: "niche_composition",
        42: "niches_on_tissue", 45: "voronoi", 47: "k_sweep",
        54: "niche_polygons", 61: "hops_to_immune", 63: "celltype_vs_niche",
    },
    "03_cell_cell_interaction_liana": {
        13: "panel_support", 23: "top_pairs", 29: "proximity",
        35: "spatial_ab", 40: "local_top", 42: "local_cxcl12",
        46: "watched_pairs", 51: "bandwidth_sweep",
    },
    "04_vit_gene_expression": {
        13: "spots_on_image", 17: "tiles", 22: "marker_sparsity",
        32: "training", 35: "per_gene_r", 37: "scatter_best_worst",
        39: "predicted_on_tissue", 43: "attention",
    },
}

MAX_W = 1500      # anything wider is downscaled; a slide box is ~7.5in at 200 dpi
PNG_KEEP_KB = 300  # line-art charts stay PNG; dense/photographic figures go to JPEG


def heading_before(cells, idx):
    head = ""
    for c in cells[: idx + 1]:
        if c["cell_type"] == "markdown":
            m = re.findall(r"^#{1,4} .*$", "".join(c["source"]), re.M)
            if m:
                head = m[-1].strip()
    return head


def main():
    os.makedirs(OUT, exist_ok=True)
    for stale in os.listdir(OUT):
        os.remove(os.path.join(OUT, stale))
    manifest = {}
    rows = []
    for stem, wanted in WANTED.items():
        path = os.path.join(SRC, stem + ".ipynb")
        nb = json.load(open(path))
        cells = nb["cells"]
        nbnum = stem[:2]
        found = set()
        for idx, slug in wanted.items():
            pngs = [
                o["data"]["image/png"]
                for o in cells[idx].get("outputs", [])
                if "image/png" in o.get("data", {})
            ]
            if not pngs:
                print(f"MISSING  {stem} cell {idx} ({slug}) has no PNG output", file=sys.stderr)
                continue
            img = Image.open(io.BytesIO(base64.b64decode(pngs[0]))).convert("RGB")
            w0, h0 = img.size
            if w0 > MAX_W:
                img = img.resize((MAX_W, round(h0 * MAX_W / w0)), Image.LANCZOS)
            # Try PNG first. Line-art charts stay small and lossless; H&E overlays and
            # dense scatters do not compress as PNG, so those become JPEG. build_deck.js
            # reads dimensions from manifest.json rather than parsing an IHDR header,
            # so a mixed-format figure set is fine.
            dest = os.path.join(OUT, f"nb{nbnum}_{slug}.png")
            img.save(dest, "PNG", optimize=True)
            if os.path.getsize(dest) > PNG_KEEP_KB * 1024:
                os.remove(dest)
                dest = os.path.join(OUT, f"nb{nbnum}_{slug}.jpg")
                img.save(dest, "JPEG", quality=88, optimize=True, subsampling=0)
            found.add(idx)
            name = os.path.basename(dest)
            manifest[f"nb{nbnum}_{slug}"] = {
                "file": name, "w": img.size[0], "h": img.size[1],
                "source": f"{stem}.ipynb cell {idx}", "heading": heading_before(cells, idx),
            }
            rows.append(
                (name, img.size[0], img.size[1],
                 os.path.getsize(dest) // 1024, heading_before(cells, idx))
            )
        for idx in set(wanted) - found:
            print(f"  (cell {idx} of {stem} produced nothing)", file=sys.stderr)

    width = max(len(r[0]) for r in rows)
    for name, w, h, kb, head in rows:
        print(f"{name:<{width}}  {w:>5}x{h:<5} {kb:>4} KB   {head[:62]}")
    with open(os.path.join(OUT, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
    total = sum(r[3] for r in rows)
    print(f"\n{len(rows)} figures, {total/1024:.1f} MB total -> {OUT}")


if __name__ == "__main__":
    main()
