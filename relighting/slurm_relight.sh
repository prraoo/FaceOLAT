#!/bin/bash
#SBATCH -p gpu20
#SBATCH -t 02:00:00
#SBATCH -c 8
#SBATCH --gres gpu:1
#SBATCH --mem-per-cpu=8000
#SBATCH -o logs/out_relight-%j.out
#SBATCH -e logs/err_relight-%j.err

# FaceOLAT Relighting Script
# Renders relit images using environment maps and OLAT captures
# Generates rotating environment map sequences (default: 256 frames)
# Usage: sbatch slurm_relight.sh <subject_id> [OPTIONS]
# Example: sbatch slurm_relight.sh ID20003
# Example: sbatch slurm_relight.sh ID20003 --envname grace_cathedral --envscale 0.02
# Example: sbatch slurm_relight.sh ID20003 --gamma 1.8 --srgb-input  # For sRGB AVIFs
# Example: sbatch slurm_relight.sh ID20003 --resize-factor 2  # Half resolution

# Check if subject argument is provided
if [ $# -eq 0 ]; then
    echo "ERROR: Subject ID required"
    echo "Usage: sbatch slurm_relight.sh <subject_id> [OPTIONS]"
    echo "Example: sbatch slurm_relight.sh ID20003"
    echo "Example: sbatch slurm_relight.sh ID20003 --envname studio --envscale 0.02"
    echo "Example: sbatch slurm_relight.sh ID20003 --gamma 1.8 --srgb-input"
    echo "Example: sbatch slurm_relight.sh ID20003 --resize-factor 2"
    exit 1
fi

SUBJECT_ARG=$1
shift  # Remove first positional argument

# Default parameters
ENVPATH="./envmaps/"
INDEXMAP="voronoi_indices.exr"
ENVNAME="grace_cathedral"
ENVSCALE="0.01"
OUTPUT_BASE="/CT/VORF_GAN5/nobackup/datasets/evaluation/FaceOLAT_relight_00"
CYCLE="10"
START_INDEX="0"
GAMMA="2.2"  # Gamma correction for linear->sRGB conversion
SRGB_INPUT=false  # Set to true if input AVIFs are in sRGB space
RESIZE_FACTOR="4"  # Resize factor for input images (default: 4 for 1/4 resolution)

# Parse optional arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --envpath)
            ENVPATH="$2"
            shift 2
            ;;
        --indexmap)
            INDEXMAP="$2"
            shift 2
            ;;
        --envname)
            ENVNAME="$2"
            shift 2
            ;;
        --envscale)
            ENVSCALE="$2"
            shift 2
            ;;
        --outdir)
            OUTPUT_BASE="$2"
            shift 2
            ;;
        --cycle)
            CYCLE="$2"
            shift 2
            ;;
        --start-index)
            START_INDEX="$2"
            shift 2
            ;;
        --gamma)
            GAMMA="$2"
            shift 2
            ;;
        --srgb-input)
            SRGB_INPUT=true
            shift
            ;;
        --resize-factor)
            RESIZE_FACTOR="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Available options: --envpath, --indexmap, --envname, --envscale, --outdir, --cycle, --start-index, --gamma, --srgb-input, --resize-factor"
            exit 1
            ;;
    esac
done

# Go to base directory
echo "Go to base directory"
STUDIO_TOOLS_PATH=/CT/LS_FRM01/work/faceolat-dataset/
cd ${STUDIO_TOOLS_PATH}/relighting

# Activate environment
echo "Activate environment"
eval "$(conda shell.bash hook)"
conda activate faceolat

# Configuration summary
echo "======================================"
echo "FaceOLAT Relighting Configuration"
echo "======================================"
echo "Subject: $SUBJECT_ARG"
echo "Environment map: $ENVNAME"
echo "Environment path: $ENVPATH"
echo "Environment scale: $ENVSCALE"
echo "Gamma correction: $GAMMA"
echo "Input color space: $([ "$SRGB_INPUT" = true ] && echo "sRGB" || echo "Linear")"
echo "Resize factor: $RESIZE_FACTOR (output: $(( 4096 / RESIZE_FACTOR ))x$(( 2160 / RESIZE_FACTOR )))"
echo "Index map: $INDEXMAP"
echo "Cycle frames: $CYCLE"
echo "Start index: $START_INDEX"
echo "======================================"

# Set output directory for this subject and environment
OUTPUT_DIR="${OUTPUT_BASE}/${SUBJECT_ARG}/${ENVNAME}_scale${ENVSCALE}"
echo "Output directory: $OUTPUT_DIR"

# Check if index map exists
if [ ! -f "$INDEXMAP" ]; then
    echo "ERROR: Index map not found: $INDEXMAP"
    echo "Current directory: $(pwd)"
    echo "Available .exr files:"
    ls -la *.exr 2>/dev/null || echo "No .exr files found"
    exit 1
fi

echo "Using index map: $INDEXMAP"

# Check if environment map directory exists
if [ ! -d "$ENVPATH" ]; then
    echo "WARNING: Environment map directory not found: $ENVPATH"
    echo "Please ensure the environment map directory exists"
fi

# Check if environment map exists
ENV_FILE="$ENVPATH/${ENVNAME}.exr"
if [ ! -f "$ENV_FILE" ]; then
    echo "WARNING: Environment map not found: $ENV_FILE"
    echo "Available environment maps in $ENVPATH:"
    ls -la "$ENVPATH"/*.exr 2>/dev/null || echo "No .exr files found"
fi

# Check if input AVIF data exists
INPUT_DIR="/CT/datasets23/static00/FaceOLAT/OutputAVIF"
SAMPLE_CAM="Cam06"
SUBJECT_DIR="$INPUT_DIR/$SAMPLE_CAM/$SUBJECT_ARG"

if [ ! -d "$SUBJECT_DIR" ]; then
    echo "ERROR: Subject AVIF data not found: $SUBJECT_DIR"
    echo "Please ensure the subject has been processed through the AVIF conversion pipeline"
    exit 1
fi

echo "Found input AVIF data: $SUBJECT_DIR"

# Build command arguments
ARGS="--sub $SUBJECT_ARG \
    --envpath $ENVPATH \
    --indexmap $INDEXMAP \
    --envname $ENVNAME \
    --envscale $ENVSCALE \
    --outdir $OUTPUT_DIR \
    --cycle $CYCLE \
    --start_index $START_INDEX \
    --gamma $GAMMA \
    --resize-factor $RESIZE_FACTOR"

# Add sRGB input flag if specified
if [ "$SRGB_INPUT" = true ]; then
    ARGS="$ARGS --srgb-input"
fi

# Run relighting
echo "======================================"
echo "Starting relighting process..."
echo "======================================"
python render_reference_envmap_relit.py $ARGS

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Successfully completed relighting for $SUBJECT_ARG with $ENVNAME"
    echo "Output saved to: $OUTPUT_DIR"
    echo "Number of generated images:"
    ls -1 "$OUTPUT_DIR"/*.png 2>/dev/null | wc -l
else
    echo "❌ Relighting failed for $SUBJECT_ARG (exit code: $EXIT_CODE)"
fi

echo "======================================"
echo "Relighting process completed"
echo "======================================"

