#!/usr/bin/env python3
"""
Test the new YOLO-based detection pipeline
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from capture.window_detector import WindowDetector
from capture.screen_capture import ScreenCapture, CaptureRegion
from detection.yolo_detector import YOLODetector, FallbackDetector
from detection.paddle_reader import PaddleReader
from detection.card_classifier import CardClassifier
from detection.hand_fsm import HandStateMachine
import cv2
from pathlib import Path
from loguru import logger
import time

def test_detection_pipeline():
    """Test the new detection components"""
    logger.info("Testing new detection pipeline...")
    
    # Find poker window
    detector = WindowDetector("betonline")
    window = detector.find_poker_window()
    
    if not window:
        logger.error("No BetOnline window found! Please open a poker table.")
        return
    
    logger.info(f"Found window: {window}")
    bounds = detector.get_window_bounds()
    x, y, width, height = bounds
    
    # Initialize components
    screen_capture = ScreenCapture()
    
    # Try YOLO detector
    try:
        yolo = YOLODetector()
        logger.info("YOLO detector initialized")
    except:
        logger.warning("YOLO not available, using fallback")
        yolo = FallbackDetector()
    
    paddle = PaddleReader()
    card_classifier = CardClassifier()
    fsm = HandStateMachine()
    
    # Capture full table
    region = CaptureRegion(x=x, y=y, width=width, height=height, name="test")
    image = screen_capture.capture_region(region)
    
    if image is None:
        logger.error("Failed to capture screen")
        return
    
    # Create output directory
    output_dir = Path("test_detection_output")
    output_dir.mkdir(exist_ok=True)
    
    # Save original
    cv2.imwrite(str(output_dir / "original.png"), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
    logger.info("Saved original to test_detection_output/original.png")
    
    # Test YOLO detection
    logger.info("\n=== Testing YOLO Detection ===")
    player_detections = yolo.detect_players(image)
    logger.info(f"Found {len(player_detections)} player boxes")
    
    if hasattr(yolo, 'visualize_detections'):
        vis_image = yolo.visualize_detections(image, player_detections)
        cv2.imwrite(str(output_dir / "yolo_detections.png"), 
                   cv2.cvtColor(vis_image, cv2.COLOR_RGB2BGR))
        logger.info("Saved YOLO visualization")
    
    # Test PaddleOCR on detected players
    logger.info("\n=== Testing PaddleOCR ===")
    for i, detection in enumerate(player_detections[:3]):  # Test first 3
        if detection.image_crop is not None:
            logger.info(f"\nPlayer {i+1}:")
            
            # Save player crop
            cv2.imwrite(str(output_dir / f"player_{i+1}.png"),
                       cv2.cvtColor(detection.image_crop, cv2.COLOR_RGB2BGR))
            
            # Read name
            name = paddle.read_player_name(detection.image_crop)
            if name:
                logger.info(f"  Name: {name}")
            else:
                logger.info("  Name: Not detected")
            
            # Read stack
            stack = paddle.read_stack_size(detection.image_crop)
            if stack:
                logger.info(f"  Stack: ${stack}")
            else:
                logger.info("  Stack: Not detected")
    
    # Test pot detection
    pot_detection = yolo.detect_pot(image)
    if pot_detection and pot_detection.image_crop is not None:
        logger.info("\n=== Pot Detection ===")
        pot_amount = paddle.read_money_amount(pot_detection.image_crop)
        if pot_amount:
            logger.info(f"Pot size: ${pot_amount}")
        else:
            logger.info("Pot not readable")
    
    # Test card detection
    card_detections = yolo.detect_cards(image)
    logger.info(f"\n=== Card Detection ===")
    logger.info(f"Community cards: {len(card_detections.get('community', []))}")
    logger.info(f"Hole cards: {len(card_detections.get('hole', []))}")
    
    # Test FSM
    logger.info("\n=== Testing FSM ===")
    observation = {
        'players': ['Player1', 'Player2', 'Player3'],
        'hero_cards': ['As', 'Kh'],
        'community_cards': [],
        'pot_size': 3.0,
        'actions': []
    }
    
    hand = fsm.update(observation)
    logger.info(f"FSM State: {fsm.get_current_state().value}")
    
    # Add flop
    observation['community_cards'] = ['Qd', 'Jc', 'Th']
    observation['pot_size'] = 15.0
    hand = fsm.update(observation)
    logger.info(f"After flop - FSM State: {fsm.get_current_state().value}")
    
    logger.info("\n=== Test Complete ===")
    logger.info("Check test_detection_output/ folder for results")
    logger.info("If detection is working better, the new pipeline is ready!")

def continuous_test():
    """Continuously test detection"""
    logger.info("Starting continuous detection test (press Ctrl+C to stop)...")
    
    # Find poker window
    detector = WindowDetector("betonline")
    window = detector.find_poker_window()
    
    if not window:
        logger.error("No BetOnline window found!")
        return
    
    bounds = detector.get_window_bounds()
    x, y, width, height = bounds
    
    # Initialize components
    screen_capture = ScreenCapture()
    
    try:
        yolo = YOLODetector()
    except:
        yolo = FallbackDetector()
    
    paddle = PaddleReader()
    fsm = HandStateMachine()
    
    try:
        while True:
            # Capture
            region = CaptureRegion(x=x, y=y, width=width, height=height, name="live")
            image = screen_capture.capture_region(region)
            
            if image is None:
                time.sleep(1)
                continue
            
            # Detect players
            players = yolo.detect_players(image)
            
            player_names = []
            for detection in players:
                if detection.image_crop is not None:
                    name = paddle.read_player_name(detection.image_crop)
                    if name:
                        player_names.append(name)
            
            if player_names:
                logger.info(f"Players detected: {', '.join(player_names)}")
            
            # Detect pot
            pot_detection = yolo.detect_pot(image)
            if pot_detection and pot_detection.image_crop is not None:
                pot = paddle.read_money_amount(pot_detection.image_crop)
                if pot:
                    logger.info(f"Pot: ${pot}")
            
            time.sleep(2)  # Update every 2 seconds
            
    except KeyboardInterrupt:
        logger.info("Test stopped")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--continuous', action='store_true', 
                       help='Run continuous detection test')
    args = parser.parse_args()
    
    if args.continuous:
        continuous_test()
    else:
        test_detection_pipeline()