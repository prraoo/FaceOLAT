#!/usr/bin/env python3

import sys
import os
import argparse
import numpy as np
from tqdm import tqdm
import torch
import glob
from pathlib import Path
import concurrent.futures
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp
from PIL import Image
import pillow_avif
import cv2  # Only used for cv2.remap (optical flow warping) - no PIL equivalent

# Add RAFT to path
sys.path.insert(0, './RAFT/core')
from raft import RAFT
from utils import flow_viz
from utils.utils import InputPadder


def parse_args():
    parser = argparse.ArgumentParser(description="Optical Flow Alignment for AVIF Images")
    parser.add_argument("input_dir", help="Input directory containing Cam** subdirectories with AVIF files")
    parser.add_argument("output_dir", help="Output directory for flow-aligned AVIF files")
    parser.add_argument("--takes", nargs="+", default=None, help="Specific takes to process (default: process all)")
    parser.add_argument("--cameras", nargs="+", default=None, help="Specific cameras to process (default: process all)")
    parser.add_argument("--model", default="RAFT/models/raft-things.pth", help="RAFT model checkpoint path")
    parser.add_argument("--center-frame", type=int, default=189, help="Center/key frame for alignment (default: 189)")
    parser.add_argument("--small", action="store_true", help="Use small RAFT model")
    parser.add_argument("--mixed-precision", action="store_true", help="Use mixed precision")
    parser.add_argument("--alternate-corr", action="store_true", help="Use efficient correlation implementation")
    parser.add_argument("--workers", type=int, default=1, help="Number of parallel workers (deprecated - use SLURM parallelization)")
    parser.add_argument("--flow-scale-factor", type=float, default=0.25, help="Scale factor for flow computation (default: 0.25 for 1/4 resolution)")
    parser.add_argument("--save-flow-viz", action="store_true", help="Save flow visualization images")
    parser.add_argument("--overwrite-flows", action="store_true", help="Overwrite existing flow matrices")
    parser.add_argument("--overwrite-aligned", action="store_true", help="Overwrite existing aligned images")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite both flows and aligned images (equivalent to --overwrite-flows --overwrite-aligned)")
    parser.add_argument("--slurm-task-id", type=int, default=None, help="SLURM array task ID for distributed processing")
    parser.add_argument("--slurm-total-tasks", type=int, default=None, help="Total number of SLURM tasks for distributed processing")
    parser.add_argument("--output-scale-factor", type=float, default=1.0, help="Scale factor for output images (0.0-1.0). 1.0 = original size, 0.5 = half size")
    
    args = parser.parse_args()
    
    # Validate output scale factor
    if not (0.0 < args.output_scale_factor <= 1.0):
        parser.error("--output-scale-factor must be between 0.0 and 1.0 (exclusive of 0.0)")
    
    # Handle legacy --overwrite flag
    if args.overwrite:
        args.overwrite_flows = True
        args.overwrite_aligned = True
    
    return args


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


def save_avif_image(image_path, image, scale_factor=1.0):
    """Save image as AVIF using PIL with pillow_avif, with optional resizing"""
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
        
        # Apply scaling if needed
        if scale_factor != 1.0:
            original_w, original_h = pil_image.size
            new_w = int(original_w * scale_factor)
            new_h = int(original_h * scale_factor)
            pil_image = pil_image.resize((new_w, new_h), Image.LANCZOS)
        
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


def pad_images_for_raft(frame1, frame2):
    """Prepare images for RAFT processing"""
    frame1 = torch.from_numpy(frame1).permute(2, 0, 1).float()
    frame2 = torch.from_numpy(frame2).permute(2, 0, 1).float()
    padder = InputPadder(frame1.shape)
    frame1, frame2 = padder.pad(frame1, frame2)
    frame1 = frame1.unsqueeze(0).cuda()
    frame2 = frame2.unsqueeze(0).cuda()
    return frame1, frame2, padder


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


def check_camera_take_completion(camera_name, take_name, input_dir, output_dir, full_lights, center_frame):
    """Check if camera/take processing is already complete"""
    input_take_dir = os.path.join(input_dir, camera_name, take_name)
    output_take_dir = os.path.join(output_dir, camera_name, take_name)
    flow_dir = os.path.join(output_take_dir, f"flow_{center_frame:03d}")
    
    if not os.path.exists(input_take_dir):
        return False, "Input directory not found"
    
    # Get input frame files
    frame_files = get_frame_files(input_take_dir)
    if not frame_files:
        return False, "No input frames found"
    
    # Check if all flow matrices exist (except center frame)
    flows_complete = True
    missing_flows = []
    for light_frame in full_lights:
        if light_frame == center_frame:
            continue
        flow_file = os.path.join(flow_dir, f"flow_{light_frame:03d}.npy")
        if not os.path.exists(flow_file):
            flows_complete = False
            missing_flows.append(light_frame)
    
    # Check if all aligned images exist
    aligned_complete = True
    missing_aligned = []
    for frame_file in frame_files:
        output_frame_path = os.path.join(output_take_dir, os.path.basename(frame_file))
        if not os.path.exists(output_frame_path):
            aligned_complete = False
            missing_aligned.append(os.path.basename(frame_file))
    
    if flows_complete and aligned_complete:
        return True, f"Complete ({len(frame_files)} aligned images)"
    elif flows_complete and not aligned_complete:
        return False, f"Flows complete, missing {len(missing_aligned)} aligned images"
    elif not flows_complete and aligned_complete:
        return False, f"Aligned images complete, missing {len(missing_flows)} flow matrices"
    else:
        return False, f"Missing {len(missing_flows)} flows and {len(missing_aligned)} aligned images"


def process_camera_take_flow(args_tuple):
    """Process optical flow for one camera/take combination"""
    (camera_name, take_name, input_dir, output_dir, model_path, 
     full_lights, center_frame, flow_scale_factor, save_flow_viz, overwrite_flows, output_scale_factor, raft_args) = args_tuple
    
    try:
        # Set up directories
        input_take_dir = os.path.join(input_dir, camera_name, take_name)
        output_take_dir = os.path.join(output_dir, camera_name, take_name)
        flow_dir = os.path.join(output_take_dir, f"flow_{center_frame:03d}")
        
        if not os.path.exists(input_take_dir):
            return f"{camera_name}/{take_name}: Input directory not found"
        
        os.makedirs(output_take_dir, exist_ok=True)
        os.makedirs(flow_dir, exist_ok=True)
        
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
        
        # Load RAFT model (create new instance for this process to avoid CUDA multiprocessing issues)
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        model = torch.nn.DataParallel(RAFT(raft_args))
        model.load_state_dict(torch.load(model_path, map_location=device))
        model = model.to(device)
        model.eval()
        
        # Load center frame
        if center_frame not in frame_mapping:
            return f"{camera_name}/{take_name}: Center frame {center_frame} not found"
        
        center_image_path = frame_mapping[center_frame]
        center_image = load_avif_image(center_image_path)
        if center_image is None:
            return f"{camera_name}/{take_name}: Could not load center frame"
        
        # Resize center image for flow computation
        h, w = center_image.shape[:2]
        flow_h, flow_w = int(h * flow_scale_factor), int(w * flow_scale_factor)
        center_image_pil = Image.fromarray(center_image)
        center_image_small_pil = center_image_pil.resize((flow_w, flow_h), Image.LANCZOS)
        center_image_small = np.array(center_image_small_pil)
        
        processed_count = 0
        
        # Compute flow for each full light frame
        for light_frame in full_lights:
            if light_frame == center_frame:
                continue  # Skip center frame
                
            if light_frame not in frame_mapping:
                print(f"Warning: Frame {light_frame} not found for {camera_name}/{take_name}")
                continue
            
            flow_file = os.path.join(flow_dir, f"flow_{light_frame:03d}.npy")
            
            # Skip if flow already computed and not overwriting flows
            if os.path.exists(flow_file) and not overwrite_flows:
                processed_count += 1
                continue
            
            # Load target frame
            target_image_path = frame_mapping[light_frame]
            target_image = load_avif_image(target_image_path)
            if target_image is None:
                print(f"Warning: Could not load frame {light_frame} for {camera_name}/{take_name}")
                continue
            
            # Resize target image for flow computation
            target_image_pil = Image.fromarray(target_image)
            target_image_small_pil = target_image_pil.resize((flow_w, flow_h), Image.LANCZOS)
            target_image_small = np.array(target_image_small_pil)
            
            # Compute optical flow
            with torch.no_grad():
                frame1, frame2, padder = pad_images_for_raft(center_image_small, target_image_small)
                _, flow_up = model(frame1, frame2, iters=20, test_mode=True)
                flow = flow_up.squeeze().permute(1, 2, 0).detach().cpu().numpy()
                
                # Remove padding
                flow = padder.unpad(torch.from_numpy(flow).permute(2, 0, 1).unsqueeze(0))
                flow = flow.squeeze().permute(1, 2, 0).numpy()
                
                # Scale flow to original resolution
                # For flow fields, we need to resize each component separately
                flow_x = Image.fromarray(flow[:, :, 0])
                flow_y = Image.fromarray(flow[:, :, 1])
                flow_x_scaled = flow_x.resize((w, h), Image.BILINEAR)
                flow_y_scaled = flow_y.resize((w, h), Image.BILINEAR)
                
                flow_scaled = np.stack([np.array(flow_x_scaled), np.array(flow_y_scaled)], axis=2)
                flow_scaled[:, :, 0] *= (w / flow_w)  # Scale x component
                flow_scaled[:, :, 1] *= (h / flow_h)  # Scale y component
                
                # Save flow
                np.save(flow_file, flow_scaled)
                
                # Save flow visualization if requested
                if save_flow_viz:
                    flow_viz_img = flow_viz.flow_to_image(flow)
                    flow_viz_path = os.path.join(flow_dir, f"flow_viz_{light_frame:03d}.jpg")
                    # flow_viz.flow_to_image returns RGB, so we can save directly with PIL
                    flow_viz_pil = Image.fromarray(flow_viz_img)
                    flow_viz_pil.save(flow_viz_path, format='JPEG', quality=95)
                
                processed_count += 1
        
        return f"{camera_name}/{take_name}: Computed {processed_count} flow fields"
        
    except Exception as e:
        return f"{camera_name}/{take_name}: Error - {str(e)}"


def apply_flow_alignment(args_tuple):
    """Apply flow alignment to all frames between full light frames"""
    (camera_name, take_name, input_dir, output_dir, full_lights, center_frame, overwrite_aligned, output_scale_factor) = args_tuple
    
    try:
        input_take_dir = os.path.join(input_dir, camera_name, take_name)
        output_take_dir = os.path.join(output_dir, camera_name, take_name)
        flow_dir = os.path.join(output_take_dir, f"flow_{center_frame:03d}")
        
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
        
        # Process frames between each pair of full light frames
        for i in range(len(full_lights) - 1):
            start_frame = full_lights[i]
            end_frame = full_lights[i + 1]
            
            # Special handling: if start_frame is the center frame, use flow from end_frame instead
            if start_frame == center_frame:
                flow_file = os.path.join(flow_dir, f"flow_{end_frame:03d}.npy")
                use_inverse_flow = True  # We'll reverse the interpolation direction
            else:
                flow_file = os.path.join(flow_dir, f"flow_{start_frame:03d}.npy")
                use_inverse_flow = False
            
            if not os.path.exists(flow_file):
                continue
                
            flow_map = np.load(flow_file)
            
            # Apply flow to intermediate frames
            for frame_num in range(start_frame + 1, end_frame):
                if frame_num not in frame_mapping:
                    continue
                
                # Calculate interpolation factor
                if use_inverse_flow:
                    # For segment after center frame: interpolate from end_frame back toward center
                    factor = (frame_num - start_frame) / (end_frame - start_frame)
                else:
                    # Normal case: interpolate from start_frame toward end
                    factor = (end_frame - frame_num) / (end_frame - start_frame)
                
                # Output path
                input_frame_path = frame_mapping[frame_num]
                output_frame_path = os.path.join(output_take_dir, os.path.basename(input_frame_path))
                
                # Skip if already exists and not overwriting aligned images
                if os.path.exists(output_frame_path) and not overwrite_aligned:
                    aligned_count += 1
                    continue
                
                # Load and align image
                image = load_avif_image(input_frame_path)
                if image is None:
                    continue
                
                aligned_image = apply_flow_correction(image, flow_map, factor)
                
                # Save aligned image
                if save_avif_image(output_frame_path, aligned_image, output_scale_factor):
                    aligned_count += 1
        
        # Copy full light frames (they don't need alignment)
        for light_frame in full_lights:
            if light_frame in frame_mapping:
                input_frame_path = frame_mapping[light_frame]
                output_frame_path = os.path.join(output_take_dir, os.path.basename(input_frame_path))
                
                if not os.path.exists(output_frame_path) or overwrite_aligned:
                    image = load_avif_image(input_frame_path)
                    if image is not None:
                        save_avif_image(output_frame_path, image, output_scale_factor)
                        aligned_count += 1
        
        return f"{camera_name}/{take_name}: Aligned {aligned_count} frames"
        
    except Exception as e:
        return f"{camera_name}/{take_name}: Error - {str(e)}"


def main():
    args = parse_args()
    
    # Full light frame indices - select based on center_frame
    # Different subjects may have different keyframe patterns (188 vs 189)
    full_lights_188 = [0, 20, 41, 62, 83, 104, 125, 146, 167, 188, 209, 230, 251, 272, 293, 314, 335, 348]
    full_lights_189 = [1, 21, 42, 63, 84, 105, 126, 147, 168, 189, 210, 231, 252, 273, 294, 315, 336, 349]
    
    # Select keyframe list based on center_frame
    if args.center_frame == 188:
        full_lights = full_lights_188
    elif args.center_frame == 189:
        full_lights = full_lights_189
    else:
        # For other center frames, try to determine the appropriate list
        if args.center_frame in full_lights_188:
            full_lights = full_lights_188
        elif args.center_frame in full_lights_189:
            full_lights = full_lights_189
        else:
            print(f"ERROR: center_frame ({args.center_frame}) not found in any predefined keyframe list")
            print(f"Available keyframes: {full_lights_188} or {full_lights_189}")
            return 1
    
    print(f"Using keyframe list: {full_lights}")
    
    # SLURM distributed processing mode
    using_slurm = (args.slurm_task_id is not None) and (args.slurm_total_tasks is not None)
    
    if using_slurm:
        print(f"SLURM Distributed Optical Flow Alignment (Task {args.slurm_task_id}/{args.slurm_total_tasks})")
    else:
        print(f"Single-node Optical Flow Alignment for AVIF Images")
        # Set multiprocessing start method for non-SLURM mode
        mp.set_start_method('spawn', force=True)
    
    print(f"Input directory: {args.input_dir}")
    print(f"Output directory: {args.output_dir}")
    print(f"Center frame: {args.center_frame}")
    print(f"Full light frames: {full_lights}")
    print(f"Flow scale factor: {args.flow_scale_factor}")
    print(f"Output scale factor: {args.output_scale_factor}")
    print("-" * 60)
    
    # Check if input directory exists
    if not os.path.exists(args.input_dir):
        print(f"Error: Input directory '{args.input_dir}' does not exist.")
        return 1
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
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
    
    # Create all camera/take combinations
    all_combinations = [(camera_name, take_name) for camera_name in camera_list for take_name in take_list]
    
    # Filter combinations for this SLURM task if in distributed mode
    if using_slurm:
        task_combinations = [combo for i, combo in enumerate(all_combinations) 
                           if (i % args.slurm_total_tasks) == (args.slurm_task_id - 1)]
        print(f"Total combinations: {len(all_combinations)}")
        print(f"This task will process: {len(task_combinations)} combinations")
        print(f"Task combinations: {task_combinations}")
    else:
        task_combinations = all_combinations
        print(f"Processing {len(camera_list)} cameras and {len(take_list)} takes")
        print(f"Cameras: {camera_list}")
        print(f"Takes: {take_list}")
    
    if not task_combinations:
        print("No combinations assigned to this task. Exiting.")
        return 0
    
    # Check if RAFT model exists
    if not os.path.exists(args.model):
        print(f"Error: RAFT model not found at {args.model}")
        return 1
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")
    
    if using_slurm:
        print("SLURM mode: Loading RAFT model directly (single GPU per task)")
    else:
        print("RAFT model found, will load in worker processes to avoid CUDA multiprocessing issues")
    print("-" * 60)
    
    if using_slurm:
        # SLURM mode: Load model once and process sequentially
        print("Loading RAFT model...")
        model = torch.nn.DataParallel(RAFT(args))
        model.load_state_dict(torch.load(args.model, map_location=device))
        model = model.to(device)
        model.eval()
        print("RAFT model loaded successfully")
        
        # Check completion status and filter tasks
        print("Checking completion status...")
        remaining_tasks = []
        for camera_name, take_name in task_combinations:
            is_complete, status_msg = check_camera_take_completion(
                camera_name, take_name, args.input_dir, args.output_dir, full_lights, args.center_frame)
            
            if is_complete:
                print(f"{camera_name}/{take_name}: SKIP - {status_msg}")
            else:
                print(f"{camera_name}/{take_name}: PROCESS - {status_msg}")
                remaining_tasks.append((camera_name, take_name))
        
        if not remaining_tasks:
            print("All tasks already completed!")
            return 0
            
        print(f"Processing {len(remaining_tasks)} remaining tasks...")
        print("-" * 60)
        
        # Phase 1: Compute optical flow (sequential processing)
        print("Phase 1: Computing optical flow fields...")
        for camera_name, take_name in tqdm(remaining_tasks, desc="Computing flows"):
            flow_task = (camera_name, take_name, args.input_dir, args.output_dir, 
                        args.model, full_lights, args.center_frame, 
                        args.flow_scale_factor, args.save_flow_viz, args.overwrite_flows, args.output_scale_factor, args)
            result = process_camera_take_flow(flow_task)
            print(result)
        
        print("-" * 60)
        
        # Phase 2: Apply flow alignment (sequential processing)
        print("Phase 2: Applying flow alignment...")
        for camera_name, take_name in tqdm(remaining_tasks, desc="Applying alignment"):
            alignment_task = (camera_name, take_name, args.input_dir, args.output_dir, 
                            full_lights, args.center_frame, args.overwrite_aligned, args.output_scale_factor)
            result = apply_flow_alignment(alignment_task)
            print(result)
    
    else:
        # Non-SLURM mode: Use multiprocessing
        # Check completion status and filter tasks
        print("Checking completion status...")
        remaining_tasks = []
        for camera_name, take_name in task_combinations:
            is_complete, status_msg = check_camera_take_completion(
                camera_name, take_name, args.input_dir, args.output_dir, full_lights, args.center_frame)
            
            if is_complete:
                print(f"{camera_name}/{take_name}: SKIP - {status_msg}")
            else:
                print(f"{camera_name}/{take_name}: PROCESS - {status_msg}")
                remaining_tasks.append((camera_name, take_name))
        
        if not remaining_tasks:
            print("All tasks already completed!")
            return 0
            
        print(f"Processing {len(remaining_tasks)} remaining tasks...")
        print("-" * 60)
        
        print("Phase 1: Computing optical flow fields...")
        flow_tasks = []
        for camera_name, take_name in remaining_tasks:
            flow_tasks.append((camera_name, take_name, args.input_dir, args.output_dir, 
                             args.model, full_lights, args.center_frame, 
                             args.flow_scale_factor, args.save_flow_viz, args.overwrite_flows, args.output_scale_factor, args))
        
        # Process flow computation (use fewer workers due to GPU memory)
        flow_workers = 1 if torch.cuda.is_available() else min(2, args.workers)
        print(f"Using {flow_workers} worker(s) for flow computation")
        
        with ProcessPoolExecutor(max_workers=flow_workers) as executor:
            futures = {executor.submit(process_camera_take_flow, task): task for task in flow_tasks}
            
            for future in tqdm(as_completed(futures), total=len(futures), desc="Computing flows"):
                result = future.result()
                print(result)
        
        print("-" * 60)
        
        # Phase 2: Apply flow alignment
        print("Phase 2: Applying flow alignment...")
        alignment_tasks = []
        for camera_name, take_name in remaining_tasks:
            alignment_tasks.append((camera_name, take_name, args.input_dir, args.output_dir, 
                                  full_lights, args.center_frame, args.overwrite_aligned, args.output_scale_factor))
        
        # Process alignment (can use more workers as it's CPU-bound)
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            futures = {executor.submit(apply_flow_alignment, task): task for task in alignment_tasks}
            
            for future in tqdm(as_completed(futures), total=len(futures), desc="Applying alignment"):
                result = future.result()
                print(result)
    
    print("-" * 60)
    print("Optical flow alignment completed!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
