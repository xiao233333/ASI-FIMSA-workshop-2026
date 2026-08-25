#!/usr/bin/env bash
# =============================================================================
#  LICENCE GATE -- CLEARED 2026-08-25, AND STILL A DELIBERATE ACT.
#
#  The Atera bundle is a 10x PRE-RELEASE dataset ("Atera v1" chemistry, Gen2
#  prototype instrument). Its redistribution licence was confirmed as CC BY 4.0
#  on 2026-08-25; the terms, the required attribution and the source URL are
#  recorded in DATA_LICENCE.md, in prep/hf_dataset_card.md, and in the `licence`
#  block of prep/manifest.json. Both origins below are public: a Hugging Face
#  dataset repo and a Google Drive folder shared with Workshop Participants.
#
#  ACK_ATERA_LICENCE is deliberately still required. Publishing derived data is
#  the thing that cannot be taken back, so every upload stays an explicit act
#  rather than something a stray `bash prep/*.sh` can do. Before running, satisfy
#  yourself that:
#    1. The artifacts about to be uploaded are the ones you meant to build.
#    2. DATA_LICENCE.md and the dataset card still describe them accurately --
#       in particular, that any NEW artifact is covered by the same CC BY 4.0
#       grant and carries its attribution.
#    3. prep/manifest.json is current (run 05_make_manifest.py after any build).
#
#  Then:  ACK_ATERA_LICENCE=yes bash prep/upload_to_origins.sh
# =============================================================================
#
# Uploads the Staged datasets to their two origins:
#   PRIMARY  Hugging Face dataset repo  xiao233333/asi-fimsa-workshop-2026
#   MIRROR   Google Drive folder        1ELxQjcswMcO7w4N6Z74u_2Yt3F5UWHbm
#
# Afterwards it rewrites prep/manifest.json so the Google Drive per-file ids
# (which gdown needs, and which only exist after the upload) are filled in.
#
# Requirements: `hf` (huggingface_hub CLI) authenticated via `hf auth login`,
# and `rclone` configured with a remote named in $RCLONE_REMOTE for Drive.
#
# Usage:
#   ACK_ATERA_LICENCE=yes bash prep/upload_to_origins.sh [--dry-run]

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="${PREP_OUT:-/scratch/project_mnt/S0010/Xiao/asi_fimsa_workshop/staged}"
HF_REPO="xiao233333/asi-fimsa-workshop-2026"
GDRIVE_FOLDER_ID="1ELxQjcswMcO7w4N6Z74u_2Yt3F5UWHbm"
RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive}"
ARTIFACTS=(atera_wholeslide_cells.h5ad atera_crop.zarr.zip atera_crop_lr.h5ad)

DRY_RUN=0
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

# -- the gate ---------------------------------------------------------------- #
if [[ "${ACK_ATERA_LICENCE:-}" != "yes" ]]; then
  cat >&2 <<'MSG'
REFUSING TO UPLOAD.

Uploading publishes derived Atera data to two public origins, which cannot be
undone. The licence itself is settled (CC BY 4.0, see DATA_LICENCE.md); this
gate is here so the upload is always an explicit decision. Read the header of
this script, check that manifest.json is current, then re-run with:

    ACK_ATERA_LICENCE=yes bash prep/upload_to_origins.sh

MSG
  exit 1
fi

# -- preflight --------------------------------------------------------------- #
echo "== preflight =="
for f in "${ARTIFACTS[@]}"; do
  [[ -f "$OUT_DIR/$f" ]] || { echo "missing: $OUT_DIR/$f -- run the build first" >&2; exit 1; }
  printf '  %-32s %s\n' "$f" "$(du -h "$OUT_DIR/$f" | cut -f1)"
done
[[ -f "$HERE/manifest.json" ]] || { echo "missing prep/manifest.json -- run 05_make_manifest.py" >&2; exit 1; }

echo "  verifying sha256 against prep/manifest.json"
python - "$HERE/manifest.json" "$OUT_DIR" <<'PY'
import hashlib, json, sys
from pathlib import Path
manifest, out_dir = json.loads(Path(sys.argv[1]).read_text()), Path(sys.argv[2])
for a in manifest["artifacts"]:
    p = out_dir / a["name"]
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(8 << 20):
            h.update(chunk)
    if h.hexdigest() != a["sha256"]:
        raise SystemExit(f"sha256 mismatch for {a['name']} -- rerun 05_make_manifest.py")
    print(f"    ok {a['name']}")
PY

if (( DRY_RUN )); then
  echo "== dry run: stopping before any upload =="
  exit 0
fi

# -- 1. Hugging Face (primary) ----------------------------------------------- #
echo "== Hugging Face: $HF_REPO =="
hf repo create "$HF_REPO" --repo-type dataset --exist-ok
for f in "${ARTIFACTS[@]}"; do
  hf upload "$HF_REPO" "$OUT_DIR/$f" "$f" --repo-type dataset \
    --commit-message "Add $f (ASI-FIMSA 2026 Staged dataset)"
done
# Ship the provenance next to the data.
hf upload "$HF_REPO" "$HERE/manifest.json" manifest.json --repo-type dataset
hf upload "$HF_REPO" "$HERE/atera_cluster_annotation.csv" \
  atera_cluster_annotation.csv --repo-type dataset
hf upload "$HF_REPO" "$HERE/cci_panel_genes.txt" \
  cci_panel_genes.txt --repo-type dataset
hf upload "$HF_REPO" "$HERE/crop_window.json" crop_window.json --repo-type dataset
hf upload "$HF_REPO" "$HERE/hf_dataset_card.md" README.md --repo-type dataset \
  --commit-message "Dataset card: CC BY 4.0 attribution, contents, caveats"

# -- 2. Google Drive (mirror) ------------------------------------------------- #
# The mirror is optional: it needs an interactively-configured rclone remote. If one is
# not present, skip it rather than failing after the primary origin already succeeded.
if [[ "${SKIP_GDRIVE:-}" == "1" ]] || ! rclone listremotes 2>/dev/null | grep -q "^${RCLONE_REMOTE}:"; then
  echo "== Google Drive mirror SKIPPED: no rclone remote '${RCLONE_REMOTE}' configured =="
  echo "   Configure with 'rclone config' (interactive), then re-run to add the mirror."
  echo "   The Hugging Face primary origin is live; Tutorials will work without the mirror."
  exit 0
fi
echo "== Google Drive mirror: $GDRIVE_FOLDER_ID =="
for f in "${ARTIFACTS[@]}"; do
  rclone copy "$OUT_DIR/$f" "$RCLONE_REMOTE:" \
    --drive-root-folder-id "$GDRIVE_FOLDER_ID" --progress
done

# -- 3. Fill the Drive file ids back into the manifest ----------------------- #
echo "== recording Google Drive file ids in prep/manifest.json =="
rclone lsjson "$RCLONE_REMOTE:" --drive-root-folder-id "$GDRIVE_FOLDER_ID" \
  > "${TMPDIR:-/tmp}/gdrive_listing.json"
python - "$HERE/manifest.json" "${TMPDIR:-/tmp}/gdrive_listing.json" <<'PY'
import json, sys
from pathlib import Path
mpath, lpath = Path(sys.argv[1]), Path(sys.argv[2])
manifest = json.loads(mpath.read_text())
ids = {e["Name"]: e.get("ID") for e in json.loads(lpath.read_text())}
for a in manifest["artifacts"]:
    for o in a["origins"]:
        if o["kind"] == "gdrive" and ids.get(a["name"]):
            o["file_id"] = ids[a["name"]]
            o["url"] = f"https://drive.google.com/uc?id={ids[a['name']]}"
manifest["uploaded"] = True
manifest.pop("upload_blocked_on", None)
mpath.write_text(json.dumps(manifest, indent=2) + "\n")
print("manifest updated -- commit it")
PY

echo
echo "Done. Commit the updated prep/manifest.json."
