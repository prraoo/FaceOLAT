#!/usr/bin/env python3

import os
import sys
import glob
import shutil
from collections import defaultdict

def count_images_in_directory(directory, extensions=['.avif']):
    """Count images with specified extensions in a directory"""
    total_count = 0
    for ext in extensions:
        pattern = os.path.join(directory, f"*{ext}")
        total_count += len(glob.glob(pattern))
    return total_count

def analyze_conversion_output(input_folder, expected_images=350):
    """
    Analyze the AVIF conversion output folder and generate summary reports.
    Creates an aligned output folder and copies conversion logs.
    
    Args:
        input_folder: Path to the input folder containing Cam** subdirectories with AVIF files
        expected_images: Expected number of AVIF images per camera/take
    """
    
    if not os.path.exists(input_folder):
        print(f"Error: Input folder '{input_folder}' does not exist.")
        return None
    
    # Create aligned output folder
    aligned_folder = f"{input_folder}_aligned"
    
    # Dictionary to store results grouped by take
    # Structure: {take_number: {camera_name: image_count}}
    take_results = defaultdict(dict)
    
    # Find all camera directories (Cam**)
    camera_pattern = os.path.join(input_folder, "Cam*")
    camera_dirs = glob.glob(camera_pattern)
    
    if not camera_dirs:
        print(f"No camera directories found in '{input_folder}' matching pattern 'Cam*'")
        return aligned_folder
    
    print(f"Found {len(camera_dirs)} camera directories")
    
    # Process each camera directory
    for camera_dir in camera_dirs:
        camera_name = os.path.basename(camera_dir)
        # print(f"Processing {camera_name}...")
        
        # Find all take subdirectories
        if not os.path.isdir(camera_dir):
            continue
            
        take_dirs = [d for d in os.listdir(camera_dir) 
                    if os.path.isdir(os.path.join(camera_dir, d))]
        
        for take_name in take_dirs:
            take_path = os.path.join(camera_dir, take_name)
            
            # Count AVIF images in this take directory
            avif_count = count_images_in_directory(take_path, ['.avif'])
            
            # Store result
            take_results[take_name][camera_name] = avif_count
            
            # print(f"  {take_name}: {avif_count} AVIF images")
    
    # Generate summary files for each take
    successful_takes = []
    for take_name, cameras_data in take_results.items():
        summary_filename = f"{take_name}_conversion_info.txt"
        summary_path = os.path.join(aligned_folder, summary_filename)
        
        # Find cameras with incorrect number of AVIF images
        problematic_cameras = []
        successful_cameras = []
        for camera_name, image_count in cameras_data.items():
            if image_count != expected_images:
                problematic_cameras.append((camera_name, image_count))
            else:
                successful_cameras.append(camera_name)
        
        # Check if this take is ready for alignment
        take_ready = len(problematic_cameras) == 0
        if take_ready:
            successful_takes.append(take_name)
        
        # Write summary file
        with open(summary_path, 'w') as f:
            f.write(f"EXR to AVIF Conversion Summary for Take: {take_name}\n")
            f.write("=" * 60 + "\n\n")
            
            if take_ready:
                f.write("✓ TAKE READY FOR OPTICAL FLOW ALIGNMENT\n")
                f.write(f"✓ All {len(cameras_data)} cameras have {expected_images} AVIF images\n\n")
            else:
                f.write("⚠️  TAKE NOT READY - INCOMPLETE CONVERSION\n")
                f.write(f"⚠️  {len(problematic_cameras)} cameras have incorrect AVIF counts\n\n")
            
            if problematic_cameras:
                f.write(f"Cameras with incorrect AVIF counts:\n")
                f.write("-" * 50 + "\n")
                for camera_name, image_count in sorted(problematic_cameras):
                    f.write(f"✗ {camera_name} - {image_count} AVIF images (expected {expected_images})\n")
                f.write("\n")
            
            if successful_cameras:
                f.write(f"Cameras with correct AVIF counts:\n")
                f.write("-" * 50 + "\n")
                for camera_name in sorted(successful_cameras):
                    f.write(f"✓ {camera_name} - {expected_images} AVIF images\n")
                f.write("\n")
            
            f.write(f"Complete camera breakdown:\n")
            f.write("-" * 50 + "\n")
            for camera_name, image_count in sorted(cameras_data.items()):
                status = "✓" if image_count == expected_images else "✗"
                f.write(f"{status} {camera_name}: {image_count} AVIF images\n")
            
            f.write(f"\nSummary:\n")
            f.write("-" * 20 + "\n")
            f.write(f"Total cameras processed: {len(cameras_data)}\n")
            f.write(f"Cameras with correct counts: {len(successful_cameras)}\n")
            f.write(f"Cameras with incorrect counts: {len(problematic_cameras)}\n")
            f.write(f"Take ready for alignment: {'YES' if take_ready else 'NO'}\n")
        
        print(f"Generated conversion summary: {summary_path}")
        if take_ready:
            print(f"  ✓ {take_name}: Ready for alignment ({len(cameras_data)} cameras)")
        else:
            print(f"  ⚠️  {take_name}: NOT ready - {len(problematic_cameras)} cameras have issues")
    
    # Generate overall summary
    overall_summary_path = os.path.join(aligned_folder, "conversion_overview.txt")
    with open(overall_summary_path, 'w') as f:
        f.write("EXR to AVIF Conversion Overview\n")
        f.write("=" * 50 + "\n\n")
        
        f.write(f"Input folder: {input_folder}\n")
        f.write(f"Aligned folder: {aligned_folder}\n")
        f.write(f"Expected AVIF images per camera: {expected_images}\n\n")
        
        f.write(f"Takes ready for optical flow alignment:\n")
        f.write("-" * 40 + "\n")
        if successful_takes:
            for take_name in sorted(successful_takes):
                f.write(f"✓ {take_name}\n")
        else:
            f.write("None - all takes have conversion issues\n")
        
        f.write(f"\nTakes with conversion issues:\n")
        f.write("-" * 40 + "\n")
        incomplete_takes = [take for take in take_results.keys() if take not in successful_takes]
        if incomplete_takes:
            for take_name in sorted(incomplete_takes):
                f.write(f"✗ {take_name}\n")
        else:
            f.write("None - all takes ready for alignment\n")
        
        f.write(f"\nSummary:\n")
        f.write("-" * 20 + "\n")
        f.write(f"Total takes: {len(take_results)}\n")
        f.write(f"Takes ready: {len(successful_takes)}\n")
        f.write(f"Takes with issues: {len(incomplete_takes)}\n")
        
        if successful_takes:
            f.write(f"\nNext step: Run optical flow alignment on ready takes:\n")
            f.write("python flow_align_avif.py {input_folder} {aligned_folder} --takes " + " ".join(successful_takes) + "\n")
    
    print(f"\nGenerated overall summary: {overall_summary_path}")
    print(f"\nConversion Analysis Results:")
    print(f"  Total takes found: {len(take_results)}")
    print(f"  Takes ready for alignment: {len(successful_takes)}")
    print(f"  Takes with conversion issues: {len(take_results) - len(successful_takes)}")
    
    if successful_takes:
        print(f"\n✓ Ready takes: {', '.join(sorted(successful_takes))}")
    
    return aligned_folder

def main():
    if len(sys.argv) < 2:
        print("Usage: python check_conversion.py <avif_input_folder> [expected_images]")
        print("Example: python check_conversion.py /path/to/OutputAVIF 350")
        print()
        print("This script:")
        print("  1. Analyzes AVIF conversion success in the input folder")
        print("  2. Creates an aligned output folder (input_folder + '_aligned')")
        print("  3. Copies conversion logs to the aligned folder")
        print("  4. Generates summaries for optical flow alignment readiness")
        sys.exit(1)
    
    input_folder = sys.argv[1]
    expected_images = int(sys.argv[2]) if len(sys.argv) > 2 else 350
    
    print(f"Analyzing EXR to AVIF conversion in: {input_folder}")
    print(f"Expected AVIF images per camera: {expected_images}")
    print("-" * 80)
    
    aligned_folder = analyze_conversion_output(input_folder, expected_images)
    
    print("-" * 80)
    print("Conversion analysis complete!")
    if aligned_folder:
        print(f"Aligned folder created: {aligned_folder}")
        print("Check the summary files for optical flow alignment readiness.")

if __name__ == "__main__":
    main()
