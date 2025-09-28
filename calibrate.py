#!/usr/bin/env python3
"""
Calibration tool to help find the correct regions for BetOnline
Run this to see where the system is looking for players
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from capture.window_detector import WindowDetector
from capture.screen_capture import ScreenCapture, CaptureRegion
import cv2
import numpy as np
from pathlib import Path
from loguru import logger

def main():
    """Main calibration function"""
    logger.info("Starting calibration tool...")
    
    # Find poker window
    detector = WindowDetector("betonline")
    window = detector.find_poker_window()
    
    if not window:
        logger.error("No BetOnline window found! Please open a poker table.")
        return
    
    logger.info(f"Found window: {window}")
    bounds = detector.get_window_bounds()
    x, y, width, height = bounds
    
    # Initialize screen capture
    screen_capture = ScreenCapture()
    
    # Capture full table
    region = CaptureRegion(x=x, y=y, width=width, height=height, name="calibration")
    image = screen_capture.capture_region(region)
    
    if image is None:
        logger.error("Failed to capture screen")
        return
    
    # Create output directory
    output_dir = Path("calibration_output")
    output_dir.mkdir(exist_ok=True)
    
    # Save original
    cv2.imwrite(str(output_dir / "original.png"), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
    logger.info(f"Saved original to calibration_output/original.png")
    
    # Define test regions (percentages to try)
    test_configs = [
        # Current config
        {"name": "current", "positions": {
            1: (0.45, 0.08, 0.10, 0.08),  # Top
            2: (0.75, 0.20, 0.10, 0.08),  # Right top
            3: (0.75, 0.50, 0.10, 0.08),  # Right bottom
            4: (0.45, 0.70, 0.10, 0.08),  # Hero
            5: (0.10, 0.50, 0.10, 0.08),  # Left bottom
            6: (0.10, 0.20, 0.10, 0.08),  # Left top
        }},
        # Alternative 1: Wider regions
        {"name": "wider", "positions": {
            1: (0.40, 0.05, 0.20, 0.10),
            2: (0.70, 0.20, 0.20, 0.10),
            3: (0.70, 0.50, 0.20, 0.10),
            4: (0.40, 0.70, 0.20, 0.10),
            5: (0.05, 0.50, 0.20, 0.10),
            6: (0.05, 0.20, 0.20, 0.10),
        }},
        # Alternative 2: Different positions
        {"name": "adjusted", "positions": {
            1: (0.45, 0.12, 0.15, 0.08),
            2: (0.65, 0.25, 0.15, 0.08),
            3: (0.65, 0.45, 0.15, 0.08),
            4: (0.45, 0.65, 0.15, 0.08),
            5: (0.20, 0.45, 0.15, 0.08),
            6: (0.20, 0.25, 0.15, 0.08),
        }},
    ]
    
    # Test each configuration
    for config in test_configs:
        overlay = image.copy()
        
        # Draw regions
        for seat, (px, py, pw, ph) in config["positions"].items():
            rx = int(px * width)
            ry = int(py * height)
            rw = int(pw * width)
            rh = int(ph * height)
            
            # Draw rectangle
            cv2.rectangle(overlay, (rx, ry), (rx + rw, ry + rh), (0, 255, 0), 2)
            cv2.putText(overlay, f"Seat {seat}", (rx, ry - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            # Extract and save region
            region_img = image[ry:ry+rh, rx:rx+rw]
            cv2.imwrite(str(output_dir / f"{config['name']}_seat{seat}.png"), 
                       cv2.cvtColor(region_img, cv2.COLOR_RGB2BGR))
        
        # Save overlay
        cv2.imwrite(str(output_dir / f"{config['name']}_overlay.png"), 
                   cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))
        logger.info(f"Saved {config['name']} configuration")
    
    logger.info("\nCalibration complete!")
    logger.info("Check calibration_output/ folder for:")
    logger.info("  - original.png: Full table screenshot")
    logger.info("  - *_overlay.png: Shows where we're looking for players")
    logger.info("  - *_seat*.png: Individual seat captures")
    logger.info("\nLook for the configuration that best captures player names/stacks")
    logger.info("Share these images to help diagnose the issue!")

if __name__ == "__main__":
    main()