# Rewrite rather than fork gml-teaching-2026

The Workshop's three Tutorials reuse code and prose from `gml-teaching-2026`, but are
authored fresh rather than maintained as a fork. The parent course targets an Apptainer
image on Bunya with baked in-house data at `/data/module2/data`; the Workshop targets
Google Colab with public data, which changes the environment, the data access, the
dependency pins, and the datasets themselves — leaving almost nothing that a diff
against the parent would usefully track.

## Consequences

Fixes do not flow between the two repos automatically. When a Tutorial is derived from a
parent notebook, say so in the notebook's header so the lineage stays findable.
