FROM python:3.12-slim

# Create a non-root user for minimal privilege execution
RUN useradd -m -s /bin/bash mcp_user

WORKDIR /app

# Install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy server logic
COPY server.py .

# Enforce non-root execution
USER mcp_user

EXPOSE 8000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
