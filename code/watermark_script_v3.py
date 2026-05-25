"""
Watermark Automation Script for Login Realty
=============================================
Place this file at: Watermark_Automation/Code/watermark_script.py

Run from the Code/ folder:
    python watermark_script.py          # batch mode (process all new files once)
    python watermark_script.py --watch  # watcher mode (polls Input Images continuously)

Supported input formats: JPG, JPEG, PNG, WEBP  →  all output as JPG
"""

import csv
import hashlib
import os
import shutil
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ── .env loader (no external dependencies) ────────────────────────────────────

def load_env(env_path: Path):
    """Parse a simple KEY=VALUE .env file and inject into os.environ."""
    if not env_path.exists():
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key   = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


# ── Resolve and load .env before reading config ───────────────────────────────

_SCRIPT_DIR = Path(__file__).parent.resolve()          # Code/
_PROJECT_ROOT = _SCRIPT_DIR.parent.resolve()           # Watermark_Automation/
load_env(_SCRIPT_DIR / ".env")

# ── Configuration (read from environment, with sensible defaults) ─────────────

def _env(key, default=""):
    return os.environ.get(key, default)

def _env_float(key, default):
    try:
        return float(os.environ.get(key, default))
    except (ValueError, TypeError):
        return default

def _env_int(key, default):
    try:
        return int(os.environ.get(key, default))
    except (ValueError, TypeError):
        return default

def _env_bool(key, default):
    v = os.environ.get(key, str(default)).lower()
    return v in ("1", "true", "yes")

INPUT_FOLDER          = Path(_env("INPUT_FOLDER",       str(_PROJECT_ROOT / "Input Images")))
OUTPUT_FOLDER         = Path(_env("OUTPUT_FOLDER",      str(_PROJECT_ROOT / "Output Images")))
ALL_RAW_FOLDER        = Path(_env("ALL_RAW_FOLDER",     str(_PROJECT_ROOT / "All Raw")))
ALL_PROCESSED_FOLDER  = Path(_env("ALL_PROCESSED_FOLDER", str(_PROJECT_ROOT / "All Processed")))
FAILED_FOLDER         = Path(_env("FAILED_FOLDER",      str(_PROJECT_ROOT / "Failed Images")))

WATERMARK_IMAGE       = Path(_env("WATERMARK_IMAGE",    str(_SCRIPT_DIR / "Watermark_image.png")))
WATERMARK_TEXT        = _env("WATERMARK_TEXT",          "Login Realty")
WATERMARK_POSITION    = _env("WATERMARK_POSITION",      "lower-center")
WATERMARK_OPACITY     = _env_float("WATERMARK_OPACITY", 0.40)
WATERMARK_SCALE_PERCENT = _env_int("WATERMARK_SCALE_PERCENT", 18)
MARGIN_PERCENT        = _env_int("MARGIN_PERCENT",       3)

OUTPUT_QUALITY        = _env_int("OUTPUT_QUALITY",       92)
WATCH_INTERVAL_SECS   = _env_int("WATCH_INTERVAL_SECS",  10)
ZIP_FILENAME          = _env("ZIP_FILENAME",             "watermarked_images")
GENERATE_ZIP          = _env_bool("GENERATE_ZIP",        False)

VALID_POSITIONS = {"lower-center", "bottom-right", "bottom-left", "top-right", "top-left", "center"}

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# Files to silently ignore (OS/sync metadata, not real images)
IGNORED_FILENAMES  = {".gitkeep", "desktop.ini", "thumbs.db", ".ds_store"}
IGNORED_EXTENSIONS = {".ini", ".db"}

# ==============================================================================
# FILENAME HELPERS
# ==============================================================================

def get_property_id(filename: str) -> str:
    """
    Extract the clean property ID stem, handling double extensions.

    Examples:
        170.jpg.jpeg  →  170
        381.jpg.jpeg  →  381
        12345.png     →  12345
        12345.jpg     →  12345
    """
    _img_exts = {".jpg", ".jpeg", ".png", ".webp"}
    p = Path(filename)
    stem = p.stem          # strips last extension
    # If what remains still ends in a known image extension, strip again
    if Path(stem).suffix.lower() in _img_exts:
        stem = Path(stem).stem
    return stem


def is_ignored(f: Path) -> bool:
    """Return True for OS/sync metadata files that should be silently skipped."""
    return (
        f.name.lower() in IGNORED_FILENAMES
        or f.suffix.lower() in IGNORED_EXTENSIONS
        or f.name.startswith(".")
    )


# ==============================================================================
# SETUP / VALIDATION
# ==============================================================================

def ensure_folders():
    for folder in [INPUT_FOLDER, OUTPUT_FOLDER, ALL_RAW_FOLDER, ALL_PROCESSED_FOLDER, FAILED_FOLDER]:
        folder.mkdir(parents=True, exist_ok=True)


def validate_config():
    errors = []
    if not WATERMARK_TEXT.strip():
        errors.append("WATERMARK_TEXT must not be empty.")
    if not (0.0 <= WATERMARK_OPACITY <= 1.0):
        errors.append(f"WATERMARK_OPACITY must be 0.0–1.0, got: {WATERMARK_OPACITY}")
    if not (0 < WATERMARK_SCALE_PERCENT <= 100):
        errors.append(f"WATERMARK_SCALE_PERCENT must be 1–100, got: {WATERMARK_SCALE_PERCENT}")
    if WATERMARK_POSITION not in VALID_POSITIONS:
        errors.append(f"Invalid WATERMARK_POSITION '{WATERMARK_POSITION}'. Choose: {VALID_POSITIONS}")
    if errors:
        print("\n[CONFIG ERROR]\n")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)


# ==============================================================================
# DUPLICATE DETECTION
# ==============================================================================

def file_hash(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def find_duplicates(file_list):
    seen = {}
    dupes = {}
    for p in file_list:
        try:
            h = file_hash(p)
        except Exception:
            continue
        if h in seen:
            dupes[p] = seen[h]
        else:
            seen[h] = p
    return dupes


# ==============================================================================
# FONT / WATERMARK RENDERING  (unchanged logic from v2)
# ==============================================================================

def _load_font(font_size):
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, font_size)
            except Exception:
                continue
    return ImageFont.load_default()


def _find_font_size_for_width(target_width, text):
    lo, hi = 8, 800
    best_font = None
    for _ in range(20):
        mid = (lo + hi) // 2
        font = _load_font(mid)
        bbox = font.getbbox(text)
        text_w = bbox[2] - bbox[0]
        if text_w < target_width:
            lo = mid
            best_font = font
        else:
            hi = mid
    return best_font or _load_font(lo)


def apply_opacity(wm_img, opacity):
    r, g, b, a = wm_img.split()
    a = a.point(lambda px: int(px * opacity))
    return Image.merge("RGBA", (r, g, b, a))


def load_watermark(image_width, image_height):
    target_width = max(10, int(image_width * WATERMARK_SCALE_PERCENT / 100))
    font = _find_font_size_for_width(target_width, WATERMARK_TEXT)

    bbox = font.getbbox(WATERMARK_TEXT)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    offset_x = -bbox[0]
    offset_y = -bbox[1]

    shadow_offset = max(2, text_h // 18)
    padding = shadow_offset * 2
    canvas_w = text_w + padding * 2 + shadow_offset
    canvas_h = text_h + padding * 2 + shadow_offset

    shadow_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw_s = ImageDraw.Draw(shadow_layer)
    draw_s.text(
        (padding + offset_x + shadow_offset, padding + offset_y + shadow_offset),
        WATERMARK_TEXT, font=font, fill=(0, 0, 0, 180),
    )
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=shadow_offset))

    text_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw_t = ImageDraw.Draw(text_layer)
    draw_t.text(
        (padding + offset_x, padding + offset_y),
        WATERMARK_TEXT, font=font, fill=(255, 255, 255, 255),
    )

    wm = Image.alpha_composite(shadow_layer, text_layer)
    return apply_opacity(wm, WATERMARK_OPACITY)


def calculate_position(image_width, image_height, wm_width, wm_height):
    margin_px = int(min(image_width, image_height) * MARGIN_PERCENT / 100)
    pos = WATERMARK_POSITION
    if pos == "lower-center":
        x = (image_width - wm_width) // 2
        y = int(image_height * 0.62) - (wm_height // 2)
    elif pos == "bottom-right":
        x = image_width  - wm_width  - margin_px
        y = image_height - wm_height - margin_px
    elif pos == "bottom-left":
        x = margin_px
        y = image_height - wm_height - margin_px
    elif pos == "top-right":
        x = image_width - wm_width - margin_px
        y = margin_px
    elif pos == "top-left":
        x = margin_px
        y = margin_px
    elif pos == "center":
        x = (image_width  - wm_width)  // 2
        y = (image_height - wm_height) // 2
    else:
        raise ValueError(f"Invalid WATERMARK_POSITION: {pos}")
    x = max(0, min(x, image_width  - wm_width))
    y = max(0, min(y, image_height - wm_height))
    return x, y


# ==============================================================================
# IMAGE PROCESSING
# ==============================================================================

def fix_exif_rotation(img: Image.Image) -> Image.Image:
    """Apply EXIF orientation so mobile photos aren't sideways."""
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass
    return img


# Delayed import so we only need it here
from PIL import ImageOps  # noqa: E402


def open_image(input_path: Path):
    """
    Open an image, applying EXIF rotation fix.
    Returns PIL Image or raises an exception.
    """
    img = Image.open(input_path)
    img = fix_exif_rotation(img)
    return img


def process_single_image(input_path: Path, output_path: Path):
    """
    Watermark one image and save as JPG to output_path.
    Returns (status: str, reason: str).
    - All formats are converted to JPG output.
    - output_path should already have .jpg extension.
    """
    try:
        img = open_image(input_path)
        base = img.convert("RGBA")
        iw, ih = base.size

        wm = load_watermark(iw, ih)
        wm_w, wm_h = wm.size
        px, py = calculate_position(iw, ih, wm_w, wm_h)

        overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        overlay.paste(wm, (px, py))
        composited = Image.alpha_composite(base, overlay)

        # Always save as JPG — flatten alpha onto white
        bg = Image.new("RGB", composited.size, (255, 255, 255))
        bg.paste(composited, mask=composited.split()[3])
        bg.save(output_path, format="JPEG", quality=OUTPUT_QUALITY, optimize=True)

        return "SUCCESS", "Watermark applied"

    except Exception as e:
        if output_path.exists():
            try:
                output_path.unlink()
            except Exception:
                pass
        return "FAILED", str(e)


# ==============================================================================
# FOLDER ROUTING HELPERS
# ==============================================================================

def safe_move(src: Path, dst_folder: Path, label: str):
    """Move src to dst_folder. If a file with the same name exists, append a counter."""
    dst_folder.mkdir(parents=True, exist_ok=True)
    dst = dst_folder / src.name
    if dst.exists():
        stem = src.stem
        suffix = src.suffix
        counter = 1
        while dst.exists():
            dst = dst_folder / f"{stem}_{counter}{suffix}"
            counter += 1
    shutil.move(str(src), str(dst))
    print(f"[{label}] Moved → {dst.relative_to(_PROJECT_ROOT)}")


def safe_copy(src: Path, dst_folder: Path, label: str):
    """Copy src to dst_folder. If duplicate name, append counter."""
    dst_folder.mkdir(parents=True, exist_ok=True)
    dst = dst_folder / src.name
    if dst.exists():
        stem = src.stem
        suffix = src.suffix
        counter = 1
        while dst.exists():
            dst = dst_folder / f"{stem}_{counter}{suffix}"
            counter += 1
    shutil.copy2(str(src), str(dst))
    print(f"[{label}] Copied → {dst.relative_to(_PROJECT_ROOT)}")


# ==============================================================================
# CSV REPORT
# ==============================================================================

def write_report(report_rows, folder: Path):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = folder / f"watermark_report_{ts}.csv"
    fieldnames = [
        "Original_Filename", "Output_Filename", "Status",
        "Reason", "Input_Path", "Output_Path", "Processed_At",
    ]
    with open(report_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(report_rows)
    print(f"[REPORT] Saved → {report_path.name}")
    return report_path


# ==============================================================================
# ZIP (optional)
# ==============================================================================

def create_zip(folder: Path, zip_name: str, files):
    if not files:
        return None
    zip_path = folder / f"{zip_name}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in files:
            zf.write(p, arcname=p.name)
    print(f"[ZIP] Created → {zip_path.name}  ({len(files)} files)")
    return zip_path


# ==============================================================================
# BATCH PROCESSING
# ==============================================================================

def run_batch():
    """Scan Input Images, process everything new, route to correct folders."""
    print(f"\n[BATCH] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} — scanning Input Images/")

    candidate_files = [
        f for f in sorted(INPUT_FOLDER.iterdir())
        if f.is_file() and not is_ignored(f)
    ]

    if not candidate_files:
        print("[BATCH] No files found.")
        return

    image_files = [f for f in candidate_files if f.suffix.lower() in SUPPORTED_EXTENSIONS]
    other_files = [f for f in candidate_files if f.suffix.lower() not in SUPPORTED_EXTENSIONS]

    # Move unsupported files straight to Failed
    for f in other_files:
        print(f"[UNSUPPORTED] {f.name}")
        safe_move(f, FAILED_FOLDER, "FAILED")

    if not image_files:
        return

    print(f"[BATCH] {len(image_files)} image(s) to process")

    # Duplicate detection
    dupes = find_duplicates(image_files)
    if dupes:
        print(f"[SCAN] {len(dupes)} duplicate(s) detected")

    report_rows     = []
    successful_paths = []
    count_ok = count_fail = count_dupe = 0

    for input_file in image_files:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Derive clean property ID — handles double extensions like 170.jpg.jpeg → 170
        property_id = get_property_id(input_file.name)
        output_name = property_id + ".jpg"
        output_path = OUTPUT_FOLDER / output_name

        # ── Duplicate input ────────────────────────────────────────────
        if input_file in dupes:
            original_name = dupes[input_file].name
            print(f"[DUPLICATE] {input_file.name}  (same bytes as {original_name})")
            safe_move(input_file, FAILED_FOLDER, "FAILED")
            report_rows.append({
                "Original_Filename": input_file.name, "Output_Filename": "",
                "Status": "SKIPPED", "Reason": f"Duplicate of {original_name}",
                "Input_Path": str(input_file), "Output_Path": "",
                "Processed_At": timestamp,
            })
            count_dupe += 1
            continue

        # ── Output filename collision ──────────────────────────────────
        if output_path.exists():
            print(f"[COLLISION] {output_name} already exists in Output Images/")
            safe_move(input_file, FAILED_FOLDER, "FAILED")
            report_rows.append({
                "Original_Filename": input_file.name, "Output_Filename": "",
                "Status": "FAILED", "Reason": f"Output collision: {output_name} already exists",
                "Input_Path": str(input_file), "Output_Path": "",
                "Processed_At": timestamp,
            })
            count_fail += 1
            continue

        # ── Process ───────────────────────────────────────────────────
        print(f"[PROCESSING] {input_file.name}")
        status, reason = process_single_image(input_file, output_path)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if status == "SUCCESS":
            print(f"[OK] {input_file.name}  →  {output_name}")
            # Move original to All Raw
            safe_move(input_file, ALL_RAW_FOLDER, "RAW")
            # Copy output to All Processed
            safe_copy(output_path, ALL_PROCESSED_FOLDER, "PROCESSED")
            successful_paths.append(output_path)
            count_ok += 1
        else:
            print(f"[FAILED] {input_file.name}  reason: {reason}")
            safe_move(input_file, FAILED_FOLDER, "FAILED")
            count_fail += 1

        report_rows.append({
            "Original_Filename": input_file.name,
            "Output_Filename":   output_name if status == "SUCCESS" else "",
            "Status":            status,
            "Reason":            reason,
            "Input_Path":        str(input_file),
            "Output_Path":       str(output_path) if status == "SUCCESS" else "",
            "Processed_At":      timestamp,
        })

    # ── Summary ───────────────────────────────────────────────────────
    print(f"\n[DONE] OK={count_ok}  FAILED={count_fail}  DUPES={count_dupe}")
    if report_rows:
        write_report(report_rows, OUTPUT_FOLDER)
    if GENERATE_ZIP and successful_paths:
        create_zip(OUTPUT_FOLDER, ZIP_FILENAME, successful_paths)


# ==============================================================================
# WATCHER MODE
# ==============================================================================

def run_watcher():
    print(f"[WATCH] Watcher started. Polling every {WATCH_INTERVAL_SECS}s. Press Ctrl+C to stop.")
    try:
        while True:
            run_batch()
            time.sleep(WATCH_INTERVAL_SECS)
    except KeyboardInterrupt:
        print("\n[WATCH] Stopped.")


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    print("[START] Login Realty Watermark Automation")
    validate_config()
    ensure_folders()

    print(f"[CONFIG] Project root:  {_PROJECT_ROOT}")
    print(f"[CONFIG] Input:         {INPUT_FOLDER}")
    print(f"[CONFIG] Output:        {OUTPUT_FOLDER}")
    print(f"[CONFIG] Watermark:     '{WATERMARK_TEXT}' | pos={WATERMARK_POSITION} | opacity={WATERMARK_OPACITY} | scale={WATERMARK_SCALE_PERCENT}%")

    if "--watch" in sys.argv:
        run_watcher()
    else:
        run_batch()


if __name__ == "__main__":
    main()