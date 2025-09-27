# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Development Commands

### Running the Application
```bash
# Main application with default settings
python src/main.py

# With custom configuration
python src/main.py --config config/settings.yaml --site pokerstars

# With BetOnline configuration
python src/main.py --config config/betonline_settings.yaml

# Enable debug logging
python src/main.py --debug
```

### Testing
```bash
# Run general tests
python test_assistant.py

# Test BetOnline parser specifically
python test_betonline.py

# Run pytest tests (when available)
pytest tests/
```

### Code Quality
```bash
# Format code with black
black src/

# Type checking
mypy src/

# Linting
flake8 src/
```

### Dependencies
```bash
# Install all dependencies
pip install -r requirements.txt

# System dependencies needed:
# - tesseract-ocr (for OCR functionality)
# - libgl1-mesa-glx (Linux, for OpenCV)
```

## Architecture Overview

This is a real-time poker assistant that monitors poker games and provides statistics and strategy recommendations. The system operates through several interconnected components:

### Core Flow
1. **Screen Capture** → Captures poker table regions from the screen
2. **OCR Processing** → Extracts text from captured images using Tesseract/EasyOCR
3. **HUD Extraction** → Reads player statistics from existing HUD displays
4. **Hand History Monitoring** → Watches hand history files for new hands
5. **Database Storage** → SQLAlchemy-based SQLite database for all game data
6. **Analysis Engine** → Calculates statistics and generates player profiles
7. **Main Loop** → Coordinates all components with configurable update intervals

### Key Components

**Database Layer (`src/database/`)**
- `models.py`: SQLAlchemy models for Player, Hand, Action, Session tables
- `manager.py`: Database operations, statistics calculations, player profiling

**Screen Capture (`src/capture/`)**
- `screen_capture.py`: MSS-based screen capture with region management
- `ocr_engine.py`: OCR text extraction using pytesseract or EasyOCR

**Hand History Parsing (`src/history/`)**
- `parser_factory.py`: Factory pattern for multi-site parser support
- `hand_parser.py`: Base parser and PokerStars implementation
- `betonline_parser.py`: BetOnline-specific parser
- `history_monitor.py`: Watchdog-based file monitoring for new hands

**HUD Integration (`src/hud/`)**
- `hud_extractor.py`: Extracts and interprets HUD statistics from screen

**Configuration (`config/`)**
- YAML-based configuration for sites, paths, and settings
- Site-specific configurations (e.g., `betonline_settings.yaml`)

### Multi-Site Support
The system uses a factory pattern for parser selection, supporting:
- PokerStars (default)
- BetOnline (fully implemented)
- GGPoker, PartyPoker (extendable)

### Player Profiling System
Automatically classifies players based on statistics:
- NIT: VPIP < 15%
- TAG: VPIP 15-20%, high PFR
- REG: VPIP 20-30%
- LAG: VPIP > 30%, high PFR
- FISH: VPIP > 35%, low PFR

### Session Management
Tracks playing sessions with:
- Start/end times
- Hands played
- Win/loss tracking
- Site-specific statistics

## Important Patterns

### Parser Factory Pattern
New site parsers should:
1. Inherit from `HandParser` base class
2. Implement `parse()` method for site-specific format
3. Register in `ParserFactory.get_parser()`

### Database Operations
- All database operations go through `DatabaseManager`
- Statistics are calculated on-demand from raw action data
- Player profiles are updated after each hand

### Configuration Hierarchy
1. Default configuration in `main.py`
2. YAML file configuration
3. Command-line arguments (highest priority)

### Error Handling
- Extensive logging with loguru
- Graceful degradation for OCR/capture failures
- Signal handlers for clean shutdown

## Current State

### Working Features
- Complete database layer with SQLAlchemy
- Hand history parsing for PokerStars and BetOnline
- Automatic hand history file monitoring
- Player statistics calculation (VPIP, PFR, 3bet, etc.)
- Player profiling and classification
- Session tracking
- OCR framework setup

### Not Yet Implemented
- Overlay UI display (PyQt5 structure exists but not rendered)
- GTO range integration
- Real-time table detection
- Multi-table support
- Advanced exploitative algorithms

## Testing Approach

The codebase includes test files:
- `test_assistant.py`: General functionality tests
- `test_betonline.py`: BetOnline parser tests

Tests verify:
- Database operations
- Hand parsing accuracy
- OCR initialization
- End-to-end flow