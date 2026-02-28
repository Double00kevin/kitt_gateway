import os
import redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

# --- Configuration ---
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = 6379
SPIRE_SOCKET = "/run/spire/sockets/agent.sock" # For future use

# --- FastAPI App ---
app = FastAPI(title="KITT MCP Server")

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
    
    return {"status": "success", "agent_id": request.agent_id}

@app.get("/context/retrieve", tags=["Context"])
def retrieve_context(agent_id: str):
    """Retrieves the last 5 messages for an agent."""
    if not redis_client:
        raise HTTPException(status_code=503, detail="Redis connection failed")
        
    list_key = f"agent:{agent_id}:context"
    messages = redis_client.lrange(list_key, 0, 4)
    
    return {"agent_id": agent_id, "messages": messages}

# --- Main ---
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
