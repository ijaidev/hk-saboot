#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RAW="$(cat proof/demo/raw_video_path.txt | tr -d '\n')"
TOTAL="$(python3 - <<'PY'
import json
from pathlib import Path
data = json.loads(Path('proof/demo/timeline.json').read_text())
print(f"{data['total_seconds']:.3f}")
PY
)"
TRIM_START="1.5"

if [ ! -f "$RAW" ]; then
  echo "raw video missing; run node tools/record_demo.js first" >&2
  exit 1
fi

ffmpeg -y -loglevel error -i proof/demo/voiceover.wav \
  -af "loudnorm=I=-16:TP=-1.5:LRA=11" -ar 48000 -ac 1 \
  proof/demo/voiceover_norm.wav

ffmpeg -y -loglevel error -i "$RAW" -i proof/demo/voiceover_norm.wav \
  -filter_complex "[0:v]trim=start=${TRIM_START}:duration=${TOTAL},setpts=PTS-STARTPTS,subtitles=proof/demo/captions.ass[v]" \
  -map "[v]" -map 1:a \
  -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p \
  -c:a aac -b:a 128k -movflags +faststart \
  -t "$TOTAL" proof/demo/saboot-demo.mp4

ffprobe -v error -show_entries format=duration,size \
  -show_entries stream=width,height,codec_name \
  -of default=nw=1 proof/demo/saboot-demo.mp4
