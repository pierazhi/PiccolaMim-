#!/usr/bin/env python3
"""
Rename photos/videos by actual capture date using exiftool.
- Works with HEIC, JPG/JPEG, PNG, MOV, MP4.
- Prefers: DateTimeOriginal (photos) -> MediaCreateDate (videos) -> CreateDate -> TrackCreateDate.
- Skips files with no metadata capture date.
- Skips files whose metadata date is between today and N days ago (default N=5).
- Falls back to file mtime ONLY if --allow-mtime is provided.
- Adds -1, -2, ... if multiple files share the same second.

Usage:
  python3 rename_by_capture_time.py "/path/to/folder" -r --dry-run
  python3 rename_by_capture_time.py "/path/to/folder" -r
"""

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

VALID_EXTS = {".heic", ".jpg", ".jpeg", ".png", ".mov", ".mp4"}

def ensure_exiftool():
    if shutil.which("exiftool") is None:
        sys.exit("exiftool not found. Install it first (macOS: brew install exiftool).")

def parse_dt_str(s: str):
    """Parse a variety of datetime strings, return naive local time."""
    if not s:
        return None
    s = s.strip().replace("UTC ", "").replace("utc ", "")
    s = s.replace("Z", "+00:00")  # ISO-ish
    fmts = [
        "%Y:%m:%d %H:%M:%S%z",
        "%Y:%m:%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y:%m:%d %H.%M.%S",
        "%Y-%m-%d %H.%M.%S",
    ]
    for fmt in fmts:
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is not None:
                dt = dt.astimezone().replace(tzinfo=None)
            return dt
        except Exception:
            continue
    return None

def get_dt_via_exiftool(path: Path):
    """
    Ask exiftool for capture date. QuickTimeUTC=1 corrects iPhone video quirks.
    Preference order is applied below.
    """
    cmd = [
        "exiftool", "-j", "-api", "QuickTimeUTC=1",
        "-DateTimeOriginal", "-MediaCreateDate", "-CreateDate", "-TrackCreateDate",
        str(path)
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        arr = json.loads(res.stdout)
        if not arr:
            return None
        data = arr[0]
    except Exception:
        return None

    for key in ("DateTimeOriginal", "MediaCreateDate", "CreateDate", "TrackCreateDate"):
        val = data.get(key)
        if val:
            dt = parse_dt_str(val)
            if dt:
                return dt
    return None

def build_target_name(dt: datetime, ext: str, taken_lower: set, pattern: str):
    base = dt.strftime(pattern)
    ext_lc = ext.lower()
    candidate = f"{base}{ext_lc}"
    i = 1
    while candidate.lower() in taken_lower:
        candidate = f"{base}-{i}{ext_lc}"
        i += 1
    taken_lower.add(candidate.lower())
    return candidate

def iter_files(root: Path, recursive: bool):
    if recursive:
        yield from (p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in VALID_EXTS)
    else:
        yield from (p for p in root.iterdir() if p.is_file() and p.suffix.lower() in VALID_EXTS)

def main():
    ap = argparse.ArgumentParser(description="Rename photos/videos by capture date using exiftool.")
    ap.add_argument("folder", help="Folder to process")
    ap.add_argument("-r", "--recursive", action="store_true", help="Process subfolders")
    ap.add_argument("--dry-run", action="store_true", help="Show planned changes only")
    ap.add_argument("--verbose-skip", action="store_true", help="Print reasons for skipped files")
    ap.add_argument(
        "--pattern",
        default="%Y-%m-%d_%H%M%S",
        help="strftime pattern for filename stem (default: %(default)s)"
    )
    ap.add_argument(
        "--recent-days",
        type=int,
        default=5,
        help="Skip files whose metadata date is within the last N days (default: 5; use 0 to disable)."
    )
    ap.add_argument(
        "--allow-mtime",
        action="store_true",
        help="If set, fall back to file mtime when no metadata date is available (otherwise skip)."
    )
    args = ap.parse_args()

    ensure_exiftool()

    root = Path(args.folder).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        sys.exit("Path is not a folder.")

    # For the recent window
    now = datetime.now()
    cutoff = now - timedelta(days=max(args.recent_days, 0))

    # Track existing names per directory to avoid collisions
    taken_map = {}
    planned = []

    skipped_missing = 0
    skipped_recent = 0

    for f in sorted(iter_files(root, args.recursive)):
        dt = get_dt_via_exiftool(f)
        if dt is None:
            if args.allow_mtime:
                dt = datetime.fromtimestamp(f.stat().st_mtime)
            else:
                skipped_missing += 1
                if args.verbose_skip:
                    print(f"[SKIP missing date] {f}")
                continue

        # Skip recent files if requested
        if args.recent_days > 0 and cutoff <= dt <= now:
            skipped_recent += 1
            if args.verbose_skip:
                print(f"[SKIP recent {args.recent_days}d] {f}  ({dt.strftime('%Y-%m-%d %H:%M:%S')})")
            continue

        d = f.parent
        taken = taken_map.setdefault(
            str(d),
            {x.name.lower() for x in d.iterdir() if x.is_file()}
        )
        new_name = build_target_name(dt, f.suffix, taken, args.pattern)
        new_path = d / new_name
        if new_path != f:
            planned.append((f, new_path))

    if args.dry_run:
        for src, dst in planned:
            print(f"[DRY] {src}  ->  {dst}")
        print(f"\nTotal to rename: {len(planned)}")
        if skipped_missing:
            print(f"Skipped (no metadata date): {skipped_missing}")
        if skipped_recent:
            print(f"Skipped (within last {args.recent_days} days): {skipped_recent}")
        return

    # Do the rename
    count = 0
    for src, dst in planned:
        try:
            src.rename(dst)
            count += 1
            print(f"Renamed: {src.name} -> {dst.name}")
        except Exception as e:
            print(f"FAILED: {src} -> {dst}  ({e})", file=sys.stderr)
    print(f"\nDone. Renamed {count} files out of {len(planned)} planned.")
    if skipped_missing:
        print(f"Skipped (no metadata date): {skipped_missing}")
    if skipped_recent:
        print(f"Skipped (within last {args.recent_days} days): {skipped_recent}")

if __name__ == "__main__":
    main()
