#!/usr/bin/env python3
"""Generate TTS clips, a timeline, an ASS caption file, and a padded voiceover.

No cloud TTS. eSpeak NG is a local, open-source TTS engine.
"""

from __future__ import annotations

import json
import re
import subprocess
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "proof" / "demo"
AUDIO = DEMO / "audio"
SPEED = 136
PITCH = 42
WORD_GAP = 4
PAD_SECONDS = 1.4


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def srt_time(seconds: float) -> str:
    milliseconds = int(round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def ass_time(seconds: float) -> str:
    centiseconds = int(round(seconds * 100))
    hours, remainder = divmod(centiseconds, 360_000)
    minutes, remainder = divmod(remainder, 6_000)
    secs, cents = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{cents:02d}"


def wrap_caption(text: str, width: int = 72) -> str:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= width:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return "\n".join(lines)


def split_cues(text: str, max_chars: int = 72, max_words: int = 13) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    cues: list[str] = []
    for sentence in sentences:
        words = sentence.split()
        current: list[str] = []
        for word in words:
            candidate = " ".join(current + [word])
            if current and (len(candidate) > max_chars or len(current) >= max_words):
                cues.append(" ".join(current))
                current = [word]
            else:
                current.append(word)
        if current:
            cues.append(" ".join(current))
    return cues or [text]


def pad_wav(source: Path, target: Path, target_seconds: float) -> None:
    with wave.open(str(source), "rb") as src:
        params = src.getparams()
        frames = src.readframes(src.getnframes())
    with wave.open(str(target), "wb") as dst:
        dst.setparams(params)
        dst.writeframes(frames)
        current = len(frames) / (params.framerate * params.nchannels * params.sampwidth)
        remaining = max(0.0, target_seconds - current)
        if remaining:
            silence = b"\x00" * int(params.framerate * remaining) * params.nchannels * params.sampwidth
            dst.writeframes(silence)


def main() -> int:
    scenes = json.loads((DEMO / "scenes.json").read_text())
    AUDIO.mkdir(parents=True, exist_ok=True)
    timeline = []
    cursor = 0.0
    srt_lines = []
    ass_events = []
    caption_index = 1

    for index, scene in enumerate(scenes, start=1):
        scene_id = scene["id"]
        narration = scene["narration"]
        wav_path = AUDIO / f"{index:02d}-{scene_id}.wav"
        run(
            [
                "espeak-ng",
                "-v",
                "en-us",
                "-s",
                str(SPEED),
                "-p",
                str(PITCH),
                "-g",
                str(WORD_GAP),
                "-w",
                str(wav_path),
                narration,
            ]
        )
        audio_seconds = duration(wav_path)
        scene_seconds = max(scene.get("min_ms", 0) / 1000.0, audio_seconds + PAD_SECONDS)
        end = cursor + scene_seconds
        timeline.append(
            {
                **scene,
                "audio": str(wav_path.relative_to(ROOT)),
                "audio_seconds": round(audio_seconds, 3),
                "start": round(cursor, 3),
                "end": round(end, 3),
                "duration_ms": int(round(scene_seconds * 1000)),
            }
        )

        cues = split_cues(narration)
        total_chars = sum(len(cue) for cue in cues) or 1
        cue_cursor = cursor
        for cue in cues:
            cue_seconds = audio_seconds * (len(cue) / total_chars)
            cue_end = min(cursor + audio_seconds, cue_cursor + cue_seconds)
            caption = wrap_caption(cue)
            srt_lines.append(
                f"{caption_index}\n{srt_time(cue_cursor)} --> {srt_time(cue_end)}\n{caption}\n"
            )
            ass_events.append(
                "Dialogue: 0,"
                f"{ass_time(cue_cursor)},{ass_time(cue_end)},Default,,0,0,0,,"
                f"{caption.replace(chr(10), '\\N')}"
            )
            caption_index += 1
            cue_cursor = cue_end
        cursor = end

    total = cursor
    (DEMO / "timeline.json").write_text(
        json.dumps({"scenes": timeline, "total_seconds": round(total, 3)}, indent=2) + "\n",
        encoding="utf-8",
    )
    (DEMO / "captions.srt").write_text("\n".join(srt_lines), encoding="utf-8")
    (DEMO / "voiceover.txt").write_text(
        "\n\n".join(scene["narration"] for scene in scenes) + "\n", encoding="utf-8"
    )

    ass = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1920",
        "PlayResY: 1080",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Default,DejaVu Sans,27,&H00FFFFFF,&H000000FF,&H00000000,&HA0000000,0,0,0,0,100,100,0,0,3,1.4,0,2,90,90,38,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        *ass_events,
        "",
    ]
    (DEMO / "captions.ass").write_text("\n".join(ass), encoding="utf-8")

    # Build one padded voiceover track by concatenating each scene WAV + silence.
    padded = []
    for scene in timeline:
        source = ROOT / scene["audio"]
        target = AUDIO / f"padded-{scene['id']}.wav"
        pad_wav(source, target, scene["duration_ms"] / 1000.0)
        padded.append(target)

    with wave.open(str(padded[0]), "rb") as first:
        params = first.getparams()
    with wave.open(str(DEMO / "voiceover.wav"), "wb") as out:
        out.setparams(params)
        for path in padded:
            with wave.open(str(path), "rb") as handle:
                out.writeframes(handle.readframes(handle.getnframes()))

    print(f"Total timeline: {total:.1f}s ({total/60:.2f} min)")
    for scene in timeline:
        print(f"  {scene['id']:9s} {scene['start']:6.1f}–{scene['end']:6.1f}s  audio {scene['audio_seconds']:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
