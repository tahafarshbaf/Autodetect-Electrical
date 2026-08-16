# Vision Scan

An intelligent electrical equipment detection and analysis system powered by YOLO object detection and Streamlit. Vision Scan automatically detects, counts, and generates detailed reports of electrical components in panel images.

## 🎯 Features

- **Real-time Object Detection**: Uses YOLO v8 to detect electrical components (MCBs, Contactors, Relays, etc.)
- **Multiple Input Methods**: Upload images or paste from clipboard
- **Confidence Tuning**: Adjustable confidence threshold for precise detection
- **Excel Export**: Generate formatted BOQ (Bill of Quantities) reports
- **Batch Processing**: Process multiple images efficiently
- **OCR Support**: Optional text extraction from images using PaddleOCR
- **Batch File Renaming**: Utility to organize image files systematically

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- CUDA-capable GPU (optional, recommended for faster inference)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd visionscan
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Download YOLO model weights**
   - Place your trained YOLO model at the path specified in `main.py` (or use a pretrained model like `yolov8n.pt`)
   - Update `MODEL_PATH` in `main.py` with your model location

### Running the Application

```bash
streamlit run main.py
```

The app will open at `http://localhost:8501`

## 📋 Project Structure

```
visionscan/
├── main.py              # Main Streamlit application
├── OCR.py               # PaddleOCR text extraction module
├── excel_export.py      # Excel report generation & BOQ template filling
├── file_renamer.py      # Batch file renaming utility
├── requirements.txt     # Python dependencies
├── LICENSE
└── README.md           # This file
```

## 🔧 Configuration

### main.py
- `LOGO_PATH`: Path to your company logo (PNG/JPG)
- `MODEL_PATH`: Path to your YOLO model weights
- `confidence_threshold`: Detection confidence level (0.0-1.0)

### OCR.py
- `IMAGE_PATH`: Image file to process
- `LANG`: Language for text detection (e.g., "en", "ch")
- `CONFIDENCE_THRESHOLD`: OCR confidence cutoff (0.0-1.0)

### excel_export.py
Configurable BOQ template structure:
- `BLOCK_HEIGHT`: Rows between panel blocks (default: 41)
- `DATA_ROWS_PER_BLOCK`: Element rows per panel (default: 30)
- `COL_DESCRIPTION`, `COL_RANGE`, `COL_QTY`: Column mappings

## 📖 Usage Guide

### Detection & Analysis
1. Open the Streamlit app
2. Select an image:
   - **Manual Upload**: Click to upload JPG/PNG files
   - **Clipboard**: Copy an image and click "Read Latest Image from Clipboard"
3. Adjust the confidence threshold in the sidebar if needed
4. View detected elements with confidence scores
5. Export results to Excel

### File Renaming Utility
```bash
python file_renamer.py
```
Enter folder path, extension, and optional prefix to batch rename files.

### OCR Text Extraction
```bash
python OCR.py
```
Edit `IMAGE_PATH` and `LANG` in the script, then run to extract text.

## 🎨 Supported Electrical Components

The model is trained to detect:
- **MCB** (Miniature Circuit Breaker) - 1P, 2P, 3P, 4P
- **Contactor** - 3P, 4P
- **Relay** - Various types
- *Add your custom classes based on your trained model*

## 📊 Excel Export Format

Detections are exported into a structured Excel template with:
- **Component Description**: Element type (MCB, Contactor, etc.)
- **Specification**: Detailed specs (1P, 3P, etc.)
- **Quantity**: Count of detected items
- **Organized by Panel**: Multiple panels per worksheet

## 🛠️ Development

### Adding Custom Classes
1. Train your YOLO model with additional classes
2. Update class names in your model weights file
3. Update `excel_export.py` if new naming conventions are needed

### Extending the App
- Modify `run_detection()` in `main.py` to add post-processing
- Add filters or analytics to the export function
- Integrate with external reporting systems

## ⚙️ Requirements

See `requirements.txt` for all dependencies:
- streamlit
- pillow (PIL)
- ultralytics (YOLO)
- pandas
- openpyxl
- paddleocr
- paddlepaddle

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| Model not found | Check `MODEL_PATH` in `main.py` |
| Clipboard paste fails | Ensure app runs on same machine as server |
| OCR not working | Run `pip install paddlepaddle paddleocr` |
| Low detection accuracy | Adjust `confidence_threshold` or retrain model |
| Slow inference | Use smaller YOLO model (e.g., `yolov8n.pt`) or GPU |

## 📄 License

See [LICENSE](LICENSE) for details.

## 👤 Author

Developed for electrical panel analysis and documentation.

## NAMES
1) Panel Scope
2) AutoDetect Electrical