"""
Window detector for finding and tracking poker table windows
"""
import sys
import re
from typing import Optional, Tuple, List, Dict
from loguru import logger

# Platform-specific imports
if sys.platform == "win32":
    import win32gui
    import win32con
    import win32api
elif sys.platform == "darwin":
    # macOS implementation would use Quartz
    pass
else:
    # Linux implementation would use X11
    pass


class WindowInfo:
    """Information about a window"""
    def __init__(self, handle: int, title: str, x: int, y: int, width: int, height: int):
        self.handle = handle
        self.title = title
        self.x = x
        self.y = y
        self.width = width
        self.height = height
    
    def __repr__(self):
        return f"WindowInfo(title='{self.title}', pos=({self.x},{self.y}), size=({self.width}x{self.height}))"


class WindowDetector:
    """Detects and tracks poker table windows"""
    
    def __init__(self, site: str = "betonline"):
        self.site = site.lower()
        self.current_window = None
        self.window_patterns = self._get_window_patterns()
        
        logger.info(f"WindowDetector initialized for {site}")
    
    def _get_window_patterns(self) -> List[str]:
        """Get window title patterns for different poker sites"""
        patterns = {
            "betonline": [
                r"BetOnline",
                r"BetOnline Poker",
                r"Table \d+",
                r"Holdem - "
            ],
            "pokerstars": [
                r"PokerStars",
                r"Table \d+",
                r"Hold'em"
            ],
            "ggpoker": [
                r"GGPoker",
                r"Table #\d+"
            ]
        }
        return patterns.get(self.site, [self.site])
    
    def find_poker_window(self) -> Optional[WindowInfo]:
        """Find the poker table window"""
        if sys.platform == "win32":
            return self._find_window_windows()
        elif sys.platform == "darwin":
            return self._find_window_macos()
        else:
            return self._find_window_linux()
    
    def _find_window_windows(self) -> Optional[WindowInfo]:
        """Find window on Windows"""
        try:
            found_windows = []
            
            def enum_callback(hwnd, windows):
                if win32gui.IsWindowVisible(hwnd):
                    window_title = win32gui.GetWindowText(hwnd)
                    if window_title:
                        # Check if title matches any of our patterns
                        for pattern in self.window_patterns:
                            if re.search(pattern, window_title, re.IGNORECASE):
                                rect = win32gui.GetWindowRect(hwnd)
                                x, y, right, bottom = rect
                                width = right - x
                                height = bottom - y
                                
                                # Only consider reasonably sized windows
                                if width > 400 and height > 300:
                                    windows.append(WindowInfo(
                                        hwnd, window_title, x, y, width, height
                                    ))
                                    break
                return True
            
            win32gui.EnumWindows(enum_callback, found_windows)
            
            if found_windows:
                # Return the largest window (likely the main table)
                largest = max(found_windows, key=lambda w: w.width * w.height)
                self.current_window = largest
                logger.info(f"Found poker window: {largest}")
                return largest
            else:
                logger.warning(f"No {self.site} window found")
                return None
                
        except Exception as e:
            logger.error(f"Error finding window on Windows: {e}")
            return None
    
    def _find_window_macos(self) -> Optional[WindowInfo]:
        """Find window on macOS - placeholder"""
        logger.warning("macOS window detection not yet implemented")
        return None
    
    def _find_window_linux(self) -> Optional[WindowInfo]:
        """Find window on Linux - placeholder"""
        logger.warning("Linux window detection not yet implemented")
        return None
    
    def get_window_bounds(self) -> Optional[Tuple[int, int, int, int]]:
        """Get current window bounds (x, y, width, height)"""
        if not self.current_window:
            self.find_poker_window()
        
        if self.current_window:
            return (self.current_window.x, self.current_window.y, 
                   self.current_window.width, self.current_window.height)
        return None
    
    def update_window_position(self) -> bool:
        """Update the current window position if it has moved"""
        if not self.current_window:
            return False
        
        if sys.platform == "win32":
            try:
                rect = win32gui.GetWindowRect(self.current_window.handle)
                x, y, right, bottom = rect
                width = right - x
                height = bottom - y
                
                # Check if window has moved or resized
                if (self.current_window.x != x or self.current_window.y != y or
                    self.current_window.width != width or self.current_window.height != height):
                    
                    self.current_window.x = x
                    self.current_window.y = y
                    self.current_window.width = width
                    self.current_window.height = height
                    
                    logger.debug(f"Window updated: pos=({x},{y}), size=({width}x{height})")
                    return True
                    
            except Exception as e:
                logger.error(f"Error updating window position: {e}")
                # Window might be closed, try to find it again
                self.current_window = None
                self.find_poker_window()
        
        return False
    
    def is_window_active(self) -> bool:
        """Check if the poker window is still active"""
        if not self.current_window:
            return False
        
        if sys.platform == "win32":
            try:
                return win32gui.IsWindow(self.current_window.handle)
            except:
                return False
        
        return True
    
    def bring_to_front(self):
        """Bring the poker window to front"""
        if not self.current_window:
            return
        
        if sys.platform == "win32":
            try:
                win32gui.SetForegroundWindow(self.current_window.handle)
            except Exception as e:
                logger.error(f"Error bringing window to front: {e}")