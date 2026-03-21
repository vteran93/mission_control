FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY . .

ENV HOST=0.0.0.0
ENV PORT=5001
ENV FLASK_DEBUG=true
ENV DATABASE_URL=sqlite:////app/instance/mission_control.db
ENV ENABLE_AGENT_WAKEUPS=false
ENV MISSION_CONTROL_API_URL=http://localhost:5001/api
ENV MISSION_CONTROL_INSTANCE_PATH=/app/instance
ENV MISSION_CONTROL_RUNTIME_DIR=/app/runtime
ENV MISSION_CONTROL_QUEUE_DIR=/app/runtime/message_queue
ENV MISSION_CONTROL_HEARTBEAT_LOCK_DIR=/app/runtime/locks
ENV MISSION_CONTROL_HEARTBEAT_SCRIPT_DIR=/app/scripts

EXPOSE 5001

CMD ["python", "app.py"]
