#!/usr/bin/env bash
# crop-watermark.sh — strip the Gemini / Imagen corner watermark from generated images.
#
# The visible watermark sits in a bottom corner, so we remove a full-width strip off
# the BOTTOM (keeps the top-left origin) — clears it whether it's bottom-left or -right.
# macOS `sips` only, no dependencies. Originals are backed up before any change.
#
# Usage:
#   scripts/crop-watermark.sh [imgDir] [bottomPercent]
#   scripts/crop-watermark.sh                       # frontend/public/img, 8%
#   scripts/crop-watermark.sh frontend/public/img 10
#
# Note: removes the *visible* mark only; the invisible SynthID stays in the pixels
# (not visible, no design impact). If a watermark overlaps the subject (not a corner),
# a plain crop can't hide it — regenerate that one with the subject centered.
set -euo pipefail

DIR="${1:-frontend/public/img}"
PCT="${2:-8}"
RAW="$DIR/_originals"          # backups (git-ignored, not deployed)
SKIP_RE='^neoori-mark\.'      # transparent square glyph — never crop

[ -d "$DIR" ] || { echo "Directory not found: $DIR"; exit 1; }
mkdir -p "$RAW"
shopt -s nullglob nocaseglob

found=0
for f in "$DIR"/*.jpg "$DIR"/*.jpeg "$DIR"/*.png; do
  base="$(basename "$f")"
  [[ "$base" == .* ]] && continue
  if [[ "$base" =~ $SKIP_RE ]]; then echo "skip    $base (transparent glyph)"; continue; fi

  W=$(sips -g pixelWidth  "$f" | awk '/pixelWidth/{print $2}')
  H=$(sips -g pixelHeight "$f" | awk '/pixelHeight/{print $2}')
  [ -z "${W:-}" ] || [ -z "${H:-}" ] && { echo "skip    $base (unreadable)"; continue; }
  found=1

  newH=$(( H - (H * PCT + 50) / 100 ))   # rounded strip
  [ -f "$RAW/$base" ] || cp "$f" "$RAW/$base"   # back up original once
  sips -c "$newH" "$W" --cropOffset 0 0 "$f" --out "$f" >/dev/null
  if [[ "$base" =~ ^og-cover\. ]]; then
    # OG card size is declared in metadata (1200x630). Pad back to the original size
    # with brand navy (invisible on the navy card) so the watermark is gone AND the
    # declared OG dimensions stay correct.
    sips -p "$H" "$W" --padColor 0F1E34 "$f" --out "$f" >/dev/null 2>&1
    echo "cropped+padded $base  ${W}x${H} preserved (watermark removed, OG dims intact)"
  else
    echo "cropped $base  ${W}x${H} -> ${W}x${newH}  (-${PCT}% bottom; rendered via object-cover, safe)"
  fi
done

if [ "$found" = 0 ]; then
  echo "No images to crop in $DIR — generate them first (see docs/image-manifest.md)."
else
  echo "Done. Originals backed up in $RAW/ (re-run resets from current files, not backups)."
fi
