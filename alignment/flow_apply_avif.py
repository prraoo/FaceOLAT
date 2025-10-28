#!/usr/bin/env python3

import os
import argparse
import numpy as np
import glob
from tqdm import tqdm
from pathlib import Path
import concurrent.futures
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp
from PIL import Image
import pillow_avif
import cv2  # Only used for cv2.remap (optical flow warping) - no PIL equivalent
import sys


def parse_args():
    parser = argparse.ArgumentParser(description="Apply Pre-computed Optical Flow to AVIF Images")
    parser.add_argument("input_dir", help="Input directory containing Cam** subdirectories with AVIF files")
    parser.add_argument("flow_dir", help="Directory containing pre-computed flow files")
    parser.add_argument("output_dir", help="Output directory for flow-aligned AVIF files")
    parser.add_argument("--takes", nargs="+", default=None, help="Specific takes to process (default: process all)")
    parser.add_argument("--cameras", nargs="+", default=None, help="Specific cameras to process (default: process all)")
    parser.add_argument("--center-frame", type=int, default=189, help="Center/key frame for alignment (default: 189)")
    parser.add_argument("--workers", type=int, default=None, help="Number of parallel workers")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing aligned images")
    parser.add_argument("--copy-full-lights", action="store_true", help="Copy full light frames without modification")
    
    return parser.parse_args()


def load_avif_image(image_path):
    """Load AVIF image using PIL with pillow_avif"""
    try:
        with Image.open(image_path) as img:
            # Convert to RGB if necessary and return as numpy array
            if img.mode != 'RGB':
                img = img.convert('RGB')
            image = np.array(img)
        return image
    except Exception as e:
        print(f"Error loading {image_path}: {e}")
        return None


def save_avif_image(image_path, image):
    """Save image as AVIF using PIL with pillow_avif"""
    try:
        # Ensure output directory exists
        os.makedirs(os.path.dirname(image_path), exist_ok=True)
        
        # Convert numpy array to PIL Image
        if isinstance(image, np.ndarray):
            # Ensure uint8 format
            if image.dtype != np.uint8:
                image = np.clip(image, 0, 255).astype(np.uint8)
            pil_image = Image.fromarray(image, mode='RGB')
        else:
            pil_image = image
        
        # Save as AVIF with high quality
        if image_path.endswith('.avif'):
            pil_image.save(image_path, format='AVIF', quality=95)
        else:
            # Fallback to JPG if not AVIF
            pil_image.save(image_path, format='JPEG', quality=95)
            
        return True
    except Exception as e:
        print(f"Error saving {image_path}: {e}")
        return False


def apply_flow_correction(image, flow_map, factor=1.0):
    """Apply optical flow to align an image"""
    h, w = image.shape[:2]
    
    # Create coordinate grid
    flow_grid_x, flow_grid_y = np.meshgrid(np.arange(w), np.arange(h))
    flow_grid_x = flow_grid_x + (flow_map[:, :, 0] * factor)
    flow_grid_y = flow_grid_y + (flow_map[:, :, 1] * factor)
    
    # Create warp matrix
    flow_grid = np.stack([flow_grid_x, flow_grid_y], axis=-1)
    warp_matrix = flow_grid.astype(np.float32)
    
    # Apply warping using cv2.remap (optimized operation, no direct PIL equivalent)
    aligned_image = cv2.remap(image, warp_matrix, None, 
                             interpolation=cv2.INTER_LINEAR, 
                             borderMode=cv2.BORDER_REFLECT_101)


    return aligned_image


def get_frame_files(take_dir):
    """Get sorted list of frame files in a take directory"""
    avif_files = glob.glob(os.path.join(take_dir, "*.avif"))
    jpg_files = glob.glob(os.path.join(take_dir, "*.jpg"))  # Fallback
    
    all_files = avif_files + jpg_files
    if not all_files:
        return []
    
    # Sort by filename to ensure correct order
    all_files.sort()
    return all_files


def extract_frame_number(filename):
    """Extract frame number from filename"""
    # Assume frame files are named like: frame_NNNN.avif or NNNN.avif
    base = os.path.splitext(os.path.basename(filename))[0]
    
    # Try to find numeric part
    import re
    numbers = re.findall(r'\d+', base)
    if numbers:
        return int(numbers[-1])  # Take the last number found
    return None


def apply_flow_to_camera_take(args_tuple):
    """Apply flow alignment to all frames for one camera/take combination"""
    (camera_name, take_name, input_dir, flow_dir, output_dir, 
     full_lights, center_frame, overwrite, copy_full_lights) = args_tuple
    
    try:
        input_take_dir = os.path.join(input_dir, camera_name, take_name)
        output_take_dir = os.path.join(output_dir, camera_name, take_name)
        camera_flow_dir = os.path.join(flow_dir, camera_name, take_name, f"flow_{center_frame:03d}")
        
        if not os.path.exists(input_take_dir):
            return f"{camera_name}/{take_name}: Input directory not found"
        
        if not os.path.exists(camera_flow_dir):
            return f"{camera_name}/{take_name}: Flow directory not found: {camera_flow_dir}"
        
        os.makedirs(output_take_dir, exist_ok=True)
        
        # Get frame files
        frame_files = get_frame_files(input_take_dir)
        if not frame_files:
            return f"{camera_name}/{take_name}: No image files found"
        
        # Create frame number to file mapping
        frame_mapping = {}
        for file_path in frame_files:
            frame_num = extract_frame_number(file_path)
            if frame_num is not None:
                frame_mapping[frame_num] = file_path
        
        aligned_count = 0
        copied_count = 0
        
        # Process frames between each pair of full light frames
        for i in range(len(full_lights) - 1):
            start_frame = full_lights[i]
            end_frame = full_lights[i + 1]
            
            # Load flow for start frame
            flow_file = os.path.join(camera_flow_dir, f"flow_{start_frame:03d}.npy")
            if not os.path.exists(flow_file):
                print(f"Warning: Flow file not found for {camera_name}/{take_name} frame {start_frame}")
                continue
                
            flow_map = np.load(flow_file)
            
            # Apply flow to intermediate frames
            for frame_num in range(start_frame + 1, end_frame):
                if frame_num not in frame_mapping:
                    continue
                
                # Calculate interpolation factor
                factor = (end_frame - frame_num) / (end_frame - start_frame)
                
                # Output path
                input_frame_path = frame_mapping[frame_num]
                output_frame_path = os.path.join(output_take_dir, os.path.basename(input_frame_path))
                
                # Skip if already exists and not overwriting
                if os.path.exists(output_frame_path) and not overwrite:
                    aligned_count += 1
                    continue
                
                # Load and align image
                image = load_avif_image(input_frame_path)
                if image is None:
                    continue
                
                aligned_image = apply_flow_correction(image, flow_map, factor)
                
                # Save aligned image
                if save_avif_image(output_frame_path, aligned_image):
                    aligned_count += 1
        
        # Copy or process full light frames
        for light_frame in full_lights:
            if light_frame in frame_mapping:
                input_frame_path = frame_mapping[light_frame]
                output_frame_path = os.path.join(output_take_dir, os.path.basename(input_frame_path))
                
                if not os.path.exists(output_frame_path) or overwrite:
                    if copy_full_lights or light_frame == center_frame:
                        # Just copy full light frames (no alignment needed)
                        image = load_avif_image(input_frame_path)
                        if image is not None:
                            save_avif_image(output_frame_path, image)
                            copied_count += 1
                    else:
                        # Apply flow alignment even to full light frames
                        flow_file = os.path.join(camera_flow_dir, f"flow_{light_frame:03d}.npy")
                        if os.path.exists(flow_file):
                            image = load_avif_image(input_frame_path)
                            if image is not None:
                                flow_map = np.load(flow_file)
                                aligned_image = apply_flow_correction(image, flow_map, factor=1.0)
                                save_avif_image(output_frame_path, aligned_image)
                                aligned_count += 1
                        else:
                            # No flow available, just copy
                            image = load_avif_image(input_frame_path)
                            if image is not None:
                                save_avif_image(output_frame_path, image)
                                copied_count += 1
        
        return f"{camera_name}/{take_name}: Aligned {aligned_count} frames, copied {copied_count} frames"
        
    except Exception as e:
        return f"{camera_name}/{take_name}: Error - {str(e)}"


def main():
    # Set multiprocessing start method to 'spawn' to avoid CUDA multiprocessing issues
    mp.set_start_method('spawn', force=True)
    
    args = parse_args()
    
    # Full light frame indices (adjust as needed for your data)
    # full_lights = [1, 21, 42, 63, 84, 105, 126, 147, 168, 189, 210, 231, 252, 273, 294, 315, 336, 349]
    full_lights = [0, 20, 41, 62, 83, 104, 125, 146, 167, 188, 209, 230, 251, 272, 293, 314, 335, 348]
    
    print(f"Applying Pre-computed Optical Flow to AVIF Images")
    print(f"Input directory: {args.input_dir}")
    print(f"Flow directory: {args.flow_dir}")
    print(f"Output directory: {args.output_dir}")
    print(f"Center frame: {args.center_frame}")
    print(f"Full light frames: {full_lights}")
    print("-" * 60)
    
    # Check if input directories exist
    if not os.path.exists(args.input_dir):
        print(f"Error: Input directory '{args.input_dir}' does not exist.")
        return 1
        
    if not os.path.exists(args.flow_dir):
        print(f"Error: Flow directory '{args.flow_dir}' does not exist.")
        return 1
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Determine number of workers
    if args.workers is None:
        args.workers = mp.cpu_count()
    
    # Get cameras to process
    if args.cameras:
        camera_list = args.cameras
    else:
        camera_dirs = glob.glob(os.path.join(args.input_dir, "Cam*"))
        camera_list = [os.path.basename(cam_dir) for cam_dir in camera_dirs if os.path.isdir(cam_dir)]
        camera_list.sort(key=lambda x: int(x.replace('Cam', '').lstrip('0') or '0'))
    
    # Get takes to process
    if args.takes:
        take_list = args.takes
    else:
        # Find all takes from any camera
        all_takes = set()
        for camera_dir in glob.glob(os.path.join(args.input_dir, "Cam*")):
            if os.path.isdir(camera_dir):
                take_dirs = [d for d in os.listdir(camera_dir) 
                           if os.path.isdir(os.path.join(camera_dir, d))]
                all_takes.update(take_dirs)
        take_list = sorted(list(all_takes))
    
    print(f"Processing {len(camera_list)} cameras and {len(take_list)} takes")
    print(f"Cameras: {camera_list}")
    print(f"Takes: {take_list}")
    print("-" * 60)
    
    # Apply flow alignment
    print("Applying flow alignment...")
    alignment_tasks = []
    for camera_name in camera_list:
        for take_name in take_list:
            alignment_tasks.append((camera_name, take_name, args.input_dir, args.flow_dir, args.output_dir, 
                                  full_lights, args.center_frame, args.overwrite, args.copy_full_lights))
    
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(apply_flow_to_camera_take, task): task for task in alignment_tasks}
        
        for future in tqdm(as_completed(futures), total=len(futures), desc="Applying flows"):
            result = future.result()
            print(result)
    
    print("-" * 60)
    print("Flow application completed!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
