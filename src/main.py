#!/usr/bin/env python3
"""
Poker Assistant - Real-time GTO and exploitative poker strategy assistant
"""

import sys
import os
import signal
import time
from pathlib import Path
from typing import Optional
from loguru import logger
import yaml
import argparse
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.manager import DatabaseManager
from capture.screen_capture import ScreenCapture, CaptureRegion
from capture.ocr_engine import OCREngine
from capture.table_reader import TableReader
from hud.hud_extractor import HUDExtractor
from history.history_monitor import HandHistoryMonitor
from overlay.player_hud import HUDManager, PlayerStats
from config.settings import Settings


class PokerAssistant:
    """Main application class for Poker Assistant"""
    
    def __init__(self, config_path: Optional[str] = None):
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Initialize components
        self.db = DatabaseManager(self.config.get('database', {}).get('path', 'data/poker.db'))
        self.screen_capture = ScreenCapture()
        self.ocr_engine = OCREngine(self.config.get('ocr', {}).get('engine', 'pytesseract'))
        
        # Site configuration
        self.site = self.config.get('site', 'pokerstars')
        
        # HUD extractor
        self.hud_extractor = HUDExtractor(
            self.screen_capture,
            self.ocr_engine,
            self.db,
            self.site
        )
        
        # Table reader for capturing hands from screen
        self.table_reader = TableReader(
            self.screen_capture,
            self.ocr_engine,
            self.site
        )
        
        # Hand history monitor
        self.history_monitor = HandHistoryMonitor(self.db)
        
        # HUD Manager for individual player windows
        self.hud_manager = HUDManager()
        
        # Session tracking
        self.current_session = None
        self.is_in_lobby = False
        
        # Running state
        self.is_running = False
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("Poker Assistant initialized")
    
    def _load_config(self, config_path: Optional[str]) -> dict:
        """Load configuration from file"""
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                logger.info(f"Loaded configuration from {config_path}")
                return config
        
        # Default configuration
        return {
            'site': 'pokerstars',
            'database': {
                'path': 'data/poker.db'
            },
            'ocr': {
                'engine': 'pytesseract',
                'confidence_threshold': 0.85
            },
            'capture': {
                'update_interval': 1.0,
                'monitor_index': 1
            },
            'hand_history': {
                'auto_detect': True,
                'directories': []
            }
        }
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)
    
    def setup_table_detection(self):
        """Setup automatic table detection"""
        logger.info("Setting up table detection...")
        
        # Try to auto-detect poker window first
        window_bounds = self.table_reader.window_detector.find_poker_window()
        
        if window_bounds:
            logger.info(f"Auto-detected poker window: {window_bounds}")
            # Window detection successful, regions will be set dynamically
            self.table_reader.update_regions()
            
            # Setup HUD regions based on window size
            bounds = self.table_reader.window_detector.get_window_bounds()
            if bounds:
                x, y, width, height = bounds
                
                # Dynamic HUD positions based on window size
                positions = {
                    "BTN": (x + int(width * 0.50), y + int(height * 0.15), int(width * 0.15), int(height * 0.10)),
                    "SB": (x + int(width * 0.70), y + int(height * 0.30), int(width * 0.15), int(height * 0.10)),
                    "BB": (x + int(width * 0.70), y + int(height * 0.60), int(width * 0.15), int(height * 0.10)),
                    "UTG": (x + int(width * 0.15), y + int(height * 0.60), int(width * 0.15), int(height * 0.10)),
                    "MP": (x + int(width * 0.15), y + int(height * 0.30), int(width * 0.15), int(height * 0.10)),
                    "CO": (x + int(width * 0.50), y + int(height * 0.75), int(width * 0.15), int(height * 0.10))
                }
                
                self.hud_extractor.setup_hud_regions(positions)
                logger.info("Table regions configured dynamically")
        else:
            # Fall back to manual configuration if auto-detection fails
            logger.warning("Auto-detection failed, trying manual configuration")
            table_config = self.config.get('table', {})
            
            if table_config and not table_config.get('auto_detect', True):
                x = table_config.get('x', 100)
                y = table_config.get('y', 100)
                width = table_config.get('width', 800)
                height = table_config.get('height', 600)
                
                self.screen_capture.setup_poker_site_regions(
                    self.site,
                    (x, y, width, height)
                )
                logger.info("Using manual table configuration")
            else:
                logger.warning("No poker window found and no manual config available")
    
    def setup_hand_history_monitoring(self):
        """Setup hand history directory monitoring"""
        config = self.config.get('hand_history', {})
        
        if config.get('auto_detect', True):
            # Auto-detect common directories
            self.history_monitor.setup_default_directories()
        
        # Add custom directories
        directories = config.get('directories', []) or []
        for directory in directories:
            site = directory.get('site', self.site)
            path = directory.get('path')
            if path:
                self.history_monitor.add_directory(path, site)
    
    def update_overlay_display(self, table_state):
        """Update the overlay with current player information"""
        try:
            # Get window bounds for positioning
            window_bounds = self.table_reader.window_detector.get_window_bounds()
            if not window_bounds:
                return
            
            x_base, y_base, width, height = window_bounds
            
            # Track which positions are active
            active_positions = set()
            
            # Process each player
            for position, player_info in table_state.players.items():
                player_name = player_info.get('name')
                if not player_name:
                    continue
                
                active_positions.add(position)
                
                # Get player stats from database
                player_db_stats = self.db.get_player_stats(player_name, self.site)
                
                # Categorize player
                category, color = self.categorize_player(player_db_stats)
                
                # Get position on screen
                seat_num = self._position_to_seat(position)
                if seat_num and seat_num in self.table_reader.seat_positions:
                    seat_pos = self.table_reader.seat_positions[seat_num]
                    
                    # Position HUD to the right of the player seat
                    hud_x = seat_pos['x'] + seat_pos['width'] + 5
                    hud_y = seat_pos['y']
                    
                    # Create stats object
                    stats = PlayerStats(
                        name=player_name,
                        vpip=player_db_stats.get('vpip', 0) if player_db_stats else 0,
                        pfr=player_db_stats.get('pfr', 0) if player_db_stats else 0,
                        three_bet=player_db_stats.get('three_bet', 0) if player_db_stats else 0,
                        hands=player_db_stats.get('hands_played', 0) if player_db_stats else 0,
                        category=category,
                        color=color
                    )
                    
                    # Create or update HUD for this player
                    self.hud_manager.create_or_update_hud(
                        position, player_name, stats, hud_x, hud_y
                    )
                    
                    # Log for debugging
                    logger.debug(f"Updated HUD for {player_name} at {position}: VPIP={stats.vpip:.1f}%, PFR={stats.pfr:.1f}%")
            
            # Show hand strength suggestion if we have hero cards
            if table_state.hero_cards and len(table_state.hero_cards) == 2:
                suggestion = self.get_hand_suggestion(table_state)
                if suggestion:
                    logger.info(f"Hand suggestion: {suggestion}")
            
        except Exception as e:
            logger.error(f"Failed to update overlay: {e}")
    
    def categorize_player(self, stats):
        """Categorize player based on stats"""
        if not stats or stats.get('hands_played', 0) < 20:
            return "Unknown", "#FFFFFF"
        
        vpip = stats.get('vpip', 0)
        pfr = stats.get('pfr', 0)
        three_bet = stats.get('three_bet', 0)
        
        # Categorize based on stats
        if vpip < 15:
            return "NIT", "#FF0000"  # Red - very tight
        elif vpip > 35 and pfr < 15:
            return "FISH", "#0000FF"  # Blue - loose passive
        elif vpip > 30 and pfr > 20:
            return "LAG", "#FFA500"  # Orange - loose aggressive
        elif vpip < 22 and pfr > 15:
            return "TAG", "#00FF00"  # Green - tight aggressive
        else:
            return "REG", "#FFFFFF"  # White - regular
    
    def get_hand_suggestion(self, table_state):
        """Get suggestion based on hand strength"""
        cards = table_state.hero_cards
        if not cards or len(cards) != 2:
            return None
        
        # Simple hand strength evaluation
        card1 = cards[0][:1] if cards[0] else ""
        card2 = cards[1][:1] if cards[1] else ""
        
        # Premium hands
        if card1 == 'A' and card2 == 'A':
            return "Premium hand! Raise/Re-raise"
        elif (card1 == 'K' and card2 == 'K') or (card1 == 'Q' and card2 == 'Q'):
            return "Strong hand! Raise for value"
        elif card1 == 'A' and card2 == 'K':
            return "AK - Premium! 3-bet/4-bet"
        
        # Check for suited
        suited = len(cards[0]) > 1 and len(cards[1]) > 1 and cards[0][-1] == cards[1][-1]
        if suited and ((card1 == 'A') or (card2 == 'A')):
            return "Suited Ace - Good for 3-bet bluffs"
        
        return None
    
    def _position_to_seat(self, position):
        """Convert position name to seat number"""
        position_map = {
            "BTN": 1, "SB": 2, "BB": 3,
            "UTG": 4, "MP": 5, "CO": 6
        }
        return position_map.get(position)
    
    def _create_test_hud(self):
        """Create a test HUD to verify the system is working"""
        try:
            logger.info("Creating test HUD window...")
            test_stats = PlayerStats(
                name="TestPlayer",
                vpip=25.5,
                pfr=18.2,
                hands=150,
                category="TAG",
                color="#00FF00"
            )
            # Create a test HUD in the center of the screen
            self.hud_manager.create_or_update_hud(
                "TEST", "TestPlayer", test_stats, 500, 300
            )
            logger.info("Test HUD created - you should see a green HUD window")
        except Exception as e:
            logger.error(f"Failed to create test HUD: {e}")
    
    def start(self):
        """Start the poker assistant"""
        logger.info("Starting Poker Assistant...")
        
        self.is_running = True
        
        # Setup components
        self.setup_table_detection()
        self.setup_hand_history_monitoring()
        
        # Start HUD manager
        self.hud_manager.start()
        logger.info("HUD Manager started - ready to display player stats")
        
        # Create a test HUD to verify system is working
        if self.config.get('test_hud', False):
            self._create_test_hud()
        
        # Start hand history monitoring
        self.history_monitor.start()
        
        # Auto-detect hero name from bottom position or use config
        hero_name = self.table_reader.detect_hero_name()
        if not hero_name:
            hero_name = self.config.get('hero_name', 'Hero')
            logger.info(f"Using configured hero name: {hero_name}")
        else:
            logger.info(f"Auto-detected hero name from bottom position: {hero_name}")
        
        # Create session
        self.current_session = self.db.create_session(self.site, hero_name)
        
        logger.info(f"Session started for {hero_name} on {self.site}")
        
        # Main loop
        self.run_main_loop()
    
    def run_main_loop(self):
        """Main application loop"""
        update_interval = self.config.get('capture', {}).get('update_interval', 1.0)
        last_update = time.time()
        last_stats_log = time.time()
        stats_log_interval = 30.0  # Only log stats every 30 seconds
        
        while self.is_running:
            try:
                current_time = time.time()
                
                if current_time - last_update >= update_interval:
                    # Check if we're in lobby
                    window_info = self.table_reader.window_detector.current_window
                    if window_info and "Lobby" in window_info.title:
                        if not self.is_in_lobby:
                            logger.info("In lobby - pausing table processing")
                            self.is_in_lobby = True
                            self.hud_manager.clear_all()
                    else:
                        self.is_in_lobby = False
                        
                        # Read table state from screen (only if not in lobby)
                        table_state = self.table_reader.read_table_state()
                        
                        if table_state:
                            # Check for new hand
                            if self.table_reader.detect_new_hand(table_state):
                                # Save previous hand if exists
                                self.save_captured_hand()
                                # Start tracking new hand
                                self.table_reader.reset_hand_tracking()
                                logger.info(f"New hand detected - Hero cards: {table_state.hero_cards}, Community: {table_state.community_cards}")
                            
                            # Track actions
                            self.table_reader.track_action(table_state)
                            
                            # Update overlay with player info
                            self.update_overlay_display(table_state)
                            
                            # Log current state periodically
                            if hasattr(self, '_last_state_log'):
                                if current_time - self._last_state_log > 10:  # Log every 10 seconds
                                    if table_state.players:
                                        logger.debug(f"Players detected: {list(table_state.players.keys())}")
                                    self._last_state_log = current_time
                            else:
                                self._last_state_log = current_time
                        
                        # Extract HUD stats (only if not in lobby)
                        if not self.is_in_lobby:
                            self.update_hud_stats()
                    
                    # Update display less frequently
                    if current_time - last_stats_log >= stats_log_interval:
                        self.display_stats()
                        last_stats_log = current_time
                    
                    last_update = current_time
                
                # Small sleep to prevent CPU overuse
                time.sleep(0.1)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(1)
    
    def update_hud_stats(self):
        """Update HUD statistics from screen"""
        try:
            all_stats = self.hud_extractor.extract_all_players()
            
            for position, stats in all_stats.items():
                if stats.confidence > 0.5:
                    logger.debug(f"{position}: {stats.username} - VPIP:{stats.vpip:.1f}% PFR:{stats.pfr:.1f}%")
                    
                    # Generate exploitative adjustments
                    adjustments = self.hud_extractor.get_exploitative_adjustments(stats)
                    if adjustments:
                        logger.info(f"Adjustments for {stats.username}: {adjustments}")
        
        except Exception as e:
            logger.error(f"Failed to update HUD stats: {e}")
    
    def save_captured_hand(self):
        """Save hand captured from screen to database and file"""
        hand_record = self.table_reader.create_hand_record()
        
        if not hand_record:
            logger.debug("No hand data to save")
            return
        
        try:
            # Log hand summary
            num_actions = len(hand_record.get('actions', []))
            hero_cards = hand_record.get('hero_cards', [])
            pot_size = hand_record.get('pot_size', 0)
            
            if num_actions > 0:
                logger.info(f"Saving hand with {num_actions} actions, pot: ${pot_size:.2f}, hero cards: {hero_cards}")
                
                # Create local hand history directory if it doesn't exist
                hand_history_dir = Path.home() / "Documents" / "BetOnline" / "HandHistory"
                hand_history_dir.mkdir(parents=True, exist_ok=True)
                
                # Save to file
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = hand_history_dir / f"hand_{timestamp}.json"
                
                import json
                with open(filename, 'w') as f:
                    # Convert datetime objects to strings for JSON serialization
                    hand_data = hand_record.copy()
                    hand_data['timestamp'] = hand_data['timestamp'].isoformat()
                    for action in hand_data.get('actions', []):
                        if 'timestamp' in action:
                            action['timestamp'] = action['timestamp'].isoformat()
                    
                    json.dump(hand_data, f, indent=2)
                
                logger.info(f"Hand saved to {filename}")
                
                # Also store in database
                self._store_hand_in_database(hand_record)
            else:
                logger.debug("Hand had no actions, skipping save")
            
        except Exception as e:
            logger.error(f"Failed to save captured hand: {e}")
    
    def _store_hand_in_database(self, hand_record: dict):
        """Store captured hand in database"""
        try:
            # Auto-detect hero name from bottom position or use config
            hero_name = self.table_reader.get_hero_name()
            if hero_name == "Hero":  # Fallback wasn't successful, try config
                hero_name = self.config.get('hero_name', 'Hero')
            
            # Create player entries for all players in the hand
            for action in hand_record.get('actions', []):
                player_name = action.get('player')
                if player_name:
                    self.db.get_or_create_player(player_name, self.site, 
                                                is_hero=(player_name == hero_name))
            
            logger.debug(f"Stored hand {hand_record['hand_id']} in database")
            
        except Exception as e:
            logger.error(f"Failed to store hand in database: {e}")
    
    def display_stats(self):
        """Display current statistics"""
        # Get database stats
        db_stats = self.db.get_database_stats()
        
        # Get monitor stats
        monitor_stats = self.history_monitor.get_stats()
        
        # Log summary only if there are changes
        if db_stats['total_hands'] > 0 or monitor_stats['hands_processed'] > 0:
            logger.info(f"Database: {db_stats['total_hands']} hands, {db_stats['total_players']} players")
            logger.info(f"Monitor: {monitor_stats['hands_processed']} processed, {monitor_stats['queue_size']} queued")
        
        # Note: HUD overlay display not yet implemented
        # Will require PyQt5/Tkinter for on-screen display
    
    def stop(self):
        """Stop the poker assistant"""
        logger.info("Stopping Poker Assistant...")
        
        self.is_running = False
        
        # Stop HUD manager
        self.hud_manager.stop()
        
        # Stop hand history monitoring
        self.history_monitor.stop()
        
        # End session
        if self.current_session:
            self.db.end_session(self.current_session.id)
        
        # Cleanup
        self.screen_capture.cleanup()
        
        logger.info("Poker Assistant stopped")
    
    def get_stats(self) -> dict:
        """Get current application statistics"""
        return {
            'session_id': self.current_session.id if self.current_session else None,
            'site': self.site,
            'is_running': self.is_running,
            'database': self.db.get_database_stats(),
            'monitor': self.history_monitor.get_stats()
        }


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Poker Assistant - Real-time poker strategy assistant')
    parser.add_argument('--config', '-c', help='Path to configuration file', default='config/settings.yaml')
    parser.add_argument('--site', '-s', help='Poker site', choices=['pokerstars', 'ggpoker', 'partypoker'])
    parser.add_argument('--debug', '-d', action='store_true', help='Enable debug logging')
    parser.add_argument('--db', help='Database path', default='data/poker.db')
    
    args = parser.parse_args()
    
    # Setup logging - DEBUG by default to diagnose issues
    log_level = "DEBUG"  # Always DEBUG for troubleshooting
    logger.remove()
    logger.add(sys.stderr, level=log_level, format="{time:HH:mm:ss} | {level} | {message}")
    logger.add("logs/poker_assistant_{time}.log", rotation="1 day", retention="7 days", level="DEBUG")
    
    # Create necessary directories
    os.makedirs("data", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    os.makedirs("config", exist_ok=True)
    
    # Start application
    try:
        app = PokerAssistant(args.config)
        
        # Override config with command line args
        if args.site:
            app.site = args.site
            app.config['site'] = args.site
        
        if args.db:
            app.config['database']['path'] = args.db
        
        logger.info("=" * 50)
        logger.info("POKER ASSISTANT")
        logger.info("=" * 50)
        logger.info(f"Site: {app.site}")
        logger.info(f"Database: {app.config['database']['path']}")
        logger.info("=" * 50)
        
        app.start()
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()