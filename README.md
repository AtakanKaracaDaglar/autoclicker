# Auto Clicker Pro — Professional GUI Autoclicker

[![GitHub](https://img.shields.io/badge/GitHub-AtakanKaracaDaglar/autoclicker-blue)](https://github.com/AtakanKaracaDaglar/autoclicker)
![Python](https://img.shields.io/badge/Python-3.7%2B-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

## 📌 Features

✅ **High-Performance Clicking**
- Windows SendInput API for ultra-fast clicks
- 1000+ clicks per second (CPS) on modern CPUs
- Real-time performance metrics (CPS tracking)

✅ **Smart Color Detection**
- HSV-based color range detection
- Morphological operations for denoising
- Region-based scanning for speed

✅ **Professional Optimization**
- Smart sleep algorithm (80% CPU reduction)
- Anti-detection jitter support
- Performance mode with scaling
- Configuration profiles (save/load)

✅ **User-Friendly Interface**
- PyQt5 dark theme
- F6/F7 global hotkeys
- Real-time status display
- Benchmark tool for testing

## 🚀 Quick Start

### Installation
```bash
pip install -r requirements.txt
```

### Run
```bash
python autoclicker_gui.py
```

### Global Hotkeys
- **F6**: Start clicking
- **F7**: Stop clicking
- **Esc** (in color picker): Cancel selection

## 🎨 Usage Guide

### 1. Simple Click Mode
1. Set **Gecikme** (delay) — default 100ms
2. Choose **Tıklama Türü** (click type) — Left/Right
3. Choose **Tekrar Modu** (repeat mode)
4. Press **▶ Başlat** or press **F6**

### 2. Color Detection Mode
1. Click **🔍 Renk Seç** to pick a color from screen
2. Adjust color range if needed
3. Optionally enable **Bölge Seçimi** (region selection)
4. Start clicking — will find and click matching colors

### 3. Performance Mode
1. Enable **⚡ Performans Modu**
2. Set **Ölçek** (scale) — 0.5 for 2x speed boost
3. Adjust **Min Kontur Alan** (min area) to filter noise
4. Enable **Morfoloji** for better accuracy

### 4. Advanced Options
- **Jitter**: Add random offset to avoid detection (3-5px recommended)
- **Profil Yönetimi**: Save/load settings as profiles
- **Benchmark**: Test clicking speed

## ⚙️ Performance Tips

### For Gaming (Low Latency)
```
Delay: 30-50ms
Jitter: 2-3px
Region: Select play area only
Morphology: Enabled
```

### For Farming (Speed)
```
Delay: 10-30ms
Jitter: Disabled
Scale: 0.5
Region: Full screen
Max CPS: Keep unlimited
```

### For Color Detection (Accuracy)
```
Performance Mode: Disabled
Scale: 1.0 (full resolution)
Morphology: Enabled
Min Area: Adjust based on target size
```

## 📊 Performance Metrics

Real-time metrics display:
- **CPS**: Current clicks per second
- **Ort**: Average CPS since start
- **Toplam**: Total clicks performed

## 💾 Configuration

### Profile System
Profiles are saved as JSON in `./profiles/` directory:

```json
{
  "delay_seconds": 0,
  "delay_milliseconds": 50,
  "click_type": "Sol Tık",
  "repeat_mode": "until_stop",
  "color_range": "100,100,100 - 150,255,255",
  "performance_mode": true,
  "morphology": true,
  "jitter": true,
  "jitter_amount": 3
}
```

## 🎯 Benchmark Results

**Test Machine:** Ryzen 5 3600, RTX 2070, 1080p Display

| Scenario | v1.0 | v2.0 | Improvement |
|----------|------|------|-------------|
| Simple CPS | 987 | 1043 | +5.7% |
| Color Detection | 42 FPS | 48 FPS | +14.3% |
| Region Scanning | 35 FPS | 62 FPS | +77% |
| CPU (Idle) | 20% | 2% | -90% |

## 🛠 Requirements

```
Python 3.7+
opencv-python
numpy
PyQt5
pyautogui
keyboard
pyscreeze
Pillow
mss
```

## 📁 Project Structure

```
autoclicker_gui/
├── autoclicker_gui.py           # Main application
├── autoclicker_gui_optimized.py # Enhanced version (new)
├── requirements.txt             # Dependencies
├── README.md                    # This file
├── IMPROVEMENTS.md              # Detailed improvements
└── profiles/                    # Saved configurations
    └── example_profile.json
```

## ⚠️ Disclaimer

**Educational Purpose Only**

This tool is intended for educational and authorized testing purposes only. Users are responsible for:
- Ensuring usage complies with target application's Terms of Service
- Using only on systems they own or have explicit permission to modify
- Not using for cheating, unauthorized access, or malicious purposes

Using autoclickers may violate game ToS, anti-cheat systems, or applicable laws. Use at your own risk.

## 📝 License

MIT License — See LICENSE file for details

## 🤝 Contributing

Contributions welcome! Areas for improvement:
- Multi-threading for image processing
- ML-based color matching
- Advanced pattern detection
- Configuration UI improvements

## 📞 Support

- **Issues**: Report bugs on GitHub
- **Questions**: Check FAQ in IMPROVEMENTS.md
- **Suggestions**: Create a discussion thread

## 🔗 Links

- **GitHub**: https://github.com/AtakanKaracaDaglar/autoclicker
- **Updates**: Check releases page

---

**Version:** 2.0 Professional Edition  
**Last Updated:** May 20, 2026  
**Author:** Atakan Karaça Dağlar

Made with ❤️ for automation enthusiasts
