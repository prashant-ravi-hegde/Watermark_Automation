"""
Watermark Automation Script for Login Realty
=============================================
Place this file at: Watermark_Automation/Code/watermark_script.py

Run from the Code/ folder:
    python watermark_script_v4.py           # batch mode (process all new files once)
    python watermark_script_v4.py --watch   # watcher mode (polls Input Images continuously)

Supported input formats: JPG, JPEG, PNG, WEBP
Output format: same filename and extension as input
"""

import csv
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

# ── .env loader ───────────────────────────────────────────────────────────────

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


_SCRIPT_DIR   = Path(__file__).parent.resolve()   # Code/
_PROJECT_ROOT = _SCRIPT_DIR.parent.resolve()       # Watermark_Automation/
load_env(_SCRIPT_DIR / ".env")

# ── Config helpers ────────────────────────────────────────────────────────────

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

# ── Folder paths ──────────────────────────────────────────────────────────────

INPUT_FOLDER         = Path(_env("INPUT_FOLDER",         str(_PROJECT_ROOT / "Input Images")))
OUTPUT_FOLDER        = Path(_env("OUTPUT_FOLDER",        str(_PROJECT_ROOT / "Output Images")))
ALL_RAW_FOLDER       = Path(_env("ALL_RAW_FOLDER",       str(_PROJECT_ROOT / "All Raw")))
ALL_PROCESSED_FOLDER = Path(_env("ALL_PROCESSED_FOLDER", str(_PROJECT_ROOT / "All Processed")))
FAILED_FOLDER        = Path(_env("FAILED_FOLDER",        str(_PROJECT_ROOT / "Failed Images")))
REPORTS_FOLDER       = Path(_env("REPORTS_FOLDER",       str(_PROJECT_ROOT / "Reports")))

# ── Watermark config ──────────────────────────────────────────────────────────

WATERMARK_TEXT      = _env("WATERMARK_TEXT",      "Login Realty")
WATERMARK_POSITION  = _env("WATERMARK_POSITION",  "lower-center")
WATERMARK_OPACITY   = _env_float("WATERMARK_OPACITY", 0.40)
WATERMARK_WIDTH_PX  = _env_int("WATERMARK_WIDTH_PX",  400)
MARGIN_PERCENT      = _env_int("MARGIN_PERCENT",       3)

# ── Output config ─────────────────────────────────────────────────────────────

OUTPUT_QUALITY      = _env_int("OUTPUT_QUALITY",      92)
WATCH_INTERVAL_SECS = _env_int("WATCH_INTERVAL_SECS", 10)

VALID_POSITIONS = {
    "lower-center", "bottom-right", "bottom-left",
    "top-right", "top-left", "center",
}

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

IGNORED_FILENAMES  = {".gitkeep", "desktop.ini", "thumbs.db", ".ds_store"}
IGNORED_EXTENSIONS = {".ini", ".db"}

REPORT_FILE = REPORTS_FOLDER / "watermark_report.csv"
REPORT_FIELDS = [
    "Original_Filename", "Output_Filename", "Status",
    "Reason", "Input_Path", "Output_Path", "Processed_At",
]

# ==============================================================================
# HELPERS
# ==============================================================================

def is_ignored(f: Path) -> bool:
    return (
        f.name.lower() in IGNORED_FILENAMES
        or f.suffix.lower() in IGNORED_EXTENSIONS
        or f.name.startswith(".")
    )


def clean_stem(filename: str) -> str:
    """
    Strip all image extensions to get a clean stem.
    Handles double extensions: IMG.jpg.jpeg → IMG, photo.png → photo
    """
    _img_exts = {".jpg", ".jpeg", ".png", ".webp"}
    p = Path(filename)
    stem = p.stem
    if Path(stem).suffix.lower() in _img_exts:
        stem = Path(stem).stem
    return stem


def ensure_folders():
    for folder in [
        INPUT_FOLDER, OUTPUT_FOLDER, ALL_RAW_FOLDER,
        ALL_PROCESSED_FOLDER, FAILED_FOLDER, REPORTS_FOLDER,
    ]:
        folder.mkdir(parents=True, exist_ok=True)


def validate_config():
    errors = []
    if not WATERMARK_TEXT.strip():
        errors.append("WATERMARK_TEXT must not be empty.")
    if not (0.0 <= WATERMARK_OPACITY <= 1.0):
        errors.append(f"WATERMARK_OPACITY must be 0.0–1.0, got: {WATERMARK_OPACITY}")
    if not (WATERMARK_WIDTH_PX > 0):
        errors.append(f"WATERMARK_WIDTH_PX must be greater than 0, got: {WATERMARK_WIDTH_PX}")
    if WATERMARK_POSITION not in VALID_POSITIONS:
        errors.append(f"Invalid WATERMARK_POSITION '{WATERMARK_POSITION}'. Choose: {VALID_POSITIONS}")
    if errors:
        print("\n[CONFIG ERROR]")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

# ==============================================================================
# DUPLICATE DETECTION  (report-based, name only)
# ==============================================================================

def load_successfully_processed() -> set:
    """
    Read the report CSV and return a set of output filenames already
    processed with SUCCESS. FAILED entries are excluded so they retry.
    """
    processed = set()
    if not REPORT_FILE.exists():
        return processed
    try:
        with open(REPORT_FILE, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("Status", "").strip().upper() == "SUCCESS":
                    name = row.get("Output_Filename", "").strip()
                    if name:
                        processed.add(name)
    except Exception:
        pass
    return processed

# ==============================================================================
# WATERMARK RENDERING
# ==============================================================================

def _load_font(font_size: int) -> ImageFont.FreeTypeFont:
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
    raise RuntimeError(
        "No TrueType font found on this system. "
        "Install one of: Arial, Calibri, DejaVu Sans, or Liberation Sans."
    )


def _find_font_size_for_width(target_width: int, text: str) -> ImageFont.FreeTypeFont:
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


def apply_opacity(wm_img: Image.Image, opacity: float) -> Image.Image:
    r, g, b, a = wm_img.split()
    a = a.point(lambda px: int(px * opacity))
    return Image.merge("RGBA", (r, g, b, a))


def load_watermark(image_width: int, image_height: int) -> Image.Image:
    target_width = max(10, WATERMARK_WIDTH_PX)
    font = _find_font_size_for_width(target_width, WATERMARK_TEXT)

    bbox = font.getbbox(WATERMARK_TEXT)
    text_w  = bbox[2] - bbox[0]
    text_h  = bbox[3] - bbox[1]
    offset_x = -bbox[0]
    offset_y = -bbox[1]

    shadow_offset = max(2, text_h // 18)
    padding  = shadow_offset * 2
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
        y = image_height - wm_height - margin_px
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

def open_image(input_path: Path) -> Image.Image:
    """Open image and apply EXIF rotation fix."""
    img = Image.open(input_path)
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass
    return img


def process_single_image(input_path: Path, output_path: Path):
    """
    Watermark one image and save to output_path as JPG.
    All input formats (PNG, WEBP, JPEG) are flattened onto white and saved as JPEG.
    Returns (status: str, reason: str).
    """
    try:
        img  = open_image(input_path)
        base = img.convert("RGBA")
        iw, ih = base.size

        wm = load_watermark(iw, ih)
        wm_w, wm_h = wm.size
        px, py = calculate_position(iw, ih, wm_w, wm_h)

        overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        overlay.paste(wm, (px, py))
        composited = Image.alpha_composite(base, overlay)

        # Always output as JPG — flatten alpha onto white
        bg = Image.new("RGB", composited.size, (255, 255, 255))
        bg.paste(composited, mask=composited.split()[3])
        bg.save(output_path, format="JPEG", quality=OUTPUT_QUALITY, optimize=True)

        return "SUCCESS", "Watermark applied"

    except RuntimeError as e:
        # Font errors — fatal, stop the run
        raise
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
    dst_folder.mkdir(parents=True, exist_ok=True)
    dst = dst_folder / src.name
    if dst.exists():
        stem, suffix = src.stem, src.suffix
        counter = 1
        while dst.exists():
            dst = dst_folder / f"{stem}_{counter}{suffix}"
            counter += 1
    shutil.move(str(src), str(dst))
    print(f"[{label}] Moved → {dst.relative_to(_PROJECT_ROOT)}")


def safe_copy(src: Path, dst_folder: Path, label: str):
    dst_folder.mkdir(parents=True, exist_ok=True)
    dst = dst_folder / src.name
    if dst.exists():
        stem, suffix = src.stem, src.suffix
        counter = 1
        while dst.exists():
            dst = dst_folder / f"{stem}_{counter}{suffix}"
            counter += 1
    shutil.copy2(str(src), str(dst))
    print(f"[{label}] Copied → {dst.relative_to(_PROJECT_ROOT)}")

# ==============================================================================
# CSV REPORT  (single persistent file, rows appended)
# ==============================================================================

def append_report(report_rows: list):
    if not report_rows:
        return
    REPORTS_FOLDER.mkdir(parents=True, exist_ok=True)
    file_exists = REPORT_FILE.exists()
    with open(REPORT_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=REPORT_FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerows(report_rows)
    print(f"[REPORT] {len(report_rows)} row(s) appended → {REPORT_FILE.name}")

# ==============================================================================
# BATCH PROCESSING
# ==============================================================================

def run_batch():
    candidate_files = [
        f for f in sorted(INPUT_FOLDER.iterdir())
        if f.is_file() and not is_ignored(f)
    ]

    if not candidate_files:
        return  # silent — nothing to do

    image_files = [f for f in candidate_files if f.suffix.lower() in SUPPORTED_EXTENSIONS]
    other_files = [f for f in candidate_files if f.suffix.lower() not in SUPPORTED_EXTENSIONS]

    if not image_files and not other_files:
        return

    previously_done = load_successfully_processed()

    report_rows = []
    count_ok = count_fail = count_skip = 0

    # ── Unsupported file types ─────────────────────────────────────────
    for f in other_files:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[SKIP]  {f.name}  — unsupported format")
        safe_move(f, FAILED_FOLDER, "FAILED")
        report_rows.append({
            "Original_Filename": f.name,
            "Output_Filename":   "",
            "Status":            "FAILED",
            "Reason":            "Unsupported file format",
            "Input_Path":        str(f),
            "Output_Path":       "",
            "Processed_At":      timestamp,
        })
        count_fail += 1

    # ── Image files ───────────────────────────────────────────────────
    if image_files:
        print(f"\n[BATCH] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  —  {len(image_files)} file(s) found")

    for input_file in image_files:
        timestamp   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        output_name = clean_stem(input_file.name) + ".jpg"
        output_path = OUTPUT_FOLDER / output_name

        # ── Already successfully processed ────────────────────────────
        if output_name in previously_done:
            print(f"[SKIP]  {input_file.name}  — already processed previously")
            safe_move(input_file, FAILED_FOLDER, "FAILED")
            report_rows.append({
                "Original_Filename": input_file.name,
                "Output_Filename":   output_name,
                "Status":            "SKIPPED",
                "Reason":            "Already successfully processed in a previous run",
                "Input_Path":        str(input_file),
                "Output_Path":       "",
                "Processed_At":      timestamp,
            })
            count_skip += 1
            continue

        # ── Process ───────────────────────────────────────────────────
        print(f"[START] {input_file.name}  →  {output_name}")
        status, reason = process_single_image(input_file, output_path)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if status == "SUCCESS":
            print(f"[OK]    {output_name}")
            safe_move(input_file, ALL_RAW_FOLDER, "RAW")
            safe_copy(output_path, ALL_PROCESSED_FOLDER, "PROCESSED")
            count_ok += 1
        else:
            print(f"[FAIL]  {input_file.name}  —  {reason}")
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

    if image_files:
        print(f"[DONE]  OK={count_ok}  FAILED={count_fail}  SKIPPED={count_skip}\n")

    append_report(report_rows)

# ==============================================================================
# WATCHER MODE
# ==============================================================================

def run_watcher():
    print(f"[WATCH] Watching Input Images/ every {WATCH_INTERVAL_SECS}s  —  Ctrl+C to stop\n")
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

    print(f"[CONFIG] Input     : {INPUT_FOLDER}")
    print(f"[CONFIG] Output    : {OUTPUT_FOLDER}")
    print(f"[CONFIG] Watermark : '{WATERMARK_TEXT}' | pos={WATERMARK_POSITION} | opacity={WATERMARK_OPACITY} | width={WATERMARK_WIDTH_PX}px\n")

    if "--watch" in sys.argv:
        run_watcher()
    else:
        run_batch()


if __name__ == "__main__":
    main()