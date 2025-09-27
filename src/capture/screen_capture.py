import mss
import numpy as np
from PIL import Image
from typing import Optional, Tuple, Dict, Any, List
from dataclasses import dataclass
from loguru import logger
import time


@dataclass
class CaptureRegion:
    """Defines a screen region to capture"""
    x: int
    y: int
    width: int
    height: int
    name: str = ""
    
    def to_dict(self) -> Dict[str, int]:
        """Convert to mss monitor dict format"""
        return {
            "left": self.x,
            "top": self.y,
            "width": self.width,
            "height": self.height
        }


class ScreenCapture:
    """Handles screen capture operations for poker tables"""
    
    def __init__(self):
        self.sct = mss.mss()
        self.monitors = self.sct.monitors
        self.regions = {}
        self.last_capture_time = {}
        logger.info(f"ScreenCapture initialized with {len(self.monitors) - 1} monitors")
    
    def get_monitors_info(self) -> List[Dict[str, Any]]:
        """Get information about all available monitors"""
        info = []
        for i, monitor in enumerate(self.monitors[1:], 1):  # Skip combined monitor
            info.append({
                "index": i,
                "width": monitor["width"],
                "height": monitor["height"],
                "left": monitor["left"],
                "top": monitor["top"]
            })
        return info
    
    def capture_region(self, region: CaptureRegion) -> np.ndarray:
        """Capture a specific screen region"""
        try:
            screenshot = self.sct.grab(region.to_dict())
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            return np.array(img)
        except Exception as e:
            logger.error(f"Failed to capture region {region.name}: {e}")
            return None
    
    def capture_monitor(self, monitor_index: int = 1) -> np.ndarray:
        """Capture entire monitor"""
        try:
            if monitor_index >= len(self.monitors):
                logger.error(f"Monitor index {monitor_index} out of range")
                return None
            
            screenshot = self.sct.grab(self.monitors[monitor_index])
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            return np.array(img)
        except Exception as e:
            logger.error(f"Failed to capture monitor {monitor_index}: {e}")
            return None
    
    def add_region(self, name: str, region: CaptureRegion):
        """Add a named region for repeated capture"""
        self.regions[name] = region
        logger.debug(f"Added capture region '{name}': {region}")
    
    def capture_named_region(self, name: str) -> Optional[np.ndarray]:
        """Capture a previously defined named region"""
        if name not in self.regions:
            logger.error(f"Region '{name}' not found")
            return None
        
        return self.capture_region(self.regions[name])
    
    def capture_multiple_regions(self, region_names: List[str] = None) -> Dict[str, np.ndarray]:
        """Capture multiple regions at once"""
        if region_names is None:
            region_names = list(self.regions.keys())
        
        captures = {}
        for name in region_names:
            if name in self.regions:
                img = self.capture_named_region(name)
                if img is not None:
                    captures[name] = img
                    self.last_capture_time[name] = time.time()
        
        return captures
    
    def find_window_region(self, window_title: str) -> Optional[CaptureRegion]:
        """Find the region of a window by its title (platform-specific)"""
        # This would need platform-specific implementation
        # For now, return None as placeholder
        logger.warning("Window detection not yet implemented")
        return None
    
    def save_capture(self, image: np.ndarray, filepath: str):
        """Save captured image to file"""
        try:
            img = Image.fromarray(image)
            img.save(filepath)
            logger.debug(f"Saved capture to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save capture: {e}")
    
    def capture_table_regions(self) -> Dict[str, np.ndarray]:
        """Capture all poker table-related regions"""
        table_regions = [
            "table",
            "community_cards",
            "pot",
            "player_cards",
            "action_buttons",
            "chat"
        ]
        
        captures = {}
        for region_name in table_regions:
            if region_name in self.regions:
                img = self.capture_named_region(region_name)
                if img is not None:
                    captures[region_name] = img
        
        return captures
    
    def setup_poker_site_regions(self, site: str, table_bounds: Tuple[int, int, int, int]):
        """Setup standard regions for a poker site"""
        x, y, width, height = table_bounds
        
        if site.lower() == "pokerstars":
            self._setup_pokerstars_regions(x, y, width, height)
        elif site.lower() == "ggpoker":
            self._setup_ggpoker_regions(x, y, width, height)
        else:
            self._setup_generic_regions(x, y, width, height)
    
    def _setup_pokerstars_regions(self, x: int, y: int, width: int, height: int):
        """Setup regions specific to PokerStars"""
        # These are approximate ratios - would need fine-tuning
        self.add_region("table", CaptureRegion(x, y, width, height, "table"))
        self.add_region("community_cards", CaptureRegion(
            x + int(width * 0.35), y + int(height * 0.35),
            int(width * 0.3), int(height * 0.1), "community_cards"
        ))
        self.add_region("pot", CaptureRegion(
            x + int(width * 0.4), y + int(height * 0.3),
            int(width * 0.2), int(height * 0.05), "pot"
        ))
        # Add more regions for player positions, etc.
    
    def _setup_ggpoker_regions(self, x: int, y: int, width: int, height: int):
        """Setup regions specific to GGPoker"""
        # GGPoker-specific layout
        self.add_region("table", CaptureRegion(x, y, width, height, "table"))
        # Add GGPoker-specific regions
    
    def _setup_generic_regions(self, x: int, y: int, width: int, height: int):
        """Setup generic poker table regions"""
        self.add_region("table", CaptureRegion(x, y, width, height, "table"))
        
        # Generic layout assumptions
        self.add_region("community_cards", CaptureRegion(
            x + int(width * 0.3), y + int(height * 0.35),
            int(width * 0.4), int(height * 0.12), "community_cards"
        ))
        
        self.add_region("pot", CaptureRegion(
            x + int(width * 0.35), y + int(height * 0.28),
            int(width * 0.3), int(height * 0.06), "pot"
        ))
        
        # Player positions (6-max example)
        positions = [
            ("player_1", 0.5, 0.15),  # Top center
            ("player_2", 0.8, 0.3),   # Top right
            ("player_3", 0.8, 0.6),   # Bottom right
            ("player_4", 0.5, 0.75),  # Bottom center (hero)
            ("player_5", 0.2, 0.6),   # Bottom left
            ("player_6", 0.2, 0.3),   # Top left
        ]
        
        for name, x_ratio, y_ratio in positions:
            self.add_region(name, CaptureRegion(
                x + int(width * (x_ratio - 0.08)),
                y + int(height * (y_ratio - 0.05)),
                int(width * 0.16), int(height * 0.1), name
            ))
    
    def get_capture_rate(self, region_name: str) -> float:
        """Get the capture rate for a specific region"""
        if region_name not in self.last_capture_time:
            return 0.0
        
        current_time = time.time()
        time_diff = current_time - self.last_capture_time.get(region_name, current_time)
        
        if time_diff > 0:
            return 1.0 / time_diff
        return 0.0
    
    def cleanup(self):
        """Clean up resources"""
        if hasattr(self, 'sct'):
            self.sct.close()
            logger.info("ScreenCapture cleanup completed")