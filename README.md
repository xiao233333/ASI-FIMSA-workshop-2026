# ASI-FIMSA Spatial Omics Workshop 2026

A two-hour, hands-on introduction to spatial omics for immunologists, run at the
ASI-FIMSA meeting. Everything happens in your browser through Google Colab — there is
nothing to install, and you do not need to be a Python programmer. We look at **one
tissue, breast cancer, through three different technologies**, so that every difference
you see on screen comes from the technology rather than from the sample. You will read
and plot the data yourself, find the tissue niches that make up a tumour
microenvironment, and finish by training a small Vision Transformer that predicts gene
expression straight from an H&E image. Four Tutorials, each self-contained, each a
single notebook you open with one click.

## The Tutorials

Click a badge to open that Tutorial in Google Colab. Start with the setup check
**before** you arrive.

| | Tutorial | What you do | Rough time |
|---|---|---|---|
| [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/xiao233333/ASI-FIMSA-workshop-2026/blob/main/notebooks/00_setup_check.ipynb) | **00 · Setup check** | Confirms Colab can install the packages and reach the data. Run it at home, not in the room. | ~10 min |
| [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/xiao233333/ASI-FIMSA-workshop-2026/blob/main/notebooks/01_read_and_visualise.ipynb) | **01 · Read and visualise** | Load and plot all three platforms — Visium spots, Xenium cells, and the whole-transcriptome Atera run — and see what each one can and cannot resolve. | ~35 min |
| [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/xiao233333/ASI-FIMSA-workshop-2026/blob/main/notebooks/02_niche_analysis.ipynb) | **02 · Niche analysis** | Find tissue niches in the tumour microenvironment — immune infiltration, tumour boundary, stroma — from which cells sit next to which. | ~35 min |
| [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/xiao233333/ASI-FIMSA-workshop-2026/blob/main/notebooks/03_cell_cell_interaction_liana.ipynb) | **03 · Cell–cell interaction** | Run LIANA+'s consensus ligand–receptor test on the same cells — and watch a gene panel decide, before you start, which questions you are allowed to ask. | ~30 min |
| [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/xiao233333/ASI-FIMSA-workshop-2026/blob/main/notebooks/04_vit_gene_expression.ipynb) | **04 · ViT for gene expression** | Train a small Vision Transformer that predicts gene expression from H&E morphology alone, then look honestly at which genes it gets right and which it does not. | ~40 min |

More material is written here than fits a two-hour slot; on the day we work through as
much as the time allows, and the rest is yours to finish afterwards.

## Before you arrive

Please do these three things at home — they take about ten minutes, and they save the
whole room waiting on downloads.

1. **Run `00_setup_check.ipynb`.** Open it with the badge above and run every cell from
   top to bottom (`Runtime → Run all`). It installs the packages the Workshop uses and
   fetches a small slice of each dataset, so any problem shows up now rather than in
   the session.
2. **Expect roughly 300 MB of downloads** during the setup check. Use a connection you
   are happy to do that on — hotel or conference wifi on the day may not cooperate.
3. **Have a Google account you are logged into.** Colab requires one. It is free, and
   nothing you run here is saved to your Google Drive unless you ask it to be.

A **GPU is optional.** Every Tutorial is written to run on Colab's ordinary free CPU
runtime. Tutorial 03 will use a GPU if Colab happens to give you one, and simply takes a
little longer if not. There is no need to hunt for one, and no need to pay for anything.

**On the day, Tutorial 03 downloads a further ~1.8 GB** — the full-resolution H&E image
for the Visium sample, which is what its Vision Transformer actually learns from. This
does *not* touch the wifi in the room: Colab pulls it over Google's network from 10x's
CDN, and it usually takes well under a minute. Nothing to do in advance.

If the setup check fails, please open an issue on this repository, or bring the error
message with you and we will sort it out at the start of the session.

## The datasets

One disease — human breast carcinoma — measured three ways.

These are **three different FFPE specimens**, not serial sections of one block. They
are matched by disease and preservation, which is enough to make the technologies
comparable, but a difference you see between two panels can still be a difference
between two tumours. The Tutorials say so where it matters.

| Platform | Sample | Resolution | Plex | Where it comes from |
|---|---|---|---|---|
| **Visium** | `V1_Breast_Cancer_Block_A_Section_1` | 55 µm spots (tens of cells each) | Whole transcriptome | Downloaded live from 10x Genomics' public CDN, including the 1.8 GB full-resolution H&E for Tutorial 03 |
| **Xenium** | `Xenium_FFPE_Human_Breast_Cancer_Rep1` | Single cell | 313 genes (pre-designed breast panel) | Downloaded live from 10x Genomics' public CDN |
| **Atera** | Whole-transcriptome Xenium preview (`chemistry_version: "Atera v1"`) | Single cell | 18,028 genes, 170,057 cells | Prepared Crop staged in the Hugging Face dataset repo [`xiao233333/asi-fimsa-workshop-2026`](https://huggingface.co/datasets/xiao233333/asi-fimsa-workshop-2026) |

**Atera** is 10x's pre-release chemistry behind a whole-transcriptome Xenium run on a
Gen2 prototype instrument — single-cell resolution *and* the whole transcriptome, rather
than the few-hundred-gene targeted panels. The full slide is far too large for a Colab
session, so the Tutorials work on a prepared Crop: one spatial sub-region, small enough
that images and cell boundaries load in seconds. The scripts that build it live in
`prep/` and are described below.

### Attribution

All three datasets are generated and made available by **10x Genomics**. We are
enormously grateful for their public data, without which this Workshop would not exist.
Please credit 10x Genomics if you reuse anything here.

The Xenium breast cancer dataset accompanies:

> Janesick, A., Shelansky, R., Gottscho, A.D. *et al.* **High resolution mapping of the
> tumor microenvironment using integrated single-cell, spatial and in situ analysis.**
> *Nature Communications* **14**, 8353 (2023).
> https://www.nature.com/articles/s41467-023-43458-x

Please cite that paper if you use the Xenium breast data in your own work.

> **Note on licensing:** the licence terms for the Atera preview dataset are still being
> confirmed with 10x Genomics. This section may be updated before the Workshop.

## For collaborators and agents

### Repo layout

```
notebooks/               The five Colab notebooks. Tracked in git; outputs are not.
  00_setup_check.ipynb
  01_read_and_visualise.ipynb
  02_niche_analysis.ipynb
  03_cell_cell_interaction_liana.ipynb
  04_vit_gene_expression.ipynb
prep/                    Prep scripts: vendor output -> Staged dataset.
verify/                  Headless notebook execution, for checking the Tutorials still run.
requirements-colab.txt   The Colab pin set, re-verified in real Colab before delivery.
docs/adr/                Architecture decision records.
CONTEXT.md               Glossary. Read this first.
PROJECT_CONTEXT.md       Durable project memory: goals, paths, stack, change log.
```

### How it is built

- **`prep/` runs on Bunya, never in Colab.** These scripts read the raw vendor bundles
  from RDM (tens of gigabytes) and write the small Staged datasets that the Tutorials
  download at run time. A Participant never opens them. Paths and Slurm conventions are
  in `PROJECT_CONTEXT.md`.
- **`verify/` runs the notebooks headlessly** so we find out that a Tutorial has broken
  before forty people do. Its executed output lands in `verify/out/`, which is
  gitignored.
- **Notebooks are tracked, their outputs are not.** Clear cell outputs before
  committing — commit the notebook, not what it printed.
- **The `spatialdata` family is pinned as a set.** `spatialdata`, `spatialdata-io`,
  `spatialdata-plot`, `squidpy` and `sopa` are bumped together — mixing majors across
  them is exactly the failure this pin set exists to prevent. See ADR-0003.

### Where to start reading

1. **`CONTEXT.md`** — the vocabulary. Workshop, Tutorial, Participant, Staged dataset,
   Crop, Prep script, Atera all mean something specific here.
2. **`PROJECT_CONTEXT.md`** — what is built, what is next, and every important path.
3. **`docs/adr/`** — the three decisions that shape everything else: why this is a
   rewrite rather than a fork of `gml-teaching-2026`, why there is no R, and why the
   modern stack on Python 3.12.

## Credits and licence

This Workshop is derived from the **`gml-teaching-2026`** course material of the
**Genomics and Machine Learning Lab, QIMR Berghofer Medical Research Institute | The University of Queensland**. Tutorial 02's
neighbourhood analysis and Tutorial 03's Vision Transformer both began as notebooks from
that course; they were rewritten for Colab and for public data rather than forked, and
each notebook names its parent in its header. Our thanks to the lab for the original
material.

Datasets are courtesy of 10x Genomics — see **Attribution** above.

**Data licences** are settled and recorded in [`DATA_LICENCE.md`](DATA_LICENCE.md). The
Atera dataset is **CC BY 4.0**, so the derived Staged datasets we host are redistributed
under the same terms with attribution to 10x Genomics. The Visium and Xenium data are
downloaded from 10x directly and are not redistributed here.

**Code and teaching material** are [MIT licensed](LICENSE) — reuse, adapt and teach from
them freely. One carve-out: `voronoi_finite_polygons_2d()` in `notebooks/voronoi.py` is
adapted from a 2013 Stack Overflow answer and is CC BY-SA 3.0 rather than MIT, as recorded
in the LICENSE file's Exceptions section.
