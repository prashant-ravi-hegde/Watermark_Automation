# Image Watermark Automation

A Python automation script that watches a folder for incoming property images, applies a text watermark, and routes each file to the right place automatically — no manual work needed after setup.

---

## What It Does

You drop images into an input folder. The script picks them up, stamps a watermark on each one, and sorts everything into the right folders:

- The watermarked image goes to **Output Images** — ready to use
- The original is archived in **All Raw**
- A copy of the watermarked output is saved to **All Processed**
- Anything that fails goes to **Failed Images** with a reason logged

Every run is logged to a single CSV report file that keeps growing over time. If a file was already processed successfully in a previous run, it won't be processed again unless you clear the report.

---

## Folder Structure

```
Watermark_Automation/
│
├── Code/
│   ├── watermark_script_v4.py
│   └── .env                      ← your config (not committed to git)
│
├── Input Images/                 ← drop images here
├── Output Images/                ← watermarked output, ready to use
├── All Raw/                      ← original files after processing
├── All Processed/                ← permanent copy of all watermarked images
├── Failed Images/                ← anything that failed or was skipped
└── Reports/
    └── watermark_report.csv
```

---

## Requirements

- Python 3.8+
- Pillow

```bash
pip install Pillow
```

A TrueType font must be available on the system (Arial, Calibri, DejaVu Sans, or Liberation Sans). The script will tell you if it can't find one.

---

## Setup

1. Clone the repository
2. Install dependencies: `pip install Pillow`
3. Copy `.env.example` to `Code/.env` and update the paths and watermark settings
4. Run the script — all folders are created automatically if they don't exist

---

## Running

From inside the `Code/` folder:

**Process all images once and exit:**
```bash
python watermark_script_v4.py
```

**Watch the input folder continuously:**
```bash
python watermark_script_v4.py --watch
```

In watch mode the script checks the input folder every few seconds and stays silent when there's nothing new. It only prints when files are actually being processed.

---

## Configuration

All settings live in `Code/.env`. No code changes needed — just update the values there.

### Folder Paths

```
INPUT_FOLDER         = /path/to/Input Images
OUTPUT_FOLDER        = /path/to/Output Images
ALL_RAW_FOLDER       = /path/to/All Raw
ALL_PROCESSED_FOLDER = /path/to/All Processed
FAILED_FOLDER        = /path/to/Failed Images
REPORTS_FOLDER       = /path/to/Reports
```

Use full absolute paths if your folders are outside the project directory.

### Watermark

```
WATERMARK_TEXT     = Your Text Here
WATERMARK_POSITION = lower-center
WATERMARK_OPACITY  = 0.40
WATERMARK_WIDTH_PX = 200
MARGIN_PERCENT     = 3
```

| Setting | What it controls | Options / Range |
|---|---|---|
| `WATERMARK_TEXT` | The text shown on the image | Any string |
| `WATERMARK_POSITION` | Where the watermark sits | `center`, `lower-center`, `bottom-right`, `bottom-left`, `top-right`, `top-left` |
| `WATERMARK_OPACITY` | How visible the watermark is | `0.0` (invisible) → `1.0` (fully opaque) |
| `WATERMARK_WIDTH_PX` | Fixed watermark width in pixels | Tune based on your smallest image — `150–200` is a good starting point for mixed sizes |
| `MARGIN_PERCENT` | Gap from the edge for non-center positions | Percentage of the shortest image dimension |

### Output

```
OUTPUT_QUALITY      = 92
WATCH_INTERVAL_SECS = 10
```

`OUTPUT_QUALITY` controls JPEG compression (1–95). 92 is high quality with minimal file size increase. `WATCH_INTERVAL_SECS` is how often the watcher checks for new files.

---

## Supported Formats

Accepts `.jpg`, `.jpeg`, `.png`, and `.webp`. All outputs are saved as `.jpg`. The original filename is preserved — only the extension changes if needed.

---

## Report File

`Reports/watermark_report.csv` is a running log of every file processed. New rows are appended each run — the file is never overwritten or duplicated.

| Column | Description |
|---|---|
| `Original_Filename` | The input file name |
| `Output_Filename` | The output file name |
| `Status` | `SUCCESS`, `FAILED`, or `SKIPPED` |
| `Reason` | Why it failed or was skipped |
| `Input_Path` | Full path of the input at time of processing |
| `Output_Path` | Full path of the saved output |
| `Processed_At` | Timestamp of when it was processed |

**To reprocess everything from scratch** — delete `watermark_report.csv`. The script will treat all files as new.

---

## How Duplicates Are Handled

The script checks the report file at the start of each run. If a filename was already processed successfully, it won't be processed again — it goes straight to `Failed Images`. If it previously failed, it will be retried.

---

## Notes

- EXIF rotation is corrected automatically on all images
- Double extensions like `image.jpg.jpeg` are handled — output will be `image.jpg`
- System files like `desktop.ini` and `.DS_Store` are ignored automatically
- If a file with the same name already exists in the destination folder during a move or copy, a numbered suffix is added (`_1`, `_2`, etc.) to avoid overwriting anything