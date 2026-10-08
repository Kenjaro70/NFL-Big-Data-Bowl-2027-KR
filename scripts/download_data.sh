#!/usr/bin/env bash
# Download the NFL Big Data Bowl 2027 competition data into data/raw/.
# Needs KAGGLE_API_TOKEN (or KAGGLE_USERNAME + KAGGLE_KEY) in the environment,
# and the competition rules accepted on kaggle.com ("Join Hackathon").
set -euo pipefail

COMP="nfl-big-data-bowl-2027"
DEST="$(cd "$(dirname "$0")/.." && pwd)/data/raw"

if [[ -z "${KAGGLE_API_TOKEN:-}" && ( -z "${KAGGLE_USERNAME:-}" || -z "${KAGGLE_KEY:-}" ) ]]; then
  echo "No Kaggle credentials: set KAGGLE_API_TOKEN, or KAGGLE_USERNAME and KAGGLE_KEY." >&2
  exit 1
fi

command -v kaggle >/dev/null || pip install -q kaggle

mkdir -p "$DEST"
kaggle competitions download -c "$COMP" -p "$DEST"
unzip -oq "$DEST/$COMP.zip" -d "$DEST"
rm -f "$DEST/$COMP.zip"
ls -lh "$DEST"
