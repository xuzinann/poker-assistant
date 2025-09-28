"""
Finite State Machine for hand reconstruction
"""
from enum import Enum
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import json
from loguru import logger


class HandState(Enum):
    """Poker hand states"""
    WAITING = "waiting"         # Waiting for new hand
    PREFLOP = "preflop"         # Hole cards dealt
    FLOP = "flop"              # 3 community cards
    TURN = "turn"              # 4th community card
    RIVER = "river"            # 5th community card
    SHOWDOWN = "showdown"      # Cards revealed
    COMPLETED = "completed"     # Hand finished


class ActionType(Enum):
    """Player action types"""
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"
    ALL_IN = "all_in"


@dataclass
class PlayerAction:
    """Single player action"""
    player_name: str
    action_type: ActionType
    amount: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class HandData:
    """Complete hand data"""
    hand_id: str
    timestamp: datetime
    state: HandState
    players: List[str]
    hero_name: str
    hero_cards: List[str]
    community_cards: List[str]
    pot_size: float
    actions: List[PlayerAction]
    winner: Optional[str] = None
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        data = {
            'hand_id': self.hand_id,
            'timestamp': self.timestamp.isoformat(),
            'state': self.state.value,
            'players': self.players,
            'hero_name': self.hero_name,
            'hero_cards': self.hero_cards,
            'community_cards': self.community_cards,
            'pot_size': self.pot_size,
            'actions': [
                {
                    'player': a.player_name,
                    'action': a.action_type.value,
                    'amount': a.amount,
                    'timestamp': a.timestamp.isoformat()
                }
                for a in self.actions
            ],
            'winner': self.winner
        }
        return json.dumps(data, indent=2)


class HandStateMachine:
    """FSM for reconstructing poker hands from observations"""
    
    def __init__(self, hero_name: str = "Hero"):
        """
        Initialize FSM
        
        Args:
            hero_name: Name of the hero player
        """
        self.hero_name = hero_name
        self.current_state = HandState.WAITING
        self.current_hand = None
        self.hand_history = []
        
        # State tracking
        self.last_community_cards = []
        self.last_pot_size = 0.0
        self.hand_counter = 0
        
        logger.info("Hand FSM initialized")
    
    def update(self, observation: Dict[str, Any]) -> Optional[HandData]:
        """
        Update FSM with new observation
        
        Args:
            observation: Dict containing:
                - players: List of player names
                - hero_cards: Hero's hole cards
                - community_cards: Community cards
                - pot_size: Current pot
                - actions: Recent actions
                
        Returns:
            Completed HandData if hand finished, None otherwise
        """
        players = observation.get('players', [])
        hero_cards = observation.get('hero_cards', [])
        community_cards = observation.get('community_cards', [])
        pot_size = observation.get('pot_size', 0.0)
        actions = observation.get('actions', [])
        
        # Detect state transitions
        new_state = self._determine_state(hero_cards, community_cards)
        
        # Handle state transitions
        if new_state != self.current_state:
            logger.debug(f"State transition: {self.current_state.value} -> {new_state.value}")
            
            # Check if starting new hand
            if self.current_state != HandState.WAITING and new_state == HandState.PREFLOP:
                # Complete previous hand
                completed = self._complete_hand()
                # Start new hand
                self._start_new_hand(players, hero_cards)
                self.current_state = new_state
                return completed
                
            elif self.current_state == HandState.WAITING and new_state == HandState.PREFLOP:
                # Start first hand
                self._start_new_hand(players, hero_cards)
                
            self.current_state = new_state
        
        # Update current hand
        if self.current_hand:
            self._update_hand(observation)
        
        # Check if hand completed
        if self._is_hand_complete(observation):
            return self._complete_hand()
            
        return None
    
    def _determine_state(self, hero_cards: List[str], community_cards: List[str]) -> HandState:
        """
        Determine current hand state from cards
        
        Args:
            hero_cards: Hero's hole cards
            community_cards: Community cards
            
        Returns:
            Current HandState
        """
        num_community = len(community_cards)
        
        if len(hero_cards) == 0:
            return HandState.WAITING
        elif num_community == 0:
            return HandState.PREFLOP
        elif num_community == 3:
            return HandState.FLOP
        elif num_community == 4:
            return HandState.TURN
        elif num_community == 5:
            return HandState.RIVER
        else:
            return self.current_state  # Keep current if unclear
    
    def _start_new_hand(self, players: List[str], hero_cards: List[str]):
        """
        Start tracking a new hand
        
        Args:
            players: List of players
            hero_cards: Hero's hole cards
        """
        self.hand_counter += 1
        hand_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.hand_counter}"
        
        self.current_hand = HandData(
            hand_id=hand_id,
            timestamp=datetime.now(),
            state=HandState.PREFLOP,
            players=players.copy(),
            hero_name=self.hero_name,
            hero_cards=hero_cards.copy(),
            community_cards=[],
            pot_size=0.0,
            actions=[]
        )
        
        logger.info(f"Started new hand: {hand_id}")
    
    def _update_hand(self, observation: Dict[str, Any]):
        """
        Update current hand with new observation
        
        Args:
            observation: New observation data
        """
        if not self.current_hand:
            return
        
        # Update community cards
        community = observation.get('community_cards', [])
        if len(community) > len(self.current_hand.community_cards):
            self.current_hand.community_cards = community.copy()
            self.current_hand.state = self._determine_state(
                self.current_hand.hero_cards, community
            )
        
        # Update pot
        pot = observation.get('pot_size', 0.0)
        if pot > self.current_hand.pot_size:
            self.current_hand.pot_size = pot
        
        # Add new actions
        for action_data in observation.get('actions', []):
            if isinstance(action_data, dict):
                action = self._parse_action(action_data)
                if action and not self._is_duplicate_action(action):
                    self.current_hand.actions.append(action)
    
    def _parse_action(self, action_data: Dict[str, Any]) -> Optional[PlayerAction]:
        """
        Parse action from observation
        
        Args:
            action_data: Action dictionary
            
        Returns:
            PlayerAction or None
        """
        try:
            player = action_data.get('player')
            action_str = action_data.get('action', '').lower()
            amount = float(action_data.get('amount', 0))
            
            if not player or not action_str:
                return None
            
            # Map action string to ActionType
            action_map = {
                'fold': ActionType.FOLD,
                'check': ActionType.CHECK,
                'call': ActionType.CALL,
                'bet': ActionType.BET,
                'raise': ActionType.RAISE,
                'all-in': ActionType.ALL_IN,
                'all in': ActionType.ALL_IN
            }
            
            action_type = action_map.get(action_str)
            if not action_type:
                # Try to find partial match
                for key, val in action_map.items():
                    if key in action_str:
                        action_type = val
                        break
            
            if action_type:
                return PlayerAction(
                    player_name=player,
                    action_type=action_type,
                    amount=amount
                )
                
        except Exception as e:
            logger.error(f"Failed to parse action: {e}")
            
        return None
    
    def _is_duplicate_action(self, action: PlayerAction) -> bool:
        """
        Check if action is duplicate
        
        Args:
            action: Action to check
            
        Returns:
            True if duplicate
        """
        if not self.current_hand:
            return False
            
        # Check last few actions for duplicates
        recent_actions = self.current_hand.actions[-5:]
        for recent in recent_actions:
            if (recent.player_name == action.player_name and
                recent.action_type == action.action_type and
                abs(recent.amount - action.amount) < 0.01):
                # Same action from same player with same amount
                time_diff = (action.timestamp - recent.timestamp).total_seconds()
                if time_diff < 2:  # Within 2 seconds = likely duplicate
                    return True
                    
        return False
    
    def _is_hand_complete(self, observation: Dict[str, Any]) -> bool:
        """
        Check if hand is complete
        
        Args:
            observation: Current observation
            
        Returns:
            True if hand complete
        """
        # Hand complete if:
        # 1. Hero cards disappeared (new hand starting)
        hero_cards = observation.get('hero_cards', [])
        if self.current_hand and len(self.current_hand.hero_cards) > 0 and len(hero_cards) == 0:
            return True
        
        # 2. Community cards reset
        community = observation.get('community_cards', [])
        if len(self.last_community_cards) > len(community) and len(community) == 0:
            return True
        
        # 3. Pot reset to small amount (new hand)
        pot = observation.get('pot_size', 0.0)
        if self.last_pot_size > 10 and pot < 5:
            return True
        
        # Update tracking
        self.last_community_cards = community
        self.last_pot_size = pot
        
        return False
    
    def _complete_hand(self) -> Optional[HandData]:
        """
        Complete current hand
        
        Returns:
            Completed HandData or None
        """
        if not self.current_hand:
            return None
        
        self.current_hand.state = HandState.COMPLETED
        completed = self.current_hand
        
        # Add to history
        self.hand_history.append(completed)
        
        # Save to file
        self._save_hand(completed)
        
        logger.info(f"Completed hand: {completed.hand_id} with {len(completed.actions)} actions")
        
        # Reset for next hand
        self.current_hand = None
        self.current_state = HandState.WAITING
        
        return completed
    
    def _save_hand(self, hand: HandData):
        """
        Save hand to file
        
        Args:
            hand: Hand to save
        """
        try:
            from pathlib import Path
            
            # Create hands directory
            hands_dir = Path("data/hands")
            hands_dir.mkdir(parents=True, exist_ok=True)
            
            # Save as JSON
            filename = hands_dir / f"{hand.hand_id}.json"
            with open(filename, 'w') as f:
                f.write(hand.to_json())
                
            logger.debug(f"Saved hand to {filename}")
            
        except Exception as e:
            logger.error(f"Failed to save hand: {e}")
    
    def get_current_state(self) -> HandState:
        """Get current FSM state"""
        return self.current_state
    
    def get_current_hand(self) -> Optional[HandData]:
        """Get current hand data"""
        return self.current_hand
    
    def get_hand_history(self) -> List[HandData]:
        """Get all completed hands"""
        return self.hand_history.copy()
    
    def reset(self):
        """Reset FSM to initial state"""
        self.current_state = HandState.WAITING
        self.current_hand = None
        self.last_community_cards = []
        self.last_pot_size = 0.0
        logger.info("Hand FSM reset")