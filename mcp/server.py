import os
import sys
import redis
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from spiffe.workloadapi.workload_api_client import WorkloadApiClient
import uvicorn

# Add project root for events module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from events import bus

# --- Configuration ---
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = 6379
SPIRE_SOCKET = "/run/spire/sockets/agent.sock"

# --- Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fetch MCP Server's own X.509-SVID from SPIRE workload API
    svid_present = False
    spiffe_id = ""
    try:
        with WorkloadApiClient(socket_path=f"unix://{SPIRE_SOCKET}") as client:
            svid = client.fetch_x509_svid()
            spiffe_id = str(svid.spiffe_id)
            svid_present = True
            print(f"[SPIRE] MCP Server SVID: {spiffe_id}")
    except Exception as e:
        print(f"[SPIRE] SVID fetch failed (fail-open): {e}")

    # Emit SPIRE identity status event
    bus.emit("spire_identity", "svid_status", {
        "svid_present": svid_present,
        "spiffe_id": spiffe_id,
    }, severity="info")

    yield

# --- FastAPI App ---
app = FastAPI(title="KITT MCP Server", lifespan=lifespan)

# --- Redis Connection ---
try:
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    redis_client.ping()
    print("Successfully connected to Redis.")
except redis.exceptions.ConnectionError as e:
    print(f"Error connecting to Redis: {e}")
    redis_client = None

# --- Pydantic Models ---
class ContextStoreRequest(BaseModel):
    agent_id: str
    content: str

# --- Endpoints ---
@app.get("/health", tags=["Health"])
def health_check():
    """Verifies the connection to Redis is active."""
    if not redis_client or not redis_client.ping():
        raise HTTPException(status_code=503, detail="Redis connection failed")
    return {"status": "ok", "redis_connection": "active"}

@app.post("/context/store", tags=["Context"])
def store_context(request: ContextStoreRequest):
    """Stores agent context into Redis."""
    if not redis_client:
        raise HTTPException(status_code=503, detail="Redis connection failed")

    list_key = f"agent:{request.agent_id}:context"
    redis_client.lpush(list_key, request.content)
    # Keep only the last 5 messages
    redis_client.ltrim(list_key, 0, 4)

    # Emit MCP context event
    bus.emit("mcp_context", "store", {
        "agent_id": request.agent_id,
        "msg_count": redis_client.llen(list_key),
    }, severity="info")

    return {"status": "success", "agent_id": request.agent_id}

@app.get("/context/retrieve", tags=["Context"])
def retrieve_context(agent_id: str):
    """Retrieves the last 5 messages for an agent."""
    if not redis_client:
        raise HTTPException(status_code=503, detail="Redis connection failed")

    list_key = f"agent:{agent_id}:context"
    messages = redis_client.lrange(list_key, 0, 4)

    bus.emit("mcp_context", "retrieve", {
        "agent_id": agent_id,
        "msg_count": len(messages),
    }, severity="info")

    return {"agent_id": agent_id, "messages": messages}

# --- Main ---
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
