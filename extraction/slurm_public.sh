#!/bin/bash
#SBATCH -p cpu20
#SBATCH -t 06:00:00
#SBATCH -c 16
#SBATCH -a 1-40%40
#SBATCH --mem-per-cpu=16000
#SBATCH -o logs/out-%j.out
#SBATCH -e logs/err-%j.err

# FaceOLAT Public Release Extraction
# Processes one subject with 40 parallel camera jobs
# Usage: sbatch slurm_public.sh <subject_id>
# Example: sbatch slurm_public.sh 001

# Check if subject argument is provided
if [ $# -eq 0 ]; then
    echo "ERROR: Subject ID required"
    echo "Usage: sbatch slurm_public.sh <subject_id>"
    echo "Example: sbatch slurm_public.sh 001"
    exit 1
fi

SUBJECT_ARG=$1

# Go to base directory
echo "Go to base directory"
STUDIO_TOOLS_PATH=/CT/LS_FRM01/work/faceolat-dataset/
cd ${STUDIO_TOOLS_PATH}/extraction

# Activate environment
echo "Activate base environment"
source /CT/StudioAndClusterExperiments/static00/miniforge/etc/profile.d/conda.sh
conda activate

# Configuration
INPUT_DIR=/CT/buffer00/nobackup/prao
OUTPUT_DIR=/CT/datasets23/static00/FaceOLAT/OutputEXR

# Convert SLURM array task ID to camera number
CAMERA=$(printf "Cam%02d" $SLURM_ARRAY_TASK_ID)

echo "Processing Subject: $SUBJECT_ARG, Camera: $CAMERA"
echo "Input directory: $INPUT_DIR"
echo "Output directory: $OUTPUT_DIR"

# Check if subject directory exists
SUBJECT_DIR="$INPUT_DIR/$SUBJECT_ARG"
if [ ! -d "$SUBJECT_DIR" ]; then
    echo "ERROR: Subject directory not found: $SUBJECT_DIR"
    exit 1
fi

echo "Found subject directory: $SUBJECT_DIR"

# Count unique IDs in subject
UNIQUE_ID_COUNT=$(find "$SUBJECT_DIR" -maxdepth 1 -type d -name "ID*" | wc -l)
echo "Found $UNIQUE_ID_COUNT unique IDs in subject $SUBJECT_ARG"

if [ "$UNIQUE_ID_COUNT" -eq 0 ]; then
    echo "WARNING: No unique ID directories found in $SUBJECT_DIR"
    exit 0
fi

# Run extraction for this subject and camera
python extract_public.py \
    "$INPUT_DIR" \
    "$OUTPUT_DIR" \
    --subjects "$SUBJECT_ARG" \
    --cameras "$CAMERA" \
    --format exr \
    --frame-count 350

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Successfully completed extraction for subject $SUBJECT_ARG, camera $CAMERA"
else
    echo "❌ Extraction failed for subject $SUBJECT_ARG, camera $CAMERA (exit code: $EXIT_CODE)"
fi

echo "Completed processing subject $SUBJECT_ARG, camera $CAMERA"
