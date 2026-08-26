# `prep/` — building the Atera Staged datasets

Everything here turns the vendor Atera bundle on RDM into the two Staged datasets a
Tutorial downloads at run time.

**Nothing in `prep/` ever runs in Colab.** These are Bunya scripts, they read
`/QRISdata`, and a Participant never opens them. A Tutorial consumes the artifacts
these scripts produce, never the scripts themselves.

---

## The three artifacts

| Artifact | Size | What it is |
|---|---|---|
| `atera_wholeslide_cells.h5ad` | 19.9 MB | All 170,057 cells: aligned centroids, vendor graphclust / kmeans / UMAP / PCA, merged cell types, and a 69-gene marker panel as dense float32 `X`. No images. |
| `atera_crop.zarr.zip` | 18.0 MB | A `SpatialData` Crop: 2000 µm window with an H&E overview, a native-resolution `he_zoom`, per-cell boundary polygons and the annotated table, all in one micrometre coordinate system. |
| `atera_crop_lr.h5ad` | 5.4 MB | The SAME 16,006 Crop cells with a different panel: 1,673 connectomeDB2020 ligands and receptors that Atera measures, as raw sparse counts. Built for Tutorial 3, whose ligand-receptor test the 69-gene panel cannot support — it yields 4 complete literature pairs against 2,168 here. |

They are written to `$PREP_OUT`
(default `/scratch/project_mnt/S0010/Xiao/asi_fimsa_workshop/staged`), not into the repo —
`.gitignore` excludes `*.h5ad` and `*.zarr.zip` deliberately.

Opening the Crop:

```python
# spatialdata 0.7.3 cannot read a .zarr.zip in place -- unzip first.
!unzip -q atera_crop.zarr.zip -d atera_crop.zarr
sdata = spatialdata.read_zarr("atera_crop.zarr")
```

Retest the in-place read when the Tutorials move to spatialdata 0.8.x; step 04 probes
it on every build and prints the answer.

---

## Order

| Step | Script | Runtime | Output |
|---|---|---|---|
| 00 | `00_extract_analysis.py` | 3 s | five parquet tables in `$PREP_WORK/analysis` |
| 01 | `01_annotate_clusters.py` | ~30 s | **`atera_cluster_annotation.csv`** + `.pdf` — **human gate 1** |
| 02 | `02_pick_crop.py` | ~5 s | **`crop_window.json`** + `crop_candidates.png` — **human gate 2** |
| 03 | `03_build_wholeslide.py` | ~30 s | `atera_wholeslide_cells.h5ad` |
| 04 | `04_build_crop.py` | ~15 s | `atera_crop.zarr.zip` + `crop_he_celltypes.png` |
| 06 | `06_build_cci_table.py` | ~30 s | `atera_crop_lr.h5ad` + **`cci_panel_genes.txt`** + `cci_panel_qc.png` |
| 05 | `05_make_manifest.py` | ~1 s | `manifest.json` |
| — | `upload_to_origins.sh` | ~2 min | Publishes to Hugging Face + the Drive mirror. Licence cleared 2026-08-25, but still gated behind `ACK_ATERA_LICENCE=yes` so the upload stays a deliberate act. |

Steps 03 and 04 both need the 307M-non-zero count matrix; 03 caches the extracted
panel to `$PREP_WORK/panel_matrix.npz` and 04 reuses it, so run them in order.

Whole pipeline on one Bunya node:

```bash
cd /scratch/user/uqxtan9/analysis_project/ASI_FIMSA_workshop
sbatch prep/jobs/run_all.slurm             # all steps
sbatch prep/jobs/run_all.slurm 03 04 05    # just rebuild the artifacts
```

Total under 3 minutes of compute; the job asks for 2 h because staging 470 MB off
RDM is the variable part.

---

> **06 runs before 05, and after 04.** It reads the built `atera_crop.zarr.zip` to take its
> cell list, rather than re-deriving the window, because 04 also drops cells with no usable
> boundary polygon — re-deriving would silently give a slightly different cell set. 05 writes
> the manifest and must therefore see every artifact that exists. `cci_panel_genes.txt` is a
> generated record, not a gate: nobody signs it off, but it is committed so a reviewer can see
> which genes the ligand-receptor Tutorial had available.

## The two human gates

Both gate files are **committed to the repo**. They exist so a person, not a score,
decides what the Workshop teaches.

### Gate 1 — `atera_cluster_annotation.csv`

Maps each of the 34 vendor graphclust clusters to a cell type. Review
`atera_cluster_annotation.pdf` (marker heatmap, dotplot, score matrix, composition
bar chart, B-cell interrogation) and then, for any row you disagree with, type the
correct type into **`manual_override`**. That column wins over `assigned_type`
everywhere downstream, and re-running step 01 preserves it (`--reset-overrides`
clears it).

The seven contract columns are `cluster, n_cells, top10_genes, assigned_type, score,
margin, manual_override`. The rest are there so a reviewer can see *why*:

- `best_scoring_type` — the raw argmax, before any rule overruled it
- `runner_up`, `expr_pct` — the second-place type, and marker rank percentile
  computed on **mean counts** instead of fold change (an independent evidence axis)
- `n_sig_de`, `markers_in_top50` — how much evidence the cluster has at all
- `state_vetoed`, `resolution` — which rule fired, in words
- `low_confidence` — set for every Unassigned or Mixed row, and for any row with a
  small margin, a low score, or weak expression evidence

The resolution rules are documented in the script's docstring. In short: a state
label (`Proliferating tumour`) needs its markers in the cluster's own top DE genes;
a cluster showing two types' markers in its top 10 becomes `Mixed (a+b)`; a cluster
with no significant DE genes, or with undetectable markers, becomes `Unassigned`
rather than being handed a name it has not earned.

### Gate 2 — `crop_window.json`

The single 2000 µm window a Tutorial renders. Review `crop_candidates.png`: the
left panel is the whole slide with cells coloured by type, the right panel is the
shortlist with the chosen window in green and the `he_zoom` sub-window in magenta.

Selection is **maximum cell count subject to a Shannon-entropy floor on cell-type
composition**. That constraint is the whole point: the densest window on this slide
holds 20,779 cells at normalised entropy 0.54 and is essentially solid tumour, which
would gut the niche Tutorial. The chosen window trades ~5,000 cells for a genuine
tumour / stroma / immune mix.

To pick a different window, edit `crop_window.json` by hand (or retune
`CROP_ENTROPY_FLOOR` in `config.py`) and re-run steps 04 and 05 only.

---

## Files

- **`config.py`** — the single source of truth: paths (all env-overridable), the
  pinned H&E pixel size, crop parameters, marker panels, the palette. Change
  behaviour here, not in the step scripts.
- **`atera_io.py`** — readers shared by more than one step: RDM staging, the aligned
  cell table, the streamed panel-matrix extraction, the barcode-keyed join of cells
  to clusters and cell types.
- `00`–`05` — the pipeline, one concern each.
- `jobs/run_all.slurm` — the Bunya job.
- `upload_to_origins.sh` — the publish step. **Gated.**

Environment overrides: `ATERA_ROOT` (bundle root), `PREP_WORK` (scratch working
directory), `PREP_OUT` (where artifacts land).

Built with the `MELagent` micromamba environment
(`/home/uqxtan9/micromamba/envs/MELagent/bin/python`, Python 3.11): spatialdata 0.7.3,
spatialdata-io 0.7.1, anndata 0.12.19, zarr 3.1.6, geopandas 1.1.4, tifffile 2026.3.3.
This is *not* the Colab pin set — `requirements-colab.txt` covers that, and the two
are independent on purpose.

---

## Things that will bite you

**Two coordinate frames, one of them unusable.** Everything here works in the
**ALIGNED** frame — Xenium geometry warped by VALIS into H&E space, H&E being the
fixed reference. The RAW instrument frame is rotated ~90° relative to it and **the
VALIS transform was never saved**, so the two are not interconvertible. Never carry a
coordinate across. `config.RAW_DIR` is used only for `analysis.tar.gz`; its `cells.parquet`
coordinates are not read by anything.

**The pixel size is not in any TIFF tag.** 0.27377667386671845 µm/px is pinned in
`qc/align_meta.json` and hard-coded in `config.HE_PX_UM`. Without it every image
element renders at the wrong scale and nothing overlays.

**170,045 ≠ 170,057.** The vendor clustering / UMAP / PCA CSVs cover 12 fewer cells
than `cells.parquet`. Every join is on `Barcode`; a positional join silently shifts
labels by up to 12 rows. Those 12 cells end up `Unassigned`.

**`spatialdata_io.xenium()` does not work on Atera.** The RAW bundle declares
`analysis_sw_version: "xenium-9.9.9.9"`, which the reader parses as ≥ 2.0.0 and
sends down a branch demanding a real `polygon_sets` zarr that a pre-release bundle
does not have. Step 04 builds the object by hand with `Image2DModel` /
`ShapesModel` / `TableModel` instead.

**`xenium_HE_aligned/cells.zarr.zip` is a broken 182-byte placeholder.** Ignore it.

**Use `he_sections/HE_section_xenium_rgb_v2.tif`, not the v1 file** — v1 is
contrast-clipped. `xenium_HE_aligned/morphology_focus.ome.tif` turns out to be
*pixel-identical* to `_v2` and additionally carries a 6-level pyramid, so that is
what steps 02 and 04 actually read; `config.HE_FULLRES_TIF` still points at `_v2`
for anything that wants the flat file.

**No `/` in a cell-type label.** A type string becomes a dict key in `uns` and a
group name in HDF5/zarr, and anndata already warns that forward slashes will be
disallowed. Mixed labels use `+` (`config.MIXED_SEP`).

---

## Publishing

`upload_to_origins.sh` pushes all three artifacts to Hugging Face
(`xiao233333/asi-fimsa-workshop-2026`, primary) and mirrors them to the Google Drive
folder `1ELxQjcswMcO7w4N6Z74u_2Yt3F5UWHbm`, then writes the resulting Drive file ids
back into `manifest.json`. It also ships the gate files and the dataset card, so the
provenance travels with the data.

It **refuses to run** unless `ACK_ATERA_LICENCE=yes` is set. The Atera bundle is a 10x
pre-release dataset; its redistribution licence was confirmed as **CC BY 4.0** on
2026-08-25 and is recorded in `DATA_LICENCE.md`, `prep/hf_dataset_card.md` and the
`licence` block of `manifest.json`. The gate stays anyway, because publishing cannot be
undone and every upload should be something someone chose to do. Two invocation notes,
both learned the hard way: the remote is `RCLONE_REMOTE=googledrive` (the script's
default is `gdrive`), and `hf` lives in the verification venv rather than on `$PATH`.

Run it after `05_make_manifest.py`, never before — the preflight verifies every
artifact's sha256 against the manifest and aborts on a mismatch.
