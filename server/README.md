# Synthetic Market Research Engine Server

FastAPI backend powered by Google Gemini Pro, SQLite, and scikit-learn for simulating consumer responses across Indian demographics.

## Prerequisites

Python 3.10+ installed on Windows, macOS, or Linux. No Docker or external database required.

## Setup

1. Create and activate a virtual environment:
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

2. Install dependencies:
```powershell
pip install -r requirements.txt
```

3. Configure your environment variables in `.env`:
```env
DATABASE_URL=sqlite:///./synth_research.db
GEMINI_API_KEY=your_actual_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-pro
```

## Running the Server

Start the API server using Uvicorn:
```powershell
uvicorn app.main:app --reload --port 8000
```

Interactive OpenAPI documentation is available at:
`http://127.0.0.1:8000/docs`

## Running Tests

Run the test suite with pytest:
```powershell
pytest tests/ -v
```

## Generating Seed Data

To generate sample demographic data:
```powershell
python -m seed_data.generate_seed_data --n 5000 --out ./seed_output
```
