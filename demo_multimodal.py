"""Live multimodal demo — analyze a real downloaded image with GPT-4o vision.

Usage:
    python demo_multimodal.py                      # uses a default sample image
    python demo_multimodal.py path/to/image.jpg     # analyze a specific image
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from agents.llm_config import build_llm_client

from multimodal.analyze_image import analyze_image

DEFAULT_IMAGE = "data/raw/images/gdelt_news/architecture/119199647147.jpg"


def pick_image() -> str:
    if len(sys.argv) > 1:
        return sys.argv[1]
    if Path(DEFAULT_IMAGE).exists():
        return DEFAULT_IMAGE
    # Fall back to whatever real downloaded image we can find.
    for pattern in ("data/raw/images/**/*.jpg", "data/raw/images/**/*.png"):
        matches = list(Path(".").glob(pattern))
        if matches:
            return str(matches[0])
    print("[ERROR] No sample image found under data/raw/images/ — pass a path explicitly.")
    raise SystemExit(1)


def main():
    image_path = pick_image()
    client = build_llm_client()

    print("=" * 65)
    print("  AI Museum of the Future — Live Multimodal Analysis")
    print(f"  Image: {image_path}")
    print("=" * 65)

    result = analyze_image(image_path, openai_client=client)

    print("\nDESCRIPTION:")
    print(" ", result.description.replace("\n", "\n  "))
    print("\nOBJECTS:")
    for o in result.objects:
        print(f"  - {o}")
    print("\nSCENE:")
    print(" ", result.scene or "(none extracted)")
    print("\nTAGS:")
    print(" ", ", ".join(result.tags) if result.tags else "(none extracted)")
    print("\nEMBEDDING:")
    print(f"  {len(result.clip_embedding)}-dim vector generated" if result.clip_embedding else "  (not generated)")

    print("\n" + "=" * 65)
    print("  Done.")
    print("=" * 65)


if __name__ == "__main__":
    main()
