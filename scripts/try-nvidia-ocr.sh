#!/usr/bin/env bash
# Try NVIDIA NIM Image OCR (NeMo Retriever OCR) against hosted or local endpoint.
# Docs: https://docs.nvidia.com/nim/ingestion/image-ocr/latest/api-reference.html
#
# Usage:
#   export NVIDIA_API_KEY=nvapi-...   # required for hosted
#   ./scripts/try-nvidia-ocr.sh
#   ./scripts/try-nvidia-ocr.sh path/to/image.png
#   API_ENDPOINT=http://localhost:8000 ./scripts/try-nvidia-ocr.sh
set -euo pipefail

IMAGE_SOURCE="${1:-https://assets.ngc.nvidia.com/products/api-catalog/nemo-retriever/image-ocr/example-1.png}"
MERGE_LEVEL="${MERGE_LEVEL:-word}"

# Hosted catalog (works on Mac). Local NIM uses http://localhost:8000 + /v1/ocr.
if [[ -n "${API_ENDPOINT:-}" ]]; then
  URL="${API_ENDPOINT%/}/v1/ocr"
  AUTH_HEADER=()
else
  URL="${OCR_INVOKE_URL:-https://ai.api.nvidia.com/v1/cv/nvidia/nemotron-ocr-v2}"
  if [[ -z "${NVIDIA_API_KEY:-}" ]]; then
    echo "Set NVIDIA_API_KEY (nvapi-...) for hosted OCR, or API_ENDPOINT=http://localhost:8000 for a local NIM." >&2
    exit 1
  fi
  AUTH_HEADER=(-H "Authorization: Bearer ${NVIDIA_API_KEY}")
fi

EXT="${IMAGE_SOURCE##*.}"
EXT="${EXT%%\?*}"
case "$(printf '%s' "$EXT" | tr '[:upper:]' '[:lower:]')" in
  jpg|jpeg) MIME="image/jpeg" ;;
  png) MIME="image/png" ;;
  *) echo "Supported formats: png, jpeg/jpg (got .${EXT})" >&2; exit 1 ;;
esac

IMG_TMP=$(mktemp)
PAYLOAD_TMP=$(mktemp)
trap 'rm -f "$IMG_TMP" "$PAYLOAD_TMP"' EXIT

if [[ "$IMAGE_SOURCE" == http* ]]; then
  curl -fsSL "$IMAGE_SOURCE" -o "$IMG_TMP"
else
  cp "$IMAGE_SOURCE" "$IMG_TMP"
fi

# macOS base64 has no -w 0; strip newlines for both GNU and BSD.
BASE64_IMAGE=$(base64 < "$IMG_TMP" | tr -d '\n')

python3 - "$PAYLOAD_TMP" "$MIME" "$BASE64_IMAGE" "$MERGE_LEVEL" <<'PY'
import json, sys
out, mime, b64, merge = sys.argv[1:5]
payload = {
    "input": [{"type": "image_url", "url": f"data:{mime};base64,{b64}"}],
    "merge_levels": [merge],
}
with open(out, "w") as f:
    json.dump(payload, f)
PY

echo "POST ${URL}" >&2
echo "image: ${IMAGE_SOURCE}" >&2
echo "merge_levels: [${MERGE_LEVEL}]" >&2

curl -sS -X POST "$URL" \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  "${AUTH_HEADER[@]}" \
  --data-binary @"$PAYLOAD_TMP" | python3 -m json.tool
