"""Build a faster demo video from real UI screenshots + French voice + subtitles."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "demo"
UI = OUT / "ui"

# Faster pacing (~2 min total)
SEGMENTS = [
    (12, "01_accueil.png",
     "Accueil du Musee du futur. L interface publique presente la collection et la visite immersive."),
    (14, "02_connexion.png",
     "Authentification visiteur. Compte demo : visiteur, mot de passe musee 2126. Sans connexion, la visite 3D reste protegee."),
    (18, "03_visite_3d.png",
     "Apres connexion, la visite immersive s ouvre. Cinq salles pour les specialistes : historien, sociologue, technologies, culture et agent visuel."),
    (16, "04_salle_agents.png",
     "Dans l atelier, on lance les agents sur les archives. Ils analysent, puis le curateur compose l exposition."),
    (16, "05_dashboard.png",
     "Le tableau de bord expose le pipeline, l exposition et les runs sauvegardes, integres avec n eight n."),
    (14, "06_historian.png",
     "L interface Historian d Eya Idi permet de tester l agent historique. Fin de la demo integree."),
]


def write_srt() -> Path:
    srt = OUT / "AI_Museum_demo_UI.srt"
    t = 0.0
    lines = []
    for i, (dur, _img, text) in enumerate(SEGMENTS, 1):
        start, end = t, t + dur
        lines += [
            str(i),
            f"{_ts(start)} --> {_ts(end)}",
            text,
            "",
        ]
        t = end
    srt.write_text("\n".join(lines), encoding="utf-8")
    return srt


def _ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_concat() -> Path:
    concat = OUT / "concat_ui.txt"
    rows = []
    for dur, img, _text in SEGMENTS:
        path = (UI / img).resolve()
        if not path.exists():
            raise SystemExit(f"Missing screenshot: {path}")
        rows.append(f"file '{path.as_posix()}'")
        rows.append(f"duration {dur}")
    last = (UI / SEGMENTS[-1][1]).resolve()
    rows.append(f"file '{last.as_posix()}'")
    concat.write_text("\n".join(rows), encoding="utf-8")
    return concat


def sapi_narration(wav_out: Path) -> None:
    """Generate narration via Windows SAPI through PowerShell."""
    ps = OUT / "_tts_ui.ps1"
    lines = [
        "Add-Type -AssemblyName System.Speech",
        "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer",
        "$synth.Rate = 2",  # slightly faster speech
        "$synth.Volume = 100",
        "$fr = $synth.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like 'fr*' } | Select-Object -First 1",
        "if ($fr) { $synth.SelectVoice($fr.VoiceInfo.Name) }",
    ]
    for i, (dur, _img, text) in enumerate(SEGMENTS, 1):
        raw = OUT / f"_ui_tts_{i}.wav"
        pad = OUT / f"_ui_pad_{i}.wav"
        safe = text.replace("'", "''")
        lines += [
            f"$synth.SetOutputToWaveFile('{raw.as_posix()}')",
            f"$synth.Speak('{safe}')",
            "$synth.SetOutputToNull()",
            f"ffmpeg -y -i '{raw.as_posix()}' -af 'apad=whole_dur={dur},atrim=0:{dur}' -ar 24000 -ac 1 '{pad.as_posix()}' 2>$null",
        ]
    pads = [str((OUT / f"_ui_pad_{i}.wav").as_posix()) for i in range(1, len(SEGMENTS) + 1)]
    clist = OUT / "_ui_narr_concat.txt"
    clist.write_text("\n".join(f"file '{p}'" for p in pads), encoding="ascii")
    lines += [
        "$synth.Dispose()",
        f"ffmpeg -y -f concat -safe 0 -i '{clist.as_posix()}' -c copy '{wav_out.as_posix()}' 2>$null",
    ]
    ps.write_text("\n".join(lines), encoding="utf-8")
    subprocess.check_call(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps)])


def main() -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg required")
    concat = write_concat()
    srt = write_srt()
    narr = OUT / "narration_ui.wav"
    sapi_narration(narr)
    raw = OUT / "_raw_ui.mp4"
    subprocess.check_call([
        ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
        "-vf", "scale=1440:900:force_original_aspect_ratio=decrease,pad=1440:900:(ow-iw)/2:(oh-ih)/2",
        "-pix_fmt", "yuv420p", "-r", "30", str(raw),
    ])
    out = OUT / "AI_Museum_demo_UI.mp4"
    srt_esc = str(srt).replace("\\", "/").replace(":", "\\:")
    style = "FontSize=20,PrimaryColour=&H00FFFFFF&,OutlineColour=&H00000000&,BorderStyle=3,Outline=1,Shadow=0"
    vf = f"subtitles='{srt_esc}':force_style='{style}'"
    subprocess.check_call([
        ffmpeg, "-y", "-i", str(raw), "-i", str(narr),
        "-c:v", "libx264", "-c:a", "aac", "-shortest",
        "-vf", vf, "-pix_fmt", "yuv420p", str(out),
    ])
    print(f"Wrote {out}")
    desktop = Path.home() / "Desktop" / "AI_Museum_demo_UI.mp4"
    shutil.copy2(out, desktop)
    shutil.copy2(srt, Path.home() / "Desktop" / "AI_Museum_demo_UI.srt")
    print(f"Copied to {desktop}")


if __name__ == "__main__":
    main()
