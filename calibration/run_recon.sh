#!/bin/bash
#SBATCH -p gpu20
#SBATCH -t 0:29:00
#SBATCH -c 10
#SBATCH -a 1
#SBATCH --gres gpu:1
#SBATCH  --mem-per-cpu=16000
#SBATCH -o /CT/LS_FRM01/nobackup/logs/out-%j.out
#SBATCH -e /CT/LS_FRM01/nobackup/logs/err-%j.err


# go to base directory
echo "Go to base directory "


# activate env
echo "Activate base environment"
eval "$(conda shell.bash hook)"

source /CT/StudioAndClusterExperiments/static00/miniforge/etc/profile.d/conda.sh
conda activate metashape
BASE_PATH=/CT/datasets23/static00/FaceOLAT/calibration/2024_09_19/

# Calibration parameters
COMPUTE_AVG=False
IMPORT_CAMERAS=True
FRAME=0

# Camera calibration files location
# Use subject-specific camera XML files from cameras/ folder
# e.g., ID40001 -> 001.xml, ID20050 -> 050.xml
CAMERAS_DIR=./cameras/

SCAN_PATH=/CT/datasets23/static00/FaceOLAT/OutputAVIF
SCAN_NAME=ID40001
OUTPUT_DIR=${BASE_PATH}/Calibration/${SCAN_NAME}_1/

python get_calibration_light_stage.py $SCAN_PATH $SCAN_NAME $FRAME $IMPORT_CAMERAS $CAMERAS_DIR $OUTPUT_DIR $COMPUTE_AVG
