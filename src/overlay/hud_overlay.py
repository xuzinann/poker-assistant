"""
HUD Overlay - Displays stats and information on screen
"""
import tkinter as tk
from tkinter import ttk
import threading
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from loguru import logger
import time


@dataclass
class PlayerDisplay:
    """Information to display for a player"""
    name: str
    position: str
    vpip: float = 0.0
    pfr: float = 0.0
    hands: int = 0
    category: str = "Unknown"  # FISH, REG, NIT, TAG, LAG
    color: str = "#FFFFFF"
    suggestion: str = ""


class HUDOverlay:
    """Transparent overlay for displaying HUD information"""
    
    def __init__(self):
        self.root = None
        self.labels = {}
        self.player_frames = {}
        self.is_running = False
        self.update_queue = []
        self.overlay_thread = None
        
        # Position offsets for player stats (relative to seat position)
        self.display_offset = {
            'x': 160,  # Offset to the right of player seat
            'y': 0     # Same height as seat
        }
        
        logger.info("HUD Overlay initialized")
    
    def start(self):
        """Start the overlay in a separate thread"""
        if self.is_running:
            return
        
        self.is_running = True
        self.overlay_thread = threading.Thread(target=self._run_overlay)
        self.overlay_thread.daemon = True
        self.overlay_thread.start()
        logger.info("HUD Overlay started")
    
    def _run_overlay(self):
        """Run the overlay window"""
        try:
            self.root = tk.Tk()
            self.root.title("Poker HUD")
            
            # Make window transparent and always on top
            self.root.attributes('-alpha', 0.85)
            self.root.attributes('-topmost', True)
            
            # Remove window decorations
            self.root.overrideredirect(True)
            
            # Make the window click-through on Windows
            try:
                import win32gui
                import win32con
                hwnd = self.root.winfo_id()
                styles = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                styles = styles | win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT
                win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, styles)
            except:
                pass  # Not on Windows or win32gui not available
            
            # Start with a small window
            self.root.geometry("1x1+0+0")
            
            # Process updates periodically
            self.root.after(100, self._process_updates)
            
            # Run the GUI loop
            self.root.mainloop()
            
        except Exception as e:
            logger.error(f"Error in overlay thread: {e}")
        finally:
            self.is_running = False
    
    def _process_updates(self):
        """Process queued updates"""
        if not self.is_running:
            return
        
        try:
            # Process all queued updates
            while self.update_queue:
                update = self.update_queue.pop(0)
                if update['type'] == 'players':
                    self._update_player_displays(update['data'])
                elif update['type'] == 'suggestion':
                    self._show_suggestion(update['data'])
                elif update['type'] == 'clear':
                    self._clear_displays()
        except Exception as e:
            logger.error(f"Error processing updates: {e}")
        
        # Schedule next update
        if self.root:
            self.root.after(100, self._process_updates)
    
    def update_players(self, players: Dict[str, PlayerDisplay], seat_positions: Dict[str, Tuple[int, int]]):
        """Update player displays"""
        self.update_queue.append({
            'type': 'players',
            'data': (players, seat_positions)
        })
    
    def _update_player_displays(self, data):
        """Update the actual player display widgets"""
        players, seat_positions = data
        
        # Clear old displays
        for frame in self.player_frames.values():
            frame.destroy()
        self.player_frames.clear()
        
        # Create new displays for each player
        for position, player in players.items():
            if position in seat_positions:
                x, y = seat_positions[position]
                self._create_player_display(player, x, y)
    
    def _create_player_display(self, player: PlayerDisplay, x: int, y: int):
        """Create a display for a single player"""
        # Create frame for this player
        frame = tk.Frame(self.root, bg='black', highlightbackground='gray', highlightthickness=1)
        
        # Player name and category
        name_label = tk.Label(frame, 
                             text=f"{player.name} ({player.category})",
                             fg=player.color, bg='black',
                             font=('Arial', 10, 'bold'))
        name_label.pack()
        
        # Stats
        stats_text = f"VPIP: {player.vpip:.1f}% PFR: {player.pfr:.1f}%"
        if player.hands > 0:
            stats_text += f" ({player.hands}h)"
        
        stats_label = tk.Label(frame,
                              text=stats_text,
                              fg='white', bg='black',
                              font=('Arial', 9))
        stats_label.pack()
        
        # Suggestion if any
        if player.suggestion:
            sug_label = tk.Label(frame,
                                text=player.suggestion,
                                fg='yellow', bg='black',
                                font=('Arial', 8, 'italic'))
            sug_label.pack()
        
        # Position the frame
        frame.place(x=x + self.display_offset['x'], y=y + self.display_offset['y'])
        
        # Store reference
        self.player_frames[player.position] = frame
    
    def show_suggestion(self, suggestion: str, position: str = "center"):
        """Show a strategy suggestion"""
        self.update_queue.append({
            'type': 'suggestion',
            'data': (suggestion, position)
        })
    
    def _show_suggestion(self, data):
        """Display a strategy suggestion"""
        suggestion, position = data
        
        # Create suggestion window
        sug_frame = tk.Frame(self.root, bg='darkgreen', highlightbackground='green', highlightthickness=2)
        
        title = tk.Label(sug_frame,
                        text="💡 Suggestion",
                        fg='white', bg='darkgreen',
                        font=('Arial', 11, 'bold'))
        title.pack(padx=5, pady=2)
        
        text = tk.Label(sug_frame,
                       text=suggestion,
                       fg='lightgreen', bg='darkgreen',
                       font=('Arial', 10),
                       wraplength=250)
        text.pack(padx=5, pady=2)
        
        # Position based on parameter
        if position == "center":
            sug_frame.place(relx=0.5, rely=0.8, anchor='center')
        else:
            sug_frame.place(x=position[0], y=position[1])
        
        # Auto-hide after 5 seconds
        self.root.after(5000, sug_frame.destroy)
    
    def clear(self):
        """Clear all displays"""
        self.update_queue.append({'type': 'clear', 'data': None})
    
    def _clear_displays(self):
        """Clear all display widgets"""
        for frame in self.player_frames.values():
            frame.destroy()
        self.player_frames.clear()
    
    def stop(self):
        """Stop the overlay"""
        self.is_running = False
        if self.root:
            self.root.quit()
        logger.info("HUD Overlay stopped")
    
    def set_window_position(self, x: int, y: int, width: int, height: int):
        """Set the overlay window position to match poker table"""
        if self.root:
            self.root.geometry(f"{width}x{height}+{x}+{y}")