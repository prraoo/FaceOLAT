#!/usr/bin/env python3
"""
FaceOLAT Public Release Extraction Script

Extracts frames from the public release dataset structure:
/CT/buffer00/nobackup/prao/001/ID20001/cameras/Cam01/C006/*.R3D
/CT/buffer00/nobackup/prao/001/ID20001/timecodes/Timecode_save1_C006.txt

Output structure:
/CT/datasets23/static00/FaceOLAT/OutputEXR/Cam01/ID20001/*.exr
"""

import os
import sys
import glob
import subprocess
import argparse
from pathlib import Path

# Constants
if os.name != 'nt':
    REDLINE_PATH = "/CT/StudioAndClusterExperiments/static00/REDline_Build_60.52530/bin/REDline"
else:
    REDLINE_PATH = "C:\\Program Files\\REDCINE-X PRO 64-bit\\REDline.exe"

TEMP_FOLDER = "RED_metadata_output"

def parse_args():
    parser = argparse.ArgumentParser(description='Extract FaceOLAT public release dataset')
    parser.add_argument('input_dir', help='Input directory (e.g., /CT/buffer00/nobackup/prao)')
    parser.add_argument('output_dir', help='Output directory (e.g., /CT/datasets23/static00/FaceOLAT/OutputEXR)')
    parser.add_argument('--subjects', help='Comma-separated list of subjects to process (e.g., 001,002,003). Default: all subjects')
    parser.add_argument('--unique-ids', help='Comma-separated list of unique IDs to process (e.g., ID20001,ID30001). Default: all IDs')
    parser.add_argument('--cameras', help='Comma-separated list of cameras to process (e.g., Cam01,Cam02). Default: all cameras')
    parser.add_argument('--takes', help='Comma-separated list of takes to process (e.g., C006,C008). Default: all takes')
    parser.add_argument('--format', choices=['exr', 'jpg'], default='exr', help='Output format')
    parser.add_argument('--frame-count', type=int, default=350, help='Number of frames to extract per take')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be processed without actually extracting')
    return parser.parse_args()

def make_dir(path):
    """Create directory if it doesn't exist"""
    os.makedirs(path, exist_ok=True)

def find_subjects(input_dir):
    """Find all subject directories (001, 002, etc.)"""
    subjects = []
    for item in os.listdir(input_dir):
        item_path = os.path.join(input_dir, item)
        if os.path.isdir(item_path) and item.isdigit() and len(item) == 3:
            subjects.append(item)
    return sorted(subjects)

def find_unique_ids(subject_path):
    """Find all unique ID directories (ID20001, ID30001, etc.)"""
    unique_ids = []
    if not os.path.exists(subject_path):
        return unique_ids
    
    for item in os.listdir(subject_path):
        item_path = os.path.join(subject_path, item)
        if os.path.isdir(item_path) and item.startswith('ID') and len(item) == 7:
            unique_ids.append(item)
    return sorted(unique_ids)

def find_cameras(cameras_path):
    """Find all camera directories (Cam01, Cam02, etc.)"""
    cameras = []
    if not os.path.exists(cameras_path):
        return cameras
    
    for item in os.listdir(cameras_path):
        item_path = os.path.join(cameras_path, item)
        if os.path.isdir(item_path) and item.startswith('Cam'):
            cameras.append(item)
    return sorted(cameras)

def find_takes(camera_path):
    """Find all take directories (C006, C008, etc.)"""
    takes = []
    if not os.path.exists(camera_path):
        return takes
    
    for item in os.listdir(camera_path):
        item_path = os.path.join(camera_path, item)
        if os.path.isdir(item_path) and item.startswith('C'):
            takes.append(item)
    return sorted(takes)

def extract_metadata(r3d_file, temp_dir, unique_id, camera, take):
    """Extract metadata from R3D file"""
    make_dir(temp_dir)
    
    logfilename = os.path.join(temp_dir, f"{unique_id}_{camera}_{take}.txt")
    
    if os.path.isfile(logfilename):
        print(f"  📄 Using existing metadata: {os.path.basename(logfilename)}")
    else:
        print(f"  📄 Extracting metadata to: {os.path.basename(logfilename)}")
        
        try:
            with open(logfilename, 'w') as logfile:
                # Extract metadata
                proc = subprocess.Popen([
                    REDLINE_PATH, "--i", r3d_file, "--printMeta", "5"
                ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                
                for line in proc.stdout:
                    logfile.write(line.decode('utf-8'))
                proc.wait()
                
                # Extract additional metadata
                proc = subprocess.Popen([
                    REDLINE_PATH, "--i", r3d_file, "--printMeta", "3"
                ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                
                for line in proc.stdout:
                    logfile.write(line.decode('utf-8'))
                proc.wait()
                
        except Exception as e:
            print(f"  ❌ Failed to extract metadata: {e}")
            return None
    
    return logfilename

def parse_metadata(logfilename):
    """Parse metadata file to get resolution, fps, and timecodes"""
    try:
        with open(logfilename, 'r') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"  ❌ Failed to read metadata file: {e}")
        return None, None, None, None
    
    source_timecode = []
    IMAGE_W = IMAGE_H = fps = -1
    index_res = index_fps = -1
    
    for line in lines:
        parts = line.split(",")
        if len(parts) < 2:
            continue
            
        # Extract resolution and fps when indices are found
        if index_res != -1 and index_fps != -1:
            try:
                IMAGE_W = int(parts[index_res])
                IMAGE_H = int(parts[index_res + 1])
                fps = int(parts[index_fps])
                break
            except (ValueError, IndexError):
                continue
        
        # Collect timecodes
        if len(parts) > 1 and parts[1] != 'Timecode':
            source_timecode.append(parts[1])
            
        # Find column indices
        if 'Frame Width' in parts:
            index_res = parts.index('Frame Width')
        if 'Record FPS' in parts:
            index_fps = parts.index('Record FPS')
    
    if IMAGE_W == -1 or IMAGE_H == -1 or fps == -1:
        print(f"  ❌ Failed to parse resolution/fps from metadata")
        return None, None, None, None
    
    print(f"  📐 Resolution: {IMAGE_W}x{IMAGE_H}, FPS: {fps}, Timecodes: {len(source_timecode)}")
    return source_timecode, IMAGE_W, IMAGE_H, fps

def find_start_frame(timecode_file, source_timecode):
    """Find start frame from timecode file"""
    if not os.path.exists(timecode_file):
        print(f"  ⚠️ No timecode file found, using first available timecode")
        return 0
    
    try:
        with open(timecode_file, 'r') as f:
            master_timecodes = [line.strip() for line in f if line.strip() and line.strip() != "Take"]
    except Exception as e:
        print(f"  ❌ Failed to read timecode file: {e}")
        return 0
    
    # Find matching timecode
    for i, master_tc in enumerate(master_timecodes):
        for j, source_tc in enumerate(source_timecode):
            if source_tc == master_tc:
                print(f"  🎯 Found matching timecode: {master_tc} at frame {j}")
                return j
    
    print(f"  ⚠️ No matching timecode found, using frame 0")
    return 0

def extract_frames(r3d_file, output_dir, start_frame, frame_count, IMAGE_W, IMAGE_H, format_type, unique_id, camera, take):
    """Extract frames using REDline"""
    
    # Check if already extracted
    existing_files = []
    extensions = ['*.exr'] if format_type == 'exr' else ['*.jpg']
    for ext in extensions:
        existing_files.extend(glob.glob(os.path.join(output_dir, ext)))
    
    if len(existing_files) == frame_count:
        print(f"  ✅ Already extracted: {len(existing_files)} files")
        return True
    
    # Clean up partial extractions
    if existing_files:
        print(f"  🗑️ Removing {len(existing_files)} partial files")
        for f in existing_files:
            os.remove(f)
    
    make_dir(output_dir)
    
    # Build REDline command
    output_prefix = os.path.join(output_dir, unique_id)
    format_code = "2" if format_type == "exr" else "3"
    
    cmd = [
        REDLINE_PATH,
        "--i", r3d_file,
        "--o", output_prefix,
        "--start", str(start_frame),
        "--renum", "0", 
        "--frameCount", str(frame_count),
        "--resizeX", str(IMAGE_H),
        "--resizeY", str(IMAGE_W),
        "--rotate", "-90",
        "--colorSpace", "15",
        "--gammaCurve", "2", 
        "--exrCompression", "2",
        "--PRcodec", "3",
        "--format", format_code,
        "--decodeThreads", "4"
    ]
    
    print(f"  🚀 Extracting {frame_count} {format_type.upper()} frames...")
    print(f"  📁 Output: {output_dir}")
    
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        proc.wait()
        
        if proc.returncode != 0:
            print(f"  ❌ REDline failed with return code: {proc.returncode}")
            return False
        
        # Verify extraction
        final_files = []
        for ext in extensions:
            final_files.extend(glob.glob(os.path.join(output_dir, ext)))
        
        if len(final_files) == frame_count:
            print(f"  ✅ Successfully extracted {len(final_files)} files")
            return True
        else:
            print(f"  ❌ Extraction incomplete: {len(final_files)}/{frame_count} files")
            return False
            
    except Exception as e:
        print(f"  ❌ Extraction failed: {e}")
        return False

def process_take(input_dir, output_dir, subject, unique_id, camera, take, format_type, frame_count, dry_run=False):
    """Process a single take"""
    
    print(f"\n🎬 Processing: {subject}/{unique_id}/{camera}/{take}")
    
    # Build paths
    cameras_path = os.path.join(input_dir, subject, unique_id, "cameras")
    timecodes_path = os.path.join(input_dir, subject, unique_id, "timecodes")
    
    camera_take_path = os.path.join(cameras_path, camera, take)
    timecode_file = os.path.join(timecodes_path, f"Timecode_save1_{take}.txt")
    
    # Find R3D file
    r3d_pattern = os.path.join(camera_take_path, "*_001.R3D")
    r3d_files = glob.glob(r3d_pattern)
    
    if not r3d_files:
        print(f"  ❌ No R3D file found: {r3d_pattern}")
        return False
    
    r3d_file = r3d_files[0]
    print(f"  📹 R3D file: {os.path.basename(r3d_file)}")
    
    if dry_run:
        print(f"  🔍 DRY RUN: Would extract {frame_count} {format_type} frames")
        return True
    
    # Extract metadata
    temp_dir = os.path.join(TEMP_FOLDER, subject)
    logfilename = extract_metadata(r3d_file, temp_dir, unique_id, camera, take)
    if not logfilename:
        return False
    
    # Parse metadata
    source_timecode, IMAGE_W, IMAGE_H, fps = parse_metadata(logfilename)
    if not source_timecode:
        return False
    
    # Find start frame
    start_frame = find_start_frame(timecode_file, source_timecode)
    
    # Set up output directory
    output_camera_unique_dir = os.path.join(output_dir, camera, unique_id)
    
    # Extract frames
    success = extract_frames(r3d_file, output_camera_unique_dir, start_frame, frame_count, 
                           IMAGE_W, IMAGE_H, format_type, unique_id, camera, take)
    
    return success

def main():
    args = parse_args()
    
    print("🎯 FaceOLAT Public Release Extraction")
    print(f"Input:  {args.input_dir}")
    print(f"Output: {args.output_dir}")
    print(f"Format: {args.format.upper()}")
    print(f"Frames: {args.frame_count}")
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - No actual extraction")
    
    # Find subjects to process
    if args.subjects:
        subjects = args.subjects.split(',')
    else:
        subjects = find_subjects(args.input_dir)
    
    print(f"📁 Subjects: {subjects}")
    
    # Process each subject
    total_processed = 0
    total_successful = 0
    
    for subject in subjects:
        subject_path = os.path.join(args.input_dir, subject)
        
        if not os.path.exists(subject_path):
            print(f"⚠️ Subject directory not found: {subject_path}")
            continue
        
        # Find unique IDs to process
        if args.unique_ids:
            unique_ids = args.unique_ids.split(',')
        else:
            unique_ids = find_unique_ids(subject_path)
        
        print(f"\n📂 Subject {subject}: {len(unique_ids)} unique IDs")
        
        for unique_id in unique_ids:
            unique_id_path = os.path.join(subject_path, unique_id)
            cameras_path = os.path.join(unique_id_path, "cameras")
            
            if not os.path.exists(cameras_path):
                print(f"⚠️ Cameras directory not found: {cameras_path}")
                continue
            
            # Find cameras to process
            if args.cameras:
                cameras = args.cameras.split(',')
            else:
                cameras = find_cameras(cameras_path)
            
            for camera in cameras:
                camera_path = os.path.join(cameras_path, camera)
                
                if not os.path.exists(camera_path):
                    continue
                
                # Find takes to process
                if args.takes:
                    takes = args.takes.split(',')
                else:
                    takes = find_takes(camera_path)
                
                for take in takes:
                    total_processed += 1
                    
                    success = process_take(
                        args.input_dir, args.output_dir,
                        subject, unique_id, camera, take,
                        args.format, args.frame_count, args.dry_run
                    )
                    
                    if success:
                        total_successful += 1
    
    print(f"\n📊 SUMMARY:")
    print(f"  Total processed: {total_processed}")
    print(f"  Successful: {total_successful}")
    print(f"  Failed: {total_processed - total_successful}")
    
    if not args.dry_run:
        print(f"  Output directory: {args.output_dir}")

if __name__ == "__main__":
    main()
