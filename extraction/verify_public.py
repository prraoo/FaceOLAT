#!/usr/bin/env python3
"""
Verify FaceOLAT Public Release Extraction

Checks extraction completeness for the public release dataset structure.
"""

import os
import sys
import glob
import argparse
from collections import defaultdict

def parse_args():
    parser = argparse.ArgumentParser(description='Verify FaceOLAT public release extraction')
    parser.add_argument('output_dir', help='Output directory to verify')
    parser.add_argument('--expected-frames', type=int, default=350, help='Expected frames per take')
    parser.add_argument('--subjects', help='Comma-separated list of subjects to check (e.g., 001,002). Default: all subjects')
    parser.add_argument('--summary-only', action='store_true', help='Show only summary statistics')
    return parser.parse_args()

def find_cameras(output_dir):
    """Find all camera directories"""
    cameras = []
    for item in os.listdir(output_dir):
        item_path = os.path.join(output_dir, item)
        if os.path.isdir(item_path) and item.startswith('Cam'):
            cameras.append(item)
    return sorted(cameras)

def find_unique_ids(camera_dir):
    """Find all unique ID directories in a camera folder"""
    unique_ids = []
    if not os.path.exists(camera_dir):
        return unique_ids
    
    for item in os.listdir(camera_dir):
        item_path = os.path.join(camera_dir, item)
        if os.path.isdir(item_path) and item.startswith('ID'):
            unique_ids.append(item)
    return sorted(unique_ids)

def count_frames(unique_id_dir):
    """Count extracted frames in a unique ID directory"""
    if not os.path.exists(unique_id_dir):
        return 0
    
    frame_files = []
    for ext in ['*.exr', '*.jpg', '*.png']:
        frame_files.extend(glob.glob(os.path.join(unique_id_dir, ext)))
    
    return len(frame_files)

def extract_subject_from_unique_id(input_dir, unique_id):
    """Find which subject directory contains this unique ID"""
    # This is a reverse lookup - in practice you might maintain a mapping
    # For now, we'll search through subject directories
    if not os.path.exists(input_dir):
        return "unknown"
    
    for subject in os.listdir(input_dir):
        if len(subject) == 3 and subject.isdigit():
            subject_path = os.path.join(input_dir, subject)
            if os.path.isdir(subject_path):
                unique_id_path = os.path.join(subject_path, unique_id)
                if os.path.exists(unique_id_path):
                    return subject
    
    return "unknown"

def main():
    args = parse_args()
    
    if not os.path.exists(args.output_dir):
        print(f"❌ Output directory not found: {args.output_dir}")
        return 1
    
    print("🔍 FaceOLAT Public Release Extraction Verification")
    print(f"📁 Output directory: {args.output_dir}")
    print(f"🎯 Expected frames per take: {args.expected_frames}")
    
    # Find all cameras
    cameras = find_cameras(args.output_dir)
    if not cameras:
        print("❌ No camera directories found")
        return 1
    
    print(f"📸 Found {len(cameras)} cameras: {cameras}")
    
    # Statistics
    total_unique_ids = 0
    complete_unique_ids = 0
    incomplete_unique_ids = 0
    missing_unique_ids = 0
    
    # Detailed results
    results = defaultdict(lambda: defaultdict(int))  # unique_id -> camera -> frame_count
    complete_by_camera = defaultdict(int)  # camera -> complete_count
    incomplete_by_camera = defaultdict(list)  # camera -> list of incomplete unique_ids
    
    # Process each camera
    for camera in cameras:
        camera_dir = os.path.join(args.output_dir, camera)
        unique_ids = find_unique_ids(camera_dir)
        
        if not args.summary_only:
            print(f"\n📸 {camera}: {len(unique_ids)} unique IDs")
        
        for unique_id in unique_ids:
            unique_id_dir = os.path.join(camera_dir, unique_id)
            frame_count = count_frames(unique_id_dir)
            
            results[unique_id][camera] = frame_count
            
            if frame_count == args.expected_frames:
                status = "✅"
                complete_by_camera[camera] += 1
            elif frame_count == 0:
                status = "❌"
                incomplete_by_camera[camera].append(f"{unique_id}(0)")
            else:
                status = "⚠️"
                incomplete_by_camera[camera].append(f"{unique_id}({frame_count})")
            
            if not args.summary_only:
                print(f"  {status} {unique_id}: {frame_count}/{args.expected_frames} frames")
    
    # Collect unique IDs across all cameras
    all_unique_ids = set(results.keys())  # results is keyed by unique_id
    all_unique_ids = sorted(all_unique_ids)
    total_unique_ids = len(all_unique_ids)
    
    # Check completeness per unique ID
    for unique_id in all_unique_ids:
        complete_cameras = 0
        total_cameras = len(cameras)
        
        for camera in cameras:
            frame_count = results[unique_id].get(camera, 0)
            if frame_count == args.expected_frames:
                complete_cameras += 1
        
        if complete_cameras == total_cameras:
            complete_unique_ids += 1
        elif complete_cameras == 0:
            missing_unique_ids += 1
        else:
            incomplete_unique_ids += 1
    
    # Print summary
    print(f"\n📊 SUMMARY:")
    print(f"  Total unique IDs found: {total_unique_ids}")
    print(f"  ✅ Complete (all {len(cameras)} cameras): {complete_unique_ids}")
    print(f"  ⚠️ Incomplete (some cameras): {incomplete_unique_ids}")
    print(f"  ❌ Missing (no cameras): {missing_unique_ids}")
    
    # Print per-camera summary
    print(f"\n📸 PER-CAMERA SUMMARY:")
    for camera in cameras:
        camera_dir = os.path.join(args.output_dir, camera)
        unique_ids_in_camera = find_unique_ids(camera_dir)
        complete_count = complete_by_camera[camera]
        incomplete_list = incomplete_by_camera[camera]
        
        print(f"  {camera}: {complete_count}/{len(unique_ids_in_camera)} complete")
        if incomplete_list and not args.summary_only:
            print(f"    Incomplete: {', '.join(incomplete_list[:10])}")
            if len(incomplete_list) > 10:
                print(f"    ... and {len(incomplete_list) - 10} more")
    
    # Filter by subjects if requested
    if args.subjects:
        requested_subjects = set(args.subjects.split(','))
        print(f"\n🎯 FILTERING BY SUBJECTS: {sorted(requested_subjects)}")
        
        # This would require reverse lookup of unique_id -> subject
        # For now, show a note that this would need the input directory
        print("  (Note: Subject filtering requires input directory for reverse lookup)")
    
    # Write detailed report
    report_file = os.path.join(args.output_dir, "extraction_verification.txt")
    with open(report_file, 'w') as f:
        f.write("FaceOLAT Public Release Extraction Verification Report\n")
        f.write("=" * 60 + "\n\n")
        
        f.write(f"Output directory: {args.output_dir}\n")
        f.write(f"Expected frames per take: {args.expected_frames}\n")
        f.write(f"Verification date: {__import__('datetime').datetime.now()}\n\n")
        
        f.write("SUMMARY:\n")
        f.write(f"  Total unique IDs: {total_unique_ids}\n")
        f.write(f"  Complete: {complete_unique_ids}\n") 
        f.write(f"  Incomplete: {incomplete_unique_ids}\n")
        f.write(f"  Missing: {missing_unique_ids}\n\n")
        
        f.write("DETAILED RESULTS:\n")
        for unique_id in all_unique_ids:
            f.write(f"\n{unique_id}:\n")
            complete_cameras = 0
            for camera in cameras:
                frame_count = results[unique_id].get(camera, 0)
                status = "✅" if frame_count == args.expected_frames else ("❌" if frame_count == 0 else "⚠️")
                f.write(f"  {camera}: {frame_count}/{args.expected_frames} {status}\n")
                if frame_count == args.expected_frames:
                    complete_cameras += 1
            
            f.write(f"  Complete cameras: {complete_cameras}/{len(cameras)}\n")
    
    print(f"\n📄 Detailed report saved to: {report_file}")
    
    # Return appropriate exit code
    if complete_unique_ids == total_unique_ids:
        print("🎉 All extractions complete!")
        return 0
    else:
        print(f"⚠️ {total_unique_ids - complete_unique_ids} unique IDs need attention")
        return 1

if __name__ == "__main__":
    sys.exit(main())
