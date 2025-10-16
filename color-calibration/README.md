# FaceOLAT Color-Calibration & AVIF Conversion

This directory converts extracted EXR images to color-calibrated AVIF format.

## Overview

Pipeline: **EXR** → **Color Calibration** → **Gamma Correction** → **AVIF Compression**

- Uses `colorcalib_exr.mat` calibration matrix
- Applies gamma correction (γ=2.2)  
- High-quality AVIF compression (default quality: 95)

## Conversion Scripts

### `slurm_calibrated_avif.sh`
SLURM array job for converting EXR to color-calibrated AVIF.

**Usage:**
```bash
# Convert single subject with color calibration (default)
sbatch slurm_calibrated_avif.sh 001

# Convert without color calibration
sbatch slurm_calibrated_avif.sh 001 --no-color-calibration
```

### `verify_avif.py`
Verification script to check color-calibration completeness.

**Usage:**
```bash
# Verify conversion completeness
python verify_avif.py /INPUT_DIR /OUTPUT_DIR

# Summary only 
python verify_avif.py /INPUT_DIR /OUTPUT_DIR --summary-only
```

### Input Structure (Extracted EXR Dataset from Step 1)
```
/INPUT_DIR                    # EXR images from extraction
├── Cam01/
│   ├── ID20001/
│   │   ├── ID20001.000001.exr
│   │   └── ... (350 OLAT frames)
│   └── ID30001/...
└── Cam02/...
```

### Output Structure  
```
/OUTPUT_DIR                   # Color-calibrated AVIF images
├── Cam01/
│   ├── ID20001/
│   │   ├── ID20001.000001.avif    # Color-calibrated
│   │   └── ... (350 OLAT frames)
│   └── ID30001/...
└── Cam02/...
```

## Requirements

- **Python 3.8+**: `numpy`, `OpenEXR`, `Imath`, `PIL`, `pillow_avif`
- **SLURM** or other workload manager for distributed processing 

**Previous step**: [`../extraction/submit_all_subjects.sh`](../extraction/README.md)
