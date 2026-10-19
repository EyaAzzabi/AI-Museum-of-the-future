"""Combine 1018.mp4 (0–1:04) + screen recording, with clear EN narration and short pauses."""
from __future__ import annotations

import shutil
import subprocess
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "demo"
OUT.mkdir(parents=True, exist_ok=True)

SRC_1018 = Path(r"C:\Users\tasni\Downloads\1018.mp4")
# Resolve Windows screen-recording path (accented folder name)
_videos = Path(r"C:\Users\tasni\Videos")
SRC_REC = next(_videos.rglob("*223213.mp4"))

PART_A_END = 64.0  # 1:04
TARGET_W, TARGET_H = 1920, 1080
FPS = 30
PAUSE_BETWEEN_PHRASES = 0.45  # small natural pause


# Phrases only — cues are placed sequentially with PAUSE_BETWEEN_PHRASES (no overlap).
# Part A covers 1018 (0–64s); Part B starts at PART_A_END (screen recording).
PHRASES_A = [
    "Welcome to the Museum of the Future.",
    "This is the public visitor experience. Warm, clear, and easy to read.",
    "From the home page, you discover the project before signing in.",
    "Scroll down to enter the three D museum on the landing page.",
    "Four specialist rooms guide the visit: Historian, Sociologist, Technology, and Culture and Art.",
    "There is no blue Visual tile on this front. The visitor gallery stays simple.",
    "Use the arrows to move from room to room and hear what each agent focuses on.",
    "To open the immersive visit and the curator dashboard, visitors sign in.",
    "Demo account: username visitor. Password: museum twenty one twenty six.",
    "After login, the full immersive galleries open with corpus images on the walls.",
]
PHRASES_B = [
    "Now the working side of the museum: the dashboard and Agent Lab.",
    "Here you can test each specialist agent, one by one, on the same archive scenarios.",
    "First, the Historian. Load a scenario, run the analysis, and read the grounded findings.",
    "Next, the Sociologist. Same documents, a social lens: lifestyles, identities, and change.",
    "Then, Technology. It surfaces innovations and future potential from the sources.",
    "Culture and Art comes next. Symbols, media, and the spirit of an era.",
    "Finally, Visual. Image reading, atmosphere, and aesthetic curation live here in the lab.",
    "Each result shows a perspective, key findings, and citations tied to the provided chunks.",
    "That keeps the agents honest. They must stay grounded in the archive, not invent facts.",
    "From visitor home, to immersive visit, to testing every agent. That is the full demo.",
    "You can also open the exhibition board to run the full pipeline: five specialists, peer review, curator, and fact check.",
    "Thank you for watching this walkthrough of the Museum of the Future.",
]


def _wav_dur(path: Path) -> float:
    with wave.open(str(path), "rb") as wf:
        return wf.getnframes() / float(wf.getframerate())


def _run(cmd: list[str]) -> None:
    subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def make_tts(phrases: list[str], prefix: str) -> list[tuple[Path, str, float]]:
    """Speak each phrase separately (Zira). Returns (wav, text, duration)."""
    ps = OUT / f"_combine_tts_{prefix}.ps1"
    lines = [
        "Add-Type -AssemblyName System.Speech",
        "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer",
        "$synth.Rate = -1",
        "$synth.Volume = 100",
        "$voices = $synth.GetInstalledVoices()",
        "$prefer = @('Microsoft Zira Desktop','Microsoft Eva Desktop')",
        "$chosen = $null",
        "foreach ($name in $prefer) {",
        "  $v = $voices | Where-Object { $_.VoiceInfo.Name -eq $name } | Select-Object -First 1",
        "  if ($v) { $chosen = $v; break }",
        "}",
        "if (-not $chosen) { $chosen = $voices | Where-Object { $_.VoiceInfo.Culture.Name -like 'en*' } | Select-Object -First 1 }",
        "if ($chosen) { $synth.SelectVoice($chosen.VoiceInfo.Name); Write-Output ('voice=' + $chosen.VoiceInfo.Name) }",
    ]
    raws: list[Path] = []
    for i, text in enumerate(phrases, 1):
        raw = OUT / f"_c_{prefix}_raw_{i}.wav"
        safe = text.replace("'", "''")
        lines += [
            f"$synth.SetOutputToWaveFile('{raw.as_posix()}')",
            f"$synth.Speak('{safe}')",
            "$synth.SetOutputToNull()",
        ]
        raws.append(raw)
    lines.append("$synth.Dispose()")
    ps.write_text("\n".join(lines), encoding="utf-8")
    subprocess.check_call(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps)])

    out: list[tuple[Path, str, float]] = []
    for i, (text, raw) in enumerate(zip(phrases, raws), 1):
        if not raw.exists() or raw.stat().st_size < 1000:
            raise SystemExit(f"TTS failed for {prefix} clip {i}")
        tight = OUT / f"_c_{prefix}_phrase_{i}.wav"
        _run([
            "ffmpeg", "-y", "-i", str(raw),
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=24000",
            "-ac", "1", str(tight),
        ])
        dur = _wav_dur(tight)
        if dur < 0.8:
            raise SystemExit(f"{prefix} phrase {i} too short ({dur:.2f}s)")
        out.append((tight, text, dur))
    return out


def place_sequential(
    spoken: list[tuple[Path, str, float]],
    start_at: float,
    hard_end: float | None = None,
) -> list[tuple[float, Path, str]]:
    """Lay phrases one after another with a short pause; never overlap."""
    t = start_at
    clips: list[tuple[float, Path, str]] = []
    for wav, text, dur in spoken:
        if hard_end is not None and t + dur > hard_end:
            # Soft clamp: still include if we have at least 1s left
            if hard_end - t < 1.0:
                print(f"  skip (no room): {text[:50]}...")
                break
        clips.append((t, wav, text))
        print(f"  cue={t:.1f}s dur={dur:.1f}s — {text[:60]}...")
        t = t + dur + PAUSE_BETWEEN_PHRASES
    return clips


def build_narration_track(clips: list[tuple[float, Path, str]], total_dur: float) -> Path:
    """Place each phrase at its cue time on a silent bed; small pauses come from cue spacing."""
    # Build with ffmpeg adelay / amix via filter_complex
    # Simpler: generate silence bed, then overlay with atrim+adelay for each
    bed = OUT / "_c_bed.wav"
    _run([
        "ffmpeg", "-y", "-f", "lavfi", "-t", f"{total_dur:.3f}",
        "-i", "anullsrc=r=24000:cl=mono", str(bed),
    ])

    # Use Sox-like approach via ffmpeg concat of silence+phrase for sequential,
    # but we have absolute cues — use filter_complex
    inputs = ["-i", str(bed)]
    filter_parts = []
    mix_labels = ["[0:a]"]
    for i, (cue, wav, _text) in enumerate(clips, 1):
        inputs += ["-i", str(wav)]
        delay_ms = int(round(cue * 1000))
        # adelay needs two values for stereo; mono uses one — use apad and adelay
        filter_parts.append(
            f"[{i}:a]adelay={delay_ms}|{delay_ms},apad=whole_dur={total_dur:.3f}[a{i}]"
        )
        mix_labels.append(f"[a{i}]")

    n = len(mix_labels)
    filt = ";".join(filter_parts) + f";{''.join(mix_labels)}amix=inputs={n}:duration=first:dropout_transition=0:normalize=0[aout]"
    narr = OUT / "_c_narration.wav"
    cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", filt, "-map", "[aout]", str(narr)]
    subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return narr


def write_srt(clips: list[tuple[float, Path, str]], total_dur: float) -> Path:
    srt = OUT / "AI_Museum_demo_COMBINED_EN.srt"
    lines = []
    for i, (cue, wav, text) in enumerate(clips, 1):
        end = min(cue + _wav_dur(wav) + 0.15, total_dur)
        # Ensure no overlap display glitch: end before next cue if needed
        if i < len(clips):
            end = min(end, clips[i][0] - 0.05)
        if end <= cue:
            end = cue + 1.0
        lines += [str(i), f"{_ts(cue)} --> {_ts(end)}", text, ""]
    srt.write_text("\n".join(lines), encoding="utf-8")
    return srt


def _ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def normalize_clip(src: Path, dest: Path, start: float | None = None, duration: float | None = None) -> float:
    """Scale to 1080p, 30fps, muted. Returns duration of output."""
    args = ["ffmpeg", "-y"]
    if start is not None:
        args += ["-ss", f"{start:.3f}"]
    args += ["-i", str(src)]
    if duration is not None:
        args += ["-t", f"{duration:.3f}"]
    vf = (
        f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease,"
        f"pad={TARGET_W}:{TARGET_H}:(ow-iw)/2:(oh-ih)/2,fps={FPS},setsar=1"
    )
    args += ["-an", "-vf", vf, "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p", str(dest)]
    _run(args)
    # probe
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(dest),
    ], text=True).strip()
    return float(out)


def main() -> None:
    if not SRC_1018.exists():
        raise SystemExit(f"Missing {SRC_1018}")
    if not SRC_REC.exists():
        raise SystemExit(f"Missing screen recording")

    print("Source A:", SRC_1018)
    print("Source B:", SRC_REC)

    part_a = OUT / "_part_a_1018.mp4"
    part_b = OUT / "_part_b_rec.mp4"
    silent = OUT / "_combined_silent.mp4"
    if silent.exists() and part_a.exists() and part_b.exists():
        print("Reusing existing silent combined video")
        dur_a = float(subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(part_a),
        ], text=True).strip())
        dur_b = float(subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(part_b),
        ], text=True).strip())
    else:
        print(f"Cutting 1018.mp4 0-{PART_A_END:.0f}s ...")
        dur_a = normalize_clip(SRC_1018, part_a, start=0.0, duration=PART_A_END)
        print(f"  part A = {dur_a:.2f}s")
        print("Normalizing screen recording ...")
        dur_b = normalize_clip(SRC_REC, part_b)
        print(f"  part B = {dur_b:.2f}s")
        concat_list = OUT / "_combine_concat.txt"
        concat_list.write_text(
            f"file '{part_a.as_posix()}'\nfile '{part_b.as_posix()}'\n",
            encoding="utf-8",
        )
        _run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
            "-c", "copy", str(silent),
        ])
    total = dur_a + dur_b
    print(f"Combined silent video ~ {total:.1f}s ({total/60:.1f} min)")

    print("Generating narration (Zira, short pauses between phrases) ...")
    print("  Part A (visitor UX):")
    spoken_a = make_tts(PHRASES_A, "a")
    # Allow a short spill into part B so every visitor phrase is spoken with pauses
    clips_a = place_sequential(spoken_a, start_at=0.5, hard_end=dur_a + 4.0)
    print("  Part B (agent lab):")
    spoken_b = make_tts(PHRASES_B, "b")
    clips_b = place_sequential(spoken_b, start_at=dur_a + 0.4, hard_end=total - 0.2)
    clips = clips_a + clips_b

    narr = build_narration_track(clips, total)
    srt = write_srt(clips, total)

    out = OUT / "AI_Museum_demo_COMBINED_EN.mp4"
    srt_esc = str(srt).replace("\\", "/").replace(":", "\\:")
    style = (
        "FontName=Arial,FontSize=20,PrimaryColour=&H00FFFFFF&,OutlineColour=&H80000000&,"
        "BackColour=&H80000000&,BorderStyle=3,Outline=1,Shadow=0,MarginV=36,Alignment=2"
    )
    vf = f"subtitles='{srt_esc}':force_style='{style}'"
    print("Muxing video + narration + subtitles …")
    _run([
        "ffmpeg", "-y", "-i", str(silent), "-i", str(narr),
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-vf", vf, "-pix_fmt", "yuv420p",
        "-shortest", str(out),
    ])

    desktop = Path.home() / "Desktop"
    shutil.copy2(out, desktop / "AI_Museum_demo_COMBINED_EN.mp4")
    shutil.copy2(srt, desktop / "AI_Museum_demo_COMBINED_EN.srt")
    print(f"Wrote {out}")
    print(f"Copied to {desktop / 'AI_Museum_demo_COMBINED_EN.mp4'}")


if __name__ == "__main__":
    main()
