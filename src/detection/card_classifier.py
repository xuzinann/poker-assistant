"""
Card classifier using MobileNetV3 or traditional CV
"""
import numpy as np
from typing import List, Optional, Tuple, Dict
from dataclasses import dataclass
import cv2
from loguru import logger

try:
    import torch
    import torchvision.transforms as transforms
    from torchvision import models
    TORCH_AVAILABLE = True
except ImportError:
    logger.warning("PyTorch not installed, using traditional CV for card detection")
    TORCH_AVAILABLE = False


@dataclass
class Card:
    """Detected card"""
    rank: str  # A, K, Q, J, T, 9, 8, 7, 6, 5, 4, 3, 2
    suit: str  # s, h, d, c
    confidence: float
    
    def __str__(self):
        suit_symbols = {'s': '♠', 'h': '♥', 'd': '♦', 'c': '♣'}
        return f"{self.rank}{suit_symbols.get(self.suit, self.suit)}"


class CardClassifier:
    """Classify playing cards from images"""
    
    RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
    SUITS = ['s', 'h', 'd', 'c']  # spades, hearts, diamonds, clubs
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize card classifier
        
        Args:
            model_path: Path to trained model weights
        """
        self.model = None
        self.model_path = model_path
        self.transform = None
        
        if TORCH_AVAILABLE:
            self._init_neural_classifier()
        else:
            logger.info("Using traditional CV for card classification")
    
    def _init_neural_classifier(self):
        """Initialize neural network classifier"""
        try:
            # Setup image transforms
            self.transform = transforms.Compose([
                transforms.ToPILImage(),
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                   std=[0.229, 0.224, 0.225])
            ])
            
            if self.model_path:
                # Load custom trained model
                self.model = torch.load(self.model_path, map_location='cpu')
                self.model.eval()
                logger.info(f"Loaded custom card model from {self.model_path}")
            else:
                # Use pretrained MobileNetV3 and adapt
                # Note: In production, you'd want a model trained on playing cards
                self.model = models.mobilenet_v3_small(pretrained=True)
                # Modify output layer for 52 cards (13 ranks * 4 suits)
                self.model.classifier[-1] = torch.nn.Linear(
                    self.model.classifier[-1].in_features, 52
                )
                self.model.eval()
                logger.warning("Using pretrained MobileNetV3 - train custom model for better accuracy")
                
        except Exception as e:
            logger.error(f"Failed to init neural classifier: {e}")
            self.model = None
    
    def classify_card(self, image: np.ndarray) -> Optional[Card]:
        """
        Classify a single card image
        
        Args:
            image: Card image (RGB)
            
        Returns:
            Card object or None
        """
        if TORCH_AVAILABLE and self.model is not None:
            return self._classify_neural(image)
        else:
            return self._classify_traditional(image)
    
    def _classify_neural(self, image: np.ndarray) -> Optional[Card]:
        """
        Classify using neural network
        
        Args:
            image: Card image
            
        Returns:
            Card or None
        """
        try:
            # Preprocess
            input_tensor = self.transform(image).unsqueeze(0)
            
            # Inference
            with torch.no_grad():
                output = self.model(input_tensor)
                probabilities = torch.nn.functional.softmax(output[0], dim=0)
                
            # Get top prediction
            confidence, idx = torch.max(probabilities, 0)
            confidence = float(confidence)
            idx = int(idx)
            
            # Convert index to rank and suit
            rank_idx = idx // 4
            suit_idx = idx % 4
            
            if confidence > 0.5:  # Minimum confidence threshold
                card = Card(
                    rank=self.RANKS[rank_idx],
                    suit=self.SUITS[suit_idx],
                    confidence=confidence
                )
                logger.debug(f"Neural classifier detected: {card}")
                return card
                
        except Exception as e:
            logger.error(f"Neural classification failed: {e}")
            
        return None
    
    def _classify_traditional(self, image: np.ndarray) -> Optional[Card]:
        """
        Classify using traditional computer vision
        
        Args:
            image: Card image
            
        Returns:
            Card or None
        """
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            
            # Detect rank
            rank = self._detect_rank_traditional(gray)
            if not rank:
                return None
            
            # Detect suit color first (red vs black)
            is_red = self._is_red_suit(image)
            
            # Detect specific suit
            suit = self._detect_suit_traditional(image, is_red)
            if not suit:
                return None
            
            card = Card(rank=rank, suit=suit, confidence=0.7)
            logger.debug(f"Traditional CV detected: {card}")
            return card
            
        except Exception as e:
            logger.error(f"Traditional classification failed: {e}")
            return None
    
    def _detect_rank_traditional(self, gray_image: np.ndarray) -> Optional[str]:
        """
        Detect card rank using template matching
        
        Args:
            gray_image: Grayscale card image
            
        Returns:
            Rank or None
        """
        # This is a simplified version
        # In production, you'd use template matching with pre-saved rank templates
        
        # Use OCR to detect rank characters
        try:
            from paddleocr import PaddleOCR
            ocr = PaddleOCR(use_angle_cls=False, lang='en', show_log=False)
            result = ocr.ocr(gray_image, cls=False)
            
            if result and result[0]:
                for line in result[0]:
                    text = line[1][0].upper()
                    # Check if text is a valid rank
                    for rank in self.RANKS:
                        if rank in text or (rank == 'T' and '10' in text):
                            return rank
                            
        except:
            pass
        
        # Fallback: analyze image features
        # Count corners/edges to distinguish face cards
        edges = cv2.Canny(gray_image, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Heuristic: more complex patterns = face card
        if len(contours) > 20:
            return 'K'  # Guess face card
        elif len(contours) > 10:
            return 'Q'
        else:
            return 'A'  # Simple pattern
    
    def _is_red_suit(self, image: np.ndarray) -> bool:
        """
        Check if card has red suit (hearts/diamonds)
        
        Args:
            image: Card image (RGB)
            
        Returns:
            True if red suit
        """
        # Extract red channel
        if len(image.shape) == 3:
            red_channel = image[:, :, 0]
            other_channels = (image[:, :, 1] + image[:, :, 2]) / 2
            
            # Check if red dominates
            red_dominance = np.mean(red_channel > other_channels)
            return red_dominance > 0.3
            
        return False
    
    def _detect_suit_traditional(self, image: np.ndarray, is_red: bool) -> Optional[str]:
        """
        Detect specific suit
        
        Args:
            image: Card image
            is_red: Whether suit is red
            
        Returns:
            Suit character or None
        """
        # Convert to binary for shape analysis
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        _, binary = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY)
        
        # Find suit symbol contours
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return None
        
        # Analyze largest contour shape
        largest_contour = max(contours, key=cv2.contourArea)
        
        # Calculate shape features
        perimeter = cv2.arcLength(largest_contour, True)
        area = cv2.contourArea(largest_contour)
        
        if area > 0:
            circularity = 4 * np.pi * area / (perimeter * perimeter)
            
            if is_red:
                # Hearts are more circular than diamonds
                if circularity > 0.7:
                    return 'h'
                else:
                    return 'd'
            else:
                # Clubs have three circles, spades are pointed
                if circularity > 0.6:
                    return 'c'
                else:
                    return 's'
        
        # Default guess
        return 'h' if is_red else 's'
    
    def classify_multiple(self, images: List[np.ndarray]) -> List[Optional[Card]]:
        """
        Classify multiple card images
        
        Args:
            images: List of card images
            
        Returns:
            List of Card objects (None for failed classifications)
        """
        results = []
        for image in images:
            card = self.classify_card(image)
            results.append(card)
            
        return results
    
    def detect_cards_in_region(self, image: np.ndarray) -> List[Tuple[Card, Tuple[int, int, int, int]]]:
        """
        Detect and classify all cards in an image region
        
        Args:
            image: Image potentially containing multiple cards
            
        Returns:
            List of (Card, bbox) tuples
        """
        cards = []
        
        # Find card-like regions
        card_regions = self._find_card_regions(image)
        
        for bbox in card_regions:
            x1, y1, x2, y2 = bbox
            card_image = image[y1:y2, x1:x2]
            
            card = self.classify_card(card_image)
            if card:
                cards.append((card, bbox))
                
        logger.debug(f"Found {len(cards)} cards in region")
        return cards
    
    def _find_card_regions(self, image: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """
        Find potential card regions in image
        
        Args:
            image: Input image
            
        Returns:
            List of bounding boxes (x1, y1, x2, y2)
        """
        regions = []
        
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        
        # Find rectangular contours
        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        height, width = image.shape[:2]
        
        for contour in contours:
            # Get bounding rectangle
            x, y, w, h = cv2.boundingRect(contour)
            
            # Check if rectangle could be a card
            # Cards have aspect ratio around 0.7 (width/height)
            if w > 0 and h > 0:
                aspect_ratio = w / h
                
                # Check aspect ratio and minimum size
                if (0.5 < aspect_ratio < 0.9 and 
                    w > width * 0.03 and h > height * 0.05):
                    
                    regions.append((x, y, x + w, y + h))
                    
        return regions