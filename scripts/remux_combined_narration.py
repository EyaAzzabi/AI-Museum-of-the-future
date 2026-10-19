"""Remux combined silent demo with short, clear EN narration (gTTS = more human than SAPI)."""
from __future__ import annotations

import shutil
import subprocess
import wave
from pathlib import Path

from gtts import gTTS

OUT = Path(__file__).resolve().parents[1] / "docs" / "demo"
SILENT = OUT / "_combined_silent.mp4"
PAUSE = 0.55

# UI on screen (from the video interfaces):
# - Accueil / Musée du futur / salles 3D
# - Connexion visiteur · Identifiant · Mot de passe · Entrer dans le musée · visiteur / musee2126
# - Agent lab: Historian, Sociologist, Technology, Culture & Art, Visual
# - Exposition / musée
#
# Narration stays short: auth → agent UIs → museum.
# Absolute cues aligned to what is on screen (auth mid-part A, agents at part B).
CUED_PHRASES: list[tuple[float, str]] = [
    (1.0, "Here is the museum interface — Musée du futur."),
    (42.0, "First, we do authentication. Connexion visiteur: sign in, then enter the museum."),
    (65.5, "Then we open the agent interfaces. We test Historian, Sociologist, Technology, Culture and Art, and Visual, one by one."),
    (100.0, "And here is the museum — the galleries, the immersive visit, and the exhibition board."),
]


def _dur(path: Path) -> float:
    with wave.open(str(path), "rb") as wf:
        return wf.getnframes() / float(wf.getframerate())


def _run(cmd: list[str]) -> None:
    subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def speak(text: str, dest_wav: Path) -> float:
    mp3 = dest_wav.with_suffix(".mp3")
    # gTTS sounds more natural than Windows Zira
    gTTS(text=text, lang="en", tld="com", slow=False).save(str(mp3))
    _run([
        "ffmpeg", "-y", "-i", str(mp3),
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=24000",
        "-ac", "1", str(dest_wav),
    ])
    return _dur(dest_wav)


def build_track(clips: list[tuple[float, Path, str]], total: float) -> Path:
    bed = OUT / "_g_bed.wav"
    _run(["ffmpeg", "-y", "-f", "lavfi", "-t", f"{total:.3f}", "-i", "anullsrc=r=24000:cl=mono", str(bed)])
    inputs = ["-i", str(bed)]
    parts = []
    labels = ["[0:a]"]
    for i, (cue, wav, _) in enumerate(clips, 1):
        inputs += ["-i", str(wav)]
        ms = int(round(cue * 1000))
        parts.append(f"[{i}:a]adelay={ms}|{ms},apad=whole_dur={total:.3f}[a{i}]")
        labels.append(f"[a{i}]")
    filt = ";".join(parts) + f";{''.join(labels)}amix=inputs={len(labels)}:duration=first:dropout_transition=0:normalize=0[aout]"
    narr = OUT / "_g_narration.wav"
    _run(["ffmpeg", "-y", *inputs, "-filter_complex", filt, "-map", "[aout]", str(narr)])
    return narr


def write_srt(clips: list[tuple[float, Path, str]], total: float) -> Path:
    srt = OUT / "AI_Museum_demo_COMBINED_EN.srt"
    lines = []
    for i, (cue, wav, text) in enumerate(clips, 1):
        end = min(cue + _dur(wav) + 0.1, total)
        if i < len(clips):
            end = min(end, clips[i][0] - 0.05)
        lines += [str(i), f"{_ts(cue)} --> {_ts(max(end, cue + 0.5))}", text, ""]
    srt.write_text("\n".join(lines), encoding="utf-8")
    return srt


def _ts(s: float) -> str:
    h, rem = divmod(s, 3600)
    m, rem = divmod(rem, 60)
    sec = int(rem)
    ms = int(round((rem - sec) * 1000))
    return f"{int(h):02d}:{int(m):02d}:{sec:02d},{ms:03d}"


def main() -> None:
    if not SILENT.exists():
        raise SystemExit(f"Missing {SILENT} — run make_combined_demo_en.py once first")
    total = float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(SILENT),
    ], text=True).strip())
    print(f"Silent video {total:.1f}s — regenerating short narration with gTTS")

    clips: list[tuple[float, Path, str]] = []
    for i, (cue, text) in enumerate(CUED_PHRASES, 1):
        wav = OUT / f"_g_phrase_{i}.wav"
        dur = speak(text, wav)
        clips.append((cue, wav, text))
        print(f"  cue={cue:.1f}s dur={dur:.1f}s — {text}")

    narr = build_track(clips, total)
    srt = write_srt(clips, total)

    out = OUT / "AI_Museum_demo_COMBINED_EN.mp4"
    srt_esc = str(srt).replace("\\", "/").replace(":", "\\:")
    style = (
        "FontName=Arial,FontSize=22,PrimaryColour=&H00FFFFFF&,OutlineColour=&H80000000&,"
        "BackColour=&H80000000&,BorderStyle=3,Outline=1,Shadow=0,MarginV=40,Alignment=2"
    )
    _run([
        "ffmpeg", "-y", "-i", str(SILENT), "-i", str(narr),
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-vf", f"subtitles='{srt_esc}':force_style='{style}'",
        "-pix_fmt", "yuv420p", "-shortest", str(out),
    ])
    desktop = Path.home() / "Desktop"
    shutil.copy2(out, desktop / "AI_Museum_demo_COMBINED_EN.mp4")
    shutil.copy2(srt, desktop / "AI_Museum_demo_COMBINED_EN.srt")
    print(f"Wrote {out}")
    print(f"Copied to {desktop / 'AI_Museum_demo_COMBINED_EN.mp4'}")


if __name__ == "__main__":
    main()
