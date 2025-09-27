from typing import Dict, Type
from loguru import logger

from history.hand_parser import HandParser, PokerStarsParser
from history.betonline_parser import BetOnlineParser


class GGPokerParser(HandParser):
    """Parser for GGPoker hand histories"""
    
    def __init__(self):
        super().__init__("GGPoker")
    
    def _compile_patterns(self):
        import re
        return {
            'header': re.compile(r'Poker Hand #(\d+):\s+(.+) - ([\d/]+) ([\d:]+)'),
            'table': re.compile(r"Table '([^']+)'"),
            'player': re.compile(r'Seat (\d+): (.+) \(([\d.]+)\)'),
            'blinds': re.compile(r'(.+) posts (small|big) blind ([\d.]+)'),
            'hole_cards': re.compile(r'Dealt to (.+) \[([^\]]+)\]'),
            'action': re.compile(r'(.+): (folds|checks|calls|bets|raises to) ?([\d.]+)?')
        }
    
    def _parse_header(self, text, hand):
        # Simplified GGPoker parsing
        lines = text.split('\n')
        for line in lines:
            if 'Poker Hand #' in line:
                import re
                match = re.search(r'#(\d+)', line)
                if match:
                    hand.hand_number = match.group(1)
                    return True
        return False
    
    def _parse_players(self, text, hand):
        # Simplified player parsing
        import re
        for line in text.split('\n'):
            if 'Seat' in line and ':' in line:
                match = re.search(r'Seat (\d+): (.+) \(([\d.]+)\)', line)
                if match:
                    from history.hand_parser import PlayerInfo
                    player = PlayerInfo(
                        name=match.group(2),
                        seat=int(match.group(1)),
                        stack=float(match.group(3))
                    )
                    hand.players[player.name] = player
        return len(hand.players) > 0
    
    def _parse_actions(self, text, hand):
        # Simplified action parsing
        pass
    
    def _parse_board(self, text, hand):
        # Simplified board parsing
        pass
    
    def _parse_results(self, text, hand):
        # Simplified results parsing
        pass


class GenericParser(HandParser):
    """Generic parser for unknown formats"""
    
    def __init__(self):
        super().__init__("Generic")
    
    def _compile_patterns(self):
        import re
        return {
            'money': re.compile(r'[$€£]?([\d,]+\.?\d*)'),
            'cards': re.compile(r'[AKQJT2-9][schd]'),
            'action': re.compile(r'(fold|check|call|bet|raise)', re.IGNORECASE)
        }
    
    def _parse_header(self, text, hand):
        # Try to extract any hand number
        import re
        match = re.search(r'#(\d+)', text)
        if match:
            hand.hand_number = match.group(1)
        else:
            # Generate a unique ID from timestamp
            import hashlib
            hand.hand_number = hashlib.md5(text.encode()).hexdigest()[:12]
        return True
    
    def _parse_players(self, text, hand):
        # Try to find player patterns
        import re
        seat_pattern = re.compile(r'(?:Seat|Player)\s*(\d+)[:\s]+([^\n(]+)\s*\(?([0-9,.]+)?')
        
        for match in seat_pattern.finditer(text):
            from .hand_parser import PlayerInfo
            player = PlayerInfo(
                name=match.group(2).strip(),
                seat=int(match.group(1)),
                stack=float(match.group(3).replace(',', '')) if match.group(3) else 0
            )
            hand.players[player.name] = player
        
        return len(hand.players) > 0
    
    def _parse_actions(self, text, hand):
        pass
    
    def _parse_board(self, text, hand):
        pass
    
    def _parse_results(self, text, hand):
        pass


class ParserFactory:
    """Factory for creating appropriate hand parsers"""
    
    def __init__(self):
        self.parsers: Dict[str, Type[HandParser]] = {
            'pokerstars': PokerStarsParser,
            'ggpoker': GGPokerParser,
            'betonline': BetOnlineParser,
            'generic': GenericParser
        }
        logger.info(f"ParserFactory initialized with {len(self.parsers)} parsers")
    
    def get_parser(self, site: str) -> HandParser:
        """Get parser for a specific site"""
        site_lower = site.lower()
        
        # Try exact match
        if site_lower in self.parsers:
            return self.parsers[site_lower]()
        
        # Try partial match
        for key, parser_class in self.parsers.items():
            if key in site_lower or site_lower in key:
                logger.info(f"Using {key} parser for {site}")
                return parser_class()
        
        # Default to generic parser
        logger.warning(f"No specific parser for {site}, using generic parser")
        return self.parsers['generic']()
    
    def register_parser(self, site: str, parser_class: Type[HandParser]):
        """Register a new parser"""
        self.parsers[site.lower()] = parser_class
        logger.info(f"Registered parser for {site}")
    
    def list_supported_sites(self) -> list:
        """List all supported poker sites"""
        return list(self.parsers.keys())