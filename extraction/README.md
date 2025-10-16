# FaceOLAT Dataset Extraction Pipeline

This directory contains tools for extracting frames from RED camera footage (.R3D files) for the FaceOLAT dataset.

## Overview

The extraction pipeline converts raw RED camera footage to high-quality EXR images. The dataset is pre-organized by subject with unique IDs already assigned.

The dataset is organized by subject with the following structure:

### Input Structure (Raw Dataset)
```
/INPUT_DIR
├── 001/                          # Subject directories (001-139)
│   ├── ID20001/                  # Unique ID directories
│   │   ├── cameras/
│   │   │   ├── Cam01/C006/       # Camera/Take structure
│   │   │   │   ├── *.R3D         # RED footage files
│   │   │   │   └── *.rtn         # RED metadata files
│   │   │   ├── Cam02/C006/
│   │   │   └── ... (40 cameras total)
│   │   └── timecodes/
│   │       └── Timecode_save1_C006.txt
│   ├── ID30001/                  # Additional unique IDs per subject
│   └── ...
├── 002/
└── ... (139 subjects total)
```

### Output Structure (Extracted EXR Images)
```
/OUTPUT_DIR
├── Cam01/
│   ├── ID20001/
│   │   ├── ID20001.000001.exr    # Frame files
│   │   ├── ID20001.000002.exr
│   │   └── ... (350 OLAT frames)
│   ├── ID30001/
│   └── ...
├── Cam02/
└── ... (40 cameras total)
```

## Extraction Scripts

### `slurm_public.sh` 
SLURM array job for extracting one subject across 40 cameras in parallel.

**Usage:**
```bash
# Process single subject (recommended approach)
sbatch slurm_public.sh 001

# Process another subject  
sbatch slurm_public.sh 050
```

**Configuration:**
Edit paths in the script for your environment:
- **Input**: `INPUT_DIR` (subject directories)  
- **Output**: `OUTPUT_DIR` (extracted EXR images)

### `submit_all_subjects.sh`
Helper script to submit extraction jobs for multiple subjects.

**Usage:**
```bash
# Submit all 139 subjects
./submit_all_subjects.sh

# Submit specific range
./submit_all_subjects.sh 1 10     # Subjects 001 to 010
./submit_all_subjects.sh 50 139   # Subjects 050 to 139
```

### `verify_public.py`
Verification script to check extraction completeness and quality.

**Usage:**
```bash
# Verify all extractions
python verify_public.py /OUTPUT_DIR

# Custom frame count
python verify_public.py /OUTPUT_DIR --expected-frames 350
```
## Requirements

- **REDline SDK** - [https://www.red.com/downloads](https://www.red.com/downloads)
- **Python 3.8+**: `numpy`, `tqdm`, `OpenEXR`, `Imath`
- **SLURM** cluster
- **Storage**: ~9TB for full dataset

**Next step**: [`../color-calibration/submit_avif_all.sh`](../color-calibration/README.md)