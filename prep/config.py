"""Single source of truth for the Atera Staged-dataset Prep scripts.

Every path, tunable and marker panel used by ``prep/0*.py`` lives here. Nothing in
``prep/`` ever runs in Colab -- these scripts run on Bunya against RDM and write
Staged datasets that a Tutorial later downloads.

Paths are environment-overridable so the same scripts can run against a staged copy
of the bundle:

    ATERA_ROOT   root of the Atera BreastCancer bundle on RDM
    PREP_WORK    scratch working directory (defaults to $TMPDIR/asi_fimsa_prep)
    PREP_OUT     where finished Staged datasets are written

Terminology follows ``CONTEXT.md``: Staged dataset, Crop, Prep script, Atera.
"""

from __future__ import annotations

import os
from pathlib import Path

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #

#: Repo directory holding the Prep scripts and the two committed human-gate files.
PREP_DIR = Path(__file__).resolve().parent
REPO_DIR = PREP_DIR.parent


def _env_path(var: str, default: Path) -> Path:
    """Return ``$var`` as a Path if set and non-empty, else ``default``."""
    raw = os.environ.get(var, "").strip()
    return Path(raw) if raw else default


ATERA_ROOT = _env_path(
    "ATERA_ROOT", Path("/QRISdata/Q1851/Xiao/Atera_dataset/BreastCancer")
)

#: Vendor output, un-aligned instrument frame. Only used for `analysis.tar.gz` and
#: `cell_feature_matrix.h5`; the *coordinates* here are NOT used anywhere -- see
#: the note on frames below.
RAW_DIR = ATERA_ROOT / "RAW" / "WTA_Preview_FFPE_Breast_Cancer"

PROC_DIR = ATERA_ROOT / "PROCESSED" / "WTA_Preview_FFPE_Breast_Cancer"

#: Xenium geometry warped by VALIS into H&E space (H&E is the fixed reference).
#: This is the frame used by every artifact, because it is the only frame in which
#: cells line up with the H&E. The VALIS transform was never saved, so the RAW and
#: ALIGNED frames are NOT interconvertible -- never mix coordinates across them.
ALIGNED_DIR = PROC_DIR / "xenium_HE_aligned"
HE_SECTIONS_DIR = PROC_DIR / "he_sections"
QC_DIR = PROC_DIR / "qc"

# -- individual input files --------------------------------------------------- #
RAW_CELLS_PARQUET = RAW_DIR / "cells.parquet"
ANALYSIS_TARBALL = RAW_DIR / "analysis.tar.gz"

#: CellRanger v2 HDF5. CSC, ``matrix/shape`` = [27104 features, 170057 cells]
#: (i.e. transposed relative to AnnData). Barcodes are in the same order as
#: ``cells.parquet``. The aligned copy is byte-identical to the RAW one, so the
#: aligned cell table indexes this matrix directly.
FEATURE_MATRIX_H5 = ALIGNED_DIR / "cell_feature_matrix.h5"

ALIGNED_CELLS_PARQUET = ALIGNED_DIR / "cells.parquet"
ALIGNED_BOUNDARIES_PARQUET = ALIGNED_DIR / "cell_boundaries.parquet"

#: Full-resolution aligned H&E, full dynamic range, plain BigTIFF (YXS, tiled 512,
#: NO pyramid). Deliberately the ``_v2`` file: the v1 ``HE_section_xenium_rgb.tif``
#: is contrast-clipped.
HE_FULLRES_TIF = HE_SECTIONS_DIR / "HE_section_xenium_rgb_v2.tif"

#: Same aligned H&E as an OME BigTIFF with 6 pyramid levels (CYX uint8, tile 1024,
#: DEFLATE). Used only for cheap whole-slide locator figures.
HE_PYRAMID_TIF = ALIGNED_DIR / "morphology_focus.ome.tif"

ALIGN_META_JSON = QC_DIR / "align_meta.json"

# -- working / output --------------------------------------------------------- #
WORK_DIR = _env_path(
    "PREP_WORK",
    Path(os.environ.get("TMPDIR", "/scratch/temp")) / "asi_fimsa_prep",
)

OUT_DIR = _env_path(
    "PREP_OUT", Path("/scratch/project_mnt/S0010/Xiao/asi_fimsa_workshop/staged")
)

#: Derived-from-`analysis.tar.gz` parquet tables written by 00_extract_analysis.py
ANALYSIS_DIR = WORK_DIR / "analysis"

FIG_DIR = WORK_DIR / "figures"

# -- named artifacts ---------------------------------------------------------- #
WHOLESLIDE_H5AD = OUT_DIR / "atera_wholeslide_cells.h5ad"
CROP_ZARR_ZIP = OUT_DIR / "atera_crop.zarr.zip"

#: The Crop's cells again, but carrying the ligand-receptor panel instead of the
#: 69-gene teaching panel. Built by 06_build_cci_table.py; see the CCI section.
CCI_LR_H5AD = OUT_DIR / "atera_crop_lr.h5ad"

#: Committed human-gate files (small, text, tracked in git).
CLUSTER_ANNOTATION_CSV = PREP_DIR / "atera_cluster_annotation.csv"
CROP_WINDOW_JSON = PREP_DIR / "crop_window.json"
MANIFEST_JSON = PREP_DIR / "manifest.json"

#: Third committed gate file: the resolved ligand-receptor gene panel, written by
#: 06_build_cci_table.py. Only the gene list is committed, never the connectomeDB
#: pair tables themselves -- see the CCI section for why.
CCI_PANEL_GENES_TXT = PREP_DIR / "cci_panel_genes.txt"

#: Reviewer-facing PDFs / PNGs. Written next to the committed gate files so a
#: reviewer finds them without digging through $TMPDIR.
CLUSTER_ANNOTATION_PDF = PREP_DIR / "atera_cluster_annotation.pdf"
CROP_CANDIDATES_PNG = PREP_DIR / "crop_candidates.png"
CROP_OVERLAY_PNG = PREP_DIR / "crop_he_celltypes.png"

# --------------------------------------------------------------------------- #
# Scale
# --------------------------------------------------------------------------- #

#: Micrometres per H&E pixel in the ALIGNED frame. This value is NOT present in any
#: TIFF tag -- it is pinned in ``qc/align_meta.json`` ("he_px_um", source "pinned").
#: Hard-coded here because everything (Crop size, image transforms, overlays)
#: renders at the wrong scale without it.
HE_PX_UM = 0.27377667386671845

#: Full-resolution aligned H&E dimensions in pixels (width, height).
HE_FULL_WH = (28868, 47337)

N_CELLS = 170_057
N_GENES = 18_028

# --------------------------------------------------------------------------- #
# Cluster annotation (01_annotate_clusters.py)
# --------------------------------------------------------------------------- #

#: Marker sets for the coarse cell types the 34 graphclust clusters are merged into.
#: Order is the canonical plotting/legend order.
CELL_TYPE_MARKERS: dict[str, list[str]] = {
    "Tumour epithelial": ["EPCAM", "KRT8", "KRT18", "ERBB2", "ESR1"],
    # A cell *state*, not a lineage -- see ANNOT_STATE_TYPES below.
    "Proliferating tumour": ["MKI67", "TOP2A", "CENPF", "NUSAP1", "PLK1"],
    "Myoepithelial": ["KRT14", "KRT5", "ACTA2", "TP63"],
    "Fibroblast": ["COL1A1", "DCN", "LUM", "PDGFRB"],
    "Endothelial": ["PECAM1", "VWF", "CDH5"],
    "Perivascular": ["RGS5", "NOTCH3"],
    "T cell": ["CD3D", "CD3E", "CD2", "TRBC2"],
    "NK": ["NKG7", "GNLY"],
    "B cell": ["MS4A1", "CD79A", "BANK1"],
    "Plasma cell": ["MZB1", "JCHAIN", "IGHG1"],
    # "Myeloid" was one bucket until the graphclust evidence was inspected: cluster
    # 15 is unambiguously cDC (CD1C/CLEC10A/FCER1A/IRF8) while 24 and 26 are the
    # LYVE1+/FOLR2+/MRC1+ perivascular macrophage flavour. An immunology audience
    # cares about the difference, and the data supports it, so they are separate.
    "Macrophage": ["CD68", "CD14", "LYZ", "C1QA", "MRC1", "CSF1R"],
    "Dendritic cell": ["ITGAX", "CD1C", "CLEC10A", "FCER1A"],
    "Mast": ["TPSAB1", "CPA3"],
}

CELL_TYPES = list(CELL_TYPE_MARKERS)

#: Label used when the evidence guards refuse to name a cluster.
UNASSIGNED_LABEL = "Unassigned"

#: Types that describe a *state* rather than a lineage. A state is only called when
#: its markers actually appear among the cluster's own top DE genes: cycling genes
#: sit moderately high in every epithelial cluster relative to the whole
#: transcriptome, so a plain argmax hands "Proliferating tumour" to clusters that
#: are simply epithelial. When a state type wins without that direct evidence it is
#: dropped from the candidate list and the next-best type is taken.
ANNOT_STATE_TYPES = frozenset({"Proliferating tumour"})

#: How deep into a cluster's significant-DE ranking to look for a type's markers.
ANNOT_MARKER_TOP_N = 50

#: Doublet / mixed detection: if markers of two or more different types show up in
#: this many top DE genes, the cluster is called Mixed rather than being handed to
#: whichever scored a hair higher.
ANNOT_MIXED_TOP_N = 10

#: Short names used to build a "Mixed (a/b)" label.
CELL_TYPE_SHORT: dict[str, str] = {
    "Tumour epithelial": "tumour",
    "Proliferating tumour": "cycling",
    "Myoepithelial": "myoepithelial",
    "Fibroblast": "fibroblast",
    "Endothelial": "endothelial",
    "Perivascular": "perivascular",
    "T cell": "T",
    "NK": "NK",
    "B cell": "B",
    "Plasma cell": "plasma",
    "Macrophage": "macrophage",
    "Dendritic cell": "DC",
    "Mast": "mast",
}

#: Explicitly interrogated in 01 and reported whatever the answer, because "no B
#: cells anywhere" is a claim a Tutorial should only make on evidence.
BCELL_CHECK_GENES = ["MS4A1", "CD79A", "CD79B", "BANK1"]


#: Separator inside a "Mixed (a+b)" label. NOT "/" -- a cell-type string ends up
#: as a dict key in ``uns`` and as a zarr/HDF5 group name, and anndata already
#: warns that forward slashes will be disallowed in h5 stores.
MIXED_SEP = "+"


def mixed_label(a: str, b: str) -> str:
    return (
        f"Mixed ({CELL_TYPE_SHORT.get(a, a)}{MIXED_SEP}{CELL_TYPE_SHORT.get(b, b)})"
    )

#: A cluster whose best score beats the runner-up by less than this is flagged
#: low-confidence rather than silently forced onto the argmax.
ANNOT_LOW_CONF_MARGIN = 0.05

#: How many genes to list per cluster in the sign-off CSV.
ANNOT_TOP_N_GENES = 10

#: graphclust is the clustering used for annotation; kmeans_10 is carried along in
#: obs so a Tutorial can show that clustering choice is a knob.
GRAPHCLUST_KEY = "graphclust"
KMEANS_KEY = "kmeans_10"

# --------------------------------------------------------------------------- #
# Marker panel carried in X (03/04)
# --------------------------------------------------------------------------- #

#: Immunology / TME genes added on top of CELL_TYPE_MARKERS so the Staged datasets
#: can support the niche Tutorial without shipping all 18,028 targets.
EXTRA_PANEL_GENES: list[str] = [
    # pan-immune and T-cell states
    "PTPRC", "CD4", "CD8A", "FOXP3", "IL7R", "CCL5", "GZMK",
    # carried so a Tutorial can re-ask the "are there any B cells?" question
    # itself rather than taking 01's answer on trust
    "CD79B",
    # chemokines that structure the TME
    "CXCL9", "CXCL13", "CXCL12",
    # antigen presentation / macrophage polarisation / granulocyte
    "HLA-DRA", "CD163", "S100A8",
    # breast-epithelial identity
    "GATA3", "FOXA1", "PGR", "KRT7", "KRT19",
    # matrix / activated stroma
    "POSTN", "FN1", "TAGLN",
]


def _ordered_unique(items):
    seen, out = set(), []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


#: The ~60-gene dense float32 panel stored as X in both Staged datasets.
PANEL_GENES: list[str] = _ordered_unique(
    [g for genes in CELL_TYPE_MARKERS.values() for g in genes] + EXTRA_PANEL_GENES
)

# --------------------------------------------------------------------------- #
# Ligand-receptor panel (06_build_cci_table.py)
# --------------------------------------------------------------------------- #

#: connectomeDB2020, as shipped inside the stlearn wheel. Fetched from GitHub at
#: build time rather than vendored: the Workshop repo is MIT and redistributing a
#: third-party curated database under it is not ours to do. Only the resolved gene
#: list -- a list of HGNC symbols, which is a fact and not the database -- is
#: committed, as CCI_PANEL_GENES_TXT.
CONNECTOMEDB_BASE = (
    "https://raw.githubusercontent.com/BiomedicalMachineLearning/stLearn/"
    "master/stlearn/tl/cci/databases"
)
CONNECTOMEDB_FILES = {
    "connectomeDB2020_lit": f"{CONNECTOMEDB_BASE}/connectomeDB2020_lit.txt",
    "connectomeDB2020_put": f"{CONNECTOMEDB_BASE}/connectomeDB2020_put.txt",
}

#: WHY A SECOND, WIDER PANEL EXISTS AT ALL.
#: PANEL_GENES above is 69 genes chosen to name cell types. Intersected with
#: connectomeDB2020 it yields exactly FOUR complete literature ligand-receptor
#: pairs (CXCL12-CD4, EPCAM-EPCAM, MRC1-PTPRC, PTPRC-MRC1), which is not an
#: analysis. The Atera run is whole-transcriptome, so the genes are there; they
#: were simply not carried into the Crop. 06 carries them into their own artifact
#: rather than widening the Crop, so the published atera_crop.zarr.zip -- and the
#: two Tutorials that read it -- are untouched.
#:
#: Measured on the 16,006 Crop cells: 1,675 of connectomeDB's genes are present in
#: the 18,028 Atera targets, giving 2,162 literature pairs whose ligand AND
#: receptor are each detected in at least 20 cells.
CCI_USE_DATABASES = ["connectomeDB2020_lit", "connectomeDB2020_put"]

#: A gene must be detected in at least this many Crop cells to enter the panel.
#: Whole-transcriptome Xenium carries a long tail of near-dropout targets, and a
#: ligand nobody expresses only inflates the multiple-testing burden. Deliberately
#: loose -- stlearn's own `min_spots` does the real filtering at analysis time, and
#: the point of the artifact is to leave that knob in a Participant's hands.
CCI_MIN_CELLS_DETECTED = 10

#: Counts are stored sparse (CSR). Over these genes the Crop is ~6.7% dense, so
#: sparse is ~14 MB against ~107 MB dense, and both scanpy and stlearn read it.
#: The Tutorial densifies after subsetting, because stlearn's get_spot_lrs calls
#: adata.to_df().
CCI_STORE_SPARSE = True

# --------------------------------------------------------------------------- #
# Crop selection (02_pick_crop.py)
# --------------------------------------------------------------------------- #

CROP_SIZE_UM = 2000.0
CROP_STRIDE_UM = 250.0

#: Shannon entropy of the cell-type composition, normalised by log(n_types), that a
#: candidate window must reach before it is allowed to compete on cell count. This
#: is the whole point of the scan: the densest window on the slide is pure tumour,
#: which would gut the niche Tutorial.
CROP_ENTROPY_FLOOR = 0.75

#: If no window clears the floor, fall back to this quantile of the observed
#: entropy distribution (and say so loudly) rather than silently returning nothing.
CROP_ENTROPY_FALLBACK_Q = 0.98

#: Cell types with fewer than this many cells in a window do not count towards the
#: entropy -- stops a handful of stray cells inflating the diversity score.
CROP_MIN_CELLS_PER_TYPE = 25

#: A window must contain at least this many cells to be considered at all.
CROP_MIN_CELLS = 5_000

CROP_TOP_N = 10

#: Minimum centre-to-centre separation, in micrometres, between the candidates
#: reported in the top-N list. Without it the top 10 are ten copies of the same
#: window shifted by one stride.
CROP_NMS_UM = 1000.0

#: Side length of the `he_zoom` sub-window picked inside the Crop -- the most
#: cell-type-diverse 300 um square, so the zoom shows an interface rather than a
#: uniform sheet of tumour.
CROP_ZOOM_SEARCH_STRIDE_UM = 50.0

# --------------------------------------------------------------------------- #
# Crop rendering (04_build_crop.py)
# --------------------------------------------------------------------------- #

#: The Crop's `he` overview is read straight off pyramid level 2 of
#: HE_PYRAMID_TIF, i.e. an exact 4x downsample, rather than resampled to a round
#: number. That keeps the scale transform exact (4 * HE_PX_UM) instead of
#: introducing a resampling error, and lands at ~1.1 um/px -- the "~1 um/px"
#: the overview needs.
CROP_OVERVIEW_LEVEL = 2
CROP_OVERVIEW_DOWNSAMPLE = 2 ** CROP_OVERVIEW_LEVEL

#: Micrometres per pixel of the downsampled H&E overview covering the whole Crop.
CROP_OVERVIEW_UM_PX = HE_PX_UM * CROP_OVERVIEW_DOWNSAMPLE

#: Side length in micrometres of the native-resolution `he_zoom` element.
CROP_ZOOM_UM = 300.0

#: `he_zoom` stays at the native H&E scale.
CROP_ZOOM_UM_PX = HE_PX_UM

#: Every element lives in one coordinate system, in micrometres, so images, shapes
#: and table overlay with no transform work in the notebook.
COORD_SYSTEM = "global"

# --------------------------------------------------------------------------- #
# Origins (05_make_manifest.py / upload_to_origins.sh)
# --------------------------------------------------------------------------- #

HF_REPO_ID = "xiao233333/asi-fimsa-workshop-2026"
HF_REVISION = "main"
GDRIVE_FOLDER_ID = "1ELxQjcswMcO7w4N6Z74u_2Yt3F5UWHbm"


def hf_url(filename: str) -> str:
    return (
        f"https://huggingface.co/datasets/{HF_REPO_ID}/resolve/"
        f"{HF_REVISION}/{filename}"
    )


def gdrive_folder_url() -> str:
    return f"https://drive.google.com/drive/folders/{GDRIVE_FOLDER_ID}"


#: Artifacts a Tutorial downloads, in the order the manifest lists them.
STAGED_ARTIFACTS = [
    WHOLESLIDE_H5AD,
    CROP_ZARR_ZIP,
    CCI_LR_H5AD,
]

# --------------------------------------------------------------------------- #
# Housekeeping
# --------------------------------------------------------------------------- #


def ensure_dirs() -> None:
    for d in (WORK_DIR, ANALYSIS_DIR, FIG_DIR, OUT_DIR):
        d.mkdir(parents=True, exist_ok=True)


def describe() -> str:
    lines = [
        f"ATERA_ROOT = {ATERA_ROOT}",
        f"WORK_DIR   = {WORK_DIR}",
        f"OUT_DIR    = {OUT_DIR}",
        f"HE_PX_UM   = {HE_PX_UM}",
        f"panel      = {len(PANEL_GENES)} genes",
        f"cell types = {len(CELL_TYPES)}",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    print(describe())


# --------------------------------------------------------------------------- #
# Shared figure palette
# --------------------------------------------------------------------------- #

#: One colour per cell type, reused by 01/02/04 so every figure and the notebook
#: legend agree. Tumour/stroma warm, immune cool, vessels green.
CELL_TYPE_COLORS: dict[str, str] = {
    "Tumour epithelial": "#c1272d",
    "Proliferating tumour": "#7a0c12",
    "Myoepithelial": "#f19a3e",
    "Fibroblast": "#8c6d3f",
    "Endothelial": "#2e8b57",
    "Perivascular": "#7fbf7b",
    "T cell": "#1f6fb4",
    "NK": "#6baed6",
    "B cell": "#6a3d9a",
    "Plasma cell": "#b07aa1",
    "Macrophage": "#00868b",
    "Dendritic cell": "#4dc4c9",
    "Mast": "#e377c2",
    "Unassigned": "#bdbdbd",
}

#: Anything the annotation invents at run time (a "Mixed (a/b)" label) gets this.
OTHER_COLOR = "#9e9e9e"


def cell_type_color(t: str) -> str:
    return CELL_TYPE_COLORS.get(t, OTHER_COLOR)


def cell_type_order(observed) -> list[str]:
    """Canonical plotting order: known types first, then Mixed, then Unassigned."""
    obs = set(observed)
    known = [t for t in CELL_TYPES if t in obs]
    mixed = sorted(t for t in obs if t.startswith("Mixed"))
    tail = [t for t in (UNASSIGNED_LABEL,) if t in obs]
    rest = [t for t in obs if t not in set(known) | set(mixed) | set(tail)]
    return known + mixed + sorted(rest) + tail

#: Genes whose peak per-cluster mean count is below this are dropped before the
#: log2FC ranking in 01 -- whole-transcriptome Xenium is full of near-zero targets
#: whose fold changes are pure noise.
ANNOT_MIN_MEAN_COUNTS = 0.01

#: Adjusted p-value cut for the top-N gene listing in the sign-off CSV.
ANNOT_MAX_ADJ_P = 0.05

#: An assignment whose own score is below this is flagged low-confidence even when
#: it beats the runner-up comfortably: on whole-transcriptome data the top of a
#: raw log2FC ranking is dominated by near-zero targets, which pushes real markers
#: down and drags the score toward 0.5 for clusters with no crisp identity.
ANNOT_MIN_SCORE = 0.70

#: Second, independent evidence axis: the mean rank percentile of the assigned
#: type's markers by *mean counts* (not fold change). Catches clusters that win a
#: type on fold change alone while the markers are barely detected -- the classic
#: false Mast call driven by TPSAB1, which is a near-dropout target here.
ANNOT_MIN_EXPR_PCT = 0.70

#: Placeholder written into top10_genes when a cluster has no gene passing
#: ANNOT_MAX_ADJ_P at all.
ANNOT_NO_DE_SENTINEL = "(no significant DE genes)"
