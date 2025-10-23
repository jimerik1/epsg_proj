#!/usr/bin/env bash
set -euo pipefail

DEST=${PROJ_DATA:-/app/proj_data}
mkdir -p "$DEST"

if ! command -v projsync >/dev/null 2>&1; then
  echo "projsync not found. Please install proj-bin inside the backend image or run manually." >&2
  exit 1
fi

echo "Downloading grids to $DEST"
projsync -s https://cdn.proj.org -r uk_os_OSTN15_NTv2_OSGBtoETRS.gsb -d "$DEST" || true
projsync -s https://cdn.proj.org -r uk_os_OSGM15_GB.tif -d "$DEST" || true

echo "Done."

