# FaceOLAT Dataset Processing Pipeline

This repository provides processing tools for the **FaceOLAT dataset** - a large-scale multi-view 4K OLAT dataset of 139 subjects.  This dataset is part of the work **"3DPR: Single Image 3D Portrait Relighting with Generative Priors"**.

## About the Dataset

The FaceOLAT dataset is hosted at [https://gvv-assets.mpi-inf.mpg.de/FaceOLAT/](https://gvv-assets.mpi-inf.mpg.de/FaceOLAT/) and is available for academic research purposes only. This dataset consists of `9 TB` of One-Light-At-a-Time (OLAT) captures that can be useful for learning human face reflectance distribution for image-based relighting applications.

For more information about the dataset and the related work, please visit the project page at [https://vcai.mpi-inf.mpg.de/projects/3dpr/](https://vcai.mpi-inf.mpg.de/projects/3dpr/).

Explore the **[FaceOLAT capture gallery](DATASET.md)** to see all 407 released capture IDs and expressions.

## Processing Pipeline

The pipeline converts raw RED camera footage (.R3D) into color-calibrated AVIF images suitable for image-based relighting applications:

```
Step 1: Frame Extraction     → High-quality EXR images (extraction/)
Step 2: Color Calibration   → Color-corrected AVIF images (color-calibration/)
Step 3: Flow Alignment      → Temporally aligned sequences (alignment/)
Step 4: Relighting          → Novel lighting synthesis (relighting/)
Step 5: Camera Calibration and FLAME Tracking → Camera parameters and FLAME head model parameters (TODO)
```

## Directory Structure

### Available Processing Steps

- **[`extraction/`](extraction/README.md)** - Extract frames from RED camera footage to EXR format
- **[`color-calibration/`](color-calibration/README.md)** - Apply professional color correction and convert to AVIF
- **[`alignment/`](alignment/README.md)** - Optical flow alignment for temporal consistency
- **[`relighting/`](relighting/README.md)** - Synthesize novel lighting using environment maps
- **[`calibration/`](calibration/README.md)** - Pre-calibrated camera parameters for 3D reconstruction (optional)

## Quick Start Guide

After downloading the raw unprocessed dataset, you can start the processing pipeline by following the steps below.

### Step 1: Frame Extraction 

Extract high-quality EXR images from RED camera footage:

```bash
cd extraction/
sbatch slurm_public.sh 001  # Process subject 001 (Recommend using this)
./submit_all_subjects.sh     # Process all subjects 001-139
```

See [`extraction/README.md`](extraction/README.md) for detailed instructions.

### Step 2: Color Calibration & AVIF Conversion

Apply color correction and convert to AVIF format:

```bash
cd color-calibration/
# Convert single subject with color calibration
sbatch slurm_calibrated_avif.sh 001
# Convert single subject without color calibration
sbatch slurm_calibrated_avif.sh 001 --no-color-calibration

# Process all subjects
./submit_avif_all.sh
```

See [`color-calibration/README.md`](color-calibration/README.md) for detailed instructions.

### Step 3: Optical Flow Alignment

Apply optical flow alignment for temporal consistency:

```bash
cd alignment/
# Install RAFT: https://github.com/princeton-vl/RAFT

# Align single subject
sbatch slurm_flow_align.sh 001

# Align with overwrite
sbatch slurm_flow_align.sh 001 --overwrite
```

See [`alignment/README.md`](alignment/README.md) for detailed instructions.

### Step 4: Relighting

Synthesize novel lighting conditions using environment maps:

```bash
cd relighting/

# Relight single subject (default: grace cathedral)
sbatch slurm_relight.sh ID20003

# Relight with custom environment and scale
sbatch slurm_relight.sh ID20003 --envname studio --envscale 0.02

# Batch processing
./submit_relight_batch.sh --subject ID20003
```

See [`relighting/README.md`](relighting/README.md) for detailed instructions.

## Dataset Details

- **139 subjects** with diverse facial characteristics and skin tones
- **40 Komodo RED cameras** capturing 4K resolution imagery  
- **OLAT (One-Light-at-A-Time) sequences** with 350 lighting conditions per take
- **Professional color calibration** for accurate color reproduction
- **High dynamic range** EXR format preserving lighting details

## Requirements

### Software Dependencies
- **Python 3.8+** with packages: `numpy`, `OpenEXR`, `PIL`, `pillow_avif`, `torch` (PyTorch)
- **REDline SDK** for .R3D file processing - [https://www.red.com/downloads](https://www.red.com/downloads)
- **RAFT** for optical flow alignment - [https://github.com/princeton-vl/RAFT](https://github.com/princeton-vl/RAFT)
- **SLURM** or other workload manager for distributed processing

**Optional (for 3D reconstruction)**:
- **Agisoft Metashape Professional** - [https://www.agisoft.com/](https://www.agisoft.com/)

### Hardware Requirements  
- **Storage**: ~9TB per full 40-camera dataset and 139 subjects. Note this is only the RAW data. Consider additional storage for the processed data.

## Output Format

The processing pipeline produces a structured dataset:

```
/OUTPUT_DIR
├── Cam01/
│   ├── ID20001/          # Subject expression sequence
│   │   ├── ID20001.000001.avif
│   │   ├── ID20001.000002.avif
│   │   └── ... (350 OLAT images)
│   ├── ID20002/
│   └── ...
├── Cam02/
└── ... (40 cameras total)
```

Each unique ID (e.g., `ID20001`) represents a complete OLAT sequence with 350 different lighting conditions captured from a specific camera viewpoint.

For detailed processing instructions, refer to the documentation in each subdirectory.

---

## License & Usage

This dataset is intended for academic and research purposes. Please refer to the dataset website for licensing terms and usage guidelines:

**Dataset Access**: [https://gvv-assets.mpi-inf.mpg.de/FaceOLAT/](https://gvv-assets.mpi-inf.mpg.de/FaceOLAT/)

---
## Citation

If you use the FaceOLAT dataset in your research, please cite:

```bibtex
@article{prao20253dpr,
    title = {3DPR: Single Image 3D Portrait Relighting with Generative Priors},
    author = {Rao, Pramod and Zhou, Xilong and Meka, Abhimitra  and Fox, Gereon and B R, Mallikarjun and Zhan, Fangneng and Weyrich, Tim and Bickel, Bernd and Seidel, Hans-Peter and Pfister, Hanspeter and Matusik, Wojciech and Elgharib, Mohamed and Theobalt, Christian },
    booktitle = {ACM SIGGRAPH ASIA 2025 Conference Proceedings},
    year={2025}
}
```
