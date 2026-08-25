# ASI-FIMSA Workshop

Teaching material for a hands-on spatial-omics session at the ASI-FIMSA meeting,
delivered as Google Colab notebooks. Derived from, but not a fork of, the
`gml-teaching-2026` course.

## Language

**Workshop**:
The two-hour hands-on session at ASI-FIMSA. More material is authored than fits,
and trimmed to the slot before delivery.
_Avoid_: course, module

**Tutorial**:
One self-contained Colab notebook covering one topic end to end. There are three.
_Avoid_: notebook (when referring to the teaching unit), practical, lab

**Participant**:
An attendee running a Tutorial in their own Colab session. Assumed to be an
immunologist with minimal Python.
_Avoid_: student, user, attendee

**Staged dataset**:
A prepared data artifact stored in the workshop Google Drive folder that a
Tutorial downloads at run time. Distinct from data a Tutorial fetches directly
from its public origin (e.g. `scanpy`'s 10x Visium downloader).
_Avoid_: input data, cached data

**Atera**:
The pre-release 10x chemistry (`chemistry_version: "Atera v1"`) behind the
whole-transcriptome Xenium run used in the Workshop — ~18k targets on a Gen2
prototype instrument, as opposed to the few-hundred-gene targeted Xenium panels.
_Avoid_: Xenium v2, new Xenium, WTA (alone — "Xenium WTA" is fine)

**Crop**:
The single spatial sub-region of a slide that a Tutorial actually renders —
chosen so imagery and boundaries fit a Colab session. Distinct from the
whole-slide cell table, which a Tutorial may load in full without images.
_Avoid_: ROI, tile (a tile is the per-spot H&E patch fed to the ViT), subset

**Prep script**:
Code in `prep/` that turns vendor output into a Staged dataset. Runs on Bunya,
never in Colab, and is never opened by a Participant.
_Avoid_: preprocessing, pipeline
