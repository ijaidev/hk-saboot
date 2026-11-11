#!/usr/bin/env python3
"""Build the final demo voiceover with ElevenLabs + forced alignment.

This replaces the earlier eSpeak build. Every scene gets a natural neural TTS
clip, then ElevenLabs forced alignment gives exact word timings for captions.
The video is recorded separately against the resulting timeline.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "proof" / "demo"
AUDIO = DEMO / "audio"
VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"  # George, narrative
MODEL_ID = "eleven_multilingual_v2"
SPEED = 0.8
PAD_SECONDS = 1.2
CLI = ["npx", "-y", "@elevenlabs/cli@latest"]


def run(cmd: list[str], timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=timeout)


def duration(path: Path) -> float:
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            str(path),
        ]
    )
    return float(result.stdout.strip())


def tts(text: str, output: Path) -> None:
    command = [
        *CLI,
        "text-to-speech",
        "convert",
        "--text",
        text,
        "--voice-id",
        VOICE_ID,
        "--model-id",
        MODEL_ID,
        "--output-format",
        "mp3_44100_128",
        "--apply-text-normalization",
        "on",
        "--voice-settings.speed",
        str(SPEED),
        "--voice-settings.stability",
        "0.5",
        "--voice-settings.similarity-boost",
        "0.75",
        "-o",
        str(output),
    ]
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            run(command)
            if output.exists() and output.stat().st_size > 1000:
                return
        except Exception as exc:  # network/CLI retry
            last_error = exc
            time.sleep(2 + attempt * 2)
    raise RuntimeError(f"TTS failed for {output.name}: {last_error}")


def align(text: str, audio: Path) -> dict:
    command = [
        *CLI,
        "forced-alignment",
        "create",
        "--file",
        str(audio),
        "--text",
        text,
        "--format",
        "json",
        "--retries",
        "3",
    ]
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            result = run(command)
            return json.loads(result.stdout)
        except Exception as exc:
            last_error = exc
            time.sleep(2 + attempt * 2)
    raise RuntimeError(f"Forced alignment failed for {audio.name}: {last_error}")


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


def wrap_caption(text: str, width: int = 64) -> str:
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


def build_cues(words: list[dict]) -> list[list[tuple[str, float, float]]]:
    tokens = [
        (str(w["text"]).strip(), float(w["start"]), float(w["end"]))
        for w in words
        if str(w.get("text", "")).strip()
    ]
    cues: list[list[tuple[str, float, float]]] = []
    current: list[tuple[str, float, float]] = []
    for token in tokens:
        candidate = current + [token]
        text = " ".join(t[0] for t in candidate)
        if current and (len(current) >= 9 or len(text) > 66):
            cues.append(current)
            current = [token]
        else:
            current.append(token)
    if current:
        cues.append(current)

    changed = True
    while changed and len(cues) > 1:
        changed = False
        for index, cue in enumerate(cues):
            cue_duration = cue[-1][2] - cue[0][1]
            if len(cue) < 3 or cue_duration < 1.2:
                if index > 0:
                    cues[index - 1] = cues[index - 1] + cue
                    cues.pop(index)
                else:
                    cues[1] = cue + cues[1]
                    cues.pop(0)
                changed = True
                break
    return cues


def convert_to_wav(source: Path, target: Path) -> None:
    run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(source),
            "-ar",
            "44100",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(target),
        ]
    )


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
    srt_lines: list[str] = []
    ass_events: list[str] = []
    caption_index = 1
    padded_files: list[Path] = []

    for index, scene in enumerate(scenes, start=1):
        scene_id = scene["id"]
        narration = scene["narration"]
        mp3_path = AUDIO / f"{index:02d}-{scene_id}.mp3"
        wav_path = AUDIO / f"{index:02d}-{scene_id}.wav"
        align_path = AUDIO / f"{index:02d}-{scene_id}.align.json"
        print(f"[{index}/{len(scenes)}] {scene_id}: TTS + alignment")
        if mp3_path.exists() and mp3_path.stat().st_size > 1000:
            print("    using existing TTS clip")
        else:
            tts(narration, mp3_path)
        audio_seconds = duration(mp3_path)
        if align_path.exists():
            alignment = json.loads(align_path.read_text())
            print("    using existing alignment")
        else:
            alignment = align(narration, mp3_path)
            align_path.write_text(json.dumps(alignment, indent=2) + "\n", encoding="utf-8")
        words = alignment.get("words", [])
        if not words:
            raise RuntimeError(f"No word alignment for {scene_id}")

        scene_seconds = max(scene.get("min_ms", 0) / 1000.0, audio_seconds + PAD_SECONDS)
        end = cursor + scene_seconds
        cues = build_cues(words)
        for cue in cues:
            cue_start = cursor + cue[0][1]
            cue_end = cursor + cue[-1][2]
            text = " ".join(token[0] for token in cue)
            caption = wrap_caption(text)
            srt_lines.append(
                f"{caption_index}\n{srt_time(cue_start)} --> {srt_time(cue_end)}\n{caption}\n"
            )
            ass_events.append(
                "Dialogue: 0,"
                f"{ass_time(cue_start)},{ass_time(cue_end)},Default,,0,0,0,,"
                f"{caption.replace(chr(10), '\\N')}"
            )
            caption_index += 1

        timeline.append(
            {
                **scene,
                "audio": str(mp3_path.relative_to(ROOT)),
                "audio_seconds": round(audio_seconds, 3),
                "start": round(cursor, 3),
                "end": round(end, 3),
                "duration_ms": int(round(scene_seconds * 1000)),
            }
        )
        convert_to_wav(mp3_path, wav_path)
        padded = AUDIO / f"padded-{scene_id}.wav"
        pad_wav(wav_path, padded, scene_seconds)
        padded_files.append(padded)
        cursor = end
        print(f"    audio {audio_seconds:.1f}s, scene {scene_seconds:.1f}s")

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
        "Style: Default,DejaVu Sans,28,&H00FFFFFF,&H000000FF,&H00000000,&HA0000000,0,0,0,0,100,100,0,0,3,1.4,0,2,90,90,38,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        *ass_events,
        "",
    ]
    (DEMO / "captions.ass").write_text("\n".join(ass), encoding="utf-8")

    with wave.open(str(padded_files[0]), "rb") as first:
        params = first.getparams()
    with wave.open(str(DEMO / "voiceover.wav"), "wb") as out:
        out.setparams(params)
        for path in padded_files:
            with wave.open(str(path), "rb") as handle:
                out.writeframes(handle.readframes(handle.getnframes()))

    print(f"Total timeline: {total:.1f}s ({total/60:.2f} min)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
