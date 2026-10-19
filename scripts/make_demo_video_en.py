"""Full English UX demo: clear visitor front + each specialist agent tested one by one."""
from __future__ import annotations

import shutil
import subprocess
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "demo"
UI = OUT / "ui"

# Longer, clear narration. Breath between clips = 0.55s (readable, not rushed, not empty).
SEGMENTS = [
    ("01_accueil.png",
     "Welcome to the Museum of the Future. This is the public visitor home — a warm, clear gallery experience. "
     "From here, anyone can discover the project before signing in."),

    ("02_salles_3d.png",
     "Scroll down and you enter the three D museum on the home page. "
     "Four specialist rooms guide the visit: Historian, Sociologist, Technology, and Culture and Art. "
     "There is no cold blue Visual tile on this front — that keeps the visitor experience simple and readable."),

    ("03_salle_historian.png",
     "Room one: the Historian. It connects today’s events to long memory — what a museum in twenty one twenty six would still care about."),

    ("03_salle_sociologist.png",
     "Room two: the Sociologist. It looks at how people live, organise, and change together."),

    ("03_salle_technology.png",
     "Room three: Technology. It highlights inventions and tools that already reshape daily life."),

    ("03_salle_culture_art.png",
     "Room four: Culture and Art. It gathers symbols, media, and creative expressions of our era."),

    ("04_connexion.png",
     "To go further — the immersive visit and the curator dashboard — visitors sign in. "
     "Demo account: username visitor, password museum twenty one twenty six."),

    ("05_visite_immersive.png",
     "After login, the full immersive visit opens. You walk the galleries with real corpus images on the walls, "
     "and each space still belongs to a specialist agent."),

    ("06_agents_overview.png",
     "Now the dashboard — the working side of the museum. Here you see all five specialist agents side by side: "
     "Historian, Sociologist, Technology, Culture and Art, and Visual. Each card has a Test button."),

    ("07_agentlab_intro.png",
     "The Agent Lab is where we test them one by one. Pick an agent tab, choose an archive scenario with real text chunks, "
     "then run the analysis. Findings must stay grounded in those chunks — no free invention."),

    ("08_test_historian.png",
     "Test one — Historian. We load a scenario, press Run, and get a perspective, key findings, and cited artifacts from the archive."),

    ("08_test_sociologist.png",
     "Test two — Sociologist. Same documents, different lens: social trends, lifestyles, and collective behaviour."),

    ("08_test_technology.png",
     "Test three — Technology. It surfaces innovations, breakthroughs, and future potential from the same sources."),

    ("08_test_culture_art.png",
     "Test four — Culture and Art. It reads cultural movements, media, and symbolic meaning in the excerpts."),

    ("08_test_visual.png",
     "Test five — Visual. This agent focuses on image reading, atmosphere, and aesthetic curation. "
     "It lives in the lab and pipeline, not as a blue room on the public home carousel."),

    ("09_exhibition.png",
     "Finally, the Exhibition board. Here the full pipeline can run: five specialists, peer review, curator, and fact check — "
     "ready to feed an n eight n workflow or a museum hall view. That is the complete user experience, from public visit to agent testing."),
]

BREATH_S = 0.55


def _wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wf:
        return wf.getnframes() / float(wf.getframerate())


def make_tts_clips() -> list[tuple[Path, float, str]]:
    """Windows SAPI English voice — slightly slow for clarity."""
    ps = OUT / "_tts_en.ps1"
    lines = [
        "Add-Type -AssemblyName System.Speech",
        "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer",
        "$synth.Rate = -2",
        "$synth.Volume = 100",
        "$voices = $synth.GetInstalledVoices()",
        # Prefer Zira (female EN-US) when available — clearer for demos
        "$prefer = @('Microsoft Zira Desktop','Microsoft Eva Desktop','Microsoft Mark Desktop')",
        "$chosen = $null",
        "foreach ($name in $prefer) {",
        "  $v = $voices | Where-Object { $_.VoiceInfo.Name -eq $name } | Select-Object -First 1",
        "  if ($v) { $chosen = $v; break }",
        "}",
        "if (-not $chosen) { $chosen = $voices | Where-Object { $_.VoiceInfo.Culture.Name -like 'en*' } | Select-Object -First 1 }",
        "if ($chosen) { $synth.SelectVoice($chosen.VoiceInfo.Name); Write-Output ('voice=' + $chosen.VoiceInfo.Name) }",
        "else { Write-Output ('voice=' + $synth.Voice.Name) }",
    ]
    clips = []
    for i, (_img, text) in enumerate(SEGMENTS, 1):
        raw = OUT / f"_en_raw_{i}.wav"
        safe = text.replace("'", "''")
        lines += [
            f"$synth.SetOutputToWaveFile('{raw.as_posix()}')",
            f"$synth.Speak('{safe}')",
            "$synth.SetOutputToNull()",
        ]
        clips.append(raw)
    lines.append("$synth.Dispose()")
    ps.write_text("\n".join(lines), encoding="utf-8")
    subprocess.check_call(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps)])

    out = []
    for i, ((_img, text), raw) in enumerate(zip(SEGMENTS, clips), 1):
        if not raw.exists():
            raise SystemExit(f"missing TTS {raw}")
        # Keep full speech: only resample. Aggressive silenceremove was eating SAPI audio.
        tight = OUT / f"_en_tight_{i}.wav"
        subprocess.check_call([
            "ffmpeg", "-y", "-i", str(raw),
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=24000",
            "-ac", "1", str(tight),
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        dur = _wav_duration(tight) + BREATH_S
        if dur < 2.0:
            raise SystemExit(f"TTS clip too short ({dur:.2f}s): {tight} — check voice output")
        out.append((tight, dur, text))
    return out


def write_srt(clips: list[tuple[Path, float, str]]) -> Path:
    srt = OUT / "AI_Museum_demo_EN.srt"
    t = 0.0
    lines = []
    for i, (_wav, dur, text) in enumerate(clips, 1):
        lines += [str(i), f"{_ts(t)} --> {_ts(t + dur - 0.05)}", text, ""]
        t += dur
    srt.write_text("\n".join(lines), encoding="utf-8")
    return srt


def _ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main() -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg required")

    missing = [img for img, _ in SEGMENTS if not (UI / img).exists()]
    if missing:
        raise SystemExit(f"Missing screenshots — run capture_demo_ui.py first: {missing}")

    clips = make_tts_clips()
    srt = write_srt(clips)
    total = sum(d for _, d, _ in clips)
    print(f"Narration total ~{total:.0f}s ({total/60:.1f} min), {len(clips)} segments")

    concat = OUT / "concat_en.txt"
    rows = []
    for (wav, dur, _text), (img, _t) in zip(clips, SEGMENTS):
        path = (UI / img).resolve()
        rows.append(f"file '{path.as_posix()}'")
        rows.append(f"duration {dur:.3f}")
    last_img = (UI / SEGMENTS[-1][0]).resolve()
    rows.append(f"file '{last_img.as_posix()}'")
    concat.write_text("\n".join(rows), encoding="utf-8")

    silence = OUT / "_en_breath.wav"
    subprocess.check_call([
        ffmpeg, "-y", "-f", "lavfi", "-t", str(BREATH_S),
        "-i", "anullsrc=r=24000:cl=mono", str(silence),
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    alist = OUT / "_en_audio_concat.txt"
    audio_rows = []
    for i, (wav, _d, _t) in enumerate(clips):
        audio_rows.append(f"file '{wav.as_posix()}'")
        if i < len(clips) - 1:
            audio_rows.append(f"file '{silence.as_posix()}'")
    alist.write_text("\n".join(audio_rows), encoding="ascii")

    narr = OUT / "narration_en.wav"
    subprocess.check_call([
        ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(alist), "-c", "copy", str(narr),
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    raw = OUT / "_raw_en.mp4"
    subprocess.check_call([
        ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
        "-vf", "scale=1440:900:force_original_aspect_ratio=decrease,pad=1440:900:(ow-iw)/2:(oh-ih)/2",
        "-pix_fmt", "yuv420p", "-r", "30", str(raw),
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    out = OUT / "AI_Museum_demo_EN.mp4"
    srt_esc = str(srt).replace("\\", "/").replace(":", "\\:")
    style = (
        "FontName=Arial,FontSize=18,PrimaryColour=&H00FFFFFF&,OutlineColour=&H80000000&,"
        "BackColour=&H80000000&,BorderStyle=3,Outline=1,Shadow=0,MarginV=28,Alignment=2"
    )
    vf = f"subtitles='{srt_esc}':force_style='{style}'"
    subprocess.check_call([
        ffmpeg, "-y", "-i", str(raw), "-i", str(narr),
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k", "-shortest",
        "-vf", vf, "-pix_fmt", "yuv420p", str(out),
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    desktop = Path.home() / "Desktop"
    shutil.copy2(out, desktop / "AI_Museum_demo_EN.mp4")
    shutil.copy2(srt, desktop / "AI_Museum_demo_EN.srt")
    print(f"Wrote {out}")
    print(f"Copied to {desktop / 'AI_Museum_demo_EN.mp4'}")


if __name__ == "__main__":
    main()
