# Watermark Automation

Local Python automation for bulk watermarking real estate listing images.

Image filenames are property IDs used in the database. **Filename preservation is critical.**

## Rules

- Input filename base = Output filename base
- All output is saved as JPG
- No prefix, no suffix, no serial number added

```
12345.jpg   →  12345.jpg
12345.png   →  12345.jpg
12345.webp  →  12345.jpg
```

## Folder Structure

```
Watermark_Automation/
├── Code/
│   ├── watermark_script.py
│   ├── Watermark_image.png
│   └── .env
├── Input Images/
├── Output Images/
├── All Raw/
├── All Processed/
├── Failed Images/
├── requirements.txt
└── README.md
```

## Flow

```
Input Images/   ←  drop images here (or Google Drive syncs them in)
      ↓
  Script runs
      ↓
Output Images/     ←  watermarked JPGs
All Raw/           ←  originals moved here after success
All Processed/     ←  copy of watermarked output kept here
Failed Images/     ←  corrupt, unsupported, or collision files
```

## Supported Formats

JPG, JPEG, PNG, WEBP — all converted to JPG output.

## Setup

```powershell
cd "C:\Users\Login Realty\Google Drive\Watermark_Automation"
pip install -r requirements.txt
```

Copy `Code/.env.sample` to `Code/.env` and adjust paths if needed.

## Run

```powershell
cd Code

# Process all files once and exit
python watermark_script.py

# Keep running, auto-pick up new files every 10 seconds
python watermark_script.py --watch
```

## Configuration

All settings live in `Code/.env`. Key options:

| Setting | Default | Description |
|---|---|---|
| `WATERMARK_TEXT` | `Login Realty` | Text rendered on images |
| `WATERMARK_POSITION` | `lower-center` | Position on image |
| `WATERMARK_OPACITY` | `0.40` | 0.0 = invisible, 1.0 = solid |
| `WATERMARK_SCALE_PERCENT` | `18` | Watermark width as % of image width |
| `OUTPUT_QUALITY` | `92` | JPG quality (1–95) |
| `WATCH_INTERVAL_SECS` | `10` | Polling interval in watcher mode |

## Notes

- Do not rename property image files manually.
- If the processing report CSV is open in Excel, close it before running the script.
- System files like `desktop.ini`, `Thumbs.db`, `.DS_Store`, and `.gitkeep` are automatically ignored.
- Double extensions like `170.jpg.jpeg` are handled correctly → output is `170.jpg`.

## What Gets Committed to GitHub

```
Code/watermark_script.py
Code/Watermark_image.png
Code/.env.sample
requirements.txt
README.md
.gitignore
Input Images/.gitkeep
Output Images/.gitkeep
All Raw/.gitkeep
All Processed/.gitkeep
Failed Images/.gitkeep
```

Do not commit bulk property images or processed output.