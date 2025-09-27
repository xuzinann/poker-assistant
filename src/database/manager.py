import os
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from contextlib import contextmanager
from sqlalchemy import create_engine, func, and_, or_
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from loguru import logger

from database.models import Base, Player, PlayerStats, Hand, HandAction, Session as PokerSession


class DatabaseManager:
    def __init__(self, db_path: str = "data/poker.db"):
        """Initialize database connection and create tables"""
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        self.engine = create_engine(f'sqlite:///{db_path}', echo=False)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        logger.info(f"Database initialized at {db_path}")
    
    @contextmanager
    def get_session(self):
        """Context manager for database sessions"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            session.close()
    
    # Player Management
    def get_or_create_player(self, username: str, site: str, is_hero: bool = False) -> Player:
        """Get existing player or create new one"""
        session = self.SessionLocal()
        try:
            player = session.query(Player).filter_by(
                username=username, site=site
            ).first()
            
            if not player:
                player = Player(
                    username=username,
                    site=site,
                    is_hero=is_hero
                )
                session.add(player)
                
                # Create initial stats
                stats = PlayerStats(player=player)
                session.add(stats)
                session.commit()
                session.refresh(player)
                logger.info(f"Created new player: {username} on {site}")
            else:
                player.last_seen = datetime.utcnow()
                session.commit()
                session.refresh(player)
            
            # Create a detached copy with the needed attributes
            player_dict = {
                'id': player.id,
                'username': player.username,
                'site': player.site,
                'is_hero': player.is_hero
            }
            session.close()
            
            # Return a new instance with the data
            result = Player(**player_dict)
            result.id = player_dict['id']
            return result
        except Exception as e:
            session.rollback()
            session.close()
            raise e
    
    def update_player_stats(self, player_id: int, stats_update: Dict[str, Any]):
        """Update player statistics"""
        with self.get_session() as session:
            stats = session.query(PlayerStats).filter_by(player_id=player_id).first()
            
            if not stats:
                stats = PlayerStats(player_id=player_id)
                session.add(stats)
            
            # Update stats
            for key, value in stats_update.items():
                if hasattr(stats, key):
                    setattr(stats, key, value)
            
            # Update confidence
            stats.confidence_level = stats.calculate_confidence()
            stats.last_updated = datetime.utcnow()
            
            session.commit()
            logger.debug(f"Updated stats for player_id={player_id}")
    
    def get_player_stats(self, username: str, site: str) -> Optional[Dict[str, Any]]:
        """Get player statistics"""
        with self.get_session() as session:
            player = session.query(Player).filter_by(
                username=username, site=site
            ).first()
            
            if player:
                stats = session.query(PlayerStats).filter_by(
                    player_id=player.id
                ).first()
                if stats:
                    # Return a dictionary instead of the ORM object
                    return {
                        'vpip': stats.vpip,
                        'pfr': stats.pfr,
                        'three_bet': stats.three_bet,
                        'hands_played': stats.hands_played,
                        'confidence_level': stats.calculate_confidence()
                    }
            return None
    
    # Hand Management
    def save_hand(self, hand_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save a new hand to database"""
        with self.get_session() as session:
            # Check if hand already exists
            existing = session.query(Hand).filter_by(
                hand_number=hand_data['hand_number']
            ).first()
            
            if existing:
                logger.warning(f"Hand {hand_data['hand_number']} already exists")
                return {'id': existing.id, 'hand_number': existing.hand_number}
            
            # Create hand
            hand = Hand(
                hand_number=hand_data['hand_number'],
                site=hand_data['site'],
                timestamp=hand_data['timestamp'],
                table_name=hand_data.get('table_name'),
                small_blind=hand_data.get('small_blind'),
                big_blind=hand_data.get('big_blind'),
                ante=hand_data.get('ante', 0),
                player_count=hand_data.get('player_count'),
                max_players=hand_data.get('max_players'),
                game_type=hand_data.get('game_type', 'NLHE'),
                raw_history=hand_data.get('raw_history'),
                parsed_data=hand_data.get('parsed_data'),
                flop=hand_data.get('flop'),
                turn=hand_data.get('turn'),
                river=hand_data.get('river'),
                pot_size=hand_data.get('pot_size'),
                rake=hand_data.get('rake'),
                winner_ids=hand_data.get('winner_ids', [])
            )
            session.add(hand)
            session.commit()
            
            logger.info(f"Saved hand #{hand_data['hand_number']}")
            return {'id': hand.id, 'hand_number': hand.hand_number}
    
    def save_hand_actions(self, hand_id: int, actions: List[Dict[str, Any]]):
        """Save hand actions"""
        with self.get_session() as session:
            for action_data in actions:
                # Get or create player
                player = self.get_or_create_player(
                    action_data['username'],
                    action_data['site']
                )
                
                action = HandAction(
                    hand_id=hand_id,
                    player_id=player.id,
                    position=action_data.get('position'),
                    hole_cards=action_data.get('hole_cards'),
                    street=action_data['street'],
                    action_number=action_data.get('action_number'),
                    action_type=action_data['action_type'],
                    amount=action_data.get('amount', 0),
                    pot_size_before=action_data.get('pot_size_before'),
                    stack_before=action_data.get('stack_before'),
                    stack_after=action_data.get('stack_after')
                )
                session.add(action)
            
            session.commit()
            logger.debug(f"Saved {len(actions)} actions for hand_id={hand_id}")
    
    def get_recent_hands(self, limit: int = 100, player_id: Optional[int] = None) -> List[Hand]:
        """Get recent hands, optionally filtered by player"""
        with self.get_session() as session:
            query = session.query(Hand).order_by(Hand.timestamp.desc())
            
            if player_id:
                query = query.join(HandAction).filter(
                    HandAction.player_id == player_id
                )
            
            return query.limit(limit).all()
    
    # Session Management
    def create_session(self, site: str, hero_username: str) -> PokerSession:
        """Create a new poker session"""
        with self.get_session() as session:
            hero = self.get_or_create_player(hero_username, site, is_hero=True)
            
            poker_session = PokerSession(
                start_time=datetime.utcnow(),
                site=site,
                hero_id=hero.id
            )
            session.add(poker_session)
            session.commit()
            
            logger.info(f"Started new session for {hero_username} on {site}")
            return poker_session
    
    def end_session(self, session_id: int):
        """End a poker session and calculate results"""
        with self.get_session() as session:
            poker_session = session.query(PokerSession).get(session_id)
            
            if poker_session:
                poker_session.end_time = datetime.utcnow()
                
                # Calculate session statistics
                hands = session.query(Hand).filter_by(session_id=session_id).all()
                poker_session.hands_played = len(hands)
                
                # Calculate profit/loss and winrate
                poker_session.calculate_winrate()
                
                session.commit()
                logger.info(f"Ended session {session_id}")
    
    # Statistics Calculations
    def calculate_player_stats_from_hands(self, player_id: int):
        """Recalculate player statistics from hand history"""
        with self.get_session() as session:
            # Get all actions for this player
            actions = session.query(HandAction).filter_by(player_id=player_id).all()
            
            if not actions:
                return
            
            # Initialize counters
            total_hands = len(set(a.hand_id for a in actions))
            vpip_hands = 0
            pfr_hands = 0
            three_bet_hands = 0
            three_bet_opportunities = 0
            
            # Group actions by hand
            hands_actions = {}
            for action in actions:
                if action.hand_id not in hands_actions:
                    hands_actions[action.hand_id] = []
                hands_actions[action.hand_id].append(action)
            
            # Analyze each hand
            for hand_id, hand_actions in hands_actions.items():
                preflop_actions = [a for a in hand_actions if a.street == 'preflop']
                
                # VPIP: Voluntarily put money in pot (call, bet, raise preflop)
                if any(a.action_type in ['call', 'bet', 'raise'] for a in preflop_actions):
                    vpip_hands += 1
                
                # PFR: Preflop raise
                if any(a.action_type in ['bet', 'raise'] for a in preflop_actions):
                    pfr_hands += 1
                
                # 3-bet detection (simplified)
                if any(a.action_type == 'raise' and a.action_number and a.action_number > 2 for a in preflop_actions):
                    three_bet_hands += 1
            
            # Update stats
            stats_update = {
                'hands_played': total_hands,
                'vpip': (vpip_hands / total_hands * 100) if total_hands > 0 else 0,
                'pfr': (pfr_hands / total_hands * 100) if total_hands > 0 else 0,
                'three_bet': (three_bet_hands / three_bet_opportunities * 100) if three_bet_opportunities > 0 else 0,
                'hands_vpip': vpip_hands,
                'hands_pfr': pfr_hands,
                'hands_3bet': three_bet_hands
            }
            
            self.update_player_stats(player_id, stats_update)
            logger.info(f"Recalculated stats for player_id={player_id}")
    
    # Search and Query Methods
    def search_players(self, username_pattern: str = None, min_hands: int = 0) -> List[Player]:
        """Search for players by username pattern and minimum hands"""
        with self.get_session() as session:
            query = session.query(Player)
            
            if username_pattern:
                query = query.filter(Player.username.like(f'%{username_pattern}%'))
            
            if min_hands > 0:
                query = query.filter(Player.total_hands >= min_hands)
            
            return query.all()
    
    def get_player_notes(self, player_id: int) -> List[Dict[str, Any]]:
        """Get all notes for a player"""
        with self.get_session() as session:
            from database.models import Note
            notes = session.query(Note).filter_by(player_id=player_id).order_by(
                Note.importance.desc(), Note.created_at.desc()
            ).all()
            
            return [
                {
                    'text': note.note_text,
                    'category': note.category,
                    'importance': note.importance,
                    'created_at': note.created_at,
                    'is_auto': note.is_auto
                }
                for note in notes
            ]
    
    def add_player_note(self, player_id: int, note_text: str, 
                       category: str = None, importance: int = 5,
                       hand_id: int = None, is_auto: bool = False):
        """Add a note for a player"""
        with self.get_session() as session:
            from database.models import Note
            note = Note(
                player_id=player_id,
                hand_id=hand_id,
                note_text=note_text,
                category=category,
                importance=importance,
                is_auto=is_auto
            )
            session.add(note)
            session.commit()
            logger.info(f"Added note for player_id={player_id}")
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get overall database statistics"""
        with self.get_session() as session:
            return {
                'total_players': session.query(Player).count(),
                'total_hands': session.query(Hand).count(),
                'total_sessions': session.query(PokerSession).count(),
                'players_with_100_hands': session.query(Player).filter(
                    Player.total_hands >= 100
                ).count(),
                'last_hand_time': session.query(func.max(Hand.timestamp)).scalar()
            }