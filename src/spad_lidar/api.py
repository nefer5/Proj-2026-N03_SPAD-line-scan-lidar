from pathlib import Path
from hashlib import sha256

from fastapi import FastAPI, Body, HTTPException
from fastapi.responses import HTMLResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
import yaml

from .models import SimulationConfig
from .simulator import simulate, derived_quantities
from .configuration import parse_yaml, read_yaml, Algorithms, ConfigurationError

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"

app = FastAPI(title="SPAD Line-Scanning LiDAR Model", version="0.1.4")
app.mount("/static", StaticFiles(directory=WEB), name="static")


@app.middleware("http")
async def development_cache_policy(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(ConfigurationError)
async def config_error(request, exc):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(ValidationError)
async def invalid_configuration(request, exc):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.get("/")
@app.get("/debug")
def index():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    # Content-addressed URLs bypass already cached unversioned JS/CSS as well.
    # Recompute on every navigation so editable source requires no release step.
    for name in ("app.js", "styles.css", "vendor/katex/katex.min.js", "vendor/katex/katex.min.css"):
        digest = sha256((WEB / name).read_bytes()).hexdigest()
        html = html.replace(f'/static/{name}"', f'/static/{name}?v={digest}"')
    return HTMLResponse(html)


@app.get("/api/defaults")
def defaults():
    return SimulationConfig().model_dump()


@app.get("/api/catalog")
def catalog():
    return {"parameters": read_yaml("parameter-help.yaml"),
            "readout_modes":read_yaml("readout-modes.yaml"),
            "algorithms": Algorithms.load().model_dump()}


@app.post("/api/derived")
def derived(config: SimulationConfig):
    return derived_quantities(config)


@app.post("/api/simulate")
def run_simulation(config: SimulationConfig, debug: bool = False):
    try:
        return simulate(config, debug=debug)
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc


@app.post("/api/config/import")
def import_config(document: str = Body(media_type="text/plain")):
    try:
        values = parse_yaml(document)
        if "simulation" in values:
            if set(values) != {"schema_version", "simulation"} or values["schema_version"] != 1:
                raise ValueError("Expected schema_version: 1 and simulation")
            values = values["simulation"]
        config = SimulationConfig.model_validate(values)
        return config.model_dump()
    except (ValueError, TypeError, yaml.YAMLError, ValidationError) as exc:
        raise HTTPException(422, detail=str(exc)) from exc


@app.post("/api/config/export")
def export_config(config: SimulationConfig):
    text = yaml.safe_dump({"schema_version": 1, "simulation": config.model_dump()},
                          allow_unicode=True, sort_keys=False)
    return Response(text, media_type="application/yaml")
