"""
Table reader for extracting game information directly from the poker table screen
"""
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import numpy as np
from loguru import logger

from capture.screen_capture import ScreenCapture, CaptureRegion
from capture.ocr_engine import OCREngine
from capture.window_detector import WindowDetector
from detection.yolo_detector import YOLODetector, FallbackDetector
from detection.paddle_reader import PaddleReader
from detection.card_classifier import CardClassifier
from detection.hand_fsm import HandStateMachine


@dataclass
class TableState:
    """Current state of the poker table"""
    pot_size: float = 0.0
    community_cards: List[str] = None
    dealer_position: str = None
    current_street: str = "preflop"  # preflop, flop, turn, river
    players: Dict[str, Dict] = None  # position -> {name, stack, action, cards}
    hero_cards: List[str] = None
    
    def __post_init__(self):
        if self.community_cards is None:
            self.community_cards = []
        if self.players is None:
            self.players = {}
        if self.hero_cards is None:
            self.hero_cards = []


class TableReader:
    """Reads game state directly from poker table screen"""
    
    def __init__(self, screen_capture: ScreenCapture, ocr_engine: OCREngine, site: str = "betonline"):
        self.screen_capture = screen_capture
        self.ocr = ocr_engine
        self.site = site
        
        # Window detection
        self.window_detector = WindowDetector(site)
        self.current_window_bounds = None
        
        # Initialize new detection components
        try:
            self.yolo_detector = YOLODetector()
        except:
            logger.warning("YOLO not available, using fallback detector")
            self.yolo_detector = FallbackDetector()
            
        self.paddle_reader = PaddleReader()
        self.card_classifier = CardClassifier()
        self.hand_fsm = HandStateMachine()
        
        # Table regions - these will be calculated dynamically
        self.regions = {}
        self.seat_positions = {}
        
        # State tracking
        self.previous_state = None
        self.current_hand_id = None
        self.hand_actions = []
        
        # Hero detection
        self.hero_name = None
        self.hero_seat = 4  # Bottom center position for 6-max
        
        logger.info(f"TableReader initialized for {site} with new detection pipeline")
    
    def update_regions(self):
        """Update regions based on current window size and position"""
        bounds = self.window_detector.get_window_bounds()
        if not bounds:
            logger.warning("No poker window found")
            return False
        
        x, y, width, height = bounds
        self.current_window_bounds = bounds
        
        # Define regions as percentages of window size
        # These percentages work for most poker table layouts
        self.regions = {
            'pot': {
                'x': x + int(width * 0.40),  # 40% from left
                'y': y + int(height * 0.35),  # 35% from top
                'width': int(width * 0.20),   # 20% of width
                'height': int(height * 0.08)  # 8% of height
            },
            'community': {
                'x': x + int(width * 0.30),
                'y': y + int(height * 0.40),
                'width': int(width * 0.40),
                'height': int(height * 0.12)
            },
            'hero_cards': {
                'x': x + int(width * 0.42),
                'y': y + int(height * 0.75),
                'width': int(width * 0.16),
                'height': int(height * 0.10)
            },
            'action_buttons': {
                'x': x + int(width * 0.55),
                'y': y + int(height * 0.80),
                'width': int(width * 0.35),
                'height': int(height * 0.15)
            }
        }
        
        # Player seat positions for BetOnline (adjusted for actual layout)
        # BetOnline has player info boxes with name and stack
        self.seat_positions = {
            1: {  # Top center
                'x': x + int(width * 0.45),  # More centered
                'y': y + int(height * 0.08),  # Higher up
                'width': int(width * 0.10),   # Narrower for name/stack box
                'height': int(height * 0.08)  # Smaller height
            },
            2: {  # Right top
                'x': x + int(width * 0.75),   # Further right
                'y': y + int(height * 0.20),  
                'width': int(width * 0.10),
                'height': int(height * 0.08)
            },
            3: {  # Right bottom
                'x': x + int(width * 0.75),
                'y': y + int(height * 0.50),
                'width': int(width * 0.10),
                'height': int(height * 0.08)
            },
            4: {  # Bottom center (HERO) - Your position
                'x': x + int(width * 0.45),
                'y': y + int(height * 0.70),  # Adjusted for actual hero position
                'width': int(width * 0.10),
                'height': int(height * 0.08)
            },
            5: {  # Left bottom
                'x': x + int(width * 0.10),   # Further left
                'y': y + int(height * 0.50),
                'width': int(width * 0.10),
                'height': int(height * 0.08)
            },
            6: {  # Left top
                'x': x + int(width * 0.10),
                'y': y + int(height * 0.20),
                'width': int(width * 0.10),
                'height': int(height * 0.08)
            }
        }
        
        logger.debug(f"Updated regions for window at ({x},{y}) size ({width}x{height})")
        return True
    
    def read_table_state(self) -> Optional[TableState]:
        """Read current table state from screen"""
        try:
            # Check if window is still active
            if not self.window_detector.is_window_active():
                # Try to find a new window
                logger.debug("Window closed, searching for new window...")
                new_window = self.window_detector.find_poker_window()
                if not new_window:
                    return None
                    
            # Update regions if window has moved or resized
            if self.window_detector.update_window_position() or not self.regions:
                if not self.update_regions():
                    return None
            
            # Save full table screenshot for debugging (once per session)
            if not hasattr(self, '_saved_full_table'):
                self._save_full_table_screenshot()
                self._saved_full_table = True
            
            state = TableState()
            
            # Capture full table for YOLO detection
            x, y, width, height = self.current_window_bounds
            region = CaptureRegion(x=x, y=y, width=width, height=height, name="full_table")
            full_image = self.screen_capture.capture_region(region)
            
            if full_image is None:
                return None
            
            # Read pot size using YOLO + PaddleOCR
            pot_detection = self.yolo_detector.detect_pot(full_image)
            if pot_detection and pot_detection.image_crop is not None:
                pot_amount = self.paddle_reader.read_money_amount(pot_detection.image_crop)
                if pot_amount:
                    state.pot_size = pot_amount
                    logger.debug(f"Detected pot: ${pot_amount}")
            else:
                # Fallback to old method
                pot_text = self._read_region('pot')
                if pot_text:
                    state.pot_size = self._extract_money(pot_text)
            
            # Read community cards
            community_text = self._read_region('community')
            if community_text:
                state.community_cards = self._extract_cards(community_text)
                state.current_street = self._determine_street(state.community_cards)
            
            # Read hero cards
            hero_text = self._read_region('hero_cards')
            if hero_text:
                state.hero_cards = self._extract_cards(hero_text)
            
            # Read player information
            state.players = self._read_all_players()
            
            # Update FSM with observation
            observation = {
                'players': list(state.players.values()),
                'hero_cards': state.hero_cards,
                'community_cards': state.community_cards,
                'pot_size': state.pot_size,
                'actions': self.hand_actions
            }
            
            completed_hand = self.hand_fsm.update(observation)
            if completed_hand:
                logger.info(f"Hand completed: {completed_hand.hand_id}")
                # Reset tracking for new hand
                self.reset_hand_tracking()
            
            # Debug logging
            if state.players:
                logger.debug(f"Found {len(state.players)} players at table")
                for pos, player in state.players.items():
                    logger.debug(f"  {pos}: {player.get('name', 'Unknown')} - Stack: ${player.get('stack', 0)}")
            else:
                logger.debug("No players detected at table")
            
            if state.hero_cards:
                logger.debug(f"Hero cards detected: {state.hero_cards}")
            
            return state
            
        except Exception as e:
            logger.error(f"Failed to read table state: {e}")
            return None
    
    def _read_region(self, region_name: str) -> Optional[str]:
        """Read text from a specific region"""
        if region_name not in self.regions:
            return None
        
        region_dict = self.regions[region_name]
        region = CaptureRegion(
            x=region_dict['x'],
            y=region_dict['y'],
            width=region_dict['width'],
            height=region_dict['height'],
            name=region_name
        )
        image = self.screen_capture.capture_region(region)
        
        if image is not None:
            # Store image for card extraction if needed
            if region_name == 'community' or region_name == 'hero_cards':
                self._last_cards_image = image
            
            result = self.ocr.extract_text(image)
            if result and result.confidence > 0.5:
                return result.text
        
        return None
    
    def _read_all_players(self) -> Dict[str, Dict]:
        """Read information for all players using new detection"""
        players = {}
        
        # Capture full table
        if not self.current_window_bounds:
            return players
            
        x, y, width, height = self.current_window_bounds
        region = CaptureRegion(x=x, y=y, width=width, height=height, name="full_table")
        full_image = self.screen_capture.capture_region(region)
        
        if full_image is None:
            return players
        
        # Use YOLO to detect player boxes
        player_detections = self.yolo_detector.detect_players(full_image)
        
        if not player_detections:
            # Fallback to old method
            logger.debug("No YOLO detections, using traditional method")
            for seat_num, position in self.seat_positions.items():
                player_info = self._read_player_at_position(position)
                if player_info and player_info.get('name'):
                    pos_name = self._seat_to_position(seat_num)
                    players[pos_name] = player_info
        else:
            # Process YOLO detections
            logger.debug(f"YOLO detected {len(player_detections)} player boxes")
            for i, detection in enumerate(player_detections):
                # Extract player info from detected region
                player_image = detection.image_crop
                if player_image is not None:
                    # Use PaddleOCR to read player info
                    name = self.paddle_reader.read_player_name(player_image)
                    stack = self.paddle_reader.read_stack_size(player_image)
                    
                    if name:
                        player_info = {'name': name}
                        if stack:
                            player_info['stack'] = stack
                        
                        # Determine position based on location
                        x1, y1, x2, y2 = detection.bbox
                        seat_num = self._bbox_to_seat_number(x1, y1, x2, y2, width, height)
                        pos_name = self._seat_to_position(seat_num)
                        players[pos_name] = player_info
                        
                        logger.debug(f"Detected player {name} at {pos_name} with stack ${stack}")
        
        return players
    
    def _bbox_to_seat_number(self, x1: int, y1: int, x2: int, y2: int, 
                            table_width: int, table_height: int) -> int:
        """
        Convert bounding box position to seat number
        
        Args:
            x1, y1, x2, y2: Bounding box coordinates
            table_width, table_height: Table dimensions
            
        Returns:
            Seat number (1-6)
        """
        # Calculate center of bbox relative to table
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        
        rel_x = cx / table_width
        rel_y = cy / table_height
        
        # Map to seat based on position
        if rel_y < 0.25:  # Top row
            if rel_x < 0.33:
                return 6  # Top left
            elif rel_x > 0.66:
                return 2  # Top right
            else:
                return 1  # Top center
        elif rel_y > 0.65:  # Bottom row
            return 4  # Hero position
        else:  # Middle row
            if rel_x < 0.33:
                return 5  # Left
            else:
                return 3  # Right
    
    def _read_player_at_position(self, position: Dict) -> Optional[Dict]:
        """Read player information at specific position"""
        region = CaptureRegion(
            x=position['x'],
            y=position['y'],
            width=position['width'],
            height=position['height'],
            name="player"
        )
        image = self.screen_capture.capture_region(region)
        
        if image is None:
            logger.debug(f"No image captured at position {position}")
            return None
        
        # Save screenshot for debugging
        if self.site == "betonline":
            import cv2
            import numpy as np
            from pathlib import Path
            debug_dir = Path("debug_screenshots")
            debug_dir.mkdir(exist_ok=True)
            
            # Save the captured region
            seat_name = f"seat_{position.get('x', 0)}_{position.get('y', 0)}"
            cv2.imwrite(str(debug_dir / f"{seat_name}.png"), 
                       cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
            logger.debug(f"Saved screenshot to debug_screenshots/{seat_name}.png")
        
        text = self.ocr.extract_text(image)
        if not text:
            logger.debug(f"No text extracted from position {position}")
            return None
        
        if text.confidence < 0.5:
            logger.debug(f"Low confidence OCR at position: '{text.text}' (conf: {text.confidence:.2f})")
            return None
        
        logger.debug(f"OCR extracted: '{text.text}' with confidence {text.confidence:.2f}")
        
        # Parse player info from text
        lines = text.text.strip().split('\n')
        player_info = {}
        
        for line in lines:
            # Extract username (usually first line)
            if not player_info.get('name') and len(line) > 2:
                player_info['name'] = line.strip()
            
            # Extract stack size
            money = self._extract_money(line)
            if money > 0:
                player_info['stack'] = money
            
            # Extract action
            if any(action in line.lower() for action in ['fold', 'call', 'raise', 'check', 'bet', 'all-in']):
                player_info['last_action'] = line.strip()
        
        return player_info if player_info else None
    
    def _extract_money(self, text: str) -> float:
        """Extract money amount from text"""
        # Look for patterns like $100, $1,000.50, etc.
        pattern = r'\$?([\d,]+\.?\d*)'
        match = re.search(pattern, text)
        if match:
            amount_str = match.group(1).replace(',', '')
            try:
                return float(amount_str)
            except ValueError:
                pass
        return 0.0
    
    def _extract_cards(self, text: str) -> List[str]:
        """Extract card values using card classifier"""
        # First try new card classifier if we have an image
        if hasattr(self, '_last_cards_image') and self._last_cards_image is not None:
            detected_cards = self.card_classifier.detect_cards_in_region(self._last_cards_image)
            if detected_cards:
                cards = [str(card) for card, _ in detected_cards]
                logger.debug(f"Card classifier detected: {cards}")
                return cards
        
        # Fallback to text extraction
        cards = []
        pattern = r'([AKQJT2-9]|10)([hsdc])'
        matches = re.findall(pattern, text, re.IGNORECASE)
        
        for rank, suit in matches:
            suit_map = {'h': '♥', 's': '♠', 'd': '♦', 'c': '♣'}
            suit_lower = suit.lower()
            if suit_lower in suit_map:
                cards.append(f"{rank.upper()}{suit_map[suit_lower]}")
        
        return cards
    
    def _determine_street(self, community_cards: List[str]) -> str:
        """Determine current betting street based on community cards"""
        num_cards = len(community_cards)
        if num_cards == 0:
            return "preflop"
        elif num_cards == 3:
            return "flop"
        elif num_cards == 4:
            return "turn"
        elif num_cards == 5:
            return "river"
        else:
            return "unknown"
    
    def _seat_to_position(self, seat_num: int) -> str:
        """Convert seat number to position name for 6-max"""
        # This is a simplified mapping - adjust based on actual dealer position
        position_map = {
            1: "BTN",
            2: "SB", 
            3: "BB",
            4: "UTG",
            5: "MP",
            6: "CO"
        }
        return position_map.get(seat_num, f"SEAT{seat_num}")
    
    def detect_hero_name(self) -> Optional[str]:
        """Auto-detect hero name from bottom center position"""
        try:
            # Read player at hero seat (bottom center - seat 4)
            hero_position = self.seat_positions.get(self.hero_seat)
            if not hero_position:
                logger.warning("Hero seat position not configured")
                return None
            
            player_info = self._read_player_at_position(hero_position)
            
            if player_info and player_info.get('name'):
                self.hero_name = player_info['name']
                logger.info(f"Auto-detected hero name: {self.hero_name}")
                return self.hero_name
            else:
                logger.debug("Could not detect hero name from bottom position")
                return None
                
        except Exception as e:
            logger.error(f"Failed to detect hero name: {e}")
            return None
    
    def get_hero_name(self) -> str:
        """Get hero name, auto-detecting if necessary"""
        if not self.hero_name:
            self.detect_hero_name()
        return self.hero_name or "Hero"
    
    def detect_new_hand(self, current_state: TableState) -> bool:
        """Detect if a new hand has started"""
        if self.previous_state is None:
            return True
        
        # New hand if community cards cleared
        if len(self.previous_state.community_cards) > 0 and len(current_state.community_cards) == 0:
            return True
        
        # New hand if hero gets new cards
        if (self.previous_state.hero_cards != current_state.hero_cards and 
            len(current_state.hero_cards) == 2):
            return True
        
        return False
    
    def track_action(self, current_state: TableState):
        """Track actions during a hand"""
        if self.previous_state is None:
            self.previous_state = current_state
            return
        
        # Track any significant state changes
        changes_detected = False
        
        # Check for player action changes
        for position, player_info in current_state.players.items():
            prev_player = self.previous_state.players.get(position, {})
            
            if player_info.get('last_action') != prev_player.get('last_action'):
                action = {
                    'timestamp': datetime.now(),
                    'position': position,
                    'player': player_info.get('name'),
                    'action': player_info.get('last_action'),
                    'street': current_state.current_street,
                    'pot': current_state.pot_size
                }
                self.hand_actions.append(action)
                logger.debug(f"Action tracked: {player_info.get('name')} - {player_info.get('last_action')}")
                changes_detected = True
        
        # Track street changes
        if current_state.current_street != self.previous_state.current_street:
            logger.debug(f"Street changed: {self.previous_state.current_street} -> {current_state.current_street}")
            changes_detected = True
        
        # Track pot changes
        if abs(current_state.pot_size - self.previous_state.pot_size) > 0.01:
            logger.debug(f"Pot changed: ${self.previous_state.pot_size} -> ${current_state.pot_size}")
            changes_detected = True
        
        if changes_detected:
            logger.debug(f"Hand #{self.current_hand_id}: {len(self.hand_actions)} actions tracked")
        
        self.previous_state = current_state
    
    def create_hand_record(self) -> Optional[Dict]:
        """Create a hand record from tracked actions"""
        if not self.hand_actions:
            return None
        
        hand_record = {
            'hand_id': datetime.now().strftime('%Y%m%d_%H%M%S'),
            'site': self.site,
            'timestamp': datetime.now(),
            'hero_name': self.get_hero_name(),
            'actions': self.hand_actions,
            'hero_cards': self.previous_state.hero_cards if self.previous_state else [],
            'community_cards': self.previous_state.community_cards if self.previous_state else [],
            'pot_size': self.previous_state.pot_size if self.previous_state else 0
        }
        
        return hand_record
    
    def reset_hand_tracking(self):
        """Reset tracking for new hand"""
        self.hand_actions = []
        self.current_hand_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        logger.debug(f"Started tracking new hand: {self.current_hand_id}")
    
    def _save_full_table_screenshot(self):
        """Save a full table screenshot for debugging"""
        try:
            import cv2
            from pathlib import Path
            
            bounds = self.window_detector.get_window_bounds()
            if not bounds:
                return
                
            x, y, width, height = bounds
            
            # Capture full window
            region = CaptureRegion(x=x, y=y, width=width, height=height, name="full_table")
            image = self.screen_capture.capture_region(region)
            
            if image is not None:
                debug_dir = Path("debug_screenshots")
                debug_dir.mkdir(exist_ok=True)
                
                # Save full table
                cv2.imwrite(str(debug_dir / "full_table.png"), 
                           cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
                logger.info(f"Saved full table screenshot to debug_screenshots/full_table.png")
                
                # Also draw rectangles showing where we're looking for players
                overlay = image.copy()
                for seat_num, pos in self.seat_positions.items():
                    # Draw rectangle on overlay
                    cv2.rectangle(overlay,
                                (pos['x'] - x, pos['y'] - y),
                                (pos['x'] - x + pos['width'], pos['y'] - y + pos['height']),
                                (0, 255, 0), 2)
                    cv2.putText(overlay, f"Seat {seat_num}",
                              (pos['x'] - x, pos['y'] - y - 5),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                
                cv2.imwrite(str(debug_dir / "full_table_regions.png"), 
                           cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))
                logger.info("Saved table with region overlay to debug_screenshots/full_table_regions.png")
                
        except Exception as e:
            logger.error(f"Failed to save full table screenshot: {e}")