"""
Individual HUD windows for each player - draggable and non-blocking
"""
import tkinter as tk
from tkinter import ttk
import threading
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from loguru import logger
import json
from pathlib import Path


@dataclass
class PlayerStats:
    """Stats for a single player"""
    name: str
    vpip: float = 0.0
    pfr: float = 0.0
    three_bet: float = 0.0
    hands: int = 0
    category: str = "Unknown"
    color: str = "#FFFFFF"


class PlayerHUD:
    """Individual HUD window for a single player"""
    
    def __init__(self, player_name: str, position: str, x: int, y: int):
        self.player_name = player_name
        self.position = position
        self.window = None
        self.x = x
        self.y = y
        self.is_dragging = False
        self.drag_start_x = 0
        self.drag_start_y = 0
        
    def create_window(self):
        """Create the HUD window"""
        self.window = tk.Toplevel()
        self.window.title(f"HUD - {self.player_name}")
        
        # Window properties
        self.window.attributes('-topmost', True)
        self.window.attributes('-alpha', 0.9)
        self.window.overrideredirect(True)  # Remove title bar
        
        # Set initial position
        self.window.geometry(f"+{self.x}+{self.y}")
        
        # Main frame
        self.main_frame = tk.Frame(self.window, bg='#1a1a1a', 
                                   highlightbackground='#333333', 
                                   highlightthickness=1)
        self.main_frame.pack(fill='both', expand=True)
        
        # Make draggable
        self.main_frame.bind('<Button-1>', self.start_drag)
        self.main_frame.bind('<B1-Motion>', self.drag)
        self.main_frame.bind('<ButtonRelease-1>', self.stop_drag)
        
        # Player name label (also draggable)
        self.name_label = tk.Label(self.main_frame,
                                  text=self.player_name,
                                  fg='#FFFFFF', bg='#1a1a1a',
                                  font=('Arial', 10, 'bold'))
        self.name_label.grid(row=0, column=0, columnspan=2, padx=3, pady=1)
        self.name_label.bind('<Button-1>', self.start_drag)
        self.name_label.bind('<B1-Motion>', self.drag)
        
        # Stats labels
        self.vpip_label = tk.Label(self.main_frame,
                                   text="VPIP: --",
                                   fg='#CCCCCC', bg='#1a1a1a',
                                   font=('Arial', 9))
        self.vpip_label.grid(row=1, column=0, padx=3, sticky='w')
        
        self.pfr_label = tk.Label(self.main_frame,
                                  text="PFR: --",
                                  fg='#CCCCCC', bg='#1a1a1a',
                                  font=('Arial', 9))
        self.pfr_label.grid(row=1, column=1, padx=3, sticky='w')
        
        self.hands_label = tk.Label(self.main_frame,
                                    text="Hands: 0",
                                    fg='#999999', bg='#1a1a1a',
                                    font=('Arial', 8))
        self.hands_label.grid(row=2, column=0, columnspan=2, padx=3)
        
        self.category_label = tk.Label(self.main_frame,
                                       text="",
                                       fg='#FFFF00', bg='#1a1a1a',
                                       font=('Arial', 8, 'italic'))
        self.category_label.grid(row=3, column=0, columnspan=2, padx=3, pady=1)
        
    def start_drag(self, event):
        """Start dragging the window"""
        self.is_dragging = True
        self.drag_start_x = event.x
        self.drag_start_y = event.y
        
    def drag(self, event):
        """Handle dragging"""
        if self.is_dragging:
            x = self.window.winfo_x() + event.x - self.drag_start_x
            y = self.window.winfo_y() + event.y - self.drag_start_y
            self.window.geometry(f"+{x}+{y}")
            
    def stop_drag(self, event):
        """Stop dragging and save position"""
        self.is_dragging = False
        self.save_position()
        
    def save_position(self):
        """Save window position to file"""
        try:
            config_file = Path.home() / ".poker_hud_positions.json"
            positions = {}
            
            if config_file.exists():
                with open(config_file, 'r') as f:
                    positions = json.load(f)
            
            positions[self.position] = {
                'x': self.window.winfo_x(),
                'y': self.window.winfo_y()
            }
            
            with open(config_file, 'w') as f:
                json.dump(positions, f)
                
        except Exception as e:
            logger.debug(f"Could not save position: {e}")
    
    def load_position(self):
        """Load saved window position"""
        try:
            config_file = Path.home() / ".poker_hud_positions.json"
            
            if config_file.exists():
                with open(config_file, 'r') as f:
                    positions = json.load(f)
                    
                if self.position in positions:
                    saved = positions[self.position]
                    self.x = saved['x']
                    self.y = saved['y']
                    if self.window:
                        self.window.geometry(f"+{self.x}+{self.y}")
                        
        except Exception as e:
            logger.debug(f"Could not load position: {e}")
    
    def update_stats(self, stats: PlayerStats):
        """Update the displayed statistics"""
        if not self.window:
            return
            
        try:
            # Update name and color based on category
            self.name_label.config(text=f"{stats.name}",
                                 fg=stats.color)
            
            # Update stats
            self.vpip_label.config(text=f"VPIP: {stats.vpip:.1f}%")
            self.pfr_label.config(text=f"PFR: {stats.pfr:.1f}%")
            self.hands_label.config(text=f"Hands: {stats.hands}")
            
            # Update category
            if stats.category != "Unknown":
                self.category_label.config(text=stats.category)
                
        except Exception as e:
            logger.error(f"Error updating HUD stats: {e}")
    
    def close(self):
        """Close this HUD window"""
        if self.window:
            self.window.destroy()
            self.window = None


class HUDManager:
    """Manages multiple player HUD windows"""
    
    def __init__(self):
        self.huds = {}  # position -> PlayerHUD
        self.root = None
        self.is_running = False
        self.update_queue = []
        self.thread = None
        
        logger.info("HUD Manager initialized")
    
    def start(self):
        """Start the HUD manager"""
        if self.is_running:
            return
            
        self.is_running = True
        self.thread = threading.Thread(target=self._run)
        self.thread.daemon = True
        self.thread.start()
        logger.info("HUD Manager started")
    
    def _run(self):
        """Run the tkinter main loop"""
        try:
            self.root = tk.Tk()
            self.root.withdraw()  # Hide the main window
            
            # Process updates periodically
            self.root.after(100, self._process_updates)
            
            # Run the event loop
            self.root.mainloop()
            
        except Exception as e:
            logger.error(f"Error in HUD manager: {e}")
        finally:
            self.is_running = False
    
    def _process_updates(self):
        """Process queued updates"""
        if not self.is_running:
            return
            
        try:
            while self.update_queue:
                update = self.update_queue.pop(0)
                
                if update['type'] == 'create':
                    self._create_hud(update['position'], update['name'], 
                                   update['x'], update['y'])
                elif update['type'] == 'update':
                    self._update_hud(update['position'], update['stats'])
                elif update['type'] == 'remove':
                    self._remove_hud(update['position'])
                elif update['type'] == 'clear':
                    self._clear_all()
                    
        except Exception as e:
            logger.error(f"Error processing updates: {e}")
        
        # Schedule next update
        if self.root:
            self.root.after(100, self._process_updates)
    
    def create_or_update_hud(self, position: str, player_name: str, 
                           stats: PlayerStats, x: int, y: int):
        """Create or update a HUD for a player"""
        self.update_queue.append({
            'type': 'create',
            'position': position,
            'name': player_name,
            'x': x,
            'y': y
        })
        self.update_queue.append({
            'type': 'update',
            'position': position,
            'stats': stats
        })
    
    def _create_hud(self, position: str, player_name: str, x: int, y: int):
        """Create a new HUD window"""
        # Remove old HUD if exists
        if position in self.huds:
            self._remove_hud(position)
        
        # Create new HUD
        hud = PlayerHUD(player_name, position, x, y)
        hud.load_position()  # Load saved position if available
        hud.create_window()
        self.huds[position] = hud
        
        logger.debug(f"Created HUD for {player_name} at {position}")
    
    def _update_hud(self, position: str, stats: PlayerStats):
        """Update HUD statistics"""
        if position in self.huds:
            self.huds[position].update_stats(stats)
    
    def _remove_hud(self, position: str):
        """Remove a HUD window"""
        if position in self.huds:
            self.huds[position].close()
            del self.huds[position]
    
    def clear_all(self):
        """Clear all HUD windows"""
        self.update_queue.append({'type': 'clear'})
    
    def _clear_all(self):
        """Clear all HUD windows"""
        for hud in list(self.huds.values()):
            hud.close()
        self.huds.clear()
        logger.debug("Cleared all HUD windows")
    
    def stop(self):
        """Stop the HUD manager"""
        self.is_running = False
        if self.root:
            self.root.quit()
        logger.info("HUD Manager stopped")