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
        
        # Table regions - these need to be configured per site
        self.regions = {}
        self.setup_default_regions()
        
        # State tracking
        self.previous_state = None
        self.current_hand_id = None
        self.hand_actions = []
        
        logger.info(f"TableReader initialized for {site}")
    
    def setup_default_regions(self):
        """Setup default regions for BetOnline"""
        if self.site.lower() == "betonline":
            # These are approximate positions - need adjustment
            self.regions = {
                'pot': {'x': 400, 'y': 300, 'width': 200, 'height': 50},
                'community': {'x': 300, 'y': 350, 'width': 400, 'height': 100},
                'hero_cards': {'x': 400, 'y': 500, 'width': 150, 'height': 80},
                'action_buttons': {'x': 500, 'y': 550, 'width': 300, 'height': 100},
                'chat': {'x': 50, 'y': 450, 'width': 250, 'height': 200},
            }
            
            # Player seat positions for 6-max
            self.seat_positions = {
                1: {'x': 400, 'y': 150, 'width': 150, 'height': 100},  # Top center
                2: {'x': 600, 'y': 250, 'width': 150, 'height': 100},  # Right top
                3: {'x': 600, 'y': 400, 'width': 150, 'height': 100},  # Right bottom
                4: {'x': 400, 'y': 500, 'width': 150, 'height': 100},  # Bottom center (hero)
                5: {'x': 200, 'y': 400, 'width': 150, 'height': 100},  # Left bottom
                6: {'x': 200, 'y': 250, 'width': 150, 'height': 100},  # Left top
            }
    
    def read_table_state(self) -> Optional[TableState]:
        """Read current table state from screen"""
        try:
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