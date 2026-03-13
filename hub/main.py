import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../a2a/agent_zero')))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import requests
from pydantic import BaseModel
from typing import Optional, List
from agent import AgentZero

app = FastAPI(title="KITT Hub")
agent = AgentZero()

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
    result = agent.fan_out(prompt=request.prompt, models=request.models)
    return {
        "prompt": request.prompt,
        "responses": result["responses"],
        "intent_flagged": result["intent"]["flagged"],
        "intent_category": result["intent"]["reason"],
        "intent_score": result["intent"]["score"]
    }


# --- Main ---

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)