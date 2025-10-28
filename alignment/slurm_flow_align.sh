#!/bin/bash
#SBATCH -p gpu20
#SBATCH -t 01:00:00
#SBATCH -c 8
#SBATCH -a 1-8%8
#SBATCH --gres gpu:1
#SBATCH --mem-per-cpu=16000
#SBATCH -o logs/out_flow_align-%j.out
#SBATCH -e logs/err_flow_align-%j.err

# FaceOLAT Optical Flow Alignment
# Processes one subject with multi-GPU parallelization
# Usage: sbatch slurm_flow_align.sh <subject_id> [--overwrite]
# Example: sbatch slurm_flow_align.sh 001
# Example: sbatch slurm_flow_align.sh 001 --overwrite

# Check if subject argument is provided
if [ $# -eq 0 ]; then
    echo "ERROR: Subject ID required"
    echo "Usage: sbatch slurm_flow_align.sh <subject_id> [--overwrite]"
    echo "Example: sbatch slurm_flow_align.sh 001"
    echo "Example: sbatch slurm_flow_align.sh 001 --overwrite"
    exit 1
fi

SUBJECT_ARG=$1
OVERWRITE_FLAG=${2:-""}  # Optional second argument

# Go to base directory
echo "Go to base directory"
STUDIO_TOOLS_PATH=/CT/LS_FRM01/work/faceolat-dataset/
cd ${STUDIO_TOOLS_PATH}/alignment

# Activate environment
echo "Activate environment"
eval "$(conda shell.bash hook)"
conda activate 3dpr

# Configuration
INPUT_DIR=/CT/datasets23/static00/FaceOLAT/OutputAVIF
OUTPUT_DIR=/CT/datasets23/static00/FaceOLAT/OutputAVIF_aligned

# Flow alignment settings
CENTER_FRAME=188          # Reference center frame for flow computation
FLOW_SCALE_FACTOR=0.25    # Scale factor for flow computation (1/4 = 0.25)
OUTPUT_SCALE_FACTOR=0.5   # Scale factor for output images (0.5 = half size)
NUM_SLURM_TASKS=8         # Number of parallel GPU tasks (must match #SBATCH -a)

# RAFT model path
RAFT_MODEL_PATH=./RAFT/models/raft-things.pth

echo "Starting optical flow alignment"
echo "Subject: $SUBJECT_ARG, SLURM Task: $SLURM_ARRAY_TASK_ID of $NUM_SLURM_TASKS"
echo "Input directory: $INPUT_DIR"
echo "Output directory: $OUTPUT_DIR"
echo "Center frame: $CENTER_FRAME"
echo "Flow scale factor: $FLOW_SCALE_FACTOR"
echo "Output scale factor: $OUTPUT_SCALE_FACTOR"

if [ "$OVERWRITE_FLAG" = "--overwrite" ]; then
    echo "Overwrite mode: ENABLED"
else
    echo "Overwrite mode: DISABLED (skip existing)"
fi

# Check if RAFT model exists
if [ ! -f "$RAFT_MODEL_PATH" ]; then
    echo "ERROR: RAFT model not found at $RAFT_MODEL_PATH"
    echo "Please download RAFT model or update the path"
    exit 1
fi

echo "Using RAFT model: $RAFT_MODEL_PATH"

# Find all unique IDs matching this subject pattern
# Subject 001 corresponds to ID20001, ID30001, ID40001, ID50001, etc.
echo "Finding unique IDs for subject $SUBJECT_ARG..."
UNIQUE_IDS=""

# Check first camera to find all matching unique IDs
CAMERA="Cam01"
CAMERA_DIR="$INPUT_DIR/$CAMERA"

if [ ! -d "$CAMERA_DIR" ]; then
    echo "ERROR: Camera directory not found: $CAMERA_DIR"
    exit 1
fi

# Find all unique IDs that end with the subject number (e.g., *001 for subject 001)
for uid_dir in "$CAMERA_DIR"/ID*"$SUBJECT_ARG"; do
    if [ -d "$uid_dir" ]; then
        UNIQUE_ID=$(basename "$uid_dir")
        UNIQUE_IDS="$UNIQUE_IDS $UNIQUE_ID"
    fi
done

UNIQUE_ID_COUNT=$(echo "$UNIQUE_IDS" | wc -w)
echo "Found $UNIQUE_ID_COUNT unique IDs for subject $SUBJECT_ARG: $UNIQUE_IDS"

if [ "$UNIQUE_ID_COUNT" -eq 0 ]; then
    echo "WARNING: No unique IDs found for subject $SUBJECT_ARG"
    echo "Expected pattern: ID*$SUBJECT_ARG (e.g., ID20001, ID30001, ID40001)"
    exit 0
fi

# Build command arguments
ARGS="$INPUT_DIR $OUTPUT_DIR \
    --center-frame $CENTER_FRAME \
    --flow-scale-factor $FLOW_SCALE_FACTOR \
    --output-scale-factor $OUTPUT_SCALE_FACTOR \
    --slurm-task-id $SLURM_ARRAY_TASK_ID \
    --slurm-total-tasks $NUM_SLURM_TASKS \
    --model $RAFT_MODEL_PATH \
    --takes $UNIQUE_IDS"

# Add overwrite flag if specified
if [ "$OVERWRITE_FLAG" = "--overwrite" ]; then
    ARGS="$ARGS --overwrite"
fi

# Execute flow alignment
echo "Processing unique IDs for subject $SUBJECT_ARG with GPU $SLURM_ARRAY_TASK_ID"
python flow_align_avif.py $ARGS

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Successfully completed optical flow alignment for subject $SUBJECT_ARG"
else
    echo "❌ Optical flow alignment failed for subject $SUBJECT_ARG (exit code: $EXIT_CODE)"
fi

echo "Completed optical flow alignment for subject $SUBJECT_ARG"
