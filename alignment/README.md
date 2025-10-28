# FaceOLAT Optical Flow Alignment

This directory performs optical flow-based alignment of AVIF images using the RAFT algorithm.

## Overview

Pipeline: **AVIF Images** → **Flow Computation** → **Alignment** → **Aligned AVIF Images**

- Uses RAFT (Recurrent All-Pairs Field Transforms) for optical flow computation
- Computes flow at 1/4 resolution for efficiency, scales to full resolution
- Multi-GPU distributed processing via SLURM

## RAFT Installation

Clone and set up the RAFT repository inside the `alignment/` directory:

```bash
cd alignment/
git clone https://github.com/princeton-vl/RAFT.git
cd RAFT
./download_models.sh  # Downloads raft-things.pth model
```

**Required folder structure:**
```
alignment/
├── RAFT/
│   ├── models/
│   │   └── raft-things.pth    # Pre-trained RAFT model
│   ├── core/                   # RAFT core modules
│   └── ...
├── flow_align_avif.py
├── slurm_flow_align.sh
└── README.md
```

**RAFT Repository**: [https://github.com/princeton-vl/RAFT](https://github.com/princeton-vl/RAFT)

## Alignment Scripts

### `slurm_flow_align.sh`
SLURM array job for optical flow alignment with multi-GPU processing.

**Usage:**
```bash
# Align single subject 
sbatch slurm_flow_align.sh 001

# Align with overwrite
sbatch slurm_flow_align.sh 001 --overwrite
```

**Features:**
- Flow computation at 1/4 resolution, output at 0.5x resolution
- Center frame: 188, Flow scale: 0.25, Output scale: 0.5

**Configuration:**
Edit paths in the script for your environment:
- **Input**: `INPUT_DIR` (AVIF images)
- **Output**: `OUTPUT_DIR` (aligned AVIF images)
- **Model**: `RAFT_MODEL_PATH` (path to raft-things.pth)

### `check_conversion.py`
Verification script to analyze AVIF conversion completeness before alignment.

**Usage:**
```bash
# Check conversion and prepare aligned folder
python check_conversion.py /INPUT_DIR

# Custom expected frame count
python check_conversion.py /INPUT_DIR 350
```

**Output:**
- Expected aligned folder is `/INPUT_DIR_aligned`
- Generates conversion summary reports per unique ID
- Reports which unique IDs are ready for alignment

## Key Frame Configuration

The alignment uses a **center frame** as reference for flow computation. Choose based on your capture:

**Option 1: Center frame = 188**
```python
full_lights = [0, 20, 41, 62, 83, 104, 125, 146, 167, 188, 209, 230, 251, 272, 293, 314, 335, 348]
```

**Option 2: Center frame = 189**
```python
full_lights = [1, 21, 42, 63, 84, 105, 126, 147, 168, 189, 210, 231, 252, 273, 294, 315, 336, 349]
```

These full-light frames serve as reference points for optical flow interpolation.

### Input Structure (Color-calibrated AVIF from Step 2)
```
/INPUT_DIR                   # AVIF images from color-calibration
├── Cam01/
│   ├── ID20001/
│   │   ├── ID20001.000001.avif
│   │   └── ... (350 OLAT frames)
│   └── ID30001/...
└── Cam02/...
```

### Output Structure
```
/OUTPUT_DIR                  # Flow-aligned AVIF images
├── Cam01/
│   ├── ID20001/
│   │   ├── ID20001.000001.avif    # Aligned frames
│   │   ├── flow_188/              # Flow matrices
│   │   │   ├── flow_001.npy
│   │   │   └── ...
│   │   └── ... (350 OLAT frames)
│   └── ID30001/...
└── Cam02/...
```

## Requirements

- **PyTorch** with CUDA support
- **Python 3.8+**: `numpy`, `PIL`, `pillow_avif`, `torch`
- **RAFT model**: `raft-things.pth` (download via RAFT repo)
- **SLURM** cluster with GPU nodes

**Previous step**: [`../color-calibration/slurm_calibrated_avif.sh`](../color-calibration/README.md)
