# Poker Assistant

A real-time poker assistant that uses advanced computer vision and AI to track game state, calculate player statistics, and provide strategic insights. Specifically optimized for BetOnline and other major poker platforms.

## 🎯 Key Features

### Advanced Detection System
- **YOLO-based Object Detection**: Automatically detects player boxes, pot areas, and cards on the poker table
- **PaddleOCR Text Recognition**: Superior text extraction from stylized game graphics 
- **Card Classification**: Neural network-based card rank and suit recognition
- **Finite State Machine**: Intelligent hand reconstruction and tracking

### Real-Time Analysis
- **Live Table Reading**: Captures and analyzes poker table state in real-time
- **Player Statistics**: Tracks VPIP, PFR, 3-bet, and other key statistics
- **Hand History Reconstruction**: Creates hand histories from screen capture (perfect for sites without local history files)
- **Dynamic Window Detection**: Automatically finds and tracks poker windows

### HUD System
- **Individual Player HUDs**: Draggable, semi-transparent HUD windows for each player
- **Player Profiling**: Automatic classification (NIT, TAG, LAG, FISH, REG)
- **Color-Coded Stats**: Visual indicators for player types
- **Position Memory**: HUD positions are saved between sessions

### Database & Analysis
- **SQLAlchemy Database**: Comprehensive storage of all hands and player data
- **Session Tracking**: Monitor your sessions with win/loss tracking
- **Player Pool Analysis**: Build profiles on opponents over time
- **Statistical Calculations**: Real-time computation of all major poker statistics

## 🚀 Installation

### Prerequisites
```bash
# Python 3.8 or higher required
python --version
```

### Basic Installation
```bash
# Clone the repository
git clone https://github.com/xuzinann/poker-assistant.git
cd poker-assistant

# Install core dependencies
pip install -r requirements.txt
```

### Additional Dependencies for Advanced Features

#### For YOLO Detection (Recommended)
```bash
pip install ultralytics torch torchvision
```

#### For PaddleOCR (Better text recognition)
```bash
pip install paddlepaddle paddleocr
```

#### For Traditional OCR (Fallback)
```bash
# Ubuntu/Debian:
sudo apt-get install tesseract-ocr

# macOS:
brew install tesseract

# Windows: 
# Download from https://github.com/UB-Mannheim/tesseract/wiki
```

## ⚙️ Configuration

### Quick Start for BetOnline
The default configuration is optimized for BetOnline. Simply run:
```bash
python src/main.py
```

### Custom Configuration
Edit `config/settings.yaml`:

```yaml
# Poker site configuration
site: betonline  # Options: betonline, pokerstars, ggpoker
hero_name: YourUsername  # Will auto-detect if not set

# Detection settings
capture:
  update_interval: 1.0  # Seconds between captures
  
# HUD settings  
hud:
  enabled: true
  min_hands_for_stats: 30  # Minimum hands before showing stats
```

## 📖 Usage Guide

### Basic Usage

1. **Start BetOnline** and open a poker table
2. **Launch the assistant**:
   ```bash
   python src/main.py
   ```
3. The assistant will automatically:
   - Find your poker window
   - Detect your hero name (bottom position)
   - Start tracking hands and players
   - Display HUD windows for each player

### Testing Detection

Check if detection is working:
```bash
# Run calibration tool to see detection regions
python calibrate.py

# Test new YOLO detection pipeline
python test_new_detection.py

# Continuous detection test
python test_new_detection.py --continuous
```

### Debugging

If players aren't being detected:
1. Check `debug_screenshots/` folder for captured regions
2. Run `calibrate.py` to verify detection areas
3. Check logs for detection confidence scores

## 🏗️ Architecture

### Detection Pipeline
```
Screen Capture (mss)
    ↓
YOLO Object Detection (finds game elements)
    ↓
PaddleOCR (reads text from detected regions)
    ↓
FSM (reconstructs complete hands)
    ↓
Database (stores all data)
    ↓
HUD Display (shows stats)
```

### Project Structure
```
poker-assistant/
├── src/
│   ├── capture/          # Screen capture and window detection
│   ├── detection/        # YOLO, PaddleOCR, card classification
│   ├── database/         # SQLAlchemy models and management
│   ├── overlay/          # HUD display system
│   ├── analysis/         # Statistical calculations
│   └── main.py          # Main application entry
├── config/              # Configuration files
├── test_*.py           # Test scripts
└── calibrate.py        # Calibration tool
```

## 🔧 Troubleshooting

### Common Issues

**No players detected**
- Ensure poker table is visible and not minimized
- Run `calibrate.py` to check detection regions
- Try adjusting window size or resolution

**OCR confidence too low**
- The new YOLO+PaddleOCR pipeline should fix this
- Ensure you've installed paddleocr: `pip install paddleocr`
- Check that game graphics are clear (not blurry)

**HUD not appearing**
- Check that `hud.enabled: true` in settings.yaml
- Look for small draggable windows (they may be minimized)
- Check logs for HUD creation messages

**Hand tracking issues**
- Verify hero name is detected correctly (check logs)
- Ensure community cards are visible on table
- Check that pot size is being detected

## 🧪 Development

### Running Tests
```bash
# Test basic functionality
python test_assistant.py

# Test BetOnline parser
python test_betonline.py

# Test new detection pipeline
python test_new_detection.py
```

### Code Quality
```bash
# Format code
black src/

# Type checking  
mypy src/

# Linting
flake8 src/
```

### Adding New Sites
1. Create parser in `src/history/[site]_parser.py`
2. Add window patterns in `src/capture/window_detector.py`
3. Register in `src/history/parser_factory.py`
4. Add configuration in `config/settings.yaml`

## 📊 Statistics Tracked

- **VPIP** (Voluntarily Put In Pot): How often player enters pots
- **PFR** (Pre-Flop Raise): How often player raises pre-flop
- **3-Bet**: Frequency of re-raising
- **AF** (Aggression Factor): Ratio of aggressive to passive actions
- **WTSD** (Went to ShowDown): How often player goes to showdown
- **Stack Size**: Current chip count
- **Position**: Table position relative to dealer

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

MIT License - See LICENSE file for details

## 🙏 Acknowledgments

- Built with love for the poker community
- Special thanks to BetOnline players for testing
- Powered by YOLO, PaddleOCR, and PyTorch

## ⚠️ Disclaimer

This tool is for educational and analytical purposes. Always follow the terms of service of your poker platform. The assistant provides information only - all decisions remain the responsibility of the player.

## 📞 Support

For issues or questions:
- Open an issue on [GitHub](https://github.com/xuzinann/poker-assistant/issues)
- Check existing issues for solutions
- Include debug screenshots when reporting detection problems

---

**Last Updated**: 2024
**Version**: 2.0 (with YOLO detection)
**Author**: xuzinann