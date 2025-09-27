from datetime import datetime
from typing import Optional, Dict, Any
import json
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, ForeignKey, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.sql import func

Base = declarative_base()


class Player(Base):
    __tablename__ = 'players'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(100), nullable=False)
    site = Column(String(50), nullable=False)
    total_hands = Column(Integer, default=0)
    last_seen = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text)
    is_hero = Column(Boolean, default=False)
    
    # Relationships
    stats = relationship("PlayerStats", back_populates="player", cascade="all, delete-orphan")
    actions = relationship("HandAction", back_populates="player")
    
    def __repr__(self):
        return f"<Player(username='{self.username}', site='{self.site}')>"


class PlayerStats(Base):
    __tablename__ = 'player_stats'
    
    id = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey('players.id'), nullable=False)
    
    # Preflop stats
    vpip = Column(Float, default=0.0)  # Voluntarily Put money In Pot
    pfr = Column(Float, default=0.0)   # Pre-Flop Raise
    three_bet = Column(Float, default=0.0)  # 3-bet percentage
    fold_to_three_bet = Column(Float, default=0.0)
    four_bet = Column(Float, default=0.0)
    fold_to_four_bet = Column(Float, default=0.0)
    
    # Postflop stats
    c_bet_flop = Column(Float, default=0.0)  # Continuation bet flop
    c_bet_turn = Column(Float, default=0.0)  # Continuation bet turn
    c_bet_river = Column(Float, default=0.0)  # Continuation bet river
    fold_to_c_bet_flop = Column(Float, default=0.0)
    fold_to_c_bet_turn = Column(Float, default=0.0)
    fold_to_c_bet_river = Column(Float, default=0.0)
    
    # Aggression stats
    af = Column(Float, default=0.0)  # Aggression Factor
    agg_freq = Column(Float, default=0.0)  # Aggression Frequency
    
    # Showdown stats
    wtsd = Column(Float, default=0.0)  # Went To ShowDown
    w_sd = Column(Float, default=0.0)  # Won money at ShowDown
    ww_sf = Column(Float, default=0.0)  # Won When Saw Flop
    
    # Positional stats (stored as JSON)
    positional_stats = Column(JSON, default={})
    
    # Sample sizes
    hands_played = Column(Integer, default=0)
    hands_vpip = Column(Integer, default=0)
    hands_pfr = Column(Integer, default=0)
    hands_3bet_opp = Column(Integer, default=0)
    hands_3bet = Column(Integer, default=0)
    
    # Metadata
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    confidence_level = Column(Float, default=0.0)  # 0-1 based on sample size
    
    # Relationship
    player = relationship("Player", back_populates="stats")
    
    def calculate_confidence(self):
        """Calculate confidence level based on sample size"""
        if self.hands_played < 30:
            return 0.1
        elif self.hands_played < 100:
            return 0.3
        elif self.hands_played < 500:
            return 0.6
        elif self.hands_played < 1000:
            return 0.8
        else:
            return 0.95


class Hand(Base):
    __tablename__ = 'hands'
    
    id = Column(Integer, primary_key=True)
    hand_number = Column(String(50), unique=True, nullable=False)
    site = Column(String(50), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    table_name = Column(String(100))
    
    # Stakes
    small_blind = Column(Float)
    big_blind = Column(Float)
    ante = Column(Float, default=0)
    
    # Game info
    player_count = Column(Integer)
    max_players = Column(Integer)
    game_type = Column(String(20))  # NLHE, PLO, etc.
    
    # Hand data
    raw_history = Column(Text)  # Original hand history text
    parsed_data = Column(JSON)  # Parsed hand data in JSON format
    
    # Board cards
    flop = Column(String(10))
    turn = Column(String(3))
    river = Column(String(3))
    
    # Results
    pot_size = Column(Float)
    rake = Column(Float)
    winner_ids = Column(JSON)  # List of winner player IDs
    
    # Relationships
    actions = relationship("HandAction", back_populates="hand", cascade="all, delete-orphan")
    session_id = Column(Integer, ForeignKey('sessions.id'))
    session = relationship("Session", back_populates="hands")
    
    def __repr__(self):
        return f"<Hand(number='{self.hand_number}', timestamp='{self.timestamp}')>"


class HandAction(Base):
    __tablename__ = 'hand_actions'
    
    id = Column(Integer, primary_key=True)
    hand_id = Column(Integer, ForeignKey('hands.id'), nullable=False)
    player_id = Column(Integer, ForeignKey('players.id'), nullable=False)
    
    # Position and cards
    position = Column(String(10))  # BTN, CO, MP, EP, SB, BB
    hole_cards = Column(String(10))  # e.g., "AhKs"
    
    # Action details
    street = Column(String(10))  # preflop, flop, turn, river
    action_number = Column(Integer)  # Order of action in the street
    action_type = Column(String(20))  # fold, check, call, bet, raise
    amount = Column(Float, default=0)
    pot_size_before = Column(Float)
    
    # Stack info
    stack_before = Column(Float)
    stack_after = Column(Float)
    
    # Relationships
    hand = relationship("Hand", back_populates="actions")
    player = relationship("Player", back_populates="actions")
    
    def __repr__(self):
        return f"<HandAction(hand_id={self.hand_id}, player_id={self.player_id}, action='{self.action_type}')>"


class Session(Base):
    __tablename__ = 'sessions'
    
    id = Column(Integer, primary_key=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime)
    
    # Session info
    site = Column(String(50))
    table_count = Column(Integer, default=1)
    hero_id = Column(Integer, ForeignKey('players.id'))
    
    # Results
    hands_played = Column(Integer, default=0)
    vpip_hands = Column(Integer, default=0)
    pfr_hands = Column(Integer, default=0)
    
    # Financial
    buy_in = Column(Float, default=0)
    cash_out = Column(Float, default=0)
    profit_loss = Column(Float, default=0)
    bb_per_100 = Column(Float, default=0)
    
    # Stats
    session_stats = Column(JSON, default={})
    
    # Relationships
    hands = relationship("Hand", back_populates="session")
    
    def calculate_winrate(self):
        """Calculate BB/100 for the session"""
        if self.hands_played > 0 and self.profit_loss is not None:
            # Assuming big_blind is stored in session_stats
            bb = self.session_stats.get('big_blind', 1)
            self.bb_per_100 = (self.profit_loss / bb) / (self.hands_played / 100)
        return self.bb_per_100


class HUDConfig(Base):
    __tablename__ = 'hud_configs'
    
    id = Column(Integer, primary_key=True)
    site = Column(String(50), nullable=False)
    hud_software = Column(String(50))  # PT4, HM3, etc.
    
    # Screen regions for OCR (stored as JSON)
    stat_regions = Column(JSON)  # {"vpip": {"x": 100, "y": 200, "width": 50, "height": 20}, ...}
    player_name_regions = Column(JSON)
    
    # OCR settings
    ocr_engine = Column(String(20), default='pytesseract')
    preprocessing = Column(JSON, default=['grayscale', 'threshold'])
    confidence_threshold = Column(Float, default=0.85)
    
    # Update frequency
    update_interval = Column(Float, default=1.0)  # seconds
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Note(Base):
    __tablename__ = 'notes'
    
    id = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey('players.id'), nullable=False)
    hand_id = Column(Integer, ForeignKey('hands.id'))
    
    note_text = Column(Text, nullable=False)
    category = Column(String(50))  # bluff, value, timing, sizing, etc.
    importance = Column(Integer, default=0)  # 0-10 scale
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Auto-generated notes
    is_auto = Column(Boolean, default=False)
    confidence = Column(Float, default=1.0)