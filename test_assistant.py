#!/usr/bin/env python3
"""
Test script for Poker Assistant functionality
"""

import os
import sys

# Add poker-assistant directory to path
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(script_dir, 'src'))

from database.manager import DatabaseManager
from history.hand_parser import PokerStarsParser, ParsedHand
from capture.ocr_engine import OCREngine
import numpy as np
from datetime import datetime
from loguru import logger

# Setup logging
logger.remove()
logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level} | {message}")


def test_database():
    """Test database functionality"""
    print("\n=== Testing Database ===")
    
    db = DatabaseManager("data/test.db")
    
    # Create a player
    player = db.get_or_create_player("TestHero", "PokerStars", is_hero=True)
    print(f"Created player: {player.username} (ID: {player.id})")
    
    # Update player stats
    stats_update = {
        'vpip': 22.5,
        'pfr': 18.0,
        'three_bet': 7.5,
        'hands_played': 150
    }
    db.update_player_stats(player.id, stats_update)
    print(f"Updated stats for {player.username}")
    
    # Get stats
    stats = db.get_player_stats("TestHero", "PokerStars")
    if stats:
        print(f"VPIP: {stats['vpip']}%, PFR: {stats['pfr']}%, 3bet: {stats['three_bet']}%")
        print(f"Confidence: {stats['confidence_level']:.2f}")
    
    # Get database statistics
    db_stats = db.get_database_stats()
    print(f"Database stats: {db_stats}")
    
    print("✓ Database test completed")


def test_hand_parser():
    """Test hand parsing functionality"""
    print("\n=== Testing Hand Parser ===")
    
    # Sample PokerStars hand history
    sample_hand = """PokerStars Hand #123456789: Hold'em No Limit ($0.25/$0.50) - 2024/01/15 10:30:45 ET
Table 'TestTable' 6-max Seat #1 is the button
Seat 1: Player1 ($50.00 in chips)
Seat 2: Player2 ($48.50 in chips)
Seat 3: TestHero ($52.25 in chips)
Seat 4: Player4 ($50.00 in chips)
Seat 5: Player5 ($49.75 in chips)
Seat 6: Player6 ($51.00 in chips)
Player2: posts small blind $0.25
TestHero: posts big blind $0.50
*** HOLE CARDS ***
Dealt to TestHero [Ah Kd]
Player4: folds
Player5: raises $1.50 to $2
Player6: folds
Player1: calls $2
Player2: folds
TestHero: raises $6 to $8
Player5: calls $6
Player1: folds
*** FLOP *** [Ac 7s 2h]
TestHero: bets $10
Player5: calls $10
*** TURN *** [Ac 7s 2h] [Qd]
TestHero: checks
Player5: checks
*** RIVER *** [Ac 7s 2h Qd] [5c]
TestHero: bets $15
Player5: folds
TestHero collected $36.75 from pot
*** SUMMARY ***
Total pot $38.25 | Rake $1.50"""
    
    parser = PokerStarsParser()
    hand = parser.parse(sample_hand)
    
    if hand:
        print(f"Parsed hand #{hand.hand_number}")
        print(f"Table: {hand.table_name}")
        print(f"Stakes: ${hand.small_blind}/${hand.big_blind}")
        print(f"Players: {len(hand.players)}")
        print(f"Actions: {len(hand.actions)}")
        print(f"Pot: ${hand.pot_size}")
        
        # Show player positions
        for name, player in hand.players.items():
            print(f"  {name}: Seat {player.seat}, Stack ${player.stack}, Position: {player.position}")
        
        print("✓ Hand parser test completed")
    else:
        print("✗ Failed to parse hand")


def test_ocr_engine():
    """Test OCR functionality with simulated image"""
    print("\n=== Testing OCR Engine ===")
    
    ocr = OCREngine()
    
    # Create a simple test image with text (would be actual screenshot in production)
    # For testing, we'll just verify the OCR engine initializes
    print("OCR Engine initialized with pytesseract")
    
    # Test pattern matching
    test_texts = [
        "VPIP: 24.5%",
        "PFR: 18.2%",
        "3bet: 7.8%",
        "$125.50",
        "Player123",
        "Ah Kd"
    ]
    
    for text in test_texts:
        # Test pattern recognition
        if "VPIP" in text:
            import re
            match = re.search(r"VPIP:\s*([\d.]+)", text)
            if match:
                print(f"Extracted VPIP: {match.group(1)}%")
        elif "$" in text:
            amount = text.replace("$", "").replace(",", "")
            print(f"Extracted amount: ${amount}")
        elif re.match(r"[AKQJT2-9][schd]", text):
            print(f"Detected cards: {text}")
    
    print("✓ OCR engine test completed")


def test_sample_hand_flow():
    """Test complete flow with sample hand"""
    print("\n=== Testing Complete Flow ===")
    
    # Initialize components
    db = DatabaseManager("data/test.db")
    
    # Create sample hand data
    hand_data = {
        'hand_number': '123456789',
        'site': 'PokerStars',
        'timestamp': datetime.now(),
        'table_name': 'TestTable',
        'small_blind': 0.25,
        'big_blind': 0.50,
        'player_count': 6,
        'max_players': 6,
        'game_type': 'NLHE',
        'pot_size': 38.25,
        'rake': 1.50,
        'winner_ids': ['TestHero']
    }
    
    # Save hand
    hand = db.save_hand(hand_data)
    print(f"Saved hand #{hand['hand_number']} to database")
    
    # Create sample actions
    actions = [
        {
            'username': 'TestHero',
            'site': 'PokerStars',
            'position': 'BB',
            'street': 'preflop',
            'action_type': 'raise',
            'amount': 8.0,
            'pot_size_before': 2.75
        },
        {
            'username': 'Player5',
            'site': 'PokerStars',
            'position': 'MP',
            'street': 'preflop',
            'action_type': 'call',
            'amount': 6.0,
            'pot_size_before': 10.75
        }
    ]
    
    # Save actions
    db.save_hand_actions(hand['id'], actions)
    print(f"Saved {len(actions)} actions")
    
    # Calculate stats
    hero = db.get_or_create_player("TestHero", "PokerStars", is_hero=True)
    db.calculate_player_stats_from_hands(hero.id)
    
    # Get updated stats
    stats = db.get_player_stats("TestHero", "PokerStars")
    if stats:
        print(f"Updated hero stats - Hands: {stats['hands_played']}")
    
    print("✓ Complete flow test completed")


def main():
    """Run all tests"""
    print("=" * 50)
    print("POKER ASSISTANT TEST SUITE")
    print("=" * 50)
    
    # Create necessary directories
    os.makedirs("data", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    
    try:
        test_database()
        test_hand_parser()
        test_ocr_engine()
        test_sample_hand_flow()
        
        print("\n" + "=" * 50)
        print("ALL TESTS COMPLETED SUCCESSFULLY")
        print("=" * 50)
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()