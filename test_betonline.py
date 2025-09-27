#!/usr/bin/env python3
"""
Test script for BetOnline poker functionality
"""

import os
import sys

# Add poker-assistant directory to path
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(script_dir, 'src'))

from database.manager import DatabaseManager
from history.betonline_parser import BetOnlineParser
from loguru import logger

# Setup logging
logger.remove()
logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level} | {message}")


def test_betonline_parser():
    """Test BetOnline hand parsing"""
    print("\n=== Testing BetOnline Parser ===")
    
    # Read sample hand
    with open('data/betonline_sample.txt', 'r') as f:
        hand_text = f.read()
    
    # Split into individual hands
    hands = hand_text.split('\n\n')
    
    parser = BetOnlineParser()
    
    for i, hand_text in enumerate(hands, 1):
        if hand_text.strip():
            print(f"\nParsing hand {i}...")
            hand = parser.parse(hand_text)
            
            if hand:
                print(f"✓ Parsed hand #{hand.hand_number}")
                print(f"  Table: {hand.table_name}")
                print(f"  Stakes: ${hand.small_blind}/${hand.big_blind}")
                print(f"  Players: {len(hand.players)}")
                print(f"  Actions: {len(hand.actions)}")
                
                # Show players
                for name, player in hand.players.items():
                    cards = f" [{' '.join(player.hole_cards)}]" if player.hole_cards else ""
                    print(f"    {name}: Seat {player.seat}, Stack ${player.stack}{cards}")
                
                # Show board
                if hand.flop:
                    board = ' '.join(hand.flop)
                    if hand.turn:
                        board += f" {hand.turn}"
                    if hand.river:
                        board += f" {hand.river}"
                    print(f"  Board: {board}")
                
                # Show winners
                if hand.winners:
                    print(f"  Winners: {', '.join(hand.winners)}")
                    print(f"  Pot: ${hand.pot_size}")
            else:
                print(f"✗ Failed to parse hand {i}")


def test_betonline_database():
    """Test saving BetOnline hands to database"""
    print("\n=== Testing BetOnline Database Integration ===")
    
    db = DatabaseManager("data/betonline_test.db")
    parser = BetOnlineParser()
    
    # Read and parse sample hand
    with open('data/betonline_sample.txt', 'r') as f:
        hand_text = f.read().split('\n\n')[0]  # First hand only
    
    hand = parser.parse(hand_text)
    
    if hand:
        # Save to database
        hand_data = {
            'hand_number': hand.hand_number,
            'site': 'BetOnline',
            'timestamp': hand.timestamp,
            'table_name': hand.table_name,
            'small_blind': hand.small_blind,
            'big_blind': hand.big_blind,
            'player_count': len(hand.players),
            'max_players': hand.max_players,
            'game_type': hand.game_type,
            'pot_size': hand.pot_size,
            'winner_ids': hand.winners
        }
        
        saved = db.save_hand(hand_data)
        print(f"✓ Saved hand #{saved['hand_number']} to database")
        
        # Get stats
        stats = db.get_database_stats()
        print(f"  Database now has {stats['total_hands']} hands")
    else:
        print("✗ Failed to parse hand for database test")


def find_betonline_hand_history():
    """Help user find BetOnline hand history folder"""
    print("\n=== Finding BetOnline Hand History Folder ===")
    
    import platform
    from pathlib import Path
    
    possible_paths = []
    
    if platform.system() == "Windows":
        # Windows paths
        user_home = Path.home()
        possible_paths = [
            user_home / "AppData" / "Local" / "BetOnline" / "HandHistory",
            user_home / "AppData" / "Roaming" / "BetOnline" / "HandHistory",
            user_home / "Documents" / "BetOnline" / "HandHistory",
            user_home / "Documents" / "BetOnline Poker" / "Hand History",
            Path("C:/BetOnline/HandHistory"),
            Path("C:/Program Files/BetOnline/HandHistory"),
            Path("C:/Program Files (x86)/BetOnline/HandHistory"),
        ]
    elif platform.system() == "Darwin":  # macOS
        user_home = Path.home()
        possible_paths = [
            user_home / "Library" / "Application Support" / "BetOnline" / "HandHistory",
            user_home / "Documents" / "BetOnline" / "HandHistory",
            user_home / "Documents" / "BetOnline Poker" / "Hand History",
            user_home / "Desktop" / "BetOnline",
        ]
    else:  # Linux
        user_home = Path.home()
        possible_paths = [
            user_home / ".betonline" / "handhistory",
            user_home / "Documents" / "BetOnline" / "HandHistory",
            user_home / ".wine" / "drive_c" / "BetOnline" / "HandHistory",
        ]
    
    found = False
    for path in possible_paths:
        if path.exists():
            print(f"✓ Found: {path}")
            found = True
            
            # Check for hand history files
            txt_files = list(path.glob("*.txt"))
            if txt_files:
                print(f"  Contains {len(txt_files)} hand history files")
            else:
                print("  No .txt files found (folder might be empty)")
    
    if not found:
        print("✗ Could not find BetOnline hand history folder automatically")
        print("\nPlease check these locations manually:")
        print("\n1. Open BetOnline Poker client")
        print("2. Go to Settings/Options")
        print("3. Look for 'Hand History' or 'Save Hand History' option")
        print("4. Note the folder path shown there")
        print("\nCommon locations to check:")
        for path in possible_paths[:3]:
            print(f"  - {path}")
        
        print("\nOnce you find it, update config/betonline_settings.yaml with the correct path")


def main():
    """Run all BetOnline tests"""
    print("=" * 60)
    print("BETONLINE POKER ASSISTANT TEST")
    print("=" * 60)
    
    try:
        test_betonline_parser()
        test_betonline_database()
        find_betonline_hand_history()
        
        print("\n" + "=" * 60)
        print("BETONLINE TESTS COMPLETED")
        print("=" * 60)
        
        print("\n📝 Next Steps:")
        print("1. Find your BetOnline hand history folder (see paths above)")
        print("2. Update config/betonline_settings.yaml with:")
        print("   - Your BetOnline username")
        print("   - Correct hand history path")
        print("   - Table window position")
        print("3. Run: python src/main.py --config config/betonline_settings.yaml")
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()