# FaceOLAT Camera Calibration

This directory contains camera calibration files for the FaceOLAT dataset.

## Overview

The `cameras/` folder contains pre-calibrated camera parameters for all 139 subjects. Each subject has a corresponding XML file with camera intrinsics and extrinsics for all 40 cameras.

## Camera Files

```
cameras/
├── 001.xml    # Camera calibration for subject 001
├── 002.xml    # Camera calibration for subject 002
├── 003.xml    # Camera calibration for subject 003
...
└── 139.xml    # Camera calibration for subject 139
```

Each XML file contains:
- Camera intrinsics (focal length, principal point, distortion)
- Camera extrinsics (rotation, translation)
- Calibration quality metrics

## Calibration Quality

⚠️ **Important**: Not all cameras were successfully calibrated for all subjects.

The number of successfully calibrated cameras varies by subject:
- **Best case**: 40/40 cameras calibrated (57.7% of subjects)
- **Typical**: 37-39/40 cameras calibrated (42.3% of subjects)
- **Average reprojection error**: 0.6-1.0 pixels (for complete calibrations)

### Checking Calibration Quality

Refer to `calibration_report.txt` for detailed quality metrics:

```bash
# View the calibration report
cat calibration_report.txt
```

The report shows for each subject:
- Number of cameras successfully calibrated (e.g., 40/40, 39/40)
- Average reprojection error in pixels (lower is better)
- Status: COMPLETE (40/40 cameras) or INCOMPLETE (<40 cameras)

**Example from report:**
```
✅ C020  40/40  0.80px  # Excellent calibration
⚠️  C017  39/40  1.20px  # Good, one camera missing
⚠️  C084  23/40  4.26px  # Lower quality, many cameras missing
```

### Improving Calibration (Optional)

If you have access to advanced photogrammetry tools (e.g., Metashape, RealityCapture), you can potentially achieve better camera parameters by:

1. Using the multi-view OLAT captures from this dataset
2. Running your own camera calibration with calibration targets
3. Leveraging the 40-camera multi-view setup for bundle adjustment

The provided camera files offer a good starting point, but custom calibration may improve results for specific applications.

## Usage for 3D Reconstruction

If you want to reconstruct 3D meshes from the OLAT images, you'll need:

1. **Software**: Agisoft Metashape Professional
2. **Input**: Color-calibrated AVIF images (from `color-calibration/` step)
3. **Cameras**: Subject-specific camera file from `cameras/`

### Running Reconstruction

Edit `run_recon.sh` to configure:

```bash
CAMERAS_DIR=./cameras/          # Camera calibration directory
SCAN_NAME=ID20001               # Subject to reconstruct
SCAN_PATH=/path/to/OutputAVIF   # Color-calibrated AVIF images
```

Then run:
```bash
sbatch run_recon.sh
```

The script automatically:
1. Extracts subject number from `SCAN_NAME` (e.g., ID20001 → 001)
2. Loads camera calibration from `cameras/001.xml`
3. Runs Metashape reconstruction

### Subject ID Mapping

| Subject ID | Camera File |
|------------|-------------|
| ID20001    | cameras/001.xml |
| ID30050    | cameras/050.xml |
| ID40100    | cameras/100.xml |

The format is `IDXXnnn` where `nnn` is the subject number (001-139).

## Requirements

- **Agisoft Metashape Professional** (for 3D reconstruction)
- **Python 3.8+**: `numpy`, `Metashape` Python API
- **SLURM** cluster (for batch processing)

## Output

Reconstruction produces:
```
OUTPUT_DIR/
├── avg_images/              # Processed input images
├── project.psx              # Metashape project
├── model.obj                # Reconstructed 3D mesh
├── cameras_export.xml       # Exported camera parameters
└── texture.jpg              # Mesh texture
```

**Previous step**: [`../color-calibration/`](../color-calibration/README.md)

