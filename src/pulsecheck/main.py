from importlib.metadata import metadata, PackageNotFoundError
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="PulseCheck")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/v1/version")
def version() -> dict:
    try:
        meta = metadata("pulsecheck")
        ver = meta["Version"]
    except PackageNotFoundError:
        # Fallback: read version directly from pyproject.toml
        from pathlib import Path
        import tomllib

        pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
        if pyproject.exists():
            ver = tomllib.loads(pyproject.read_text())["project"]["version"]
        else:
            ver = "unknown"
    return {"version": ver}
