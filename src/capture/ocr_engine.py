import cv2
import numpy as np
import pytesseract
from PIL import Image
from typing import Optional, Dict, Any, List, Tuple
import re
from loguru import logger
from dataclasses import dataclass


@dataclass
class OCRResult:
    """Container for OCR results"""
    text: str
    confidence: float
    region: str = ""
    processed_image: Optional[np.ndarray] = None


class OCREngine:
    """Handles OCR operations for extracting text from poker table images"""
    
    def __init__(self, engine: str = "pytesseract"):
        self.engine = engine
        self.config = self._get_default_config()
        self.preprocessing_pipeline = ["grayscale", "threshold", "denoise"]
        
        # Regex patterns for poker-specific text
        self.patterns = {
            "money": r"[\$€£]?[\d,]+\.?\d*",
            "cards": r"[AKQJT2-9][schd]",
            "action": r"(fold|check|call|bet|raise|all-in)",
            "vpip": r"VPIP:\s*([\d.]+)%?",
            "pfr": r"PFR:\s*([\d.]+)%?",
            "3bet": r"3bet:\s*([\d.]+)%?",
            "username": r"[A-Za-z0-9_]+",
            "percentage": r"([\d.]+)%"
        }
        
        logger.info(f"OCREngine initialized with {engine}")
    
    def _get_default_config(self) -> str:
        """Get default Tesseract configuration"""
        return "--oem 3 --psm 11 -c tessedit_char_whitelist=0123456789AKQJTschd$.,%()/- "
    
    def preprocess_image(self, image: np.ndarray, operations: List[str] = None) -> np.ndarray:
        """Apply preprocessing operations to improve OCR accuracy"""
        if operations is None:
            operations = self.preprocessing_pipeline
        
        processed = image.copy()
        
        for op in operations:
            if op == "grayscale":
                if len(processed.shape) == 3:
                    processed = cv2.cvtColor(processed, cv2.COLOR_RGB2GRAY)
            
            elif op == "threshold":
                if len(processed.shape) == 2:  # Ensure grayscale
                    _, processed = cv2.threshold(processed, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            elif op == "adaptive_threshold":
                if len(processed.shape) == 2:
                    processed = cv2.adaptiveThreshold(processed, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                                    cv2.THRESH_BINARY, 11, 2)
            
            elif op == "denoise":
                if len(processed.shape) == 2:
                    processed = cv2.medianBlur(processed, 3)
            
            elif op == "dilate":
                kernel = np.ones((2, 2), np.uint8)
                processed = cv2.dilate(processed, kernel, iterations=1)
            
            elif op == "erode":
                kernel = np.ones((2, 2), np.uint8)
                processed = cv2.erode(processed, kernel, iterations=1)
            
            elif op == "invert":
                processed = cv2.bitwise_not(processed)
            
            elif op == "resize":
                # Upscale for better OCR
                processed = cv2.resize(processed, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        
        return processed
    
    def extract_text(self, image: np.ndarray, preprocess: bool = True, 
                    custom_config: str = None) -> OCRResult:
        """Extract text from image using OCR"""
        try:
            # Preprocess image if requested
            if preprocess:
                processed_image = self.preprocess_image(image)
            else:
                processed_image = image
            
            # Use custom config if provided
            config = custom_config or self.config
            
            # Perform OCR
            if self.engine == "pytesseract":
                # Get detailed results with confidence scores
                data = pytesseract.image_to_data(processed_image, config=config, output_type=pytesseract.Output.DICT)
                
                # Filter and combine text with confidence
                texts = []
                confidences = []
                
                for i in range(len(data['text'])):
                    if int(data['conf'][i]) > 0:  # Valid detection
                        texts.append(data['text'][i])
                        confidences.append(int(data['conf'][i]))
                
                text = ' '.join(texts)
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0
                
                return OCRResult(
                    text=text.strip(),
                    confidence=avg_confidence / 100,  # Convert to 0-1 scale
                    processed_image=processed_image
                )
            
            else:
                # Placeholder for other OCR engines (easyocr, etc.)
                logger.warning(f"OCR engine {self.engine} not fully implemented")
                return OCRResult(text="", confidence=0.0)
                
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            return OCRResult(text="", confidence=0.0)
    
    def extract_number(self, image: np.ndarray, is_money: bool = False) -> Optional[float]:
        """Extract numerical value from image"""
        result = self.extract_text(image, preprocess=True, 
                                  custom_config="--psm 8 -c tessedit_char_whitelist=0123456789.$,")
        
        if result.confidence < 0.5:
            return None
        
        # Clean and parse number
        text = result.text.replace(',', '').replace('$', '').replace('€', '').replace('£', '')
        
        try:
            return float(text)
        except ValueError:
            # Try to find number pattern
            match = re.search(r'[\d.]+', text)
            if match:
                try:
                    return float(match.group())
                except ValueError:
                    pass
        
        return None
    
    def extract_cards(self, image: np.ndarray) -> List[str]:
        """Extract playing cards from image"""
        # Preprocess for card detection
        processed = self.preprocess_image(image, ["grayscale", "threshold", "resize"])
        
        # OCR with card-specific config
        result = self.extract_text(processed, preprocess=False,
                                  custom_config="--psm 8 -c tessedit_char_whitelist=AKQJT23456789schd")
        
        if result.confidence < 0.5:
            return []
        
        # Find card patterns
        cards = re.findall(r'[AKQJT2-9][schd]', result.text)
        
        # Validate cards (should be 2-character strings)
        valid_cards = []
        for card in cards:
            if len(card) == 2:
                rank = card[0]
                suit = card[1]
                if rank in 'AKQJT23456789' and suit in 'schd':
                    valid_cards.append(card)
        
        return valid_cards
    
    def extract_hud_stats(self, image: np.ndarray) -> Dict[str, float]:
        """Extract HUD statistics from image"""
        stats = {}
        
        # Extract text with high accuracy settings
        result = self.extract_text(image, preprocess=True)
        
        if result.confidence < 0.5:
            return stats
        
        text = result.text
        
        # Extract common HUD stats
        stat_patterns = {
            "vpip": r"(?:VPIP|VP)[:\s]*([\d.]+)",
            "pfr": r"(?:PFR|PR)[:\s]*([\d.]+)",
            "3bet": r"(?:3B|3bet)[:\s]*([\d.]+)",
            "fold_3bet": r"(?:F3B|Fold3B)[:\s]*([\d.]+)",
            "cbet": r"(?:CB|Cbet)[:\s]*([\d.]+)",
            "af": r"(?:AF|Agg)[:\s]*([\d.]+)",
            "wtsd": r"(?:WTSD|WtSD)[:\s]*([\d.]+)",
            "wwsf": r"(?:WWSF|W\$SF)[:\s]*([\d.]+)"
        }
        
        for stat_name, pattern in stat_patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    value = float(match.group(1))
                    stats[stat_name] = value
                except ValueError:
                    pass
        
        return stats
    
    def extract_player_name(self, image: np.ndarray) -> Optional[str]:
        """Extract player username from image"""
        # Use less restrictive preprocessing for names
        processed = self.preprocess_image(image, ["grayscale", "denoise"])
        
        result = self.extract_text(processed, preprocess=False,
                                  custom_config="--psm 8")
        
        if result.confidence < 0.5:
            return None
        
        # Clean up common OCR errors in usernames
        text = result.text.strip()
        # Remove non-alphanumeric characters except underscore and dash
        text = re.sub(r'[^A-Za-z0-9_\-]', '', text)
        
        # Validate username (must be reasonable)
        if len(text) >= 3 and len(text) <= 20:  # Reasonable username length
            # Check if it's likely a real username (not random OCR garbage)
            # Must have at least one letter or number
            if re.search(r'[A-Za-z0-9]', text):
                # Avoid common OCR misreads that look like system text
                garbage_patterns = [
                    r'^Error',
                    r'^INFO',
                    r'^DEBUG',
                    r'window',
                    r'poker',
                    r'Found',
                    r'updated',
                    r'session',
                    r'detected'
                ]
                
                for pattern in garbage_patterns:
                    if re.search(pattern, text, re.IGNORECASE):
                        logger.debug(f"Rejected garbage username: {text}")
                        return None
                
                return text
        
        return None
    
    def extract_pot_size(self, image: np.ndarray) -> Optional[float]:
        """Extract pot size from image"""
        return self.extract_number(image, is_money=True)
    
    def extract_stack_size(self, image: np.ndarray) -> Optional[float]:
        """Extract player stack size from image"""
        return self.extract_number(image, is_money=True)
    
    def extract_action_text(self, image: np.ndarray) -> Optional[str]:
        """Extract action text (fold, call, raise, etc.)"""
        result = self.extract_text(image, preprocess=True)
        
        if result.confidence < 0.5:
            return None
        
        text = result.text.lower()
        
        # Look for action keywords
        actions = ["fold", "check", "call", "bet", "raise", "all-in", "all in"]
        
        for action in actions:
            if action in text:
                # Try to extract amount if present
                amount_match = re.search(r'[\d,]+\.?\d*', text)
                if amount_match and action in ["bet", "raise", "call"]:
                    return f"{action} {amount_match.group()}"
                return action
        
        return None
    
    def batch_extract(self, images: Dict[str, np.ndarray]) -> Dict[str, OCRResult]:
        """Extract text from multiple images"""
        results = {}
        
        for name, image in images.items():
            result = self.extract_text(image)
            result.region = name
            results[name] = result
            
            logger.debug(f"OCR for {name}: {result.text[:50]}... (confidence: {result.confidence:.2f})")
        
        return results
    
    def validate_extraction(self, text: str, expected_pattern: str) -> bool:
        """Validate extracted text against expected pattern"""
        if expected_pattern in self.patterns:
            pattern = self.patterns[expected_pattern]
        else:
            pattern = expected_pattern
        
        return bool(re.match(pattern, text))
    
    def improve_accuracy_for_region(self, image: np.ndarray, region_type: str) -> OCRResult:
        """Apply region-specific preprocessing for better accuracy"""
        if region_type == "cards":
            # High contrast for card detection
            operations = ["grayscale", "threshold", "resize"]
            config = "--psm 8 -c tessedit_char_whitelist=AKQJT23456789schd"
        
        elif region_type == "money":
            # Optimize for numbers and currency
            operations = ["grayscale", "adaptive_threshold", "denoise"]
            config = "--psm 8 -c tessedit_char_whitelist=0123456789.$,"
        
        elif region_type == "hud":
            # Balance for mixed text and numbers
            operations = ["grayscale", "threshold", "denoise"]
            config = "--psm 6"
        
        elif region_type == "username":
            # Less aggressive preprocessing for text
            operations = ["grayscale", "denoise"]
            config = "--psm 8"
        
        else:
            # Default settings
            operations = self.preprocessing_pipeline
            config = self.config
        
        processed = self.preprocess_image(image, operations)
        return self.extract_text(processed, preprocess=False, custom_config=config)