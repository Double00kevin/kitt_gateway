import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../a2a/agent_zero')))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
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
    return {"status": "ok", "service": "kitt-hub"}

@app.post("/chat")
def chat(request: ChatRequest):
    results = agent.fan_out(prompt=request.prompt, models=request.models)
    return {"prompt": request.prompt, "responses": results}


# --- Main ---

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)