# BetOnline Poker Assistant Setup Guide

## ✅ BetOnline Support is Ready!

The poker assistant now fully supports BetOnline with:
- Custom hand history parser for BetOnline format
- Automatic hand history monitoring
- Player statistics tracking
- HUD data extraction (if you use one)

## Quick Setup for BetOnline

### 1. Find Your BetOnline Hand History Folder

First, enable hand history saving in BetOnline:
1. Open BetOnline Poker client
2. Go to **Settings** or **Options**
3. Find **"Hand History"** settings
4. Enable **"Save Hand History to Disk"**
5. Note the folder path shown

Common locations:
- **Windows**: 
  - `C:\Users\[YourName]\Documents\BetOnline\HandHistory`
  - `C:\Users\[YourName]\AppData\Local\BetOnline\HandHistory`
  - `C:\BetOnline\HandHistory`
  
- **macOS**: 
  - `~/Documents/BetOnline/HandHistory`
  - `~/Library/Application Support/BetOnline/HandHistory`

### 2. Configure for BetOnline

Edit `config/betonline_settings.yaml`:

```yaml
# Your BetOnline username
hero_name: YourUsername  # ← Change this!

# Hand history folder - use YOUR actual path
hand_history:
  directories:
    - path: C:\Users\YourName\Documents\BetOnline\HandHistory  # ← Change this!
      site: betonline
```

### 3. Install Dependencies

```bash
# Install Python packages
pip install -r requirements.txt

# Install Tesseract OCR (if using HUD extraction)
# Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki
# macOS: brew install tesseract
# Linux: sudo apt-get install tesseract-ocr
```

### 4. Test BetOnline Parser

```bash
python test_betonline.py
```

You should see:
```
✓ Parsed hand #3890432123
✓ Saved hand to database
```

### 5. Run the Assistant

```bash
# Using BetOnline config
python src/main.py --config config/betonline_settings.yaml

# Or directly specify site
python src/main.py --site betonline
```

## Features That Work with BetOnline

### ✅ Working Now:
- **Hand History Parsing**: Reads BetOnline hand format
- **Player Statistics**: Tracks VPIP, PFR, 3bet, etc.
- **Database Storage**: Stores all hands and stats
- **Session Tracking**: Monitors your sessions
- **Real-time Monitoring**: Processes new hands as you play
- **Player Profiling**: Classifies opponents (TAG, LAG, FISH, etc.)

### 📊 Statistics Tracked:
- VPIP (Voluntarily Put $ In Pot)
- PFR (Pre-Flop Raise)
- 3-bet frequency
- C-bet frequency
- Aggression factor
- WTSD (Went to Showdown)
- W$SD (Won $ at Showdown)

### 🎯 Player Classifications:
Based on statistics, opponents are classified as:
- **NIT**: Very tight (VPIP < 15%)
- **TAG**: Tight Aggressive (VPIP 15-20%, high PFR)
- **REG**: Regular (VPIP 20-30%)
- **LAG**: Loose Aggressive (VPIP > 30%, high PFR)
- **FISH**: Loose Passive (VPIP > 35%, low PFR)

## BetOnline Hand Format Support

The parser handles:
- Tournament hands ✅
- Cash game hands ✅
- All-in situations ✅
- Multi-way pots ✅
- Split pots ✅
- Antes and blinds ✅

## Typical BetOnline Workflow

1. **Start BetOnline client** and join tables
2. **Run the assistant**:
   ```bash
   python src/main.py --config config/betonline_settings.yaml
   ```
3. **Play normally** - the assistant will:
   - Read new hands automatically
   - Build player statistics
   - Show opponent tendencies

4. **Check the console** for real-time updates:
   ```
   21:45:00 | INFO | Processing BetOnline hand #3890432123
   21:45:01 | INFO | Player 'Villain1' classified as LAG
   21:45:01 | INFO | Stats: VPIP: 35%, PFR: 28%, 3bet: 12%
   ```

## Troubleshooting BetOnline

### Hand histories not detected?
1. Make sure hand history saving is enabled in BetOnline
2. Check the folder path is correct in config
3. Try using absolute paths (C:\... not relative paths)
4. Make sure .txt files are being created when you play

### Parser errors?
- Send me a sample hand history and I'll update the parser
- The parser handles most standard BetOnline formats
- Tournament and cash game formats are both supported

### Finding table window position:
For screen capture features, you need the table window coordinates:

**Windows PowerShell**:
```powershell
# Click on BetOnline table first, then run:
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32 {
    [DllImport("user32.dll")]
    public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
}
public struct RECT {
    public int Left, Top, Right, Bottom;
}
"@
$handle = [Win32]::GetForegroundWindow()
$rect = New-Object RECT
[Win32]::GetWindowRect($handle, [ref]$rect)
echo "Add to config: x: $($rect.Left), y: $($rect.Top), width: $($rect.Right - $rect.Left), height: $($rect.Bottom - $rect.Top)"
```

## Sample Output with BetOnline

When running with BetOnline hands:
```
==================================================
POKER ASSISTANT - BETONLINE
==================================================
Site: betonline
Database: data/betonline_poker.db
==================================================
21:50:00 | INFO | Monitoring: C:\Users\You\Documents\BetOnline\HandHistory
21:50:15 | INFO | New hand detected: #3890432125
21:50:15 | INFO | Parsed BetOnline hand #3890432125
21:50:15 | INFO | Table: Table 5, Stakes: $0.50/$1.00
21:50:15 | INFO | Updated stats for 'Villain1': VPIP: 32%, PFR: 24%
21:50:15 | INFO | Player type: LAG (Loose Aggressive)
21:50:15 | INFO | Recommendation: 3bet more for value against this player
```

## Next Steps

1. **Enable hand history** in BetOnline client
2. **Update config** with your username and paths
3. **Run the assistant** while playing
4. **Monitor statistics** building up over time
5. **Use player classifications** to adjust strategy

## Need Help?

- The BetOnline parser is tested and working
- If you have unusual hand formats, share them and I'll update the parser
- Check `logs/betonline_assistant.log` for detailed debugging

## Advanced Features (Future)

Once basic tracking works, you can:
- Add HUD overlay display
- Integrate GTO ranges
- Set up multi-table support
- Create custom player notes
- Export statistics for analysis

The foundation for BetOnline is fully functional - just configure your paths and start playing!