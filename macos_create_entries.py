#!/usr/bin/env python3
"""
Emit HTML entries from filenames saved as: YYYY-MM-DD.jpg (date-only).
- Groups by date (YYYY-MM-DD), sorts naturally within each day.
- Outputs ONLY the <section>/<figure> blocks (no full page).
- Works recursively if you ask nicely.

Usage:
  python3 emit_entries_dates_only.py "/path/to/images" -r --base-url ./foto
  python3 emit_entries_dates_only.py "/path/to/images" -r --base-url ./foto --out entries.html
"""

import argparse
import html
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List

DEFAULT_EXTS = {".jpg", ".jpeg"}  # extend via --ext (png/webp/etc.)

# Start-of-stem match. Accepts "-" or "_" as separators: 2024-04-26, 2024_04_26.
DATE_ONLY_RE = re.compile(r"^(?P<y>\d{4})[-_](?P<m>\d{2})[-_](?P<d>\d{2})")

def natural_key(s: str):
    # Human-ish sort: file2 < file10
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]

def collect_files(root: Path, recursive: bool, exts: List[str]) -> List[Path]:
    extset = {"." + e.lower().lstrip(".") for e in exts} if exts else set(DEFAULT_EXTS)
    if recursive:
        files = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in extset]
    else:
        files = [p for p in root.iterdir() if p.is_file() and p.suffix.lower() in extset]
    # Sort by relative path string naturally for deterministic order across subfolders
    files.sort(key=lambda p: natural_key(p.relative_to(root).as_posix()))
    return files

def parse_day_from_stem(stem: str) -> str:
    m = DATE_ONLY_RE.match(stem)
    if not m:
        raise ValueError("filename does not start with YYYY-MM-DD or YYYY_MM_DD")
    y, mo, d = int(m.group("y")), int(m.group("m")), int(m.group("d"))
    datetime(y, mo, d)  # sanity
    return f"{y:04d}-{mo:02d}-{d:02d}"

def build_entries(groups: Dict[str, List[Path]], base_url: str, root: Path,
                  sender: str, symbol: str) -> str:
    esc_sender = html.escape(sender, quote=True)
    esc_symbol = html.escape(symbol, quote=True)

    lines: List[str] = []
    for day in sorted(groups.keys()):
        lines.append(f'<section data-date="{day}">')
        for path in groups[day]:
            rel = path.relative_to(root).as_posix()
            src = f"{base_url.rstrip('/')}/{rel}" if base_url else rel
            # Alt text: simple and non-annoying. If you want the filename, swap to path.stem.
            alt = day
            lines.append(f'  <figure data-sender="{esc_sender}" data-symbol="{esc_symbol}">')
            lines.append(f'    <img src="{src}" alt="{alt}" />')
            lines.append('    <figcaption>Placeholder — scrivi qui la descrizione.</figcaption>')
            lines.append('  </figure>')
        lines.append('</section>')
    return "\n".join(lines)

def main():
    ap = argparse.ArgumentParser(description="Emit HTML entries from YYYY-MM-DD.* filenames.")
    ap.add_argument("folder", help="Folder with images")
    ap.add_argument("-r", "--recursive", action="store_true", help="Scan subfolders too")
    ap.add_argument("--ext", action="append", help="Extra extension(s) to include (repeatable)")
    ap.add_argument("--base-url", default="./foto", help="Prefix for image src (default: ./foto)")
    ap.add_argument("--sender", default="Gegè 👨🏻", help="data-sender value (default: 'Fra 🍐')")
    ap.add_argument("--symbol", default="👨🏻", help="data-symbol value (default: '🍐')")
    ap.add_argument("--out", default="", help="Write output to file instead of stdout")
    ap.add_argument("--skip-nonmatching", action="store_true",
                    help="Silently skip files not starting with YYYY[-_]MM[-_]DD")
    args = ap.parse_args()

    root = Path(args.folder).expanduser().resolve()
    if not root.is_dir():
        raise SystemExit("Path is not a folder.")

    exts = list(DEFAULT_EXTS)
    if args.ext:
        for e in args.ext:
            norm = "." + e.lower().lstrip(".")
            if norm not in exts:
                exts.append(norm)

    files = collect_files(root, args.recursive, exts)
    if not files:
        raise SystemExit("No matching image files found (try --ext png or webp).")

    groups: Dict[str, List[Path]] = defaultdict(list)
    skipped = []

    for p in files:
        try:
            day = parse_day_from_stem(p.stem)
            groups[day].append(p)
        except Exception:
            if args.skip_nonmatching:
                continue
            skipped.append(p)

    if not groups:
        raise SystemExit("No filenames matched the expected pattern YYYY[-_]MM[-_]DD.*")

    html_out = build_entries(groups, args.base_url, root, args.sender, args.symbol)

    if args.out:
        Path(args.out).write_text(html_out, encoding="utf-8")
        print(f"Wrote {args.out}")
        if skipped:
            print(f"Skipped {len(skipped)} non-matching file(s).")
    else:
        print(html_out)
        if skipped:
            print(f"\n<!-- Skipped {len(skipped)} non-matching file(s). -->")

if __name__ == "__main__":
    main()
