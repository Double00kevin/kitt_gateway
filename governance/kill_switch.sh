#!/bin/bash
echo "[CRITICAL] Initiating ISO 42001 Immediate Cessation Protocol..."

echo "Severing Inference Engine (Ollama/Llama-3.2)..."
sudo docker stop mpx-inference-edge

echo "Severing A2A Communications Proxy..."
sudo docker stop mpx-a2a-proxy

echo "Stopping KITT Hub (chat UI / model router)..."
sudo systemctl stop kitt-hub

echo "Stopping Agent Zero (autonomous daemon)..."
sudo systemctl stop kitt-agent

echo "Checking SPIRE agent status..."
if curl -sf http://127.0.0.1:8082/ready >/dev/null; then
    echo "SPIRE agent healthy"
else
    echo "SPIRE agent unhealthy - stopping anyway"
fi

echo "[LOCKED] Autonomous operations have been successfully terminated. Memory and Identity layers remain intact."
