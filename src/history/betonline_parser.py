import re
from datetime import datetime
from typing import Optional, List, Dict, Any
from loguru import logger

from history.hand_parser import HandParser, ParsedHand, PlayerInfo, PlayerAction, ActionType, Street


class BetOnlineParser(HandParser):
    """Parser for BetOnline hand histories"""
    
    def __init__(self):
        super().__init__("BetOnline")
    
    def _compile_patterns(self) -> Dict[str, re.Pattern]:
        return {
            # BetOnline format patterns
            'header': re.compile(r'Hand #(\d+).*?(\d{4}[/-]\d{2}[/-]\d{2}\s+\d{2}:\d{2}:\d{2})'),
            'game_info': re.compile(r'Game:\s+(.+?)\s+-\s+Blinds\s+\$?([\d.]+)/\$?([\d.]+)'),
            'table': re.compile(r'Table:\s+(.+?)(?:\s+\((\d+)\s+max\))?'),
            'player': re.compile(r'Seat\s+(\d+):\s+(.+?)\s+\(\$?([\d,]+\.?\d*)\)'),
            'button': re.compile(r'Dealer:\s+Seat\s+(\d+)'),
            'blinds': re.compile(r'(.+?)\s+posted\s+(Small|Big|small|big)\s+Blind\s+\$?([\d.]+)'),
            'ante': re.compile(r'(.+?)\s+posted\s+ante\s+\$?([\d.]+)'),
            'hole_cards': re.compile(r'Dealt to\s+(.+?)\s+\[([^\]]+)\]'),
            'flop': re.compile(r'\*\*\*\s+FLOP\s+\*\*\*\s+\[([^\]]+)\]'),
            'turn': re.compile(r'\*\*\*\s+TURN\s+\*\*\*\s+\[[^\]]+\]\s+\[([^\]]+)\]'),
            'river': re.compile(r'\*\*\*\s+RIVER\s+\*\*\*\s+\[[^\]]+\]\s+\[([^\]]+)\]'),
            'action': re.compile(r'(.+?):\s+(folds?|checks?|calls?|bets?|raises?|all-in|shows?)\s*\$?([\d,]+\.?\d*)?'),
            'winner': re.compile(r'(.+?)\s+(?:wins?|won|collected)\s+\$?([\d,]+\.?\d*)'),
            'showdown': re.compile(r'(.+?)\s+shows?\s+\[([^\]]+)\]'),
            'pot': re.compile(r'Total\s+Pot\s*[:=]\s*\$?([\d,]+\.?\d*)'),
            'rake': re.compile(r'Rake\s*[:=]\s*\$?([\d,]+\.?\d*)')
        }
    
    def parse(self, hand_text: str) -> Optional[ParsedHand]:
        """Parse a BetOnline hand history"""
        try:
            # Clean up the text
            hand_text = hand_text.replace('\r\n', '\n').replace('\r', '\n')
            
            hand = ParsedHand(
                hand_number="",
                timestamp=datetime.now(),
                site=self.site,
                raw_text=hand_text
            )
            
            # Parse components
            if not self._parse_header(hand_text, hand):
                logger.warning("Failed to parse header")
                return None
            
            if not self._parse_players(hand_text, hand):
                logger.warning("Failed to parse players")
                return None
            
            self._parse_actions(hand_text, hand)
            self._parse_board(hand_text, hand)
            self._parse_results(hand_text, hand)
            
            return hand
            
        except Exception as e:
            logger.error(f"Failed to parse BetOnline hand: {e}")
            return None
    
    def _parse_header(self, text: str, hand: ParsedHand) -> bool:
        """Parse hand header for BetOnline format"""
        # Extract hand number
        hand_match = re.search(r'Hand\s+#(\d+)', text)
        if hand_match:
            hand.hand_number = hand_match.group(1)
        else:
            # Try alternative format
            hand_match = re.search(r'Game\s+Hand\s+#(\d+)', text)
            if hand_match:
                hand.hand_number = hand_match.group(1)
            else:
                logger.warning("Could not find hand number")
                return False
        
        # Extract timestamp
        time_patterns = [
            r'(\d{4}[/-]\d{2}[/-]\d{2}\s+\d{2}:\d{2}:\d{2})',
            r'(\d{2}[/-]\d{2}[/-]\d{4}\s+\d{2}:\d{2}:\d{2})',
            r'(\w+\s+\d+,\s+\d{4}\s+\d{1,2}:\d{2}:\d{2}\s+[AP]M)'
        ]
        
        for pattern in time_patterns:
            time_match = re.search(pattern, text)
            if time_match:
                try:
                    # Try different date formats
                    date_str = time_match.group(1)
                    for fmt in ['%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S', 
                               '%m/%d/%Y %H:%M:%S', '%m-%d-%Y %H:%M:%S']:
                        try:
                            hand.timestamp = datetime.strptime(date_str, fmt)
                            break
                        except:
                            continue
                except:
                    hand.timestamp = datetime.now()
                break
        
        # Extract game type and blinds
        game_match = self.patterns['game_info'].search(text)
        if game_match:
            game_type = game_match.group(1)
            if 'Hold' in game_type or 'Holdem' in game_type:
                hand.game_type = 'NLHE'
            elif 'Omaha' in game_type:
                hand.game_type = 'PLO'
            else:
                hand.game_type = game_type
            
            hand.small_blind = float(game_match.group(2))
            hand.big_blind = float(game_match.group(3))
        else:
            # Try alternative blind format
            blind_match = re.search(r'\$?([\d.]+)/\$?([\d.]+)', text)
            if blind_match:
                hand.small_blind = float(blind_match.group(1))
                hand.big_blind = float(blind_match.group(2))
        
        # Extract table name
        table_match = self.patterns['table'].search(text)
        if table_match:
            hand.table_name = table_match.group(1).strip()
            if table_match.group(2):
                hand.max_players = int(table_match.group(2))
            else:
                # Count seats to determine max players
                seat_count = len(re.findall(r'Seat\s+\d+:', text))
                hand.max_players = 9 if seat_count > 6 else 6
        
        # Find button/dealer
        button_match = self.patterns['button'].search(text)
        if button_match:
            hand.button_seat = int(button_match.group(1))
        else:
            # Try to find from dealer designation
            dealer_match = re.search(r'Seat\s+(\d+)\s+is\s+the\s+(?:button|dealer)', text)
            if dealer_match:
                hand.button_seat = int(dealer_match.group(1))
        
        return True
    
    def _parse_players(self, text: str, hand: ParsedHand) -> bool:
        """Parse player information for BetOnline"""
        # Find all players
        for match in self.patterns['player'].finditer(text):
            seat = int(match.group(1))
            name = match.group(2).strip()
            stack_str = match.group(3).replace(',', '')
            stack = float(stack_str)
            
            # Clean up name (remove [ME] or similar markers)
            name = re.sub(r'\s*\[.*?\]\s*', '', name)
            
            hand.players[name] = PlayerInfo(
                name=name,
                seat=seat,
                stack=stack
            )
        
        # Parse hole cards for hero
        hole_match = self.patterns['hole_cards'].search(text)
        if hole_match:
            player = hole_match.group(1).strip()
            cards = self._parse_cards(hole_match.group(2))
            if player in hand.players:
                hand.players[player].hole_cards = cards
        
        # Determine positions
        self._determine_positions(hand)
        
        return len(hand.players) > 0
    
    def _parse_actions(self, text: str, hand: ParsedHand):
        """Parse player actions for BetOnline"""
        pot = 0.0
        
        # Define street markers
        street_markers = {
            Street.PREFLOP: (r'(?:Dealt to|HOLE CARDS)', r'(?:\*\*\*\s+FLOP\s+\*\*\*|\*\*\*\s+SUMMARY\s+\*\*\*)'),
            Street.FLOP: (r'\*\*\*\s+FLOP\s+\*\*\*', r'(?:\*\*\*\s+TURN\s+\*\*\*|\*\*\*\s+SUMMARY\s+\*\*\*)'),
            Street.TURN: (r'\*\*\*\s+TURN\s+\*\*\*', r'(?:\*\*\*\s+RIVER\s+\*\*\*|\*\*\*\s+SUMMARY\s+\*\*\*)'),
            Street.RIVER: (r'\*\*\*\s+RIVER\s+\*\*\*', r'\*\*\*\s+SUMMARY\s+\*\*\*')
        }
        
        for street, (start_marker, end_marker) in street_markers.items():
            # Extract street text
            start_match = re.search(start_marker, text)
            end_match = re.search(end_marker, text)
            
            if not start_match:
                continue
            
            if end_match:
                street_text = text[start_match.end():end_match.start()]
            else:
                street_text = text[start_match.end():]
            
            # Parse blinds in preflop
            if street == Street.PREFLOP:
                for match in self.patterns['blinds'].finditer(street_text):
                    player = match.group(1).strip()
                    blind_type = match.group(2).lower()
                    amount = float(match.group(3))
                    
                    action = PlayerAction(
                        player=player,
                        action=ActionType.POST,
                        amount=amount,
                        street=Street.PREFLOP,
                        pot_before=pot
                    )
                    hand.actions.append(action)
                    pot += amount
                
                # Parse antes
                for match in self.patterns['ante'].finditer(street_text):
                    player = match.group(1).strip()
                    amount = float(match.group(2))
                    
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
            for line in street_text.split('\n'):
                action_match = self.patterns['action'].search(line)
                if action_match:
                    player = action_match.group(1).strip()
                    action_str = action_match.group(2).lower()
                    amount_str = action_match.group(3)
                    
                    # Map action strings to ActionType
                    action_map = {
                        'fold': ActionType.FOLD,
                        'folds': ActionType.FOLD,
                        'check': ActionType.CHECK,
                        'checks': ActionType.CHECK,
                        'call': ActionType.CALL,
                        'calls': ActionType.CALL,
                        'bet': ActionType.BET,
                        'bets': ActionType.BET,
                        'raise': ActionType.RAISE,
                        'raises': ActionType.RAISE,
                        'all-in': ActionType.ALL_IN,
                        'allin': ActionType.ALL_IN
                    }
                    
                    action_type = action_map.get(action_str, ActionType.FOLD)
                    amount = float(amount_str.replace(',', '')) if amount_str else 0.0
                    
                    action = PlayerAction(
                        player=player,
                        action=action_type,
                        amount=amount,
                        street=street,
                        pot_before=pot,
                        is_all_in='all' in action_str.lower()
                    )
                    hand.actions.append(action)
                    
                    if action_type in [ActionType.CALL, ActionType.BET, ActionType.RAISE]:
                        pot += amount
    
    def _parse_board(self, text: str, hand: ParsedHand):
        """Parse board cards for BetOnline"""
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
        """Parse hand results for BetOnline"""
        # Parse pot size
        pot_match = self.patterns['pot'].search(text)
        if pot_match:
            hand.pot_size = float(pot_match.group(1).replace(',', ''))
        
        # Parse rake
        rake_match = self.patterns['rake'].search(text)
        if rake_match:
            hand.rake = float(rake_match.group(1).replace(',', ''))
        
        # Parse winners
        for match in self.patterns['winner'].finditer(text):
            player = match.group(1).strip()
            amount = float(match.group(2).replace(',', ''))
            
            hand.winners.append(player)
            if player in hand.players:
                hand.players[player].winnings = amount
        
        # Parse showdown
        for match in self.patterns['showdown'].finditer(text):
            player = match.group(1).strip()
            cards = self._parse_cards(match.group(2))
            
            if player in hand.players:
                if not hand.players[player].hole_cards:
                    hand.players[player].hole_cards = cards
                hand.players[player].showed_cards = True