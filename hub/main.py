import sys
import os
import hmac
import json
import uuid
import asyncio

from fastapi import FastAPI, Depends, Header, HTTPException, Request, WebSocket, WebSocketDisconnect, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse, Response
import requests
from pydantic import BaseModel
from typing import Optional, List
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Add project root to path for events module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from events import bus
from events.dashboard import get_dashboard_data, get_posture_score
from events.payloads import load_payloads, get_categories, get_payload_count
from events.report import generate_report, is_available as pdf_available
from shared.health import check_services, overall_status

# --- Rate Limiter ---
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="KITT Hub")
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"error": "Rate limit exceeded. Max 10 requests per minute."})

# --- Auth ---
HUB_API_KEY = os.getenv("KITT_HUB_API_KEY", "")

def verify_api_key(authorization: str = Header(None)):
    if not HUB_API_KEY:
        return  # auth disabled if no key configured
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if not hmac.compare_digest(token, HUB_API_KEY):
        raise HTTPException(status_code=403, detail="Invalid API key")


def _verify_token(token: str) -> bool:
    """Verify a token string (for WebSocket query param auth)."""
    if not HUB_API_KEY:
        return True
    if not token:
        return False
    return hmac.compare_digest(token, HUB_API_KEY)


# --- Config ---
AGENT_URL = "http://127.0.0.1:9001"
USE_DIRECT = os.getenv("USE_DIRECT_AGENT_ZERO", "false").lower() == "true"

if USE_DIRECT:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../a2a/agent_zero')))
    from agent import AgentZero
    _direct_agent = AgentZero()

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

# Mount static AFTER all routes are defined (at bottom) to avoid route conflicts


# --- Models ---

class ChatRequest(BaseModel):
    prompt: str
    models: Optional[List[str]] = None  # None = all

class DemoRequest(BaseModel):
    category: Optional[str] = None  # filter payloads by category
    models: Optional[List[str]] = None  # subset of models for cost control


# --- Core Routes ---

@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/dashboard")
def dashboard_page(_auth=Depends(verify_api_key)):
    return FileResponse(os.path.join(STATIC_DIR, "dashboard.html"))


@app.get("/health")
def health():
    checks = check_services()
    overall = overall_status(checks)
    code = 200 if overall == "ok" else 503
    return JSONResponse(status_code=code, content={"status": overall, "service": "kitt-hub", "checks": checks})


@app.post("/chat")
@limiter.limit("10/minute")
def chat(request: ChatRequest, raw_request: Request, _auth=Depends(verify_api_key)):
    request_id = str(uuid.uuid4())[:8]

    if USE_DIRECT:
        result = _direct_agent.fan_out(prompt=request.prompt, models=request.models, request_id=request_id)
    else:
        try:
            r = requests.post(
                f"{AGENT_URL}/fan_out",
                json={"prompt": request.prompt, "models": request.models, "request_id": request_id},
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
        "request_id": request_id,
    }


# --- Dashboard API ---

@app.get("/api/dashboard")
def api_dashboard(_auth=Depends(verify_api_key)):
    return get_dashboard_data()


@app.get("/api/posture")
def api_posture(_auth=Depends(verify_api_key)):
    return get_posture_score()


# --- Demo Mode (dedicated endpoint — no rate limit) ---

@app.post("/api/demo")
def api_demo(req: DemoRequest, _auth=Depends(verify_api_key)):
    """
    Fire attack payloads through the pipeline. Streams progress via SSE.
    Uses a dedicated endpoint to bypass /chat rate limiting.
    """
    payloads = load_payloads(category=req.category)
    if not payloads:
        raise HTTPException(status_code=404, detail="No payloads found")

    def generate():
        for i, payload in enumerate(payloads):
            request_id = f"demo-{str(uuid.uuid4())[:8]}"
            status = "ok"
            try:
                body = {
                    "prompt": payload["prompt"],
                    "models": req.models,
                    "request_id": request_id,
                }
                if USE_DIRECT:
                    _direct_agent.fan_out(
                        prompt=payload["prompt"],
                        models=req.models,
                        request_id=request_id,
                    )
                else:
                    r = requests.post(
                        f"{AGENT_URL}/fan_out",
                        json=body,
                        timeout=120,
                    )
                    if not r.ok:
                        status = f"error:{r.status_code}"
            except Exception as e:
                status = f"error:{e}"

            progress = {
                "index": i + 1,
                "total": len(payloads),
                "payload_id": payload.get("id"),
                "category": payload.get("category"),
                "technique": payload.get("technique"),
                "owasp": payload.get("owasp"),
                "status": status,
                "request_id": request_id,
            }
            yield f"data: {json.dumps(progress)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# --- Replay API ---

@app.get("/api/replay/requests")
def api_replay_requests(_auth=Depends(verify_api_key)):
    return bus.get_recent_request_ids(count=50)


@app.get("/api/replay/{request_id}")
def api_replay_detail(request_id: str, _auth=Depends(verify_api_key)):
    events = bus.read_events_by_request(request_id)
    if not events:
        raise HTTPException(status_code=404, detail="Request not found or events expired")
    return events


# --- PDF Report ---

@app.get("/api/report/pdf")
def api_report_pdf(_auth=Depends(verify_api_key)):
    if not pdf_available():
        raise HTTPException(status_code=503, detail="PDF generation unavailable — install fpdf2")
    events = bus.read_events(count=1000)
    posture = get_posture_score()
    pdf_bytes = generate_report(events, posture)
    if pdf_bytes is None:
        raise HTTPException(status_code=500, detail="PDF generation failed")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=kitt-security-report.pdf"},
    )


# --- Payload Library API ---

@app.get("/api/payloads")
def api_payloads(category: Optional[str] = None, _auth=Depends(verify_api_key)):
    return {"payloads": load_payloads(category), "categories": get_categories(), "total": get_payload_count()}


# --- WebSocket Live Events ---

_ws_clients: list[WebSocket] = []
MAX_WS_CLIENTS = 5


@app.websocket("/ws/events")
async def ws_events(websocket: WebSocket, token: str = Query(default="")):
    if not _verify_token(token):
        await websocket.close(code=4001, reason="Invalid token")
        return
    if len(_ws_clients) >= MAX_WS_CLIENTS:
        await websocket.close(code=4002, reason="Too many connections")
        return

    await websocket.accept()
    _ws_clients.append(websocket)

    # Stream events via polling Redis Streams
    last_id = "$"
    r = bus._get_redis()
    try:
        while True:
            if r is None:
                await asyncio.sleep(2)
                r = bus._get_redis()
                continue
            try:
                loop = asyncio.get_event_loop()
                results = await loop.run_in_executor(
                    None, lambda: r.xread({bus.STREAM_KEY: last_id}, count=10, block=2000)
                )
            except Exception:
                await asyncio.sleep(1)
                r = bus._get_redis()
                continue
            if results:
                for stream_name, messages in results:
                    for msg_id, fields in messages:
                        last_id = msg_id
                        try:
                            details = json.loads(fields.get("details", "{}"))
                        except (json.JSONDecodeError, TypeError):
                            details = {"raw": fields.get("details", "")}
                        event = {
                            "type": "event",
                            "id": msg_id,
                            "ts": fields.get("ts", ""),
                            "layer": fields.get("layer", ""),
                            "event_type": fields.get("type", ""),
                            "details": details,
                            "severity": fields.get("severity", "info"),
                            "request_id": fields.get("request_id", ""),
                        }
                        await websocket.send_json(event)
            else:
                # No new events — send heartbeat to detect disconnection
                try:
                    await websocket.send_json({"type": "heartbeat"})
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in _ws_clients:
            _ws_clients.remove(websocket)


# --- Static Files (mounted last to avoid route conflicts) ---
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# --- Main ---

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
