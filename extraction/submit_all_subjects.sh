#!/bin/bash

# Submit extraction jobs for FaceOLAT public release
# Usage: ./submit_all_subjects.sh [start_subject] [end_subject]
# Example: ./submit_all_subjects.sh 1 139
# Example: ./submit_all_subjects.sh 1 10  (process only subjects 001-010)

START_SUBJECT=${1:-1}
END_SUBJECT=${2:-139}

echo "🚀 Submitting FaceOLAT public release extraction jobs"
echo "📁 Processing subjects $(printf "%03d" $START_SUBJECT) to $(printf "%03d" $END_SUBJECT)"
echo "🎥 Each subject will use 40 parallel camera jobs"
echo ""

SUBMITTED_JOBS=0
FAILED_SUBMISSIONS=0

for i in $(seq $START_SUBJECT $END_SUBJECT); do
    SUBJECT=$(printf "%03d" $i)
    
    # Check if subject directory exists
    SUBJECT_DIR="/CT/buffer00/nobackup/prao/$SUBJECT"
    if [ ! -d "$SUBJECT_DIR" ]; then
        echo "⚠️  Subject $SUBJECT: Directory not found, skipping"
        continue
    fi
    
    # Count unique IDs
    UNIQUE_ID_COUNT=$(find "$SUBJECT_DIR" -maxdepth 1 -type d -name "ID*" 2>/dev/null | wc -l)
    
    if [ "$UNIQUE_ID_COUNT" -eq 0 ]; then
        echo "⚠️  Subject $SUBJECT: No unique IDs found, skipping"
        continue
    fi
    
    echo "📂 Subject $SUBJECT: Found $UNIQUE_ID_COUNT unique IDs"
    
    # Submit job
    JOB_OUTPUT=$(sbatch slurm_public.sh $SUBJECT 2>&1)
    
    if [ $? -eq 0 ]; then
        JOB_ID=$(echo "$JOB_OUTPUT" | grep -o '[0-9]\+' | tail -1)
        echo "✅ Subject $SUBJECT: Submitted job $JOB_ID (40 camera array jobs)"
        SUBMITTED_JOBS=$((SUBMITTED_JOBS + 1))
    else
        echo "❌ Subject $SUBJECT: Failed to submit job"
        echo "   Error: $JOB_OUTPUT"
        FAILED_SUBMISSIONS=$((FAILED_SUBMISSIONS + 1))
    fi
done

echo ""
echo "📊 SUBMISSION SUMMARY:"
echo "  ✅ Successfully submitted: $SUBMITTED_JOBS subjects"
echo "  ❌ Failed submissions: $FAILED_SUBMISSIONS subjects"
echo "  🎯 Total array jobs: $((SUBMITTED_JOBS * 40))"
echo ""
echo "📋 Monitor with:"
echo "  squeue -u \$USER"
echo "  tail -f logs/out-*.out"
echo ""
echo "🔍 Check specific subject progress:"
echo "  tail -f logs/out-<job_id>_*.out"
