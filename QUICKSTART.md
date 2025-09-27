# Poker Assistant - Quick Start Guide

## Overview
Real-time poker assistant with HUD integration, hand history tracking, and GTO/exploitative strategy suggestions.

## Key Features
- ✅ **Database System**: SQLite database for player stats and hand histories
- ✅ **Screen Capture**: Real-time screen capture with configurable regions
- ✅ **OCR Engine**: Text extraction from poker tables and HUD
- ✅ **HUD Extraction**: Read and store HUD statistics
- ✅ **Hand History Parser**: Parse PokerStars and other formats
- ✅ **Hand History Monitor**: Auto-detect and monitor hand history files
- ✅ **Player Profiling**: Classify players (NIT, TAG, LAG, FISH)
- ✅ **Statistics Calculation**: Calculate VPIP, PFR, 3bet, and more

## Installation

1. **Install Python Dependencies**:
```bash
pip3 install -r requirements.txt
```

2. **Install System Dependencies**:
```bash
# For Ubuntu/Debian:
sudo apt-get install tesseract-ocr libgl1-mesa-glx

# For macOS:
brew install tesseract

# For Windows:
# Download Tesseract from https://github.com/UB-Mannheim/tesseract/wiki
```

## Configuration

Edit `config/settings.yaml` to configure:
- Poker site (pokerstars, ggpoker, etc.)
- Table window position
- Hand history directories
- HUD settings
- Database location

## Running the Application

### Main Application
```bash
python3 src/main.py
```

### With Custom Settings
```bash
python3 src/main.py --config my_config.yaml --site pokerstars
```

### Run Tests
```bash
python3 test_assistant.py
```

## Architecture

```
poker-assistant/
├── src/
│   ├── capture/        # Screen capture & OCR
│   ├── database/       # Database models & manager
│   ├── hud/           # HUD extraction
│   ├── history/       # Hand history parsing
│   ├── analysis/      # Strategy analysis
│   └── ui/            # Overlay interface
├── data/              # Database & cache files
└── config/            # Configuration files
```

## How It Works

1. **Screen Capture**: Continuously captures poker table regions
2. **OCR Processing**: Extracts text from captured images
3. **HUD Reading**: Extracts player statistics from HUD
4. **Hand Monitoring**: Watches hand history files for new hands
5. **Database Storage**: Stores all data in SQLite database
6. **Analysis**: Calculates statistics and generates recommendations
7. **Display**: Shows recommendations via overlay (future feature)

## Current Capabilities

### What Works
- Database creation and management
- Hand history parsing (PokerStars format)
- OCR text extraction setup
- HUD statistics extraction framework
- Player statistics calculation
- Hand history file monitoring
- Session tracking

### Next Steps for Full Functionality
1. **Overlay UI**: Implement PyQt5 overlay for displaying suggestions
2. **GTO Integration**: Add pre-solved GTO ranges
3. **Real-time Detection**: Implement table/window detection
4. **Multi-table Support**: Handle multiple tables simultaneously
5. **More Sites**: Add parsers for GGPoker, PartyPoker, etc.

## Testing

Run the test suite to verify installation:
```bash
python3 test_assistant.py
```

Expected output:
- Database operations ✓
- Hand parsing ✓
- OCR initialization ✓
- Complete flow test ✓

## Usage Example

```python
from src.database.manager import DatabaseManager
from src.history.hand_parser import PokerStarsParser

# Initialize database
db = DatabaseManager("data/poker.db")

# Parse a hand
parser = PokerStarsParser()
hand = parser.parse(hand_text)

# Get player stats
stats = db.get_player_stats("PlayerName", "PokerStars")
print(f"VPIP: {stats['vpip']}%, PFR: {stats['pfr']}%")
```

## Troubleshooting

1. **OCR not working**: Ensure Tesseract is installed
2. **Database errors**: Check file permissions in data/ directory
3. **Import errors**: Verify all dependencies are installed
4. **Screen capture issues**: Check monitor index in settings

## Security Note

- Never store passwords or sensitive data
- Hand histories may contain personal information
- Use only for personal analysis on your own games

## Development Status

This is a functional foundation that includes:
- Complete database layer
- Hand history parsing
- Screen capture framework
- HUD extraction system
- Statistics calculation

Ready for expansion with:
- Real-time overlay UI
- GTO solver integration
- Advanced exploitative algorithms
- Multi-site support