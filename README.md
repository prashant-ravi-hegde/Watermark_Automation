# Watermark Automation

Local Python automation for bulk watermarking real estate listing images.

This project is designed for property listing platform images. The image filenames are property IDs used in the database, so filename preservation is critical.

## Important Rule

The script must preserve every image filename exactly.

```text
Input filename = Output filename
```

Example:

```text
input images/1075.avif
Grade A Final/1075.avif
```

No prefix, no suffix, no serial number, and no extension change.

## Folder Structure

```text
Watermark_Automation/
│
├── code/
│   ├── watermark_script.py
│   └── Watermark_image.png
│
├── input images/
│   └── .gitkeep
│
├── Grade A Final/
│   └── .gitkeep
│
├── requirements.txt
├── README.md
└── .gitignore
```

## What Gets Committed to GitHub

Commit:

```text
code/watermark_script.py
code/Watermark_image.png
requirements.txt
README.md
.gitignore
input images/.gitkeep
Grade A Final/.gitkeep
```

Do not commit bulk property images or final watermarked images.

The `.gitignore` file is configured to ignore:

```text
input images/*
Grade A Final/*
```

but still keep the folders using `.gitkeep`.

## Setup

Open PowerShell or Command Prompt inside the project folder:

```powershell
cd "C:\Users\Login Realty\Documents\Watermark_Automation"
```

Install requirements:

```powershell
pip install -r requirements.txt
```

## Run

The script is inside the `code` folder.

Run it like this:

```powershell
cd code
python watermark_script.py
```

Or from the project root:

```powershell
python .\code\watermark_script.py
```

## Input

Put original property images inside:

```text
input images/
```

Supported image formats depend on the script configuration, but commonly include:

```text
.jpg, .jpeg, .png, .webp, .bmp, .tiff, .tif, .avif
```

## Output

Watermarked images are saved inside:

```text
Grade A Final/
```

The output image keeps the exact same filename as the input image.

## Report

The script creates a processing report:

```text
Grade A Final/watermark_processing_report.csv
```

The report records successful, skipped, and failed files.

If the report file is open in Excel, close it before running the script again. Otherwise, Windows may show a permission error.

## Notes

- Do not rename property image files manually.
- Do not change file extensions manually.
- Keep `OVERWRITE_EXISTING = False` if you want the script to skip already processed images.
- If only one missing image needs processing, keep all existing output images in `Grade A Final` and rerun the script. Existing files will be skipped.
- AVIF support requires `pillow-avif-plugin`, which is included in `requirements.txt`.
