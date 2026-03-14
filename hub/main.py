import sys
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import requests
from pydantic import BaseModel
from typing import Optional, List

app = FastAPI(title="KITT Hub")

AGENT_URL = "http://127.0.0.1:9001"
USE_DIRECT = os.getenv("USE_DIRECT_AGENT_ZERO", "false").lower() == "true"

if USE_DIRECT:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../a2a/agent_zero')))
    from agent import AgentZero
    _direct_agent = AgentZero()

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# --- Models ---

class ChatRequest(BaseModel):
    prompt: str
    models: Optional[List[str]] = None  # None = all


# --- Routes ---

@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/health")
def health():
    checks = {}

    try:
        r = requests.get("http://localhost:8000/health", timeout=2)
        checks["mcp"] = "ok" if r.status_code == 200 else "degraded"
    except Exception:
        checks["mcp"] = "down"

    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=2)
        checks["ollama"] = "ok" if r.status_code == 200 else "degraded"
    except Exception:
        checks["ollama"] = "down"

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    code = 200 if overall == "ok" else 503
    return JSONResponse(status_code=code, content={"status": overall, "service": "kitt-hub", "checks": checks})

@app.post("/chat")
def chat(request: ChatRequest):
    if USE_DIRECT:
        result = _direct_agent.fan_out(prompt=request.prompt, models=request.models)
    else:
        try:
            r = requests.post(
                f"{AGENT_URL}/fan_out",
                json={"prompt": request.prompt, "models": request.models},
                timeout=120
            )
            r.raise_for_status()
            result = r.json()
        except requests.RequestException:
            return JSONResponse(status_code=503, content={"error": "Agent Zero unavailable"})

    return {
        "prompt": request.prompt,
        "responses": result["responses"],
        "intent_flagged": result["intent"]["flagged"],
        "intent_category": result["intent"]["reason"],
        "intent_score":    result["intent"]["score"],
    }


# --- Main ---

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
