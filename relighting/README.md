# FaceOLAT Relighting

This stage combines OLAT (One-Light-At-a-Time) captures with environment maps to synthesize realistic relighting under novel lighting conditions. The script generates **rotating environment map sequences** showing the subject under continuously varying lighting directions.

## Overview

Pipeline: **AVIF Images** + **Environment Map** → **Weighted Combination** → **Rotating Relit Sequence**

The relighting process:
1. **Loads OLAT captures** - Individual lighting condition images from aligned AVIF output
2. **Loads environment map** - Target lighting environment (HDR .exr format)
3. **Projects environment** - Maps environment lighting onto OLAT basis using Voronoi tessellation
4. **Generates rotation** - Creates rotating light sequence (default: 256 frames)
5. **Combines captures** - Weighted sum of OLAT images to produce relit result for each rotation
6. **Applies gamma** - Gamma correction for proper display (default: γ=2.2)

## Prerequisites

Ensure you have completed the previous pipeline stages:
- ✅ **Step 1**: Frame extraction ([`extraction/`](../extraction/))
- ✅ **Step 2**: Color calibration ([`color-calibration/`](../color-calibration/))
  - ⚠️ **Important**: Use `--no-color-calibration` flag for linear AVIF output (recommended for relighting)
- ✅ **Step 3**: Optical flow alignment ([`alignment/`](../alignment/))

## Quick Start

### Single Subject Relighting

Relight a subject with default settings (grace cathedral environment):

```bash
cd relighting/
sbatch slurm_relight.sh ID20003
```

### Custom Environment and Scale

```bash
sbatch slurm_relight.sh ID20003 --envname studio --envscale 0.02
```

### Change Output Resolution

Adjust the resize factor for different output resolutions:

```bash
# Higher resolution (1/2 of original, 2048x1080)
sbatch slurm_relight.sh ID20003 --resize-factor 2

# Lower resolution (1/8 of original, 512x270)
sbatch slurm_relight.sh ID20003 --resize-factor 8
```

### Batch Processing

Create a subjects file (`subjects_to_relight.txt`):
```text
ID20001
ID20003
ID30005
```

Submit batch jobs:
```bash
./submit_relight_batch.sh --subjects subjects_to_relight.txt
```

Or process a single subject:
```bash
./submit_relight_batch.sh --subject ID20003 --envname grace_cathedral
```

### Verify Results

Check if relighting completed successfully:

```bash
# Verify all subjects
python verify_relight.py /OUTPUT_DIR

# Verify specific subjects
python verify_relight.py /OUTPUT_DIR --subjects ID20003 ID20005

# Verify specific environment
python verify_relight.py /OUTPUT_DIR --envname grace_cathedral
```

## Configuration

### SLURM Script Options

The `slurm_relight.sh` script accepts the following options:

```bash
sbatch slurm_relight.sh <subject_id> [OPTIONS]

Options:
  --envpath PATH       Directory containing environment maps (.exr files)
                       Default: /CT/RelightAvatar/nobackup/tmp/latlongs
  
  --envname NAME       Environment map filename (without .exr extension)
                       Default: grace_cathedral
  
  --envscale FLOAT     Scaling factor for environment intensity
                       Default: 0.01
                       Typical range: 0.001 - 0.1
  
  --gamma FLOAT        Gamma correction for output images
                       Default: 2.2 (standard display)
                       Adjust if output appears too bright/dark
  
  --resize-factor INT  Resize factor for input images
                       Default: 4 (1/4 resolution: 1024x540)
                       Use 2 for half resolution, 8 for 1/8 resolution
  
  --indexmap PATH      Voronoi index map file
                       Default: voronoi_indices.exr
  
  --outdir PATH        Base output directory
                       Default: /OUTPUT_DIR
  
  --cycle INT          Number of rotation frames to generate
                       Default: 256
  
  --start-index INT    Starting rotation frame index
                       Default: 0
```

### Batch Submission Options

The `submit_relight_batch.sh` helper script simplifies batch job submission:

```bash
./submit_relight_batch.sh [OPTIONS]

Options:
  --subjects FILE      File with subject IDs (one per line)
  --subject ID         Process single subject
  --envpath PATH       Directory containing environment maps
  --envname NAME       Environment map name
  --envscale SCALE     Environment scale factor
  --gamma FLOAT        Gamma correction value
  --resize-factor N    Resize factor for input images
  --dry-run            Preview submissions without submitting
  -h, --help           Show help message
```

**Note**: The batch script is a convenience wrapper that calls `slurm_relight.sh` for each subject.

## Input Requirements

### AVIF Captures
- **Location**: `/INPUT_DIR/Cam06/<subject_id>/`
- **Format**: AVIF images (e.g., `ID20003.000001.avif`)
- **Count**: 348 frames with OLAT lighting conditions
- **Color space**: Linear (recommended - use `--no-color-calibration` flag in color calibration step)
- **Resolution**: Original 4096x2160 (resized by factor during loading)

### Environment Maps
- **Location**: Configurable via `--envpath`
- **Format**: HDR .exr files (latitude-longitude format)
- **Resolution**: Must match Voronoi index map dimensions

### Voronoi Index Map
- **File**: `voronoi_indices.exr` (included in repository)
- **Purpose**: Maps environment map pixels to OLAT light indices
- **Format**: Single-channel integer .exr

### Light Pattern Metadata
- **Location**: `lights/` directory
  - `light_pattern_per_frame.json` - Frame-to-light mapping
  - `light_pattern_metadata.json` - Light configuration metadata

## Output Structure

```
/OUTPUT_DIR/
├── ID20003/
│   ├── grace_cathedral_scale0.01/
│   │   ├── 0.png
│   │   ├── 1.png
│   │   ├── ...
│   │   └── 255.png    (256 rotation frames)
│   └── studio_scale0.02/
│       └── ...
├── ID20005/
│   └── ...
└── ...
```

Each output directory contains:
- **PNG images**: sRGB relit frames (numbered 0 to cycle-1)
- **Rotation**: Each frame represents a different rotation angle of the environment

## Important: Input Format for Relighting

⚠️ **For best relighting results, use linear (uncalibrated) AVIF images.**

When running the color calibration step, use the `--no-color-calibration` flag:

```bash
cd color-calibration/
sbatch slurm_calibrated_avif.sh 001 --no-color-calibration
```

**Why linear format?**
- Relighting is a **linear operation** - combining light intensities requires linear color space
- Color-calibrated images (with gamma correction) are in sRGB space, which is non-linear
- Using non-linear images can produce incorrect lighting results

**Note**: Linear AVIF images will appear darker when viewed directly. This is expected - the relighting script applies proper gamma correction (γ=2.2) to the output for display.

## Advanced Usage

### Generate Partial Rotation

Generate only 90-degree rotation (64 frames from a different starting point):

```bash
sbatch slurm_relight.sh ID20003 --cycle 64 --start-index 64
```

### Custom Voronoi Tessellation

Use a different light-to-environment mapping:

```bash
sbatch slurm_relight.sh ID20003 --indexmap custom_voronoi.exr
```

### Dry Run Testing

Test batch submission without actually submitting jobs:

```bash
./submit_relight_batch.sh --subjects test_subjects.txt --dry-run
```

## Performance

- **Single subject processing**: ~10-30 minutes (256 frames, GPU)
- **GPU requirement**: 1 GPU with 16GB+ VRAM recommended
- **CPU memory**: 8GB per core (8 cores = 64GB total)
- **Output size**: ~50-100MB per subject/environment combination

## Notes

- The script currently uses `Cam06` as the reference camera for loading OLAT captures
- For different camera views, modify `load_image()` function in `render_reference_envmap_relit.py`
- **Input color space**: Linear (use `--no-color-calibration` in color calibration step)
- **Output**: sRGB color space (gamma-corrected PNG format)
- **Resolution**: Default resize factor of 4 produces 1024x540 output; adjust with `--resize-factor`

**Previous step**: [`../alignment/`](../alignment/README.md)

