from __future__ import annotations

import fcntl
import glob
import json
import subprocess
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, current_app, jsonify, render_template, request
from flask_cors import CORS

from config import load_settings
from database import Agent, DaemonLog, Document, Message, Notification, Sprint, Task, TaskQueue, db


def ensure_runtime_directories(app: Flask) -> None:
    for key in (
        "MISSION_CONTROL_INSTANCE_PATH",
        "MISSION_CONTROL_RUNTIME_DIR",
        "MISSION_CONTROL_QUEUE_DIR",
        "MISSION_CONTROL_HEARTBEAT_LOCK_DIR",
    ):
        Path(app.config[key]).mkdir(parents=True, exist_ok=True)


def database_scheme(database_uri: str) -> str:
    parsed = urlparse(database_uri)
    return parsed.scheme or "unknown"


def trigger_agent_wake(agent_label: str) -> None:
    app = current_app._get_current_object()

    if not app.config["ENABLE_AGENT_WAKEUPS"]:
        return

    lock_file = Path(app.config["MISSION_CONTROL_HEARTBEAT_LOCK_DIR"]) / f"{agent_label}.lock"
    script_path = Path(app.config["MISSION_CONTROL_HEARTBEAT_SCRIPT_DIR"]) / f"{agent_label}-heartbeat.sh"

    def run_heartbeat() -> None:
        try:
            lock_file.parent.mkdir(parents=True, exist_ok=True)
            with lock_file.open("w", encoding="utf-8") as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

                if script_path.exists():
                    subprocess.run(
                        ["/bin/bash", str(script_path)],
                        timeout=60,
                        check=False,
                    )
        except BlockingIOError:
            print(f"{agent_label} already running, skipping")
        except Exception as exc:
            print(f"Error triggering {agent_label}: {exc}")

    thread = threading.Thread(target=run_heartbeat, daemon=True)
    thread.start()


def init_db(app: Flask | None = None) -> None:
    application = app or current_app._get_current_object()
    ensure_runtime_directories(application)
    from db_bootstrap import initialize_database

    initialize_database(application)


def create_app(config_overrides: dict | None = None) -> Flask:
    settings = load_settings()
    app = Flask(__name__, instance_path=str(settings.instance_path))
    app.config.update(settings.to_flask_config())

    if config_overrides:
        app.config.update(config_overrides)

    ensure_runtime_directories(app)
    CORS(app)
    db.init_app(app)
    register_routes(app)
    return app


def register_routes(app: Flask) -> None:
    @app.route("/")
    def index():
        cache_bust = int(datetime.now().timestamp())
        return render_template("index.html", cache_bust=cache_bust)

    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify(
            {
                "status": "ok",
                "service": "mission-control",
                "database": {"scheme": database_scheme(app.config["SQLALCHEMY_DATABASE_URI"])},
                "agent_wakeups_enabled": app.config["ENABLE_AGENT_WAKEUPS"],
            }
        )

    @app.route("/api/agents", methods=["GET", "POST"])
    def agents():
        if request.method == "GET":
            return jsonify([agent.to_dict() for agent in Agent.query.all()])

        data = request.get_json(force=True)
        agent = Agent(
            name=data["name"],
            role=data["role"],
            session_key=data.get("session_key"),
            status=data.get("status", "idle"),
        )
        db.session.add(agent)
        db.session.commit()
        return jsonify(agent.to_dict()), 201

    @app.route("/api/agents/<int:agent_id>", methods=["PUT"])
    def update_agent(agent_id: int):
        agent = Agent.query.get_or_404(agent_id)
        data = request.get_json(force=True)

        if "status" in data:
            agent.status = data["status"]
        if "last_seen_at" in data:
            agent.last_seen_at = datetime.utcnow()

        db.session.commit()
        return jsonify(agent.to_dict())

    @app.route("/api/tasks", methods=["GET", "POST"])
    def tasks():
        if request.method == "GET":
            status_filter = request.args.get("status")
            sprint_filter = request.args.get("sprint_id", type=int)

            query = Task.query
            if status_filter:
                query = query.filter_by(status=status_filter)
            if sprint_filter:
                query = query.filter_by(sprint_id=sprint_filter)

            return jsonify([task.to_dict() for task in query.order_by(Task.created_at.desc()).all()])

        data = request.get_json(force=True)
        task = Task(
            title=data["title"],
            description=data.get("description", ""),
            status=data.get("status", "todo"),
            priority=data.get("priority", "medium"),
            assignee_agent_ids=data.get("assignee_agent_ids", ""),
            sprint_id=data.get("sprint_id"),
            created_by=data.get("created_by", "Victor"),
        )
        db.session.add(task)
        db.session.commit()
        return jsonify(task.to_dict()), 201

    @app.route("/api/tasks/<int:task_id>", methods=["GET", "PUT"])
    def task_detail(task_id: int):
        task = Task.query.get_or_404(task_id)

        if request.method == "GET":
            return jsonify(task.to_dict())

        data = request.get_json(force=True)
        if "status" in data:
            task.status = data["status"]
        if "assignee_agent_ids" in data:
            task.assignee_agent_ids = data["assignee_agent_ids"]
        if "priority" in data:
            task.priority = data["priority"]
        if "sprint_id" in data:
            task.sprint_id = data["sprint_id"]

        task.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify(task.to_dict())

    @app.route("/api/sprints", methods=["GET", "POST"])
    def sprints():
        if request.method == "GET":
            return jsonify([sprint.to_dict() for sprint in Sprint.query.order_by(Sprint.created_at.desc()).all()])

        data = request.get_json(force=True)
        sprint = Sprint(
            name=data["name"],
            goal=data.get("goal", ""),
            start_date=datetime.fromisoformat(data["start_date"]) if data.get("start_date") else None,
            end_date=datetime.fromisoformat(data["end_date"]) if data.get("end_date") else None,
            status=data.get("status", "active"),
        )
        db.session.add(sprint)
        db.session.commit()
        return jsonify(sprint.to_dict()), 201

    @app.route("/api/sprints/<int:sprint_id>", methods=["GET", "PUT"])
    def sprint_detail(sprint_id: int):
        sprint = Sprint.query.get_or_404(sprint_id)

        if request.method == "GET":
            sprint_dict = sprint.to_dict()
            sprint_tasks = Task.query.filter_by(sprint_id=sprint_id).all()
            sprint_dict["tasks"] = [task.to_dict() for task in sprint_tasks]
            sprint_dict["task_count"] = len(sprint_tasks)
            return jsonify(sprint_dict)

        data = request.get_json(force=True)
        if "status" in data:
            sprint.status = data["status"]
        if "name" in data:
            sprint.name = data["name"]
        if "goal" in data:
            sprint.goal = data["goal"]

        db.session.commit()
        return jsonify(sprint.to_dict())

    @app.route("/api/messages", methods=["GET", "POST"])
    def messages():
        if request.method == "GET":
            task_id = request.args.get("task_id", type=int)
            show_hidden = request.args.get("show_hidden", "false").lower() == "true"

            query = Message.query
            if task_id:
                query = query.filter_by(task_id=task_id)
            if not show_hidden:
                query = query.filter_by(visible=True)

            messages_list = query.order_by(Message.created_at.desc()).limit(50).all()
            return jsonify([message.to_dict() for message in messages_list])

        data = request.get_json(force=True)
        message = Message(
            task_id=data.get("task_id"),
            from_agent=data["from_agent"],
            content=data["content"],
            attachments=data.get("attachments"),
        )
        db.session.add(message)
        db.session.commit()

        content_lower = data["content"].lower()
        for agent_label in app.config["SUPPORTED_AGENT_LABELS"]:
            if agent_label in content_lower:
                trigger_agent_wake(agent_label)

        return jsonify(message.to_dict()), 201

    @app.route("/api/documents", methods=["GET", "POST"])
    def documents():
        if request.method == "GET":
            task_id = request.args.get("task_id", type=int)
            query = Document.query
            if task_id:
                query = query.filter_by(task_id=task_id)
            documents_list = query.order_by(Document.created_at.desc()).all()
            return jsonify([document.to_dict() for document in documents_list])

        data = request.get_json(force=True)
        document = Document(
            title=data["title"],
            content_md=data.get("content_md", ""),
            type=data.get("type", "code"),
            task_id=data.get("task_id"),
        )
        db.session.add(document)
        db.session.commit()
        return jsonify(document.to_dict()), 201

    @app.route("/api/notifications", methods=["GET", "POST"])
    def notifications():
        if request.method == "GET":
            unread_only = request.args.get("unread", "false").lower() == "true"
            query = Notification.query
            if unread_only:
                query = query.filter_by(delivered=False)
            notifications_list = query.order_by(Notification.created_at.desc()).limit(20).all()
            return jsonify([notification.to_dict() for notification in notifications_list])

        data = request.get_json(force=True)
        notification = Notification(
            agent_id=data.get("agent_id"),
            content=data["content"],
            delivered=False,
        )
        db.session.add(notification)
        db.session.commit()
        return jsonify(notification.to_dict()), 201

    @app.route("/api/notifications/<int:notif_id>/mark-delivered", methods=["POST"])
    def mark_notification_delivered(notif_id: int):
        notification = Notification.query.get_or_404(notif_id)
        notification.delivered = True
        db.session.commit()
        return jsonify(notification.to_dict())

    @app.route("/api/send-agent-message", methods=["POST"])
    def send_agent_message():
        data = request.get_json(force=True)
        target_agent = data.get("target_agent")
        message_content = data.get("message")
        task_id = data.get("task_id")

        if not target_agent or not message_content:
            return jsonify({"error": "Missing target_agent or message"}), 400

        if target_agent not in app.config["SUPPORTED_AGENT_LABELS"]:
            return jsonify({"error": f"Unsupported target_agent: {target_agent}"}), 400

        message = Message(
            task_id=task_id,
            from_agent=data.get("from_agent", "Victor"),
            content=f"📤 → {target_agent}: {message_content}",
        )
        db.session.add(message)
        db.session.commit()

        queue_dir = Path(app.config["MISSION_CONTROL_QUEUE_DIR"])
        queue_dir.mkdir(parents=True, exist_ok=True)

        message_id = str(uuid.uuid4())[:8]
        message_file = queue_dir / f"{message_id}_{target_agent}.json"
        message_file.write_text(
            json.dumps(
                {
                    "target_agent": target_agent,
                    "message": message_content,
                    "task_id": task_id,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        return (
            jsonify(
                {
                    "status": "queued",
                    "target_agent": target_agent,
                    "message": message_content,
                    "message_id": message_id,
                    "info": "Mensaje en cola. Mission Control lo dejará disponible para el runtime de agentes.",
                }
            ),
            200,
        )

    @app.route("/api/message-queue", methods=["GET"])
    def get_message_queue():
        queue_dir = Path(app.config["MISSION_CONTROL_QUEUE_DIR"])
        queue_dir.mkdir(parents=True, exist_ok=True)

        messages_list = []
        for filepath in sorted(glob.glob(str(queue_dir / "*.json"))):
            try:
                with open(filepath, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
                data["message_id"] = Path(filepath).stem
                data["filepath"] = filepath
                messages_list.append(data)
            except Exception as exc:
                print(f"Error reading {filepath}: {exc}")

        return jsonify(messages_list)

    @app.route("/api/message-queue/<message_id>", methods=["DELETE"])
    def delete_queued_message(message_id: str):
        queue_dir = Path(app.config["MISSION_CONTROL_QUEUE_DIR"])
        for filepath in glob.glob(str(queue_dir / f"{message_id}_*.json")):
            try:
                Path(filepath).unlink()
                return jsonify({"status": "deleted", "message_id": message_id})
            except Exception as exc:
                return jsonify({"error": str(exc)}), 500
        return jsonify({"error": "Message not found"}), 404

    @app.route("/api/dashboard", methods=["GET"])
    def dashboard():
        tasks_by_status = {
            "todo": Task.query.filter_by(status="todo").count(),
            "in_progress": Task.query.filter_by(status="in_progress").count(),
            "review": Task.query.filter_by(status="review").count(),
            "done": Task.query.filter_by(status="done").count(),
            "blocked": Task.query.filter_by(status="blocked").count(),
        }
        recent_messages = (
            Message.query.filter_by(visible=True).order_by(Message.created_at.desc()).limit(10).all()
        )
        unread_notifications = Notification.query.filter_by(delivered=False).count()

        return jsonify(
            {
                "agents": [agent.to_dict() for agent in Agent.query.all()],
                "tasks_summary": tasks_by_status,
                "recent_messages": [message.to_dict() for message in recent_messages],
                "unread_notifications": unread_notifications,
            }
        )

    @app.route("/api/daemons/<agent_name>/logs", methods=["GET"])
    def get_daemon_logs(agent_name: str):
        valid_agents = ["dev", "qa", "pm"]
        if agent_name not in valid_agents:
            return jsonify({"error": f"Invalid agent. Must be one of: {valid_agents}"}), 400

        limit = min(int(request.args.get("limit", 50)), 200)
        level = request.args.get("level", "").upper()
        since = request.args.get("since")

        query = DaemonLog.query.filter_by(agent_name=agent_name)
        if level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            query = query.filter_by(level=level)

        if since:
            try:
                since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
                query = query.filter(DaemonLog.timestamp >= since_dt)
            except ValueError:
                pass

        logs = query.order_by(DaemonLog.timestamp.desc()).limit(limit).all()
        return jsonify(
            {
                "agent_name": agent_name,
                "count": len(logs),
                "logs": [log.to_dict() for log in logs],
            }
        )

    @app.route("/api/daemons/logs/all", methods=["GET"])
    def get_all_daemon_logs():
        limit = min(int(request.args.get("limit", 100)), 500)
        logs = DaemonLog.query.order_by(DaemonLog.timestamp.desc()).limit(limit).all()
        logs_by_agent = {"dev": [], "qa": [], "pm": []}

        for log in logs:
            if log.agent_name in logs_by_agent:
                logs_by_agent[log.agent_name].append(log.to_dict())

        return jsonify({"count": len(logs), "logs_by_agent": logs_by_agent})

    @app.route("/api/queue", methods=["GET"])
    def get_task_queue():
        summary = {
            "pending": TaskQueue.query.filter_by(status="pending").count(),
            "processing": TaskQueue.query.filter_by(status="processing").count(),
            "completed": TaskQueue.query.filter_by(status="completed").count(),
            "failed": TaskQueue.query.filter_by(status="failed").count(),
        }
        limit = min(int(request.args.get("limit", 20)), 100)
        recent_tasks = TaskQueue.query.order_by(TaskQueue.created_at.desc()).limit(limit).all()
        pending_tasks = TaskQueue.query.filter_by(status="pending").order_by(TaskQueue.created_at.asc()).all()

        return jsonify(
            {
                "summary": summary,
                "recent_tasks": [task.to_dict() for task in recent_tasks],
                "pending_tasks": [task.to_dict() for task in pending_tasks],
            }
        )

    @app.route("/api/queue/<int:task_id>", methods=["GET"])
    def get_task_detail(task_id: int):
        task = TaskQueue.query.get_or_404(task_id)
        return jsonify(task.to_dict())

    @app.route("/api/messages/visibility", methods=["POST"])
    def toggle_messages_visibility():
        data = request.get_json(force=True)
        action = data.get("action")

        if action == "hide_sprint_1":
            result = db.session.execute(
                db.update(Message).where(Message.task_id.between(1, 10)).values(visible=False)
            )
            db.session.commit()
            return jsonify(
                {
                    "status": "success",
                    "action": "hide_sprint_1",
                    "rows_updated": result.rowcount,
                }
            )

        if action == "show_all":
            result = db.session.execute(db.update(Message).values(visible=True))
            db.session.commit()
            return jsonify(
                {
                    "status": "success",
                    "action": "show_all",
                    "rows_updated": result.rowcount,
                }
            )

        if action == "hide_before_date":
            date_str = data.get("date")
            if not date_str:
                return jsonify({"error": "date parameter required"}), 400

            cutoff_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            result = db.session.execute(
                db.update(Message).where(Message.created_at < cutoff_date).values(visible=False)
            )
            db.session.commit()
            return jsonify(
                {
                    "status": "success",
                    "action": "hide_before_date",
                    "cutoff": date_str,
                    "rows_updated": result.rowcount,
                }
            )

        return jsonify({"error": f"Unknown action: {action}"}), 400


app = create_app()


if __name__ == "__main__":
    init_db(app)
    print(f"🚀 Mission Control Backend running on http://localhost:{app.config['PORT']}")
    app.run(
        debug=app.config["DEBUG"],
        host=app.config["HOST"],
        port=app.config["PORT"],
    )
