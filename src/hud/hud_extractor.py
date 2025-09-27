import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger
import json

from capture.screen_capture import ScreenCapture, CaptureRegion
from capture.ocr_engine import OCREngine
from database.manager import DatabaseManager


@dataclass
class PlayerHUDStats:
    """Container for a player's HUD statistics"""
    username: str
    position: str
    vpip: float = 0.0
    pfr: float = 0.0
    three_bet: float = 0.0
    fold_to_three_bet: float = 0.0
    c_bet: float = 0.0
    fold_to_c_bet: float = 0.0
    af: float = 0.0  # Aggression factor
    wtsd: float = 0.0  # Went to showdown
    w_sd: float = 0.0  # Won at showdown
    hands: int = 0
    confidence: float = 0.0
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'username': self.username,
            'position': self.position,
            'vpip': self.vpip,
            'pfr': self.pfr,
            '3bet': self.three_bet,
            'fold_3bet': self.fold_to_three_bet,
            'cbet': self.c_bet,
            'fold_cbet': self.fold_to_c_bet,
            'af': self.af,
            'wtsd': self.wtsd,
            'w$sd': self.w_sd,
            'hands': self.hands,
            'confidence': self.confidence
        }


class HUDExtractor:
    """Extracts HUD statistics from screen captures"""
    
    def __init__(self, screen_capture: ScreenCapture, ocr_engine: OCREngine, 
                 db_manager: DatabaseManager, site: str = "generic"):
        self.screen_capture = screen_capture
        self.ocr = ocr_engine
        self.db = db_manager
        self.site = site
        
        # HUD configuration per site
        self.hud_configs = self._load_hud_configs()
        self.current_config = self.hud_configs.get(site, self.hud_configs["generic"])
        
        # Cache for player stats
        self.stats_cache = {}
        self.last_extraction = {}
        
        logger.info(f"HUDExtractor initialized for {site}")
    
    def _load_hud_configs(self) -> Dict[str, Dict]:
        """Load HUD configurations for different sites and software"""
        return {
            "pokerstars": {
                "software": ["pt4", "hm3"],
                "stat_layout": {
                    "vpip": {"row": 0, "col": 0},
                    "pfr": {"row": 0, "col": 1},
                    "3bet": {"row": 1, "col": 0},
                    "cbet": {"row": 1, "col": 1},
                    "hands": {"row": 2, "col": 0}
                },
                "stat_format": "{stat}%",
                "username_offset": {"x": 0, "y": -20}
            },
            "ggpoker": {
                "software": ["custom"],
                "stat_layout": {
                    "vpip": {"row": 0, "col": 0},
                    "pfr": {"row": 0, "col": 1},
                    "af": {"row": 1, "col": 0},
                    "wtsd": {"row": 1, "col": 1}
                },
                "stat_format": "{stat}",
                "username_offset": {"x": 0, "y": -25}
            },
            "generic": {
                "software": ["any"],
                "stat_layout": {
                    "vpip": {"row": 0, "col": 0},
                    "pfr": {"row": 0, "col": 1},
                    "3bet": {"row": 1, "col": 0},
                    "hands": {"row": 2, "col": 0}
                },
                "stat_format": "{stat}%",
                "username_offset": {"x": 0, "y": -20}
            }
        }
    
    def setup_hud_regions(self, player_positions: Dict[str, Tuple[int, int, int, int]]):
        """Setup HUD regions for each player position"""
        for position, bounds in player_positions.items():
            x, y, width, height = bounds
            
            # Main HUD panel region
            hud_region = CaptureRegion(
                x=x,
                y=y - 30,  # HUD typically above player box
                width=width,
                height=60,
                name=f"hud_{position}"
            )
            self.screen_capture.add_region(f"hud_{position}", hud_region)
            
            # Username region
            username_region = CaptureRegion(
                x=x,
                y=y + height - 20,
                width=width,
                height=20,
                name=f"username_{position}"
            )
            self.screen_capture.add_region(f"username_{position}", username_region)
    
    def extract_player_stats(self, position: str) -> Optional[PlayerHUDStats]:
        """Extract HUD stats for a specific player position"""
        try:
            # Capture HUD region
            hud_image = self.screen_capture.capture_named_region(f"hud_{position}")
            if hud_image is None:
                return None
            
            # Capture username
            username_image = self.screen_capture.capture_named_region(f"username_{position}")
            username = None
            if username_image is not None:
                username = self.ocr.extract_player_name(username_image)
            username = username if username else f"Unknown_{position}"
            
            # Extract stats from HUD
            stats = self.ocr.extract_hud_stats(hud_image)
            
            # Create PlayerHUDStats object
            player_stats = PlayerHUDStats(
                username=username,
                position=position,
                vpip=stats.get("vpip", 0.0),
                pfr=stats.get("pfr", 0.0),
                three_bet=stats.get("3bet", 0.0),
                fold_to_three_bet=stats.get("fold_3bet", 0.0),
                c_bet=stats.get("cbet", 0.0),
                fold_to_c_bet=stats.get("fold_cbet", 0.0),
                af=stats.get("af", 0.0),
                wtsd=stats.get("wtsd", 0.0),
                w_sd=stats.get("w$sd", 0.0),
                hands=int(stats.get("hands", 0)),
                confidence=self._calculate_confidence(stats)
            )
            
            # Cache the stats
            self.stats_cache[position] = player_stats
            self.last_extraction[position] = datetime.utcnow()
            
            # Update database
            self._update_database(player_stats)
            
            return player_stats
            
        except Exception as e:
            logger.error(f"Failed to extract stats for position {position}: {e}")
            return None
    
    def extract_all_players(self) -> Dict[str, PlayerHUDStats]:
        """Extract HUD stats for all players at the table"""
        positions = ["BTN", "SB", "BB", "UTG", "MP", "CO"]
        all_stats = {}
        
        for position in positions:
            if f"hud_{position}" in self.screen_capture.regions:
                stats = self.extract_player_stats(position)
                if stats:
                    all_stats[position] = stats
                    logger.debug(f"Extracted stats for {position}: {stats.username}")
        
        return all_stats
    
    def extract_stats_from_region(self, image: np.ndarray, stat_layout: Dict) -> Dict[str, float]:
        """Extract individual stats from HUD region based on layout"""
        stats = {}
        height, width = image.shape[:2]
        
        # Calculate grid cell size
        max_row = max(layout["row"] for layout in stat_layout.values()) + 1
        max_col = max(layout["col"] for layout in stat_layout.values()) + 1
        
        cell_height = height // max_row
        cell_width = width // max_col
        
        for stat_name, position in stat_layout.items():
            row = position["row"]
            col = position["col"]
            
            # Extract cell region
            y1 = row * cell_height
            y2 = (row + 1) * cell_height
            x1 = col * cell_width
            x2 = (col + 1) * cell_width
            
            cell_image = image[y1:y2, x1:x2]
            
            # Extract number from cell
            value = self.ocr.extract_number(cell_image)
            if value is not None:
                stats[stat_name] = value
        
        return stats
    
    def _calculate_confidence(self, stats: Dict[str, float]) -> float:
        """Calculate confidence score based on extracted stats"""
        if not stats:
            return 0.0
        
        # Check if key stats are present
        key_stats = ["vpip", "pfr"]
        present_count = sum(1 for stat in key_stats if stat in stats and stats[stat] > 0)
        
        # Check if values are reasonable
        confidence = present_count / len(key_stats)
        
        # Validate stat ranges
        if "vpip" in stats:
            if 0 <= stats["vpip"] <= 100:
                confidence += 0.2
        
        if "pfr" in stats:
            if 0 <= stats["pfr"] <= stats.get("vpip", 100):
                confidence += 0.2
        
        # Check sample size
        if "hands" in stats and stats["hands"] > 30:
            confidence += 0.2
        
        return min(confidence, 1.0)
    
    def _update_database(self, player_stats: PlayerHUDStats):
        """Update database with extracted HUD stats"""
        try:
            # Skip if username is None or empty
            if not player_stats.username:
                logger.debug(f"Skipping database update for position {player_stats.position}: no username")
                return
            
            # Get or create player
            player = self.db.get_or_create_player(player_stats.username, self.site)
            
            # Update stats
            stats_update = {
                'vpip': player_stats.vpip,
                'pfr': player_stats.pfr,
                'three_bet': player_stats.three_bet,
                'fold_to_three_bet': player_stats.fold_to_three_bet,
                'c_bet_flop': player_stats.c_bet,
                'fold_to_c_bet_flop': player_stats.fold_to_c_bet,
                'af': player_stats.af,
                'wtsd': player_stats.wtsd,
                'w_sd': player_stats.w_sd,
                'hands_played': player_stats.hands,
                'confidence_level': player_stats.confidence
            }
            
            self.db.update_player_stats(player.id, stats_update)
            
        except Exception as e:
            logger.error(f"Failed to update database: {e}")
    
    def get_cached_stats(self, position: str, max_age_seconds: int = 5) -> Optional[PlayerHUDStats]:
        """Get cached stats if they're recent enough"""
        if position not in self.stats_cache:
            return None
        
        if position not in self.last_extraction:
            return None
        
        age = (datetime.utcnow() - self.last_extraction[position]).total_seconds()
        
        if age <= max_age_seconds:
            return self.stats_cache[position]
        
        return None
    
    def identify_player_types(self, stats: PlayerHUDStats) -> str:
        """Identify player type based on stats"""
        if stats.hands < 30:
            return "Unknown (insufficient data)"
        
        vpip = stats.vpip
        pfr = stats.pfr
        af = stats.af
        
        # Basic player type classification
        if vpip < 15 and pfr < 10:
            return "NIT (Very Tight)"
        elif vpip < 20 and pfr < 15:
            return "TAG (Tight Aggressive)"
        elif vpip < 30 and pfr < 25:
            return "REG (Regular)"
        elif vpip > 35 and pfr < 15:
            return "FISH (Loose Passive)"
        elif vpip > 30 and pfr > 20:
            return "LAG (Loose Aggressive)"
        elif vpip > 50:
            return "MANIAC (Very Loose)"
        else:
            return "Mixed Style"
    
    def get_exploitative_adjustments(self, stats: PlayerHUDStats) -> Dict[str, str]:
        """Generate exploitative adjustments based on player stats"""
        adjustments = {}
        
        if stats.vpip > 35:
            adjustments["preflop"] = "Tighten up, value bet more"
        elif stats.vpip < 15:
            adjustments["preflop"] = "Steal more, 3bet light"
        
        if stats.fold_to_three_bet > 70:
            adjustments["3bet"] = "3bet more as a bluff"
        elif stats.fold_to_three_bet < 40:
            adjustments["3bet"] = "3bet for value only"
        
        if stats.fold_to_c_bet > 60:
            adjustments["postflop"] = "C-bet more frequently"
        elif stats.fold_to_c_bet < 40:
            adjustments["postflop"] = "C-bet less, check strong hands"
        
        if stats.af < 1:
            adjustments["aggression"] = "Bet for value, check marginal hands"
        elif stats.af > 3:
            adjustments["aggression"] = "Call down lighter, trap more"
        
        return adjustments
    
    def export_stats(self, filepath: str):
        """Export current HUD stats to file"""
        export_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "site": self.site,
            "players": {}
        }
        
        for position, stats in self.stats_cache.items():
            export_data["players"][position] = stats.to_dict()
        
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        logger.info(f"Exported HUD stats to {filepath}")