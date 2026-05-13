"""
Bulk Watermarking Script for Real Estate Listing Images
========================================================
Place this file at: Watermark_Automation/code/watermark_script.py
Run from the code/ folder: python watermark_script.py
"""

import csv
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ==============================================================================
# EDITABLE CONFIGURATION
# ==============================================================================

INPUT_FOLDER          = r"C:\Users\Login Realty\Documents\Watermark_Automation\input images"
OUTPUT_FOLDER         = r"C:\Users\Login Realty\Documents\Watermark_Automation\Grade A Final"
WATERMARK_IMAGE       = r"C:\Users\Login Realty\Documents\Watermark_Automation\code\Watermark_image.png"

WATERMARK_TEXT        = "Login Realty"   # Text rendered as watermark
WATERMARK_POSITION    = "lower-center"   # lower-center | bottom-right | bottom-left | top-right | top-left | center
WATERMARK_OPACITY     = 0.40             # 0.0 (transparent) to 1.0 (fully opaque)
WATERMARK_SCALE_PERCENT = 20             # watermark text width as % of main image width
MARGIN_PERCENT        = 3               # margin as % of shorter edge (used by edge positions)

SUPPORTED_EXTENSIONS  = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif", ".avif"}

OVERWRITE_EXISTING    = False

# ==============================================================================
# VALID POSITIONS
# ==============================================================================

VALID_POSITIONS = {"lower-center", "bottom-right", "bottom-left", "top-right", "top-left", "center"}


# ==============================================================================
# PATH HELPERS
# ==============================================================================

def get_project_paths():
    """Resolve all paths relative to the script's location."""
    script_dir = Path(__file__).parent.resolve()
    return {
        "input":  (script_dir / INPUT_FOLDER).resolve(),
        "output": (script_dir / OUTPUT_FOLDER).resolve(),
    }


def validate_paths(paths):
    """Validate config before any processing begins. Raises SystemExit on failure."""
    errors = []

    if not paths["input"].exists():
        errors.append(f"Input folder does not exist: {paths['input']}")
    if not WATERMARK_TEXT.strip():
        errors.append("WATERMARK_TEXT must not be empty.")
    if not (0.0 <= WATERMARK_OPACITY <= 1.0):
        errors.append(f"WATERMARK_OPACITY must be between 0 and 1, got: {WATERMARK_OPACITY}")
    if not (0 < WATERMARK_SCALE_PERCENT <= 100):
        errors.append(f"WATERMARK_SCALE_PERCENT must be > 0 and <= 100, got: {WATERMARK_SCALE_PERCENT}")
    if MARGIN_PERCENT < 0:
        errors.append(f"MARGIN_PERCENT must be >= 0, got: {MARGIN_PERCENT}")
    if WATERMARK_POSITION not in VALID_POSITIONS:
        errors.append(f"Invalid WATERMARK_POSITION '{WATERMARK_POSITION}'. Choose from: {VALID_POSITIONS}")
    if not SUPPORTED_EXTENSIONS:
        errors.append("SUPPORTED_EXTENSIONS must not be empty.")

    try:
        paths["output"].mkdir(parents=True, exist_ok=True)
    except Exception as e:
        errors.append(f"Cannot create output folder: {e}")

    if errors:
        print("\n[CONFIG ERROR] Invalid configuration. Fix the following before running:\n")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)


# ==============================================================================
# TEXT WATERMARK HELPERS
# ==============================================================================

def _load_font(font_size):
    """
    Try to load a clean sans-serif system font at the given size.
    Falls back gracefully to Pillow's built-in font if none are found.
    """
    candidates = [
        # Linux / Ubuntu
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        # macOS
        "/Library/Fonts/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNSText.ttf",
        # Windows
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, font_size)
            except Exception:
                continue
    # Pillow built-in fallback (no size control, but always works)
    return ImageFont.load_default()


def _find_font_size_for_width(target_width, text):
    """
    Binary-search the font size that makes `text` render at approximately `target_width` pixels.
    """
    lo, hi = 8, 800
    best_font = None
    for _ in range(20):          # 20 iterations is more than enough precision
        mid = (lo + hi) // 2
        font = _load_font(mid)
        # getbbox returns (left, top, right, bottom)
        bbox = font.getbbox(text)
        text_w = bbox[2] - bbox[0]
        if text_w < target_width:
            lo = mid
            best_font = font
        else:
            hi = mid
    return best_font or _load_font(lo)


def load_watermark(image_width, image_height):
    """
    Render WATERMARK_TEXT as an RGBA image sized to WATERMARK_SCALE_PERCENT% of image_width.
    Uses a white text layer with a subtle dark shadow for visibility on any background.
    Returns the watermark as an RGBA Image with opacity already applied.
    """
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

    # --- Shadow layer (dark, slightly blurred for depth) ---
    shadow_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw_s = ImageDraw.Draw(shadow_layer)
    draw_s.text(
        (padding + offset_x + shadow_offset, padding + offset_y + shadow_offset),
        WATERMARK_TEXT,
        font=font,
        fill=(0, 0, 0, 180),
    )
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=shadow_offset))

    # --- White text layer ---
    text_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw_t = ImageDraw.Draw(text_layer)
    draw_t.text(
        (padding + offset_x, padding + offset_y),
        WATERMARK_TEXT,
        font=font,
        fill=(255, 255, 255, 255),
    )

    # Composite shadow beneath text
    wm = Image.alpha_composite(shadow_layer, text_layer)

    # Apply opacity to the entire watermark
    wm = apply_opacity(wm, WATERMARK_OPACITY)
    return wm


def apply_opacity(watermark_img, opacity):
    """Apply opacity to the watermark's alpha channel only."""
    r, g, b, a = watermark_img.split()
    a = a.point(lambda px: int(px * opacity))
    return Image.merge("RGBA", (r, g, b, a))


def resize_watermark(watermark_img, image_width):
    """No-op: text watermark is already sized to target_width in load_watermark."""
    return watermark_img


def calculate_position(image_width, image_height, wm_width, wm_height):
    """Calculate (x, y) top-left paste coordinates for the watermark."""
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

    # Clamp to image bounds
    x = max(0, min(x, image_width  - wm_width))
    y = max(0, min(y, image_height - wm_height))
    return x, y


# ==============================================================================
# IMAGE PROCESSING
# ==============================================================================

def process_single_image(input_path, output_path, _unused_watermark):
    """
    Apply text watermark to one image and save to output_path with the exact same filename.
    The watermark is generated fresh per image so it scales correctly to each image's dimensions.
    Returns (status, reason).
    """
    ext = input_path.suffix.lower()

    try:
        img = Image.open(input_path)
        original_mode = img.mode

        # Work in RGBA for compositing
        base = img.convert("RGBA")
        iw, ih = base.size

        # Generate text watermark sized to this specific image
        wm = load_watermark(iw, ih)
        wm_w, wm_h = wm.size
        px, py = calculate_position(iw, ih, wm_w, wm_h)

        # Create a transparent overlay and paste the watermark
        overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        overlay.paste(wm, (px, py))

        composited = Image.alpha_composite(base, overlay)

        return save_image_safely(composited, output_path, ext, original_mode)

    except Exception as e:
        return "FAILED", str(e)


def save_image_safely(composited_rgba, output_path, ext, original_mode):
    """
    Save the composited RGBA image using the original extension.
    Never changes the extension. Returns (status, reason).
    """
    try:
        if ext in (".jpg", ".jpeg"):
            # JPEG does not support alpha — flatten onto white background
            bg = Image.new("RGB", composited_rgba.size, (255, 255, 255))
            bg.paste(composited_rgba, mask=composited_rgba.split()[3])
            bg.save(output_path, format="JPEG", quality=95, optimize=True)

        elif ext == ".png":
            composited_rgba.save(output_path, format="PNG", optimize=True)

        elif ext == ".webp":
            composited_rgba.save(output_path, format="WEBP", quality=95, method=6)

        elif ext == ".bmp":
            composited_rgba.convert("RGB").save(output_path, format="BMP")

        elif ext in (".tiff", ".tif"):
            composited_rgba.save(output_path, format="TIFF")

        elif ext == ".avif":
            image.save(output_path, format="AVIF", quality=95)

        else:
            return "FAILED", f"No save handler for extension '{ext}'"

        return "SUCCESS", "Watermark applied"

    except Exception as e:
        # Clean up any partial file
        if output_path.exists():
            try:
                output_path.unlink()
            except Exception:
                pass
        return "FAILED", str(e)


# ==============================================================================
# CSV REPORT
# ==============================================================================

def write_report(report_rows, output_folder):
    """Write processing report CSV inside the output folder."""
    report_path = output_folder / "watermark_processing_report.csv"
    fieldnames = [
        "Original_Filename",
        "Output_Filename",
        "Status",
        "Reason",
        "Input_Path",
        "Output_Path",
        "Processed_At",
    ]
    with open(report_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(report_rows)
    return report_path


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    print("[START] Bulk watermarking started")

    paths = get_project_paths()
    validate_paths(paths)

    input_folder  = paths["input"]
    output_folder = paths["output"]

    print(f"[CONFIG] Input folder:    {input_folder}")
    print(f"[CONFIG] Output folder:   {output_folder}")
    print(f"[CONFIG] Watermark text:  {WATERMARK_TEXT}")
    print(f"[CONFIG] Position:        {WATERMARK_POSITION}")
    print(f"[CONFIG] Opacity:         {WATERMARK_OPACITY}")
    print(f"[CONFIG] Scale:           {WATERMARK_SCALE_PERCENT}%")
    print(f"[CONFIG] Overwrite:       {OVERWRITE_EXISTING}")

    all_files = sorted(input_folder.iterdir())
    report_rows = []
    count_total = 0
    count_success = 0
    count_skipped = 0
    count_failed  = 0

    for input_file in all_files:
        if not input_file.is_file():
            continue

        count_total += 1
        ext_lower = input_file.suffix.lower()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Preserve exact filename (name = stem + suffix, all original capitalization)
        output_path = output_folder / input_file.name

        # Skip unsupported file types
        if ext_lower not in SUPPORTED_EXTENSIONS:
            print(f"[SKIPPED] unsupported file: {input_file.name}")
            report_rows.append({
                "Original_Filename": input_file.name,
                "Output_Filename":   "",
                "Status":            "SKIPPED",
                "Reason":            "Unsupported file type",
                "Input_Path":        str(input_file),
                "Output_Path":       "",
                "Processed_At":      timestamp,
            })
            count_skipped += 1
            continue

        # Skip if output already exists and OVERWRITE_EXISTING is False
        if not OVERWRITE_EXISTING and output_path.exists():
            print(f"[SKIPPED] already exists: {input_file.name}")
            report_rows.append({
                "Original_Filename": input_file.name,
                "Output_Filename":   output_path.name,
                "Status":            "SKIPPED",
                "Reason":            "Output already exists",
                "Input_Path":        str(input_file),
                "Output_Path":       str(output_path),
                "Processed_At":      timestamp,
            })
            count_skipped += 1
            continue

        print(f"[PROCESSING] {input_file.name}")
        status, reason = process_single_image(input_file, output_path, None)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if status == "SUCCESS":
            # Enforce the cardinal rule: input name == output name
            assert input_file.name == output_path.name, \
                f"INTERNAL ERROR: filename mismatch {input_file.name} != {output_path.name}"
            print(f"[SUCCESS] {input_file.name} -> {output_path.name}")
            count_success += 1
        else:
            print(f"[FAILED] {input_file.name} | reason: {reason}")
            count_failed += 1

        report_rows.append({
            "Original_Filename": input_file.name,
            "Output_Filename":   output_path.name if status == "SUCCESS" else "",
            "Status":            status,
            "Reason":            reason,
            "Input_Path":        str(input_file),
            "Output_Path":       str(output_path) if status == "SUCCESS" else "",
            "Processed_At":      timestamp,
        })

    report_path = write_report(report_rows, output_folder)

    print("\n[DONE] Completed")
    print(f"  Total files found:  {count_total}")
    print(f"  Images processed:   {count_success}")
    print(f"  Images skipped:     {count_skipped}")
    print(f"  Images failed:      {count_failed}")
    print(f"  Report path:        {report_path}")
    print(f"  Output folder:      {output_folder}")


if __name__ == "__main__":
    main()