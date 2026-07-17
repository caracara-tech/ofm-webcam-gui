# OFM Webcam Viewer

A minimal PyQt5 + OpenCV application for streaming webcam feeds and capturing snapshots or recordings. Includes optional stage control functionality for precision microscopy setups.

## Features

- **Live Webcam Streaming**: Real-time video feed from USB cameras
- **Snapshot Capture**: Save individual frames as PNG images
- **Video Recording**: Record video clips as MP4 files
- **Stage Control**: Integrated control for Sangaboard precision stages
- **Simulation Mode**: Mock stage controller for testing without hardware
- **Backlash Compensation**: Optional backlash compensation for precise positioning
- **Camera Detection**: Automatic camera name detection (Windows, optional)
- **Multiple Backends**: Support for Media Foundation, DirectShow, and V4L2
- **Configurable Resolution**: Multiple resolution presets
- **Timestamp Overlay**: Optional timestamp burning into frames
- **Extensible Hardware Layer**: Abstract base classes for adding new hardware controllers

## Installation

### Prerequisites

- Python 3.7 or higher
- Virtual environment (recommended)

### Setup

```bash
# Clone or navigate to the project directory
cd ofm-webcam-gui

# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Basic Webcam Usage

```bash
python webcam_viewer.py
```

### Simulation Mode (No Hardware Required)

Test the GUI and stage control features without physical hardware:

```bash
python webcam_viewer.py --simulate
```

**Automatic Fallback**: If the app doesn't detect a connected stage controller, it will automatically fall back to simulation mode and display a message in the status bar.

In simulation mode:
- Stage control buttons work with a mock controller
- Movements are simulated with accelerated timing (10x faster)
- Position tracking and backlash compensation work as expected
- Window title shows "[SIMULATION]" to indicate mode
- Status bar shows "SIMULATION MODE: Stage controller not detected, using mock controller"
- Useful for UI testing, demonstrations, and development

### Controls

1. **Camera Setup**
   - Select device index (0, 1, 2...) in the spinbox
   - Choose backend (Media Foundation recommended for Windows)
   - Select resolution from dropdown
   - Click "Start Stream"

2. **Capture**
   - Click "Save Snapshot (PNG)" to capture current frame
   - Click "Start Recording (.mp4)" to begin video recording
   - Files are saved to `gallery/` folder in the project directory by default

3. **Stage Control** (if connected)
   - Use U/D/L/R buttons for XY movement
   - Use W/S buttons for Z movement (focus)
   - Adjust step sizes and speed using spinboxes
   - View live X, Y, Z position coordinates (updated in real-time)
   - Enable "Auto-Level Z" for backlash compensation

## Hardware Requirements

### Optional: Stage Control

For stage control functionality, you need:
- **Sangaboard** controller connected via USB (default)
- Default port: `COM5` (Windows) or `/dev/ttyACM0` (Linux)
- Install `sangaboard` Python package

**Note**: The codebase also includes an `ArduinoStageController` implementation for Arduino-based stages (default port: `COM12`). To use it instead of Sangaboard, modify the initialization code in `webcam_viewer.py`.

### Optional: Camera Name Detection (Windows)

For automatic camera name detection:
- Install `pygrabber` package (included in requirements.txt)
- Click "Detect Camera Names" button in the app

## Configuration

### Stage Port

Edit `webcam_viewer.py` line 233 to change the default port:

```python
self.stage = SangaboardStageController(port='COM5', timeout=2)
```

### Output Directory

Default output directory is `gallery/` in the project directory. Change via the "Browse" button in the app.

## Troubleshooting

### Camera won't start

- Try different device indices (0, 1, 2...)
- Switch backend from "Media Foundation" to "DirectShow" (Windows)
- Check if another application is using the camera
- Ensure camera drivers are installed

### Stage not connecting

- Verify Sangaboard is connected to the correct port
- Check device manager (Windows) or `/dev/tty*` (Linux)
- Ensure `sangaboard` package is installed
- Try increasing timeout value in the code

### Import errors

- Ensure virtual environment is activated
- Reinstall dependencies: `pip install -r requirements.txt`
- Check Python version compatibility (3.7+)

## Project Structure

```
ofm-webcam-gui/
├── webcam_viewer.py          # Main application
├── requirements.txt          # Python dependencies
├── hardware/
│   ├── __init__.py
│   ├── abstract.py          # Base controller classes
│   └── stage.py             # Stage controller implementations (Sangaboard, Arduino, Mock)
├── core/                     # Future shared utilities
├── helpers/                  # Future helper functions
├── logic/                    # Future algorithms/analysis
└── ui/                       # Future UI components
```

## Dependencies

- **PyQt5** - GUI framework
- **opencv-python** - Camera capture and image processing
- **numpy** - Array operations
- **sangaboard** - Sangaboard stage controller (optional)
- **pyserial** - Serial communication for Arduino stage controller (optional)
- **pygrabber** - Camera name detection (Windows, optional)

## License

This project is provided as-is for laboratory and educational use.

## Contributors

Pierre Padilla-Huamantinco, Caracara Tech

## Support

For issues related to:
- **Sangaboard hardware**: Refer to Sangaboard documentation
- **Camera compatibility**: Check OpenCV backend compatibility
- **Python dependencies**: Ensure correct Python version and virtual environment
