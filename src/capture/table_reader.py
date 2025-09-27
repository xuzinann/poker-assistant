"""
Table reader for extracting game information directly from the poker table screen
"""
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import numpy as np
from loguru import logger

from capture.screen_capture import ScreenCapture
from capture.ocr_engine import OCREngine
from capture.window_detector import WindowDetector


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
        
        logger.info(f"TableReader initialized for {site}")
    
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
        
        # Player seat positions as percentages (for 6-max)
        # These work for most table layouts
        self.seat_positions = {
            1: {  # Top center
                'x': x + int(width * 0.42),
                'y': y + int(height * 0.15),
                'width': int(width * 0.16),
                'height': int(height * 0.12)
            },
            2: {  # Right top
                'x': x + int(width * 0.70),
                'y': y + int(height * 0.25),
                'width': int(width * 0.16),
                'height': int(height * 0.12)
            },
            3: {  # Right bottom
                'x': x + int(width * 0.70),
                'y': y + int(height * 0.55),
                'width': int(width * 0.16),
                'height': int(height * 0.12)
            },
            4: {  # Bottom center (HERO)
                'x': x + int(width * 0.42),
                'y': y + int(height * 0.78),
                'width': int(width * 0.16),
                'height': int(height * 0.12)
            },
            5: {  # Left bottom
                'x': x + int(width * 0.14),
                'y': y + int(height * 0.55),
                'width': int(width * 0.16),
                'height': int(height * 0.12)
            },
            6: {  # Left top
                'x': x + int(width * 0.14),
                'y': y + int(height * 0.25),
                'width': int(width * 0.16),
                'height': int(height * 0.12)
            }
        }
        
        logger.debug(f"Updated regions for window at ({x},{y}) size ({width}x{height})")
        return True
    
    def read_table_state(self) -> Optional[TableState]:
        """Read current table state from screen"""
        try:
            # Update regions if window has moved or resized
            self.window_detector.update_window_position()
            if not self.regions or self.window_detector.get_window_bounds() != self.current_window_bounds:
                if not self.update_regions():
                    return None
            
            state = TableState()
            
            # Read pot size
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
            
            return state
            
        except Exception as e:
            logger.error(f"Failed to read table state: {e}")
            return None
    
    def _read_region(self, region_name: str) -> Optional[str]:
        """Read text from a specific region"""
        if region_name not in self.regions:
            return None
        
        region = self.regions[region_name]
        image = self.screen_capture.capture_region(
            region['x'], region['y'], 
            region['width'], region['height']
        )
        
        if image is not None:
            result = self.ocr.extract_text(image)
            if result and result.confidence > 0.5:
                return result.text
        
        return None
    
    def _read_all_players(self) -> Dict[str, Dict]:
        """Read information for all players"""
        players = {}
        
        for seat_num, position in self.seat_positions.items():
            player_info = self._read_player_at_position(position)
            if player_info and player_info.get('name'):
                # Map seat number to position name
                pos_name = self._seat_to_position(seat_num)
                players[pos_name] = player_info
        
        return players
    
    def _read_player_at_position(self, position: Dict) -> Optional[Dict]:
        """Read player information at specific position"""
        image = self.screen_capture.capture_region(
            position['x'], position['y'],
            position['width'], position['height']
        )
        
        if image is None:
            return None
        
        text = self.ocr.extract_text(image)
        if not text or text.confidence < 0.5:
            return None
        
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
        """Extract card values from text"""
        cards = []
        
        # Card patterns: Ah, KS, 10c, etc.
        pattern = r'([AKQJT2-9]|10)([hsdc])'
        matches = re.findall(pattern, text, re.IGNORECASE)
        
        for rank, suit in matches:
            # Normalize suit
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
                logger.debug(f"Action tracked: {action}")
        
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