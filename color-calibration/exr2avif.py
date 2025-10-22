#!/usr/bin/env python3
"""
EXR to Color-Calibrated AVIF Conversion for FaceOLAT Public Release

Converts EXR images to AVIF format with color calibration applied.
Input:  /FaceOLAT/OutputEXR/Cam01/ID20001/*.exr
Output: /FaceOLAT/OutputAVIF/Cam01/ID20001/*.avif

The workflow:
1. Load EXR image (linear RGB)
2. Apply color calibration matrix from colorcalib_exr.mat
3. Convert to AVIF format
"""

import os
import sys
import glob
import argparse
import subprocess
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import time
import numpy as np
import OpenEXR
import Imath
from PIL import Image
import tempfile

# Check for pillow_avif support
def check_avif_support():
    """Check if AVIF format is supported by PIL"""
    try:
        # Try to create a small test image and save as AVIF
        test_img = Image.new('RGB', (1, 1), (0, 0, 0))
        with tempfile.NamedTemporaryFile(suffix='.avif', delete=True) as tmp:
            test_img.save(tmp.name, 'AVIF')
        return True
    except Exception:
        return False

# Check AVIF support at module level
AVIF_SUPPORTED = check_avif_support()

def parse_args():
    parser = argparse.ArgumentParser(description='Convert EXR to color-calibrated AVIF for FaceOLAT public release')
    parser.add_argument('input_dir', help='Input EXR directory (e.g., /CT/datasets23/static00/FaceOLAT/OutputEXR)')
    parser.add_argument('output_dir', help='Output AVIF directory (e.g., /CT/datasets23/static00/FaceOLAT/OutputAVIF)')
    parser.add_argument('--quality', type=int, default=95, help='AVIF quality (1-100, default: 95)')
    parser.add_argument('--workers', type=int, default=8, help='Number of parallel workers')
    parser.add_argument('--cameras', help='Comma-separated list of cameras to process (e.g., Cam01,Cam02)')
    parser.add_argument('--unique-ids', help='Comma-separated list of unique IDs to process (e.g., ID20001,ID30001)')
    parser.add_argument('--expected-images', type=int, default=350, help='Expected number of images per unique ID')
    parser.add_argument('--delete-originals', action='store_true', help='Delete original EXR files after conversion')
    parser.add_argument('--force', action='store_true', help='Convert even if AVIF files already exist')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be converted without actually converting')
    parser.add_argument('--calib-matrix', default='colorcalib_exr.mat', help='Color calibration matrix file')
    parser.add_argument('--gamma', type=float, default=2.2, help='Gamma correction (default: 2.2)')
    parser.add_argument('--no-color-calibration', action='store_true', help='Skip color calibration (for testing)')
    return parser.parse_args()

def load_calibration_matrix(matrix_path):
    """Load the 4x4 color calibration matrix from file"""
    if not os.path.exists(matrix_path):
        raise FileNotFoundError(f"Calibration matrix not found: {matrix_path}")
    
    matrix = np.loadtxt(matrix_path)
    if matrix.shape != (4, 4):
        raise ValueError(f"Expected 4x4 matrix, got {matrix.shape}")
    
    return matrix

def load_exr_image(exr_path):
    """Load EXR image and return RGB array"""
    try:
        exr_file = OpenEXR.InputFile(exr_path)
        header = exr_file.header()
        
        # Get image dimensions
        dw = header['dataWindow']
        width = dw.max.x - dw.min.x + 1
        height = dw.max.y - dw.min.y + 1
        
        # Read RGB channels
        FLOAT = Imath.PixelType(Imath.PixelType.FLOAT)
        channels = ['R', 'G', 'B']
        
        rgb_data = []
        for channel in channels:
            channel_data = exr_file.channel(channel, FLOAT)
            channel_array = np.frombuffer(channel_data, dtype=np.float32)
            channel_array = channel_array.reshape(height, width)
            rgb_data.append(channel_array)
        
        # Stack into RGB image (H, W, 3)
        rgb_image = np.stack(rgb_data, axis=2)
        
        exr_file.close()
        return rgb_image
        
    except Exception as e:
        raise RuntimeError(f"Failed to load EXR image {exr_path}: {str(e)}")

def apply_color_calibration(image_rgb, calib_matrix):
    """
    Apply color calibration to RGB image using 4x4 matrix
    
    Args:
        image_rgb (np.ndarray): RGB image (H, W, 3) in linear space
        calib_matrix (np.ndarray): 4x4 color calibration matrix
    
    Returns:
        np.ndarray: Color-calibrated RGB image (H, W, 3)
    """
    # Extract 3x3 color matrix and black level offset
    color_matrix = calib_matrix[:3, :3]
    black_level = calib_matrix[:3, 3]
    
    # Get image shape
    h, w, c = image_rgb.shape
    
    # Reshape image for matrix operations: (3, H*W)
    image_flat = image_rgb.reshape(-1, 3).T  # (3, H*W)
    
    # Apply black level subtraction
    image_corrected = image_flat - black_level[:, np.newaxis]
    
    # Apply color correction matrix
    image_calibrated = color_matrix @ image_corrected
    
    # Reshape back to (H, W, 3)
    image_calibrated = image_calibrated.T.reshape(h, w, c)
    
    # Clip negative values
    image_calibrated = np.maximum(image_calibrated, 0.0)
    
    return image_calibrated

def apply_gamma_correction(image_linear, gamma=2.2):
    """Apply gamma correction to linear RGB image"""
    return np.power(image_linear, 1.0 / gamma)

def convert_exr_to_calibrated_avif(exr_file, avif_file, calib_matrix, quality, gamma, skip_calibration=False):
    """Convert single EXR file to AVIF with optional color calibration"""
    try:
        # Load EXR image (linear RGB)
        rgb_linear = load_exr_image(exr_file)
        
        # Apply color calibration (optional)
        if skip_calibration:
            rgb_calibrated = rgb_linear
        else:
            rgb_calibrated = apply_color_calibration(rgb_linear, calib_matrix)
        
        # Apply gamma correction for display
        rgb_gamma = apply_gamma_correction(rgb_calibrated, gamma)
        
        # Convert to 8-bit
        rgb_8bit = np.clip(rgb_gamma * 255, 0, 255).astype(np.uint8)
        
        # Create PIL image
        pil_image = Image.fromarray(rgb_8bit, 'RGB')
        
        # Save as AVIF using PIL
        if not AVIF_SUPPORTED:
            return False, "AVIF format not supported. Please install pillow_avif: pip install pillow-avif-plugin"
        
        try:
            pil_image.save(avif_file, 'AVIF', quality=quality)
            return True, None
        except Exception as e:
            return False, f"AVIF encoding failed: {str(e)}"
            
    except Exception as e:
        return False, f"EXR processing error: {str(e)}"

def find_cameras(input_dir):
    """Find all camera directories"""
    cameras = []
    if not os.path.exists(input_dir):
        return cameras
    
    for item in os.listdir(input_dir):
        item_path = os.path.join(input_dir, item)
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

def count_images(directory, extensions=['*.exr']):
    """Count images in directory"""
    count = 0
    for ext in extensions:
        count += len(glob.glob(os.path.join(directory, ext)))
    return count

def process_unique_id(args_tuple):
    """Process all EXR files in a unique ID directory"""
    (camera, unique_id, input_dir, output_dir, quality, expected_images, 
     delete_originals, force, dry_run, calib_matrix, gamma, skip_calibration) = args_tuple
    
    input_unique_dir = os.path.join(input_dir, camera, unique_id)
    output_unique_dir = os.path.join(output_dir, camera, unique_id)
    
    # Check if input directory exists
    if not os.path.exists(input_unique_dir):
        return camera, unique_id, 0, 0, "Input directory not found"
    
    # Count EXR files
    exr_files = glob.glob(os.path.join(input_unique_dir, "*.exr"))
    exr_count = len(exr_files)
    
    if exr_count == 0:
        return camera, unique_id, 0, 0, "No EXR files found"
    
    # Check if we have expected number of images
    if exr_count != expected_images:
        return camera, unique_id, 0, 0, f"Incomplete extraction: {exr_count}/{expected_images} images"
    
    # Check if already converted (unless force)
    if not force and os.path.exists(output_unique_dir):
        avif_count = count_images(output_unique_dir, ['*.avif'])
        if avif_count == expected_images:
            return camera, unique_id, avif_count, 0, "Already converted"
    
    if dry_run:
        calibration_note = "" if skip_calibration else " with color calibration"
        return camera, unique_id, exr_count, 0, f"DRY RUN: Would convert {exr_count} EXR files{calibration_note}"
    
    # Create output directory
    os.makedirs(output_unique_dir, exist_ok=True)
    
    successful_conversions = 0
    failed_conversions = 0
    
    # Convert each EXR file
    for exr_file in exr_files:
        # Generate output filename
        base_name = os.path.splitext(os.path.basename(exr_file))[0]
        avif_file = os.path.join(output_unique_dir, f"{base_name}.avif")
        
        # Skip if already exists (unless force)
        if not force and os.path.exists(avif_file):
            successful_conversions += 1
            continue
        
        # Convert file with optional color calibration
        success, error = convert_exr_to_calibrated_avif(exr_file, avif_file, calib_matrix, quality, gamma, skip_calibration)
        
        if success:
            successful_conversions += 1
            # Delete original if requested
            if delete_originals:
                try:
                    os.remove(exr_file)
                except Exception as e:
                    print(f"Warning: Could not delete {exr_file}: {e}")
        else:
            failed_conversions += 1
            print(f"Failed to convert {exr_file}: {error}")
    
    calibration_note = "(no calibration)" if skip_calibration else "(color-calibrated)"
    status = f"Converted {successful_conversions}/{exr_count} files {calibration_note}"
    if failed_conversions > 0:
        status += f" ({failed_conversions} failed)"
    
    return camera, unique_id, successful_conversions, failed_conversions, status

def main():
    args = parse_args()
    
    print("🎨 FaceOLAT EXR to Color-Calibrated AVIF Conversion (Public Release)")
    print(f"Input:   {args.input_dir}")
    print(f"Output:  {args.output_dir}")
    print(f"Quality: {args.quality}")
    print(f"Gamma:   {args.gamma}")
    print(f"Workers: {args.workers}")
    print(f"Expected images per unique ID: {args.expected_images}")
    
    # Check AVIF support
    if not AVIF_SUPPORTED:
        print("❌ AVIF format not supported!")
        print("💡 Please install pillow-avif-plugin:")
        print("   pip install pillow-avif-plugin")
        print("   or")
        print("   mamba install pillow-avif-plugin")
        return 1
    else:
        print("✅ AVIF format supported")
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - No actual conversion")
    
    if not os.path.exists(args.input_dir):
        print(f"❌ Input directory not found: {args.input_dir}")
        return 1
    
    # Load calibration matrix (if needed)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    matrix_path = os.path.join(script_dir, args.calib_matrix)
    calib_matrix = None
    
    if not args.no_color_calibration:
        try:
            calib_matrix = load_calibration_matrix(matrix_path)
            print(f"📊 Loaded calibration matrix from: {matrix_path}")
            print(f"    Matrix shape: {calib_matrix.shape}")
        except Exception as e:
            print(f"❌ Failed to load calibration matrix: {e}")
            print(f"💡 Use --no-color-calibration to skip calibration")
            return 1
    else:
        print("⚠️  Color calibration disabled (--no-color-calibration)")
        calib_matrix = np.eye(4)  # Identity matrix as placeholder
    
    # Find cameras to process
    if args.cameras:
        cameras = args.cameras.split(',')
    else:
        cameras = find_cameras(args.input_dir)
    
    if not cameras:
        print("❌ No camera directories found")
        return 1
    
    print(f"📸 Processing {len(cameras)} cameras: {cameras}")
    
    # Collect all unique ID tasks
    tasks = []
    total_unique_ids = 0
    
    for camera in cameras:
        camera_dir = os.path.join(args.input_dir, camera)
        
        # Find unique IDs to process
        if args.unique_ids:
            unique_ids = args.unique_ids.split(',')
        else:
            unique_ids = find_unique_ids(camera_dir)
        
        for unique_id in unique_ids:
            tasks.append((
                camera, unique_id, args.input_dir, args.output_dir,
                args.quality, args.expected_images, args.delete_originals,
                args.force, args.dry_run, calib_matrix, args.gamma, args.no_color_calibration
            ))
            total_unique_ids += 1
    
    if not tasks:
        print("❌ No unique IDs found to process")
        return 1
    
    print(f"🎯 Processing {total_unique_ids} unique IDs across {len(cameras)} cameras")
    if not args.no_color_calibration:
        print(f"🎨 Color calibration matrix: {args.calib_matrix}")
    else:
        print("⚠️  Color calibration: DISABLED")
    
    # Process tasks in parallel
    start_time = time.time()
    successful_tasks = 0
    failed_tasks = 0
    total_conversions = 0
    total_failures = 0
    
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        future_to_task = {executor.submit(process_unique_id, task): task for task in tasks}
        
        for future in as_completed(future_to_task):
            camera, unique_id, successful, failed, status = future.result()
            
            if "failed" in status.lower() or "error" in status.lower():
                print(f"❌ {camera}/{unique_id}: {status}")
                failed_tasks += 1
            else:
                print(f"✅ {camera}/{unique_id}: {status}")
                successful_tasks += 1
            
            total_conversions += successful
            total_failures += failed
    
    end_time = time.time()
    elapsed = end_time - start_time
    
    # Print summary
    print(f"\n📊 CONVERSION SUMMARY:")
    print(f"  Total unique IDs processed: {total_unique_ids}")
    print(f"  ✅ Successful: {successful_tasks}")
    print(f"  ❌ Failed: {failed_tasks}")
    print(f"  🖼️  Total images converted: {total_conversions}")
    print(f"  ⚠️  Total conversion failures: {total_failures}")
    print(f"  ⏱️  Total time: {elapsed/60:.1f} minutes")
    if not args.no_color_calibration:
        print(f"  🎨 Color calibration applied: {args.calib_matrix}")
    else:
        print(f"  ⚠️  Color calibration: SKIPPED")
    
    if not args.dry_run:
        print(f"  📁 Output directory: {args.output_dir}")
    
    # Return appropriate exit code
    if failed_tasks == 0:
        print("🎉 All conversions completed successfully!")
        return 0
    else:
        print(f"⚠️ {failed_tasks} unique IDs had issues")
        return 1

if __name__ == "__main__":
    sys.exit(main())
