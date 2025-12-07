#!/bin/bash
#SBATCH -p cpu20
#SBATCH -t 06:00:00
#SBATCH -c 16
#SBATCH -a 1-40%40
#SBATCH --mem-per-cpu=8000
#SBATCH -o logs/out-%j.out
#SBATCH -e logs/err-%j.err

# FaceOLAT Public Release EXR to AVIF Conversion
# Processes 40 cameras in parallel for a given subject
# Usage: sbatch slurm_avif.sh <subject_id> [--no-color-calibration]
# Example: sbatch slurm_avif.sh 001
# Example: sbatch slurm_avif.sh 001 --no-color-calibration

# Check if subject argument is provided
if [ $# -eq 0 ]; then
    echo "ERROR: Subject ID required"
    echo "Usage: sbatch slurm_avif.sh <subject_id> [--no-color-calibration]"
    echo "Example: sbatch slurm_avif.sh 001"
    echo "Example: sbatch slurm_avif.sh 001 --no-color-calibration"
    exit 1
fi

SUBJECT_ARG=$1
CALIBRATION_FLAG=${2:-""}  # Optional second argument

# Go to base directory
echo "Go to base directory"
STUDIO_TOOLS_PATH=/CT/LS_FRM01/work/faceolat-dataset/
cd ${STUDIO_TOOLS_PATH}/color-calibration

# Activate environment
echo "Activate base environment"
eval "$(conda shell.bash hook)"
conda activate faceolat

# Configuration
INPUT_DIR=/CT/datasets23/static00/FaceOLAT/OutputEXR
OUTPUT_DIR=/CT/datasets23/static00/FaceOLAT/OutputAVIF

# AVIF conversion settings
AVIF_QUALITY=99
EXPECTED_IMAGES=350
GAMMA=1.0
CALIB_MATRIX="colorcalib_exr.mat"

# Convert SLURM array task ID to camera number
CAMERA=$(printf "Cam%02d" $SLURM_ARRAY_TASK_ID)

echo "Processing EXR to AVIF conversion"
echo "Subject: $SUBJECT_ARG, Camera: $CAMERA"
echo "Input directory: $INPUT_DIR"
echo "Output directory: $OUTPUT_DIR"
echo "Quality: $AVIF_QUALITY"
echo "Gamma: $GAMMA"

if [ "$CALIBRATION_FLAG" = "--no-color-calibration" ]; then
    echo "Color calibration: DISABLED"
else
    echo "Calibration matrix: $CALIB_MATRIX"
fi

# Check if input camera directory exists
CAMERA_DIR="$INPUT_DIR/$CAMERA"
if [ ! -d "$CAMERA_DIR" ]; then
    echo "ERROR: Camera directory not found: $CAMERA_DIR"
    exit 1
fi

echo "Found camera directory: $CAMERA_DIR"

# Find unique IDs in this camera folder
UNIQUE_IDS_IN_CAMERA=$(find "$CAMERA_DIR" -maxdepth 1 -type d -name "ID*" -exec basename {} \; | sort)
UNIQUE_ID_COUNT=$(echo "$UNIQUE_IDS_IN_CAMERA" | wc -w)

echo "Found $UNIQUE_ID_COUNT unique IDs in camera $CAMERA"

if [ "$UNIQUE_ID_COUNT" -eq 0 ]; then
    echo "WARNING: No unique ID directories found in $CAMERA_DIR"
    exit 0
fi

# Check if calibration matrix exists (only if calibration is enabled)
if [ "$CALIBRATION_FLAG" != "--no-color-calibration" ]; then
    if [ ! -f "$CALIB_MATRIX" ]; then
        echo "ERROR: Calibration matrix not found: $CALIB_MATRIX"
        echo "Available files in current directory:"
        ls -la *.mat 2>/dev/null || echo "No .mat files found"
        exit 1
    fi
    echo "Using calibration matrix: $CALIB_MATRIX"
fi

# Build conversion arguments
ARGS="$INPUT_DIR $OUTPUT_DIR --cameras $CAMERA --quality $AVIF_QUALITY --expected-images $EXPECTED_IMAGES --workers 8 --gamma $GAMMA"

# Add calibration flag if specified
if [ "$CALIBRATION_FLAG" = "--no-color-calibration" ]; then
    ARGS="$ARGS --no-color-calibration"
else
    ARGS="$ARGS --calib-matrix $CALIB_MATRIX"
fi

# Run EXR to AVIF conversion for this camera
echo "Processing all unique IDs in camera $CAMERA"
python exr2avif.py $ARGS

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Successfully completed AVIF conversion for camera $CAMERA"
else
    echo "❌ AVIF conversion failed for camera $CAMERA (exit code: $EXIT_CODE)"
fi

echo "Completed AVIF conversion for camera $CAMERA"
