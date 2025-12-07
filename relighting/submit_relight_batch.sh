#!/bin/bash

# Batch submission script for FaceOLAT relighting
# Submits relighting jobs for multiple subjects
# Usage: ./submit_relight_batch.sh [OPTIONS]

# Default configuration
SUBJECTS_FILE="subjects_to_relight.txt"
ENVPATH="/CT/RelightAvatar/nobackup/tmp/latlongs"
ENVNAME="grace_cathedral"
ENVSCALE="0.01"
GAMMA="2.2"
SRGB_INPUT=false
RESIZE_FACTOR="4"
DRY_RUN=false

# Help message
show_help() {
    cat << EOF
FaceOLAT Batch Relighting Submission

Usage: ./submit_relight_batch.sh [OPTIONS]

Options:
    --subjects FILE     File containing subject IDs (one per line)
                       Default: subjects_to_relight.txt
    --subject ID       Process single subject (e.g., ID20003)
    --envpath PATH     Directory containing environment maps (default: /CT/RelightAvatar/nobackup/tmp/latlongs)
    --envname NAME     Environment map name (default: grace_cathedral)
    --envscale SCALE   Environment scale factor (default: 0.01)
    --gamma VALUE      Gamma correction for output (default: 2.2)
    --srgb-input       Input AVIFs are in sRGB space (apply sRGB to linear conversion)
    --resize-factor N  Resize factor for input images (default: 4)
    --dry-run          Show what would be submitted without submitting
    -h, --help         Show this help message

Examples:
    # Submit from subjects file
    ./submit_relight_batch.sh --subjects my_subjects.txt

    # Submit single subject
    ./submit_relight_batch.sh --subject ID20003

    # Submit with different environment and custom path
    ./submit_relight_batch.sh --subject ID20003 --envpath /path/to/envmaps --envname studio --envscale 0.02

    # Adjust gamma for darker OLATs (e.g., from no-gamma AVIF conversion)
    ./submit_relight_batch.sh --subject ID20003 --gamma 1.8

    # Use sRGB input (if AVIFs are in sRGB space)
    ./submit_relight_batch.sh --subject ID20003 --srgb-input

    # Change resize factor for higher resolution output
    ./submit_relight_batch.sh --subject ID20003 --resize-factor 2

    # Dry run to see what would be submitted
    ./submit_relight_batch.sh --subjects subjects.txt --dry-run

Subject File Format:
    Create a text file with one subject ID per line:
    ID20001
    ID20003
    ID30005
    ...
EOF
}

# Parse arguments
SINGLE_SUBJECT=""
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        --subjects)
            SUBJECTS_FILE="$2"
            shift 2
            ;;
        --subject)
            SINGLE_SUBJECT="$2"
            shift 2
            ;;
        --envpath)
            ENVPATH="$2"
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
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Color output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================"
echo "FaceOLAT Batch Relighting Submission"
echo -e "======================================${NC}"
echo "Environment path: $ENVPATH"
echo "Environment: $ENVNAME"
echo "Scale: $ENVSCALE"
echo "Gamma: $GAMMA"
echo "Input color space: $([ "$SRGB_INPUT" = true ] && echo "sRGB" || echo "Linear")"
echo "Resize factor: $RESIZE_FACTOR"
if [ "$DRY_RUN" = true ]; then
    echo -e "${RED}DRY RUN MODE - No jobs will be submitted${NC}"
fi
echo ""

# Determine subjects to process
if [ -n "$SINGLE_SUBJECT" ]; then
    # Single subject mode
    SUBJECTS=("$SINGLE_SUBJECT")
    echo "Processing single subject: $SINGLE_SUBJECT"
elif [ -f "$SUBJECTS_FILE" ]; then
    # Read from file
    mapfile -t SUBJECTS < <(grep -v '^#' "$SUBJECTS_FILE" | grep -v '^[[:space:]]*$')
    echo "Found ${#SUBJECTS[@]} subjects in $SUBJECTS_FILE"
else
    echo -e "${RED}ERROR: Subjects file not found: $SUBJECTS_FILE${NC}"
    echo "Create a file with subject IDs (one per line) or use --subject for a single subject"
    echo "Use --help for more information"
    exit 1
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# Submit jobs
SUBMITTED=0
SKIPPED=0

for SUBJECT in "${SUBJECTS[@]}"; do
    # Trim whitespace
    SUBJECT=$(echo "$SUBJECT" | xargs)
    
    # Skip empty lines
    if [ -z "$SUBJECT" ]; then
        continue
    fi
    
    # Build sbatch command
    SBATCH_CMD="sbatch --job-name=relight_${SUBJECT} slurm_relight.sh $SUBJECT --envpath $ENVPATH --envname $ENVNAME --envscale $ENVSCALE --gamma $GAMMA --resize-factor $RESIZE_FACTOR"
    
    # Add sRGB input flag if specified
    if [ "$SRGB_INPUT" = true ]; then
        SBATCH_CMD="$SBATCH_CMD --srgb-input"
    fi
    
    if [ "$DRY_RUN" = true ]; then
        echo -e "${BLUE}[DRY RUN]${NC} Would submit: $SBATCH_CMD"
        ((SKIPPED++))
    else
        echo -e "${GREEN}Submitting${NC} $SUBJECT with $ENVNAME..."
        JOB_ID=$(eval "$SBATCH_CMD" 2>&1)
        if [ $? -eq 0 ]; then
            JOB_NUM=$(echo "$JOB_ID" | grep -o '[0-9]\+' | head -1)
            echo -e "  ${GREEN}✓${NC} Job $JOB_NUM submitted"
            ((SUBMITTED++))
        else
            echo -e "  ${RED}✗${NC} Failed to submit: $JOB_ID"
            ((SKIPPED++))
        fi
    fi
done

echo ""
echo -e "${BLUE}======================================"
echo "Submission Summary"
echo -e "======================================${NC}"
if [ "$DRY_RUN" = true ]; then
    echo -e "${BLUE}Would submit: $SKIPPED jobs${NC}"
else
    echo -e "${GREEN}Successfully submitted: $SUBMITTED jobs${NC}"
    if [ $SKIPPED -gt 0 ]; then
        echo -e "${RED}Failed/Skipped: $SKIPPED jobs${NC}"
    fi
    echo ""
    echo "Monitor jobs with: squeue -u \$USER"
    echo "View logs in: logs/"
fi

