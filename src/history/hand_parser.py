import re
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger


class Street(Enum):
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    SHOWDOWN = "showdown"


class ActionType(Enum):
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"
    ALL_IN = "all-in"
    POST = "post"
    SHOW = "show"
    MUCK = "muck"


@dataclass
class PlayerAction:
    """Represents a single player action"""
    player: str
    action: ActionType
    amount: float = 0.0
    street: Street = Street.PREFLOP
    pot_before: float = 0.0
    is_all_in: bool = False


@dataclass
class PlayerInfo:
    """Information about a player in the hand"""
    name: str
    seat: int
    stack: float
    position: Optional[str] = None
    hole_cards: Optional[List[str]] = None
    winnings: float = 0.0
    showed_cards: bool = False


@dataclass
class ParsedHand:
    """Parsed hand data structure"""
    hand_number: str
    timestamp: datetime
    site: str
    game_type: str = "NLHE"
    
    # Table info
    table_name: str = ""
    max_players: int = 6
    
    # Stakes
    small_blind: float = 0.0
    big_blind: float = 0.0
    ante: float = 0.0
    
    # Players
    players: Dict[str, PlayerInfo] = field(default_factory=dict)
    button_seat: int = 0
    
    # Cards
    flop: Optional[List[str]] = None
    turn: Optional[str] = None
    river: Optional[str] = None
    
    # Actions
    actions: List[PlayerAction] = field(default_factory=list)
    
    # Results
    pot_size: float = 0.0
    rake: float = 0.0
    winners: List[str] = field(default_factory=list)
    
    # Raw text
    raw_text: str = ""
    
    def get_actions_by_street(self, street: Street) -> List[PlayerAction]:
        """Get all actions for a specific street"""
        return [a for a in self.actions if a.street == street]
    
    def get_player_actions(self, player: str) -> List[PlayerAction]:
        """Get all actions by a specific player"""
        return [a for a in self.actions if a.player == player]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage"""
        return {
            'hand_number': self.hand_number,
            'timestamp': self.timestamp.isoformat(),
            'site': self.site,
            'game_type': self.game_type,
            'table_name': self.table_name,
            'max_players': self.max_players,
            'small_blind': self.small_blind,
            'big_blind': self.big_blind,
            'ante': self.ante,
            'players': {name: {
                'seat': p.seat,
                'stack': p.stack,
                'position': p.position,
                'hole_cards': p.hole_cards,
                'winnings': p.winnings
            } for name, p in self.players.items()},
            'button_seat': self.button_seat,
            'flop': self.flop,
            'turn': self.turn,
            'river': self.river,
            'pot_size': self.pot_size,
            'rake': self.rake,
            'winners': self.winners,
            'actions': [{
                'player': a.player,
                'action': a.action.value,
                'amount': a.amount,
                'street': a.street.value,
                'pot_before': a.pot_before,
                'is_all_in': a.is_all_in
            } for a in self.actions]
        }


class HandParser:
    """Base class for hand history parsers"""
    
    def __init__(self, site: str):
        self.site = site
        self.patterns = self._compile_patterns()
        logger.info(f"HandParser initialized for {site}")
    
    def _compile_patterns(self) -> Dict[str, re.Pattern]:
        """Compile regex patterns for parsing - override in subclasses"""
        return {}
    
    def parse(self, hand_text: str) -> Optional[ParsedHand]:
        """Parse a hand history text"""
        try:
            hand = ParsedHand(
                hand_number="",
                timestamp=datetime.now(),
                site=self.site,
                raw_text=hand_text
            )
            
            # Parse hand header
            if not self._parse_header(hand_text, hand):
                return None
            
            # Parse players
            if not self._parse_players(hand_text, hand):
                return None
            
            # Parse actions
            self._parse_actions(hand_text, hand)
            
            # Parse board
            self._parse_board(hand_text, hand)
            
            # Parse results
            self._parse_results(hand_text, hand)
            
            return hand
            
        except Exception as e:
            logger.error(f"Failed to parse hand: {e}")
            return None
    
    def _parse_header(self, text: str, hand: ParsedHand) -> bool:
        """Parse hand header information"""
        raise NotImplementedError("Subclasses must implement _parse_header")
    
    def _parse_players(self, text: str, hand: ParsedHand) -> bool:
        """Parse player information"""
        raise NotImplementedError("Subclasses must implement _parse_players")
    
    def _parse_actions(self, text: str, hand: ParsedHand):
        """Parse player actions"""
        raise NotImplementedError("Subclasses must implement _parse_actions")
    
    def _parse_board(self, text: str, hand: ParsedHand):
        """Parse board cards"""
        raise NotImplementedError("Subclasses must implement _parse_board")
    
    def _parse_results(self, text: str, hand: ParsedHand):
        """Parse hand results"""
        raise NotImplementedError("Subclasses must implement _parse_results")
    
    def _parse_cards(self, cards_str: str) -> List[str]:
        """Parse card string into list of cards"""
        # Match patterns like "Ah Kd" or "AhKd"
        cards = re.findall(r'[AKQJT2-9][schd]', cards_str)
        return cards
    
    def _parse_amount(self, amount_str: str) -> float:
        """Parse money amount from string"""
        # Remove currency symbols and convert to float
        cleaned = re.sub(r'[$€£,]', '', amount_str)
        try:
            return float(cleaned)
        except ValueError:
            return 0.0
    
    def _determine_positions(self, hand: ParsedHand):
        """Determine player positions based on button"""
        seats = sorted([(p.seat, name) for name, p in hand.players.items()])
        num_players = len(seats)
        
        if num_players == 0:
            return
        
        # Find button index
        button_idx = next((i for i, (seat, _) in enumerate(seats) if seat == hand.button_seat), 0)
        
        # 6-max positions
        if num_players <= 6:
            positions_6max = ["BTN", "SB", "BB", "UTG", "MP", "CO"]
            for i, (_, name) in enumerate(seats):
                pos_idx = (i - button_idx) % num_players
                if pos_idx < len(positions_6max):
                    hand.players[name].position = positions_6max[pos_idx]
        
        # 9-max positions
        else:
            positions_9max = ["BTN", "SB", "BB", "UTG", "UTG+1", "MP", "MP+1", "CO", "HJ"]
            for i, (_, name) in enumerate(seats):
                pos_idx = (i - button_idx) % num_players
                if pos_idx < len(positions_9max):
                    hand.players[name].position = positions_9max[pos_idx]


class PokerStarsParser(HandParser):
    """Parser for PokerStars hand histories"""
    
    def __init__(self):
        super().__init__("PokerStars")
    
    def _compile_patterns(self) -> Dict[str, re.Pattern]:
        return {
            'header': re.compile(r'PokerStars Hand #(\d+):\s+(.+) - ([\d/]+) ([\d:]+)'),
            'table': re.compile(r"Table '([^']+)' (\d+)-max Seat #(\d+)"),
            'player': re.compile(r'Seat (\d+): (.+) \([$€£]?([\d.]+) in chips\)'),
            'blinds': re.compile(r'(.+): posts (small|big) blind [$€£]?([\d.]+)'),
            'hole_cards': re.compile(r'Dealt to (.+) \[([^\]]+)\]'),
            'flop': re.compile(r'\*\*\* FLOP \*\*\* \[([^\]]+)\]'),
            'turn': re.compile(r'\*\*\* TURN \*\*\* \[[^\]]+\] \[([^\]]+)\]'),
            'river': re.compile(r'\*\*\* RIVER \*\*\* \[[^\]]+\] \[([^\]]+)\]'),
            'action': re.compile(r'(.+): (folds|checks|calls|bets|raises) [$€£]?([\d.]+)?'),
            'winner': re.compile(r'(.+) collected [$€£]?([\d.]+) from pot'),
            'showdown': re.compile(r'(.+): shows \[([^\]]+)\]')
        }
    
    def _parse_header(self, text: str, hand: ParsedHand) -> bool:
        match = self.patterns['header'].search(text)
        if not match:
            return False
        
        hand.hand_number = match.group(1)
        game_info = match.group(2)
        
        # Parse stakes from game info
        stakes_match = re.search(r'[$€£]?([\d.]+)/[$€£]?([\d.]+)', game_info)
        if stakes_match:
            hand.small_blind = float(stakes_match.group(1))
            hand.big_blind = float(stakes_match.group(2))
        
        # Parse timestamp
        date_str = match.group(3)
        time_str = match.group(4)
        hand.timestamp = datetime.strptime(f"{date_str} {time_str}", "%Y/%m/%d %H:%M:%S")
        
        # Parse table info
        table_match = self.patterns['table'].search(text)
        if table_match:
            hand.table_name = table_match.group(1)
            hand.max_players = int(table_match.group(2))
            hand.button_seat = int(table_match.group(3))
        
        return True
    
    def _parse_players(self, text: str, hand: ParsedHand) -> bool:
        for match in self.patterns['player'].finditer(text):
            seat = int(match.group(1))
            name = match.group(2)
            stack = float(match.group(3))
            
            hand.players[name] = PlayerInfo(
                name=name,
                seat=seat,
                stack=stack
            )
        
        # Parse hole cards
        hole_match = self.patterns['hole_cards'].search(text)
        if hole_match:
            player = hole_match.group(1)
            cards = self._parse_cards(hole_match.group(2))
            if player in hand.players:
                hand.players[player].hole_cards = cards
        
        # Determine positions
        self._determine_positions(hand)
        
        return len(hand.players) > 0
    
    def _parse_actions(self, text: str, hand: ParsedHand):
        current_street = Street.PREFLOP
        pot = 0.0
        
        # Split text into streets
        streets_text = {
            Street.PREFLOP: text.split('*** FLOP ***')[0] if '*** FLOP ***' in text else text,
            Street.FLOP: text.split('*** FLOP ***')[1].split('*** TURN ***')[0] if '*** FLOP ***' in text else "",
            Street.TURN: text.split('*** TURN ***')[1].split('*** RIVER ***')[0] if '*** TURN ***' in text else "",
            Street.RIVER: text.split('*** RIVER ***')[1].split('*** SUMMARY ***')[0] if '*** RIVER ***' in text else ""
        }
        
        for street, street_text in streets_text.items():
            if not street_text:
                continue
            
            for line in street_text.split('\n'):
                # Parse blinds
                blind_match = self.patterns['blinds'].search(line)
                if blind_match:
                    player = blind_match.group(1)
                    blind_type = blind_match.group(2)
                    amount = float(blind_match.group(3))
                    
                    action = PlayerAction(
                        player=player,
                        action=ActionType.POST,
                        amount=amount,
                        street=Street.PREFLOP,
                        pot_before=pot
                    )
                    hand.actions.append(action)
                    pot += amount
                
                # Parse regular actions
                action_match = self.patterns['action'].search(line)
                if action_match:
                    player = action_match.group(1)
                    action_str = action_match.group(2).lower()
                    amount_str = action_match.group(3)
                    
                    action_type = {
                        'folds': ActionType.FOLD,
                        'checks': ActionType.CHECK,
                        'calls': ActionType.CALL,
                        'bets': ActionType.BET,
                        'raises': ActionType.RAISE
                    }.get(action_str, ActionType.FOLD)
                    
                    amount = float(amount_str) if amount_str else 0.0
                    
                    action = PlayerAction(
                        player=player,
                        action=action_type,
                        amount=amount,
                        street=street,
                        pot_before=pot,
                        is_all_in='all-in' in line.lower()
                    )
                    hand.actions.append(action)
                    
                    if action_type in [ActionType.CALL, ActionType.BET, ActionType.RAISE]:
                        pot += amount
    
    def _parse_board(self, text: str, hand: ParsedHand):
        # Parse flop
        flop_match = self.patterns['flop'].search(text)
        if flop_match:
            hand.flop = self._parse_cards(flop_match.group(1))
        
        # Parse turn
        turn_match = self.patterns['turn'].search(text)
        if turn_match:
            hand.turn = turn_match.group(1).strip()
        
        # Parse river
        river_match = self.patterns['river'].search(text)
        if river_match:
            hand.river = river_match.group(1).strip()
    
    def _parse_results(self, text: str, hand: ParsedHand):
        # Parse winners
        for match in self.patterns['winner'].finditer(text):
            player = match.group(1)
            amount = float(match.group(2))
            
            hand.winners.append(player)
            if player in hand.players:
                hand.players[player].winnings = amount
            
            hand.pot_size += amount
        
        # Parse showdown
        for match in self.patterns['showdown'].finditer(text):
            player = match.group(1)
            cards = self._parse_cards(match.group(2))
            
            if player in hand.players:
                hand.players[player].hole_cards = cards
                hand.players[player].showed_cards = True