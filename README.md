# Poker Assistant

Real-time GTO and exploitative poker strategy assistant with HUD integration and hand history tracking.

## Features

- **Screen Capture & OCR**: Real-time reading of poker tables and HUD data
- **Hand History Tracking**: Automatic capture and parsing of hand histories
- **Player Database**: Comprehensive player statistics and profiling
- **GTO/Exploitative Engine**: Strategy suggestions based on game theory and opponent tendencies
- **Overlay UI**: Non-intrusive display of recommendations
- **Multi-table Support**: Handle multiple tables simultaneously

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/poker-assistant.git
cd poker-assistant

# Install dependencies
pip install -r requirements.txt

# Install Tesseract OCR (required for pytesseract)
# Ubuntu/Debian:
sudo apt-get install tesseract-ocr
# macOS:
brew install tesseract
# Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki

# Run the application
python src/main.py
```

## Configuration

Edit `config/settings.yaml` to configure:
- Poker site settings
- Screen capture regions
- Database preferences
- HUD stat mappings

## Usage

1. Start your poker client
2. Launch the Poker Assistant
3. Configure screen regions for table and HUD
4. The assistant will provide real-time suggestions

## Development

```bash
# Run tests
pytest tests/

# Format code
black src/

# Type checking
mypy src/
```

## License

MIT License