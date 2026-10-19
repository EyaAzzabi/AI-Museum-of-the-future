"""Build a short French demo video with burnt-in + sidecar subtitles.

Usage:
  python scripts/make_demo_video.py

Needs: ffmpeg on PATH. Optional: edge-tts (pip install edge-tts) for voice.
Without TTS, produces a silent slideshow with subtitles only.
"""
from __future__ import annotations

import asyncio
import shutil
import subprocess
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "demo"
SLIDES = OUT / "slides"
W, H = 1280, 720

SEGMENTS = [
    (20, "Bienvenue dans AI Museum of the Future.\nUn musee virtuel qui raconte 2020-2026\ncomme si nous etions en 2126.",
     "AI Museum of the Future", "Visiteur en 2126 · Tunisie 2020-2026"),
    (25, "Le pipeline collecte des sources publiques,\nles indexe en RAG hybride,\npuis cinq agents specialistes analysent les preuves.",
     "Architecture", "Data → RAG → Multimodal → Agents → Exposition"),
    (30, "Historian, Sociologist, Technology,\nCulture & Art et Visual travaillent en parallele,\npuis revue, curateur et fact-check.",
     "Multi-agents", "5 specialistes + revue + curateur + fact-check"),
    (30, "Le multimodal ne genere pas d'images :\nil lit les photos du corpus\net decrit ce qu'elles montrent vraiment.",
     "Multimodal", "Vision LLM · cache · Vision: dans le RAG"),
    (35, "n8n orchestre le bout en bout :\nwebhook, exposition, attente,\npuis telecharge les images des salles\nvisibles en binaire dans le workflow.",
     "n8n end-to-end", "Download museum images → Binary preview"),
    (40, "La visite immersive place ces images\nsur les murs des salles.\nChaque section du curateur devient une galerie.",
     "Visite 3D /virtual", "Corpus images on the walls — no generated art"),
    (30, "Resultat : une exposition sourcee, verifiee,\net un musee ou l'on voit\nles archives reelles de notre epoque.",
     "Demo integree", "Tasnim · Exhibition + multimodal + n8n + main"),
]


def _require_pillow():
    try:
        from PIL import Image, ImageDraw, ImageFont  # noqa: F401
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pillow", "-q"])
    from PIL import Image, ImageDraw, ImageFont
    return Image, ImageDraw, ImageFont


def _font(ImageFont, size: int):
    for name in ("arial.ttf", "segoeui.ttf", "DejaVuSans.ttf", "calibri.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render_slides() -> list[Path]:
    Image, ImageDraw, ImageFont = _require_pillow()
    SLIDES.mkdir(parents=True, exist_ok=True)
    paths = []
    title_f = _font(ImageFont, 48)
    body_f = _font(ImageFont, 28)
    small_f = _font(ImageFont, 22)
    for i, (_dur, _voice, title, subtitle) in enumerate(SEGMENTS, 1):
        img = Image.new("RGB", (W, H), (18, 16, 14))
        draw = ImageDraw.Draw(img)
        draw.rectangle((0, 0, W, 8), fill=(212, 180, 131))
        draw.text((64, 120), title, fill=(243, 239, 230), font=title_f)
        draw.text((64, 220), subtitle, fill=(180, 170, 150), font=body_f)
        draw.text((64, H - 80), f"{i}/{len(SEGMENTS)}  ·  AI Museum of the Future", fill=(120, 110, 95), font=small_f)
        path = SLIDES / f"slide_{i:02d}.png"
        img.save(path)
        paths.append(path)
    return paths


def write_srt() -> Path:
    srt = OUT / "AI_Museum_demo.srt"
    t = 0.0
    lines = []
    for i, (dur, text, _title, _sub) in enumerate(SEGMENTS, 1):
        start, end = t, t + dur
        lines.append(str(i))
        lines.append(f"{_ts(start)} --> {_ts(end)}")
        lines.append(text.replace("\n", " "))
        lines.append("")
        t = end
    srt.write_text("\n".join(lines), encoding="utf-8")
    return srt


def _ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_concat(slides: list[Path]) -> Path:
    concat = OUT / "concat.txt"
    rows = []
    for path, (dur, *_rest) in zip(slides, SEGMENTS):
        rows.append(f"file '{path.as_posix()}'")
        rows.append(f"duration {dur}")
    rows.append(f"file '{slides[-1].as_posix()}'")
    concat.write_text("\n".join(rows), encoding="utf-8")
    return concat


async def synthesize_voice(wav_path: Path) -> bool:
    try:
        import edge_tts  # type: ignore
    except ImportError:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "edge-tts", "-q"])
            import edge_tts  # type: ignore
        except Exception:
            return False

    # Build one continuous script with pauses approximated by segment joins
    script = " ... ".join(text.replace("\n", " ") for _d, text, *_ in SEGMENTS)
    communicate = edge_tts.Communicate(script, voice="fr-FR-DeniseNeural")
    tmp_mp3 = wav_path.with_suffix(".mp3")
    await communicate.save(str(tmp_mp3))
    # Keep mp3; ffmpeg can use it directly
    if tmp_mp3.exists():
        wav_path.write_bytes(tmp_mp3.read_bytes())  # store as .mp3 bytes under narration.*
        return True
    return False


def silent_audio(path: Path, duration: float) -> Path:
    """Write a silent WAV if TTS is unavailable."""
    rate = 24000
    frames = int(rate * duration)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(b"\x00\x00" * frames)
    return path


def run_ffmpeg(concat: Path, srt: Path, audio: Path | None, out_mp4: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg not found on PATH")

    # First pass: slideshow video
    raw = OUT / "_raw_slides.mp4"
    subprocess.check_call([
        ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
        "-vf", f"scale={W}:{H}", "-pix_fmt", "yuv420p", "-r", "30", str(raw),
    ])

    # Burn subtitles + optional audio (Windows paths need escaped drive colon for subtitles filter)
    srt_escaped = str(srt).replace("\\", "/").replace(":", "\\:")
    style = "FontSize=22,PrimaryColour=&H00FFFFFF&,OutlineColour=&H00000000&,BorderStyle=3,Outline=1,Shadow=0"
    vf = f"subtitles='{srt_escaped}':force_style='{style}'"
    cmd = [ffmpeg, "-y", "-i", str(raw)]
    if audio and audio.exists():
        cmd += ["-i", str(audio), "-c:v", "libx264", "-c:a", "aac", "-shortest"]
    else:
        cmd += ["-c:v", "libx264"]
    cmd += ["-vf", vf, "-pix_fmt", "yuv420p", str(out_mp4)]
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError:
        # Fallback without burn-in if libass missing
        cmd2 = [ffmpeg, "-y", "-i", str(raw)]
        if audio and audio.exists():
            cmd2 += ["-i", str(audio), "-c:v", "copy", "-c:a", "aac", "-shortest", str(out_mp4)]
        else:
            cmd2 += ["-c", "copy", str(out_mp4)]
        subprocess.check_call(cmd2)
        print("Note: subtitles burnt-in failed; sidecar SRT kept next to the MP4.")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    slides = render_slides()
    srt = write_srt()
    concat = write_concat(slides)
    total = sum(d for d, *_ in SEGMENTS)
    audio = OUT / "narration.mp3"
    has_voice = False
    try:
        has_voice = asyncio.run(synthesize_voice(audio))
    except Exception as exc:  # noqa: BLE001
        print(f"TTS skipped: {exc}")
    if not has_voice:
        audio = OUT / "silence.wav"
        silent_audio(audio, total)
        print("No edge-tts voice; using silence + subtitles.")
    out_mp4 = OUT / "AI_Museum_demo.mp4"
    run_ffmpeg(concat, srt, audio, out_mp4)
    print(f"Wrote {out_mp4}")
    print(f"Subtitles {srt}")


if __name__ == "__main__":
    main()
