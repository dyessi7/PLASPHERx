# PLASPHERx — SPHEREx Infrared Sky Viewer

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19-61DAFB.svg?logo=react&logoColor=black)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-8-646CFF.svg?logo=vite&logoColor=white)](https://vitejs.dev/)
[![Astropy](https://img.shields.io/badge/Astropy-6.1+-FF6F00.svg?logo=python&logoColor=white)](https://www.astropy.org/)
[![Tests](https://img.shields.io/badge/Tests-22%20passed-brightgreen.svg)]()
[![NASA Space Apps Challenge](https://img.shields.io/badge/NASA%20Space%20Apps-2026-blue.svg)](https://www.spaceappschallenge.org/)

**PLASPHERx (SPHEREx Sky Viewer)** is an interactive, real-time web platform for exploring time-domain astrophysics and celestial variability in the infrared sky using data from NASA's **SPHEREx** (Spectro-Photometer for the History of the Universe, Epoch of Reionization, and Ices Explorer) space telescope.

Unlike static catalog browsers, PLASPHERx dynamically queries the **NASA/IPAC Infrared Science Archive (IRSA)**, performs on-the-fly WCS reprojection, co-adds survey epochs, calculates difference images, and measures aperture photometry across all 6 SPHEREx detector bands ($0.75\,\mu\text{m}$ to $5.0\,\mu\text{m}$).

---

## 🌌 The Scientific Challenge & Motivation

NASA's SPHEREx mission is mapping the entire celestial sphere every six months in 102 infrared spectral bands. This unprecedented dataset contains millions of transient events, variable stars, and moving solar system bodies. However:
- **Massive Data Scale**: Raw Level-2 FITS files are large, multi-extension arrays with non-linear coordinate grids (`WCS-TAB`).
- **High Barrier to Entry**: Citizen scientists, students, and researchers need immediate, intuitive visual access to temporal sequences without downloading gigabytes of FITS files and writing custom reduction scripts.
- **Detector Artifacts**: Bright astronomical sources saturate infrared detectors, leaving `NaN` gaps in raw images that traditional pipelines misrepresent as empty dark sky.

**PLASPHERx bridges this gap**: A high-performance, purely dynamic web interface that turns NASA's archive into a live infrared telescope in your browser.

---

## 🚀 Key Features

### 1. Progressive Infrared Frame Player
- Enter any celestial coordinates ($\text{RA}$, $\text{Dec}$, $\text{FOV}$) or select suggested high-interest targets.
- Streams and aligns observations chronologically, animating subtle infrared changes over time.
- Direct extraction of observed central wavelength ($\lambda$) from the FITS tabular WCS.
- Keyboard navigation (Space to play/pause, Arrow keys to step frames).

### 2. Epoch Stacking & Difference Imaging
- Automatically clusters temporal observations into SPHEREx survey epochs based on scan timeline gaps (e.g., 45-day threshold).
- Computes co-added stacks via noise-resistant mean averaging (`nanmean`) with shared photometric stretch limits across epochs.
- Performs consecutive difference imaging ($\text{Epoch}_B - \text{Epoch}_A$) to immediately highlight stellar pulsations, circumstellar disc eclipses, or fast proper motion.

### 3. Multi-Band Spectral Photometry
- Measures aperture photometry at the target position, converting surface brightness ($\text{MJy/sr}$) to integrated physical flux ($\text{mJy}$).
- Scans all 6 SPHEREx detectors (`D1` through `D6`) concurrently to construct a complete spectrophotometric curve ($0.75\,\mu\text{m}$ to $5.0\,\mu\text{m}$).
- Plots interactive flux vs. wavelength charts with photometric error bars ($\sigma$) and tabular data.

### 4. Smart Saturation Handling & Astrophotometric Rigor
- Reads the official SPHEREx `FLAGS` HDU extension (`OVERFLOW` and `SUR_ERROR` bits).
- Renders saturated cores in natural bright white rather than misleading black holes.
- Rigorously flags saturated aperture measurements as scientific **lower limits** ($\ge$), drawing them as distinct hollow indicators on spectral plots.

### 5. Kinematic Proper Motion Engine
- Implements linear astrometric kinematic propagation for high-proper-motion targets (e.g., Barnard's Star, WISE 0855), ensuring correct coordinate pointing for epoch J2026.0+.

---

## 🛠️ System Architecture

PLASPHERx is built with a decoupled, high-throughput microservices architecture:

```
┌────────────────────────────────────────────────────────┐
│                   Frontend (Client)                    │
│   React 19 + Vite · Pure CSS Dark Mode · Recharts UI   │
└───────────────────────────┬────────────────────────────┘
                            │ HTTP / JSON / Streaming PNG
┌───────────────────────────▼────────────────────────────┐
│                    Backend (FastAPI)                   │
│  - SIA Query Resolver      - WCS Reprojection Engine   │
│  - Epoch Clustering        - Aperture Photometer       │
│  - Concurrency Semaphore   - LRU 2-GiB Disk Cache      │
└───────────────────────────┬────────────────────────────┘
                            │ HTTPS / SIA & Cutout API
┌───────────────────────────▼────────────────────────────┐
│         NASA/IPAC Infrared Science Archive (IRSA)       │
│              SPHEREx Level-2 Data Products             │
└────────────────────────────────────────────────────────┘
```

- **Zero Precomputed Static Assets**: All images, differences, and spectra are computed dynamically on demand.
- **Pure Memory Pipeline**: Processing operates on in-memory `bytes` streams, minimizing I/O bottlenecks.
- **Respectful to NASA Infrastructure**: A concurrency semaphore throttles outbound connections to IRSA, preventing IP rate-limiting.
- **Multi-Tiered LRU Cache**: Automatically caches raw FITS, processed PNGs, and search metadata on disk up to 2 GiB with least-recently-used eviction.

---

## 📊 Predefined Demonstration Targets

| Target | RA (J2000) | Dec (J2000) | Type | Phenomenon |
| :--- | :---: | :---: | :---: | :--- |
| **R Draconis** | `248.1675°` | `+66.7550°` | Variable | Mira-type pulsating red giant with drastic infrared amplitude |
| **RW Aurigae** | `76.9564°` | `+30.4014°` | Variable | Young stellar object experiencing circumstellar disc occultations |
| **Barnard's Star** | `269.4521°` | `+4.6934°` | Mover | Fastest proper-motion star in the sky ($10.36''/\text{yr}$) |
| **WISE 0855-0714** | `133.7599°` | `-7.2422°` | Mover | Ultra-cold sub-stellar brown dwarf near the solar neighborhood |
| **Epsilon Indi B** | `331.0960°` | `-56.8010°` | Mover | Binary brown dwarf system with substantial proper motion |

---

## ⚡ Quickstart & Installation

### Prerequisites
- **Node.js** v20+
- **Python** 3.11 or 3.12

### 1. Backend Setup

```powershell
# Navigate to backend directory
cd backend

# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install scientific dependencies
pip install -r requirements.txt

# Run the development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
- API Docs (Swagger): `http://localhost:8000/docs`
- Healthcheck: `http://localhost:8000/api/health`

### 2. Frontend Setup

```powershell
# In a new terminal, navigate to frontend directory
cd frontend

# Install Node dependencies
npm install

# Start Vite development server
npm run dev
```
- Web Application: `http://localhost:5173`

### 3. Automated Test Suite

PLASPHERx includes comprehensive unit and integration tests covering coordinate kinematics, FITS alignment, WCS extraction, and API contracts:

```powershell
$env:PYTHONPATH="backend"
pytest backend/tests -v
```
**Test Results:** `22 passed in 0.35s` (100% passing).

---

## 🛰️ NASA Data Integration & Open Science

- **Primary Source**: NASA/IPAC Infrared Science Archive (IRSA), California Institute of Technology.
- **Mission**: NASA SPHEREx (Spectro-Photometer for the History of the Universe, Epoch of Reionization and Ices Explorer).
- **Protocols Used**: IVOA Simple Image Access (SIA v1) and IRSA Cutout API (`/ibe/data/spherex`).
- **Data Products**: SPHEREx Level 2 calibrated spectral images (`IMAGE`, `WCS-TAB`, and `FLAGS` extensions).

---

## 📜 References & Acknowledgments

- **Astropy Collaboration** (2022). Astropy: A community Python library for astronomy. *Astronomy & Astrophysics*.
- **IRSA / IPAC**: Infrared Science Archive operated by the Jet Propulsion Laboratory, California Institute of Technology, under contract with NASA.
- **FastAPI**: Modern, fast web framework for building APIs with Python.
- **React & Vite**: Modern frontend library and tooling by the open-source community.
- **Recharts**: Redefined chart library built with React and D3.

---

*Developed for the NASA International Space Apps Challenge 2026.*
