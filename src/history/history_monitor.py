import os
import time
from pathlib import Path
from typing import Dict, List, Callable, Optional, Set
from datetime import datetime, timedelta
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent
from loguru import logger
import threading
from queue import Queue

from history.hand_parser import HandParser, ParsedHand
from history.parser_factory import ParserFactory
from database.manager import DatabaseManager


class HandHistoryHandler(FileSystemEventHandler):
    """Handles file system events for hand history files"""
    
    def __init__(self, callback: Callable[[str], None], file_extensions: List[str] = ['.txt']):
        self.callback = callback
        self.file_extensions = file_extensions
        self.processed_files = set()
        self.file_positions = {}  # Track read position in files
    
    def on_modified(self, event):
        if event.is_directory:
            return
        
        if any(event.src_path.endswith(ext) for ext in self.file_extensions):
            self.callback(event.src_path)
    
    def on_created(self, event):
        if event.is_directory:
            return
        
        if any(event.src_path.endswith(ext) for ext in self.file_extensions):
            self.callback(event.src_path)


class HandHistoryMonitor:
    """Monitors hand history directories and processes new hands"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.parser_factory = ParserFactory()
        
        # Monitoring configuration
        self.monitored_paths = {}  # {path: site}
        self.observers = []
        self.is_running = False
        
        # Hand processing
        self.hand_queue = Queue()
        self.processed_hands = set()
        self.file_positions = {}  # Track position in each file
        
        # Statistics
        self.stats = {
            'hands_processed': 0,
            'hands_failed': 0,
            'files_monitored': 0,
            'last_hand_time': None
        }
        
        # Processing thread
        self.processing_thread = None
        
        logger.info("HandHistoryMonitor initialized")
    
    def add_directory(self, path: str, site: str):
        """Add a directory to monitor for hand histories"""
        if not os.path.exists(path):
            logger.error(f"Directory does not exist: {path}")
            return False
        
        self.monitored_paths[path] = site
        logger.info(f"Added monitoring for {site} at {path}")
        return True
    
    def setup_default_directories(self):
        """Setup monitoring for common poker site directories"""
        home = Path.home()
        
        # Common hand history locations
        default_paths = {
            # PokerStars
            str(home / "Documents" / "PokerStars" / "HandHistory"): "PokerStars",
            str(home / "AppData" / "Local" / "PokerStars" / "HandHistory"): "PokerStars",
            
            # BetOnline
            str(home / "Documents" / "BetOnline" / "HandHistory"): "BetOnline",
            str(home / "AppData" / "Local" / "BetOnline" / "HandHistory"): "BetOnline",
            str(home / "Documents" / "BetOnlinePoker" / "HandHistory"): "BetOnline",
            
            # GGPoker
            str(home / "Documents" / "GGPoker" / "HandHistory"): "GGPoker",
            
            # PartyPoker
            str(home / "Documents" / "PartyPoker" / "HandHistory"): "PartyPoker",
            
            # 888poker
            str(home / "Documents" / "888poker" / "HandHistory"): "888poker",
        }
        
        for path, site in default_paths.items():
            if os.path.exists(path):
                self.add_directory(path, site)
                logger.info(f"Found {site} directory at {path}")
    
    def start(self):
        """Start monitoring hand history directories"""
        if self.is_running:
            logger.warning("Monitor is already running")
            return
        
        self.is_running = True
        
        # Start observers for each directory
        for path, site in self.monitored_paths.items():
            observer = Observer()
            handler = HandHistoryHandler(
                callback=lambda filepath: self._handle_file_event(filepath, site)
            )
            observer.schedule(handler, path, recursive=True)
            observer.start()
            self.observers.append(observer)
            logger.info(f"Started monitoring {path}")
        
        # Start processing thread
        self.processing_thread = threading.Thread(target=self._process_hands)
        self.processing_thread.daemon = True
        self.processing_thread.start()
        
        # Process existing files
        self._scan_existing_files()
        
        logger.info(f"HandHistoryMonitor started with {len(self.observers)} observers")
    
    def stop(self):
        """Stop monitoring"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # Stop all observers
        for observer in self.observers:
            observer.stop()
            observer.join()
        
        self.observers.clear()
        
        # Wait for processing thread
        if self.processing_thread:
            self.processing_thread.join(timeout=5)
        
        logger.info("HandHistoryMonitor stopped")
    
    def _handle_file_event(self, filepath: str, site: str):
        """Handle a file system event"""
        try:
            # Read new content from file
            new_hands = self._read_new_hands(filepath, site)
            
            # Add hands to processing queue
            for hand_text in new_hands:
                self.hand_queue.put((hand_text, site, filepath))
            
            self.stats['files_monitored'] = len(self.file_positions)
            
        except Exception as e:
            logger.error(f"Error handling file {filepath}: {e}")
    
    def _read_new_hands(self, filepath: str, site: str) -> List[str]:
        """Read new hands from a file"""
        try:
            # Get last read position
            last_position = self.file_positions.get(filepath, 0)
            
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                # Seek to last position
                f.seek(last_position)
                
                # Read new content
                new_content = f.read()
                
                # Update position
                self.file_positions[filepath] = f.tell()
            
            if not new_content:
                return []
            
            # Split into individual hands
            hands = self._split_hands(new_content, site)
            
            return hands
            
        except Exception as e:
            logger.error(f"Error reading file {filepath}: {e}")
            return []
    
    def _split_hands(self, content: str, site: str) -> List[str]:
        """Split file content into individual hands"""
        hands = []
        
        # Different sites have different hand delimiters
        if site == "PokerStars":
            # PokerStars hands start with "PokerStars Hand #"
            pattern = r'(?=PokerStars Hand #\d+:)'
        elif site == "GGPoker":
            # GGPoker format
            pattern = r'(?=Poker Hand #\d+:)'
        else:
            # Generic: double newline
            pattern = r'\n\n+'
        
        import re
        hand_texts = re.split(pattern, content)
        
        for hand_text in hand_texts:
            hand_text = hand_text.strip()
            if hand_text and len(hand_text) > 100:  # Minimum viable hand length
                hands.append(hand_text)
        
        return hands
    
    def _process_hands(self):
        """Process hands from the queue"""
        while self.is_running:
            try:
                # Get hand from queue with timeout
                if not self.hand_queue.empty():
                    hand_text, site, filepath = self.hand_queue.get(timeout=1)
                    
                    # Parse hand
                    parser = self.parser_factory.get_parser(site)
                    parsed_hand = parser.parse(hand_text)
                    
                    if parsed_hand:
                        # Check if already processed
                        if parsed_hand.hand_number not in self.processed_hands:
                            # Save to database
                            self._save_hand(parsed_hand)
                            self.processed_hands.add(parsed_hand.hand_number)
                            self.stats['hands_processed'] += 1
                            self.stats['last_hand_time'] = datetime.now()
                            
                            logger.debug(f"Processed hand #{parsed_hand.hand_number}")
                    else:
                        self.stats['hands_failed'] += 1
                        logger.warning(f"Failed to parse hand from {filepath}")
                else:
                    time.sleep(0.1)
                    
            except Exception as e:
                logger.error(f"Error processing hand: {e}")
                time.sleep(0.1)
    
    def _save_hand(self, parsed_hand: ParsedHand):
        """Save parsed hand to database"""
        try:
            # Prepare hand data for database
            hand_data = {
                'hand_number': parsed_hand.hand_number,
                'site': parsed_hand.site,
                'timestamp': parsed_hand.timestamp,
                'table_name': parsed_hand.table_name,
                'small_blind': parsed_hand.small_blind,
                'big_blind': parsed_hand.big_blind,
                'ante': parsed_hand.ante,
                'player_count': len(parsed_hand.players),
                'max_players': parsed_hand.max_players,
                'game_type': parsed_hand.game_type,
                'raw_history': parsed_hand.raw_text,
                'parsed_data': parsed_hand.to_dict(),
                'flop': ' '.join(parsed_hand.flop) if parsed_hand.flop else None,
                'turn': parsed_hand.turn,
                'river': parsed_hand.river,
                'pot_size': parsed_hand.pot_size,
                'rake': parsed_hand.rake,
                'winner_ids': parsed_hand.winners
            }
            
            # Save hand
            hand = self.db.save_hand(hand_data)
            
            # Save actions
            actions_data = []
            for action in parsed_hand.actions:
                player_info = parsed_hand.players.get(action.player)
                if player_info:
                    actions_data.append({
                        'username': action.player,
                        'site': parsed_hand.site,
                        'position': player_info.position,
                        'hole_cards': ' '.join(player_info.hole_cards) if player_info.hole_cards else None,
                        'street': action.street.value,
                        'action_type': action.action.value,
                        'amount': action.amount,
                        'pot_size_before': action.pot_before
                    })
            
            if actions_data:
                self.db.save_hand_actions(hand.id, actions_data)
            
            # Update player statistics
            for player_name, player_info in parsed_hand.players.items():
                player = self.db.get_or_create_player(player_name, parsed_hand.site)
                self.db.calculate_player_stats_from_hands(player.id)
            
        except Exception as e:
            logger.error(f"Error saving hand to database: {e}")
    
    def _scan_existing_files(self):
        """Scan existing files for unprocessed hands"""
        for path, site in self.monitored_paths.items():
            for root, dirs, files in os.walk(path):
                for file in files:
                    if file.endswith('.txt'):
                        filepath = os.path.join(root, file)
                        # Only process recent files (last 24 hours)
                        if self._is_recent_file(filepath, hours=24):
                            self._handle_file_event(filepath, site)
    
    def _is_recent_file(self, filepath: str, hours: int = 24) -> bool:
        """Check if file was modified recently"""
        try:
            mtime = os.path.getmtime(filepath)
            file_time = datetime.fromtimestamp(mtime)
            cutoff_time = datetime.now() - timedelta(hours=hours)
            return file_time > cutoff_time
        except:
            return False
    
    def get_stats(self) -> Dict:
        """Get monitoring statistics"""
        return {
            **self.stats,
            'monitored_directories': len(self.monitored_paths),
            'queue_size': self.hand_queue.qsize(),
            'cached_hands': len(self.processed_hands),
            'is_running': self.is_running
        }
    
    def clear_cache(self):
        """Clear processed hands cache"""
        self.processed_hands.clear()
        logger.info("Cleared processed hands cache")
    
    def reprocess_file(self, filepath: str, site: str):
        """Reprocess a specific file"""
        # Reset file position
        if filepath in self.file_positions:
            del self.file_positions[filepath]
        
        # Process file
        self._handle_file_event(filepath, site)