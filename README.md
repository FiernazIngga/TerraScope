
# TerraScope

**An Interactive Geospatial Analysis and Simulation Platform.**

TerraScope is a geospatial platform designed to explore, analyze, visualize, and simulate spatial data through an interactive mapping environment.

The platform aims to support various geospatial applications, including environmental monitoring, disaster risk analysis, land cover prediction, and spatial modeling.

## Features

- Interactive geospatial visualization.
- Spatial data analysis.
- Scenario-based simulation.
- Geographic data management.
- Support for multiple geospatial datasets.
- Modular architecture for different geospatial applications.

## Technology Stack

- **Programming Language:** Python 3.11
- **Desktop Framework:** PySide6
- **Map Rendering Engine:** MapLibre GL JS
- **Geospatial Data Format:** GeoJSON

## Requirements

- Python 3.11
- Git
- pip
- Internet connection for online basemap services.

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/FiernazIngga/TerraScope.git
cd TerraScope
```

### 2. Create a Virtual Environment

```bash
python3.11 -m venv venv
```

### 3. Activate the Virtual Environment

**Linux:**

```bash
source venv/bin/activate
```

**Windows:**

```bash
venv\Scripts\activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Run the Application

```bash
python app.py
```

## Project Structure

```text
TerraScope/
├── app.py
├── assets/
├── core/
├── data/
├── maps/
├── simulation/
├── ui/
├── utils/
├── visualization/
├── requirements.txt
└── README.md
```

## Mapping Resources

- **Map Rendering:** MapLibre GL JS
- **Basemap Services:** OpenFreeMap
- **Spatial Data:** Locally stored geospatial datasets.

## Notes

- An internet connection is required for online basemap services.
- Map rendering libraries and application resources are stored locally.
- Additional modules and geospatial analysis capabilities can be developed independently.

## License

License information will be added in a future release.
