from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .models import SimulationConfig
from .simulator import simulate

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"

app = FastAPI(title="SPAD Line-Scanning LiDAR Model", version="0.1.0")
app.mount("/static", StaticFiles(directory=WEB), name="static")


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


@app.get("/api/defaults")
def defaults():
    return SimulationConfig().model_dump()


@app.post("/api/simulate")
def run_simulation(config: SimulationConfig):
    return simulate(config)

