#!/usr/bin/env python3
"""
Recursively convert image files to AVIF.

By default, the script:
- scans the current directory recursively
- skips common dependency/build directories
- writes `name.avif` next to each source image
- deletes the original file after a successful conversion
- skips files whose `.avif` output already exists

Supported source extensions:
  .jpg, .jpeg, .png, .webp, .bmp, .tif, .tiff, .gif

Conversion backends are tried in this order:
  1. avifenc
  2. magick (ImageMagick)
  3. ffmpeg
  4. Pillow with AVIF support
"""

from __future__ import annotations

import argparse
import importlib
import os
import shutil
import subprocess
import sys
from pathlib import Path


SUPPORTED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
    ".gif",
}

DEFAULT_EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recursively convert images to AVIF.")
    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        help="Root directory to scan. Defaults to the current directory.",
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=60,
        help="Target quality from 0 to 100. Defaults to 60.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing .avif files instead of skipping them.",
    )
    parser.add_argument(
        "--keep-originals",
        action="store_true",
        help="Keep the original file after a successful conversion.",
    )
    parser.add_argument(
        "--exclude-dir",
        action="append",
        default=[],
        help="Directory name to exclude. Can be passed multiple times.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print each conversion command as it runs.",
    )
    return parser.parse_args()


def ensure_valid_quality(quality: int) -> int:
    if not 0 <= quality <= 100:
        raise SystemExit("--quality must be between 0 and 100.")
    return quality


def find_backend() -> str:
    if shutil.which("avifenc"):
        return "avifenc"
    if shutil.which("magick"):
        return "magick"
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    if pillow_backend_available():
        return "pillow"

    raise SystemExit(
        "No AVIF conversion backend is available.\n"
        "Install one of: avifenc, ImageMagick (`magick`), ffmpeg, or Pillow with AVIF support."
    )


def pillow_backend_available() -> bool:
    if importlib.util.find_spec("PIL") is None:
        return False

    try:
        from PIL import Image  # type: ignore
    except Exception:
        return False

    try:
        import pillow_avif  # type: ignore  # noqa: F401
    except Exception:
        pass

    try:
        import pillow_avif_plugin  # type: ignore  # noqa: F401
    except Exception:
        pass

    registered_extensions = getattr(Image, "registered_extensions", lambda: {})()
    formats = {fmt.upper() for fmt in registered_extensions.values()}
    return "AVIF" in formats or ".avif" in registered_extensions


def iter_image_files(root: Path, excluded_dirs: set[str]) -> list[Path]:
    image_paths: list[Path] = []
    for current_root, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in excluded_dirs]
        current_path = Path(current_root)
        for filename in filenames:
            source = current_path / filename
            if source.suffix.lower() in SUPPORTED_EXTENSIONS:
                image_paths.append(source)
    image_paths.sort()
    return image_paths


def output_path_for(source: Path) -> Path:
    return source.with_suffix(".avif")


def quality_to_avifenc_cq(quality: int) -> int:
    return max(0, min(63, round((100 - quality) * 63 / 100)))


def quality_to_ffmpeg_crf(quality: int) -> int:
    return max(0, min(63, round((100 - quality) * 63 / 100)))


def run_command(command: list[str], verbose: bool) -> None:
    if verbose:
        print(" ".join(command))
    subprocess.run(command, check=True)


def convert_with_backend(source: Path, target: Path, quality: int, backend: str, verbose: bool) -> None:
    if backend == "avifenc":
        cq = quality_to_avifenc_cq(quality)
        run_command(
            [
                "avifenc",
                "--min",
                str(cq),
                "--max",
                str(cq),
                str(source),
                str(target),
            ],
            verbose,
        )
        return

    if backend == "magick":
        run_command(
            [
                "magick",
                str(source),
                "-quality",
                str(quality),
                str(target),
            ],
            verbose,
        )
        return

    if backend == "ffmpeg":
        crf = quality_to_ffmpeg_crf(quality)
        run_command(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(source),
                "-c:v",
                "libaom-av1",
                "-still-picture",
                "1",
                "-crf",
                str(crf),
                "-b:v",
                "0",
                str(target),
            ],
            verbose,
        )
        return

    if backend == "pillow":
        from PIL import Image  # type: ignore

        with Image.open(source) as image:
            if image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
            image.save(target, format="AVIF", quality=quality)
        return

    raise RuntimeError(f"Unsupported backend: {backend}")


def main() -> int:
    args = parse_args()
    quality = ensure_valid_quality(args.quality)
    root = Path(args.root).resolve()

    if not root.exists():
        print(f"Root path does not exist: {root}", file=sys.stderr)
        return 1

    excluded_dirs = DEFAULT_EXCLUDED_DIRS | set(args.exclude_dir)
    backend = find_backend()
    image_files = iter_image_files(root, excluded_dirs)

    if not image_files:
        print(f"No supported image files found under {root}")
        return 0

    converted = 0
    skipped = 0
    failed = 0

    print(f"Using backend: {backend}")
    print(f"Scanning: {root}")
    print(f"Found {len(image_files)} image(s)")

    for source in image_files:
        target = output_path_for(source)
        if target.exists() and not args.overwrite:
            skipped += 1
            print(f"skip  {source} -> {target} (already exists)")
            continue

        target.parent.mkdir(parents=True, exist_ok=True)

        try:
            convert_with_backend(source, target, quality, backend, args.verbose)
            converted += 1
            print(f"ok    {source} -> {target}")
            if not args.keep_originals and source != target:
                source.unlink()
        except subprocess.CalledProcessError as exc:
            failed += 1
            print(f"fail  {source} (backend exited with {exc.returncode})", file=sys.stderr)
            if target.exists():
                target.unlink(missing_ok=True)
        except Exception as exc:
            failed += 1
            print(f"fail  {source} ({exc})", file=sys.stderr)
            if target.exists():
                target.unlink(missing_ok=True)

    print(
        f"Done. converted={converted} skipped={skipped} failed={failed}"
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
