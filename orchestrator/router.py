from typing import TypedDict, Annotated
import operator
import redis
import logging
import os
import json
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END

# Initialize ATS Telemetry Logging
log_file = os.path.expanduser("~/kitt_gateway/governance/telemetry/ats_audit.log")
logging.basicConfig(filename=log_file, level=logging.INFO, format='%(asctime)s | ATS_EVENT | %(message)s')

# Connect to the local Shared Context Store (Redis Blackboard)
scs = redis.Redis(host='127.0.0.1', port=6379, decode_responses=True)

class AgentState(TypedDict):
    messages: Annotated[list[str], operator.add]

# Bind to the isolated Inference Engine using the updated provider
llm = ChatOllama(model="llama3.2", base_url="http://127.0.0.1:11434")

# Define the stateful and observable execution node
def process_node(state: AgentState):
    user_input = state['messages'][-1]
    logging.info(json.dumps({"agent_id": "spiffe://mpx.sovereign/kitt_node/edge_router", "action": "intent_received"}))
    
    # 1. Read existing state
    current_memory = scs.get("mission_status") or "No previous data."
    logging.info(json.dumps({"action": "memory_read", "target": "redis_scs", "key": "mission_status"}))
    
    # 2. Inject context and invoke inference
    system_prompt = f"Blackboard Context: {current_memory}\n\nUser Command: {user_input}"
    response = llm.invoke(system_prompt)
    logging.info(json.dumps({"action": "inference_complete", "status": "success"}))
    
    # 3. Write updated state
    new_state = "Phase 6 ATS Telemetry Active. KITT Gateway Fully Operational."
    scs.set("mission_status", new_state)
    logging.info(json.dumps({"action": "memory_write", "target": "redis_scs", "key": "mission_status"}))
    
    return {"messages": [response.content]}

# Construct and compile the graph
workflow = StateGraph(AgentState)
workflow.add_node("router", process_node)
workflow.add_edge(START, "router")
workflow.add_edge("router", END)
app = workflow.compile()

if __name__ == "__main__":
    print("Executing Clean ATS Telemetry Sequence...")
    result = app.invoke({"messages": ["System check: Acknowledge that the LangChain warning is cleared and operations are nominal."]})
    print(f"\n[Engine Return]: {result['messages'][-1]}\n")
