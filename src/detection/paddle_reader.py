"""
PaddleOCR reader for extracting text from poker table
"""
import numpy as np
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass
import re
from loguru import logger

try:
    from paddleocr import PaddleOCR
except ImportError:
    logger.warning("PaddleOCR not installed, text reading will fallback to pytesseract")
    PaddleOCR = None


@dataclass
class TextResult:
    """Text extraction result"""
    text: str
    confidence: float
    bbox: Optional[Tuple[int, int, int, int]] = None


class PaddleReader:
    """Read text from poker table using PaddleOCR"""
    
    def __init__(self, use_gpu: bool = False, lang: str = 'en'):
        """
        Initialize PaddleOCR reader
        
        Args:
            use_gpu: Whether to use GPU acceleration
            lang: Language for OCR
        """
        self.ocr = None
        self.use_gpu = use_gpu
        self.lang = lang
        
        self._init_ocr()
        
        # Patterns for poker-specific text
        self.patterns = {
            'money': re.compile(r'[\$€£]?\s*([0-9,]+\.?[0-9]*)\s*[kKmM]?'),
            'username': re.compile(r'^[A-Za-z0-9_\-]{3,20}$'),
            'action': re.compile(r'(fold|check|call|raise|bet|all[\s\-]?in)', re.IGNORECASE),
            'cards': re.compile(r'([AKQJT2-9])[♠♥♦♣schd]', re.IGNORECASE)
        }
    
    def _init_ocr(self):
        """Initialize OCR engine"""
        if PaddleOCR is None:
            logger.error("PaddleOCR not available, install with: pip install paddleocr paddlepaddle")
            return
            
        try:
            # Initialize PaddleOCR with optimized settings for game text
            self.ocr = PaddleOCR(
                use_angle_cls=True,     # Enable text angle detection
                lang=self.lang,
                use_gpu=self.use_gpu,
                show_log=False,         # Suppress verbose logging
                det_db_thresh=0.3,      # Lower threshold for detection
                rec_batch_num=6,        # Batch size for recognition
                max_text_length=25,     # Max text length for poker
                use_space_char=True,    # Enable space character
                drop_score=0.3          # Minimum score to keep
            )
            logger.info("PaddleOCR initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize PaddleOCR: {e}")
            self.ocr = None
    
    def read_text(self, image: np.ndarray, preprocess: bool = True) -> List[TextResult]:
        """
        Read all text from image
        
        Args:
            image: Input image (RGB)
            preprocess: Whether to preprocess image
            
        Returns:
            List of text results
        """
        if self.ocr is None:
            return self._fallback_read(image)
        
        results = []
        
        try:
            # Preprocess if requested
            if preprocess:
                processed = self._preprocess_for_text(image)
            else:
                processed = image
            
            # Run OCR
            ocr_results = self.ocr.ocr(processed, cls=True)
            
            if not ocr_results or not ocr_results[0]:
                return results
            
            # Parse results
            for line in ocr_results[0]:
                if len(line) >= 2:
                    bbox = line[0]
                    text, confidence = line[1]
                    
                    # Convert bbox to x1,y1,x2,y2
                    x1 = int(min(p[0] for p in bbox))
                    y1 = int(min(p[1] for p in bbox))
                    x2 = int(max(p[0] for p in bbox))
                    y2 = int(max(p[1] for p in bbox))
                    
                    result = TextResult(
                        text=text.strip(),
                        confidence=confidence,
                        bbox=(x1, y1, x2, y2)
                    )
                    results.append(result)
                    
            logger.debug(f"PaddleOCR found {len(results)} text regions")
            
        except Exception as e:
            logger.error(f"PaddleOCR failed: {e}")
            return self._fallback_read(image)
            
        return results
    
    def read_player_name(self, image: np.ndarray) -> Optional[str]:
        """
        Extract player username from image
        
        Args:
            image: Cropped player box image
            
        Returns:
            Player name or None
        """
        texts = self.read_text(image)
        
        for text_result in texts:
            # Check if text matches username pattern
            if self.patterns['username'].match(text_result.text):
                if text_result.confidence > 0.6:
                    logger.debug(f"Found player name: {text_result.text}")
                    return text_result.text
        
        # Try to find best candidate
        if texts:
            # Filter out obvious non-usernames
            candidates = []
            for t in texts:
                text = t.text.strip()
                # Basic filtering
                if (3 <= len(text) <= 20 and 
                    not any(word in text.lower() for word in ['fold', 'call', 'raise', 'bet', 'pot', 'all'])):
                    candidates.append(t)
            
            if candidates:
                # Return highest confidence candidate
                best = max(candidates, key=lambda x: x.confidence)
                if best.confidence > 0.5:
                    return best.text
                    
        return None
    
    def read_money_amount(self, image: np.ndarray) -> Optional[float]:
        """
        Extract money amount from image
        
        Args:
            image: Cropped image containing money text
            
        Returns:
            Money amount or None
        """
        texts = self.read_text(image)
        
        for text_result in texts:
            match = self.patterns['money'].search(text_result.text)
            if match:
                try:
                    # Extract number
                    amount_str = match.group(1).replace(',', '')
                    amount = float(amount_str)
                    
                    # Handle k/m suffixes
                    if 'k' in text_result.text.lower():
                        amount *= 1000
                    elif 'm' in text_result.text.lower():
                        amount *= 1000000
                        
                    logger.debug(f"Found money amount: ${amount}")
                    return amount
                    
                except ValueError:
                    continue
                    
        return None
    
    def read_stack_size(self, image: np.ndarray) -> Optional[float]:
        """
        Extract player stack size
        
        Args:
            image: Cropped player box image
            
        Returns:
            Stack size or None
        """
        # Stack is usually the largest number in player box
        texts = self.read_text(image)
        
        amounts = []
        for text_result in texts:
            match = self.patterns['money'].search(text_result.text)
            if match:
                try:
                    amount_str = match.group(1).replace(',', '')
                    amount = float(amount_str)
                    
                    # Handle k/m suffixes
                    if 'k' in text_result.text.lower():
                        amount *= 1000
                    elif 'm' in text_result.text.lower():
                        amount *= 1000000
                        
                    amounts.append(amount)
                except ValueError:
                    continue
        
        if amounts:
            # Return largest amount (usually the stack)
            return max(amounts)
            
        return None
    
    def read_action(self, image: np.ndarray) -> Optional[str]:
        """
        Extract player action from image
        
        Args:
            image: Cropped action area image
            
        Returns:
            Action text or None
        """
        texts = self.read_text(image)
        
        for text_result in texts:
            match = self.patterns['action'].search(text_result.text)
            if match:
                action = match.group(1).lower()
                
                # Check for amount after action
                money_match = self.patterns['money'].search(text_result.text)
                if money_match and action in ['raise', 'bet', 'call']:
                    try:
                        amount = float(money_match.group(1).replace(',', ''))
                        return f"{action} {amount}"
                    except ValueError:
                        pass
                        
                return action
                
        return None
    
    def _preprocess_for_text(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocess image for better OCR
        
        Args:
            image: Input image
            
        Returns:
            Preprocessed image
        """
        import cv2
        
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image
        
        # Enhance contrast
        enhanced = cv2.convertScaleAbs(gray, alpha=1.5, beta=10)
        
        # Denoise
        denoised = cv2.fastNlMeansDenoising(enhanced, h=10)
        
        # Sharpen
        kernel = np.array([[-1,-1,-1],
                          [-1, 9,-1],
                          [-1,-1,-1]])
        sharpened = cv2.filter2D(denoised, -1, kernel)
        
        return sharpened
    
    def _fallback_read(self, image: np.ndarray) -> List[TextResult]:
        """
        Fallback to pytesseract if PaddleOCR unavailable
        
        Args:
            image: Input image
            
        Returns:
            List of text results
        """
        try:
            import pytesseract
            
            # Preprocess
            processed = self._preprocess_for_text(image)
            
            # Get text with confidence
            data = pytesseract.image_to_data(processed, output_type=pytesseract.Output.DICT)
            
            results = []
            for i in range(len(data['text'])):
                if int(data['conf'][i]) > 30:  # Min confidence
                    text = data['text'][i].strip()
                    if text:
                        result = TextResult(
                            text=text,
                            confidence=int(data['conf'][i]) / 100.0,
                            bbox=(data['left'][i], data['top'][i],
                                 data['left'][i] + data['width'][i],
                                 data['top'][i] + data['height'][i])
                        )
                        results.append(result)
                        
            logger.debug(f"Tesseract fallback found {len(results)} text regions")
            return results
            
        except Exception as e:
            logger.error(f"Fallback OCR also failed: {e}")
            return []
    
    def batch_read(self, images: Dict[str, np.ndarray]) -> Dict[str, List[TextResult]]:
        """
        Read text from multiple images
        
        Args:
            images: Dictionary of name -> image
            
        Returns:
            Dictionary of name -> text results
        """
        results = {}
        for name, image in images.items():
            results[name] = self.read_text(image)
            
        return results