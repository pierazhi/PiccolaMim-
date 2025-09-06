#!/usr/bin/env python3
import argparse
import os
from pathlib import Path
from typing import Optional
from PIL import Image, ImageCms
import pillow_heif
from io import BytesIO

pillow_heif.register_heif_opener()

def to_srgb(img: Image.Image, icc_bytes: Optional[bytes]) -> Image.Image:
    """Convert image to sRGB if an ICC profile is present; otherwise ensure 8-bit RGB."""
    if icc_bytes:
        try:
            src = ImageCms.ImageCmsProfile(BytesIO(icc_bytes))
            dst = ImageCms.createProfile("sRGB")
            # Some HEICs are not in RGB mode; ImageCms will handle conversion
            img = ImageCms.profileToProfile(img, src, dst, outputMode="RGB")
            return img
        except Exception:
            pass  # if conversion fails, fall through to simple convert
    return img.convert("RGB")

def convert_one(src: Path, dst: Path, to_fmt: str, quality: int, srgb: bool, overwrite: bool, dry: bool) -> str:
    if not overwrite and dst.exists():
        return f"SKIP (exists): {src.name} -> {dst.name}"
    with Image.open(src) as im:
        exif_bytes = im.info.get("exif")  # pillow-heif exposes HEIC EXIF here when present
        icc = im.info.get("icc_profile")

        if srgb:
            im = to_srgb(im, icc)
            icc_to_save = None  # already converted, no need to embed original ICC
        else:
            # Ensure we don't accidentally save in modes some encoders hate
            if im.mode not in ("RGB", "L", "LA", "RGBA"):
                im = im.convert("RGB")
            icc_to_save = icc

        if to_fmt == "jpg":
            save_kwargs = dict(format="JPEG", quality=quality, optimize=True, progressive=True)
            if exif_bytes:
                save_kwargs["exif"] = exif_bytes
            if icc_to_save:
                save_kwargs["icc_profile"] = icc_to_save
            if not dry:
                im.save(dst, **save_kwargs)
            return f"JPG: {src.name} -> {dst.name}"

        elif to_fmt == "png":
            # PNG has no widely supported EXIF; we keep ICC profile if present
            save_kwargs = dict(format="PNG", optimize=True)
            if icc_to_save:
                save_kwargs["icc_profile"] = icc_to_save
            if not dry:
                im.save(dst, **save_kwargs)
            return f"PNG: {src.name} -> {dst.name}"

        else:
            return f"ERROR: unsupported format {to_fmt}"

def main():
    ap = argparse.ArgumentParser(description="Convert HEIC to JPG or PNG, preserving color profile and (for JPG) EXIF.")
    ap.add_argument("folder", help="Folder to scan")
    ap.add_argument("-r", "--recursive", action="store_true", help="Recurse into subfolders")
    ap.add_argument("--to", choices=["jpg", "png"], default="jpg", help="Output format (default: jpg)")
    ap.add_argument("--quality", type=int, default=92, help="JPEG quality 1-100 (default: 92)")
    ap.add_argument("--outdir", type=str, default="", help="Output root directory (mirror tree). Default: alongside source")
    ap.add_argument("--overwrite", action="store_true", help="Overwrite existing outputs")
    ap.add_argument("--srgb", action="store_true", help="Convert colors to sRGB for maximum compatibility")
    ap.add_argument("--dry-run", action="store_true", help="Show what would happen, do not write files")
    ap.add_argument("--delete-original", action="store_true", help="Delete .HEIC after successful conversion (not used with --dry-run)")
    args = ap.parse_args()

    root = Path(args.folder).expanduser().resolve()
    if not root.is_dir():
        raise SystemExit("Path is not a folder.")

    heics = (root.rglob("*.HEIC") if args.recursive else root.glob("*.HEIC"))
    heics = list(heics) + (list(root.rglob("*.heic")) if args.recursive else list(root.glob("*.heic")))
    heics.sort()

    out_root = Path(args.outdir).expanduser().resolve() if args.outdir else None
    made = 0
    for src in heics:
        rel = src.relative_to(root)
        stem = src.stem
        ext = f".{args.to}"
        if out_root:
            dst_dir = out_root / rel.parent
        else:
            dst_dir = src.parent
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / f"{stem}{ext}"

        msg = convert_one(src, dst, args.to, args.quality, args.srgb, args.overwrite, args.dry_run)
        print(msg)
        if msg.startswith(("JPG:", "PNG:")):
            made += 1
            if args.delete_original and not args.dry_run:
                try:
                    os.remove(src)
                    print(f"Deleted original: {src}")
                except Exception as e:
                    print(f"Failed to delete {src}: {e}")

    print(f"\nDone. {'Would convert' if args.dry_run else 'Converted'} {made} file(s).")

if __name__ == "__main__":
    main()
