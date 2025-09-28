"""
YOLO-based detector for poker table elements
"""
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import cv2
from loguru import logger

try:
    from ultralytics import YOLO
except ImportError:
    logger.warning("ultralytics not installed, YOLO detector will not work")
    YOLO = None


@dataclass
class Detection:
    """Single detection result"""
    label: str
    confidence: float
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2
    image_crop: Optional[np.ndarray] = None


class YOLODetector:
    """Detects poker table elements using YOLO"""
    
    # Class labels for poker elements
    LABELS = {
        0: 'player_box',
        1: 'pot_area',
        2: 'community_cards',
        3: 'hole_cards',
        4: 'dealer_button',
        5: 'action_buttons',
        6: 'bet_chips'
    }
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize YOLO detector
        
        Args:
            model_path: Path to custom YOLO model, or None to use pretrained
        """
        self.model = None
        self.model_path = model_path
        
        if YOLO is None:
            logger.error("YOLO not available, install with: pip install ultralytics")
            return
            
        self._load_model()
    
    def _load_model(self):
        """Load YOLO model"""
        try:
            if self.model_path and Path(self.model_path).exists():
                # Load custom poker-trained model
                self.model = YOLO(self.model_path)
                logger.info(f"Loaded custom YOLO model from {self.model_path}")
            else:
                # Use pretrained model and adapt for poker
                # Note: In production, you'd want a poker-specific trained model
                self.model = YOLO('yolov8s.pt')  # Small model for speed
                logger.info("Using pretrained YOLOv8s model")
                logger.warning("For best results, train a custom model on poker tables")
                
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            self.model = None
    
    def detect(self, image: np.ndarray, confidence_threshold: float = 0.5) -> List[Detection]:
        """
        Detect poker elements in image
        
        Args:
            image: Input image (RGB)
            confidence_threshold: Minimum confidence for detections
            
        Returns:
            List of Detection objects
        """
        if self.model is None:
            return []
        
        detections = []
        
        try:
            # Run inference
            results = self.model(image, conf=confidence_threshold)
            
            for result in results:
                if result.boxes is None:
                    continue
                    
                for box in result.boxes:
                    # Extract detection info
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                    conf = float(box.conf[0])
                    cls = int(box.cls[0])
                    
                    # Get label name
                    label = self.LABELS.get(cls, f"class_{cls}")
                    
                    # Crop detection from image
                    crop = image[y1:y2, x1:x2]
                    
                    detection = Detection(
                        label=label,
                        confidence=conf,
                        bbox=(x1, y1, x2, y2),
                        image_crop=crop
                    )
                    detections.append(detection)
                    
            logger.debug(f"Found {len(detections)} detections")
            
        except Exception as e:
            logger.error(f"Detection failed: {e}")
            
        return detections
    
    def detect_players(self, image: np.ndarray) -> List[Detection]:
        """
        Detect only player boxes
        
        Returns:
            List of player box detections
        """
        all_detections = self.detect(image)
        return [d for d in all_detections if d.label == 'player_box']
    
    def detect_cards(self, image: np.ndarray) -> Dict[str, List[Detection]]:
        """
        Detect cards on table
        
        Returns:
            Dict with 'community' and 'hole' card detections
        """
        all_detections = self.detect(image)
        
        return {
            'community': [d for d in all_detections if d.label == 'community_cards'],
            'hole': [d for d in all_detections if d.label == 'hole_cards']
        }
    
    def detect_pot(self, image: np.ndarray) -> Optional[Detection]:
        """
        Detect pot area
        
        Returns:
            Pot detection or None
        """
        all_detections = self.detect(image)
        pot_detections = [d for d in all_detections if d.label == 'pot_area']
        
        if pot_detections:
            # Return highest confidence pot detection
            return max(pot_detections, key=lambda d: d.confidence)
        return None
    
    def detect_table_elements(self, image: np.ndarray) -> Dict[str, List[Detection]]:
        """
        Detect all table elements organized by type
        
        Returns:
            Dictionary of detections by element type
        """
        all_detections = self.detect(image)
        
        # Group by label
        organized = {}
        for detection in all_detections:
            if detection.label not in organized:
                organized[detection.label] = []
            organized[detection.label].append(detection)
            
        return organized
    
    def visualize_detections(self, image: np.ndarray, detections: List[Detection]) -> np.ndarray:
        """
        Draw detections on image for debugging
        
        Args:
            image: Original image
            detections: List of detections to draw
            
        Returns:
            Image with drawn detections
        """
        vis_image = image.copy()
        
        # Color map for different detection types
        colors = {
            'player_box': (0, 255, 0),      # Green
            'pot_area': (255, 255, 0),      # Yellow
            'community_cards': (0, 255, 255), # Cyan
            'hole_cards': (255, 0, 255),     # Magenta
            'dealer_button': (255, 128, 0),  # Orange
            'action_buttons': (128, 128, 255), # Light blue
            'bet_chips': (255, 0, 0)         # Red
        }
        
        for detection in detections:
            x1, y1, x2, y2 = detection.bbox
            color = colors.get(detection.label, (255, 255, 255))
            
            # Draw bounding box
            cv2.rectangle(vis_image, (x1, y1), (x2, y2), color, 2)
            
            # Draw label with confidence
            label_text = f"{detection.label}: {detection.confidence:.2f}"
            cv2.putText(vis_image, label_text, (x1, y1 - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                       
        return vis_image
    
    def save_debug_visualization(self, image: np.ndarray, detections: List[Detection], 
                                 output_path: str = "debug_detections.png"):
        """
        Save visualization for debugging
        
        Args:
            image: Original image
            detections: Detections to visualize
            output_path: Where to save the visualization
        """
        vis_image = self.visualize_detections(image, detections)
        cv2.imwrite(output_path, cv2.cvtColor(vis_image, cv2.COLOR_RGB2BGR))
        logger.info(f"Saved detection visualization to {output_path}")


class FallbackDetector:
    """
    Fallback detector using traditional CV when YOLO is unavailable
    Uses template matching and contour detection
    """
    
    def __init__(self):
        logger.info("Using fallback detector (traditional CV)")
        
    def detect_players(self, image: np.ndarray) -> List[Detection]:
        """
        Detect player areas using contour detection
        Looks for rectangular regions with expected player box characteristics
        """
        detections = []
        
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        
        # Edge detection
        edges = cv2.Canny(gray, 50, 150)
        
        # Find contours
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        height, width = image.shape[:2]
        
        for contour in contours:
            # Get bounding box
            x, y, w, h = cv2.boundingRect(contour)
            
            # Filter by expected player box size (5-20% of image dimensions)
            if (0.05 * width < w < 0.2 * width and 
                0.05 * height < h < 0.15 * height):
                
                # Check aspect ratio (player boxes are usually wider than tall)
                aspect_ratio = w / h
                if 1.5 < aspect_ratio < 4.0:
                    detection = Detection(
                        label='player_box',
                        confidence=0.7,  # Fixed confidence for fallback
                        bbox=(x, y, x + w, y + h),
                        image_crop=image[y:y+h, x:x+w]
                    )
                    detections.append(detection)
                    
        logger.debug(f"Fallback detector found {len(detections)} potential player boxes")
        return detections