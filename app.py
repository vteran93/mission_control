from __future__ import annotations

from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, current_app, jsonify, render_template, request
from flask_cors import CORS

from autonomous_scrum import AutonomousScrumPlannerService
from config import load_settings
from crew_runtime import AgenticRuntime
from database import (
    Agent,
    DaemonLog,
    DeliveryTaskRecord,
    Document,
    Message,
    Notification,
    ProjectBlueprintRecord,
    Sprint,
    Task,
    TaskQueue,
    db,
)
from delivery_tracking import DeliveryTrackingService
from spec_intake import BlueprintPersistenceService, SpecIntakeService


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


def init_db(app: Flask | None = None) -> None:
    application = app or current_app._get_current_object()
    ensure_runtime_directories(application)
    from db_bootstrap import initialize_database

    initialize_database(application)
    application.extensions["mission_control_runtime"].start_background_dispatcher(application)


def create_app(config_overrides: dict | None = None) -> Flask:
    settings = load_settings()
    app = Flask(__name__, instance_path=str(settings.instance_path))
    app.config.update(settings.to_flask_config())

    if config_overrides:
        app.config.update(config_overrides)

    ensure_runtime_directories(app)
    CORS(app)
    db.init_app(app)
    runtime = AgenticRuntime(settings)
    app.extensions["mission_control_runtime"] = runtime
    app.extensions["queue_dispatcher"] = runtime.dispatcher
    app.extensions["spec_intake_service"] = SpecIntakeService()
    app.extensions["blueprint_persistence_service"] = BlueprintPersistenceService()
    app.extensions["delivery_tracking_service"] = DeliveryTrackingService()
    app.extensions["autonomous_scrum_service"] = AutonomousScrumPlannerService()
    register_routes(app)
    return app


def register_routes(app: Flask) -> None:
    def resolve_input_path(raw_path: str) -> Path:
        candidate = Path(raw_path).expanduser()
        if not candidate.is_absolute():
            candidate = Path(app.config["MISSION_CONTROL_BASE_DIR"]) / candidate
        return candidate.resolve()

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
                "agentic_runtime_enabled": app.config["MISSION_CONTROL_RUNTIME_ENABLED"],
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

    @app.route("/api/spec-intake/preview", methods=["POST"])
    def spec_intake_preview():
        data = request.get_json(force=True)
        requirements_path = data.get("requirements_path")
        roadmap_path = data.get("roadmap_path")

        if not requirements_path or not roadmap_path:
            return jsonify({"error": "requirements_path and roadmap_path are required"}), 400

        resolved_requirements = resolve_input_path(requirements_path)
        resolved_roadmap = resolve_input_path(roadmap_path)

        if not resolved_requirements.is_file():
            return jsonify({"error": f"requirements_path not found: {resolved_requirements}"}), 404
        if not resolved_roadmap.is_file():
            return jsonify({"error": f"roadmap_path not found: {resolved_roadmap}"}), 404

        blueprint = app.extensions["spec_intake_service"].build_blueprint(
            requirements_path=resolved_requirements,
            roadmap_path=resolved_roadmap,
        )
        return jsonify(blueprint.to_dict())

    @app.route("/api/blueprints/import", methods=["POST"])
    def import_blueprint():
        data = request.get_json(force=True)
        requirements_path = data.get("requirements_path")
        roadmap_path = data.get("roadmap_path")

        if not requirements_path or not roadmap_path:
            return jsonify({"error": "requirements_path and roadmap_path are required"}), 400

        resolved_requirements = resolve_input_path(requirements_path)
        resolved_roadmap = resolve_input_path(roadmap_path)

        if not resolved_requirements.is_file():
            return jsonify({"error": f"requirements_path not found: {resolved_requirements}"}), 404
        if not resolved_roadmap.is_file():
            return jsonify({"error": f"roadmap_path not found: {resolved_roadmap}"}), 404

        spec_service = app.extensions["spec_intake_service"]
        persistence_service = app.extensions["blueprint_persistence_service"]
        blueprint = spec_service.build_blueprint(
            requirements_path=resolved_requirements,
            roadmap_path=resolved_roadmap,
        )
        blueprint_record = persistence_service.persist_blueprint(blueprint)
        return jsonify(persistence_service.serialize_blueprint_detail(blueprint_record)), 201

    @app.route("/api/blueprints", methods=["GET"])
    def list_blueprints():
        persistence_service = app.extensions["blueprint_persistence_service"]
        blueprint_records = persistence_service.list_blueprints()
        return jsonify([blueprint.to_dict() for blueprint in blueprint_records])

    @app.route("/api/blueprints/<int:blueprint_id>", methods=["GET"])
    def blueprint_detail(blueprint_id: int):
        persistence_service = app.extensions["blueprint_persistence_service"]
        blueprint_record = persistence_service.get_blueprint(blueprint_id)
        if blueprint_record is None:
            return jsonify({"error": "Blueprint not found"}), 404
        return jsonify(persistence_service.serialize_blueprint_detail(blueprint_record))

    @app.route("/api/blueprints/<int:blueprint_id>/feedback", methods=["POST"])
    def create_blueprint_feedback(blueprint_id: int):
        persistence_service = app.extensions["blueprint_persistence_service"]
        blueprint_record = persistence_service.get_blueprint(blueprint_id)
        if blueprint_record is None:
            return jsonify({"error": "Blueprint not found"}), 404

        data = request.get_json(force=True)
        stage_name = data.get("stage_name")
        feedback_text = data.get("feedback_text")
        if not stage_name or not feedback_text:
            return jsonify({"error": "stage_name and feedback_text are required"}), 400

        feedback = persistence_service.add_stage_feedback(
            blueprint_id=blueprint_id,
            stage_name=stage_name,
            status=data.get("status", "captured"),
            source=data.get("source", "system"),
            feedback_text=feedback_text,
        )
        return jsonify(feedback.to_dict()), 201

    @app.route("/api/blueprints/<int:blueprint_id>/retrospective-items", methods=["POST"])
    def create_retrospective_item(blueprint_id: int):
        persistence_service = app.extensions["blueprint_persistence_service"]
        blueprint_record = persistence_service.get_blueprint(blueprint_id)
        if blueprint_record is None:
            return jsonify({"error": "Blueprint not found"}), 404

        data = request.get_json(force=True)
        category = data.get("category")
        summary = data.get("summary")
        if not category or not summary:
            return jsonify({"error": "category and summary are required"}), 400

        item = persistence_service.add_retrospective_item(
            blueprint_id=blueprint_id,
            category=category,
            summary=summary,
            action_item=data.get("action_item"),
            owner=data.get("owner"),
            status=data.get("status", "open"),
        )
        return jsonify(item.to_dict()), 201

    @app.route("/api/blueprints/<int:blueprint_id>/sprint-cycles", methods=["GET", "POST"])
    def sprint_cycles(blueprint_id: int):
        persistence_service = app.extensions["blueprint_persistence_service"]
        blueprint_record = persistence_service.get_blueprint(blueprint_id)
        if blueprint_record is None:
            return jsonify({"error": "Blueprint not found"}), 404

        if request.method == "GET":
            items = sorted(
                blueprint_record.sprint_cycles,
                key=lambda item: item.created_at.isoformat() if item.created_at else "",
            )
            return jsonify([item.to_dict() for item in items])

        tracking_service = app.extensions["delivery_tracking_service"]
        data = request.get_json(force=True)

        try:
            sprint_cycle = tracking_service.create_sprint_cycle(
                blueprint_id=blueprint_id,
                name=data["name"],
                goal=data.get("goal"),
                capacity=data.get("capacity"),
                status=data.get("status", "planned"),
                start_date=datetime.fromisoformat(data["start_date"]) if data.get("start_date") else None,
                end_date=datetime.fromisoformat(data["end_date"]) if data.get("end_date") else None,
                metadata=data.get("metadata"),
            )
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except (KeyError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400

        return jsonify(sprint_cycle.to_dict()), 201

    @app.route("/api/blueprints/<int:blueprint_id>/stage-events", methods=["POST"])
    def create_stage_event(blueprint_id: int):
        tracking_service = app.extensions["delivery_tracking_service"]
        data = request.get_json(force=True)

        try:
            event = tracking_service.create_stage_event(
                blueprint_id=blueprint_id,
                stage_name=data["stage_name"],
                status=data["status"],
                source=data.get("source", "system"),
                summary=data["summary"],
                metadata=data.get("metadata"),
            )
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except (KeyError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400

        return jsonify(event.to_dict()), 201

    @app.route("/api/blueprints/<int:blueprint_id>/agent-runs", methods=["POST"])
    def create_agent_run(blueprint_id: int):
        tracking_service = app.extensions["delivery_tracking_service"]
        data = request.get_json(force=True)

        try:
            run = tracking_service.create_agent_run(
                blueprint_id=blueprint_id,
                agent_name=data["agent_name"],
                agent_role=data.get("agent_role"),
                provider=data.get("provider"),
                model=data.get("model"),
                status=data.get("status", "queued"),
                input_summary=data.get("input_summary"),
                output_summary=data.get("output_summary"),
                error_message=data.get("error_message"),
                runtime_name=data.get("runtime_name"),
                completed=data.get("completed", False),
            )
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except (KeyError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400

        return jsonify(run.to_dict()), 201

    @app.route("/api/blueprints/<int:blueprint_id>/task-executions", methods=["POST"])
    def create_task_execution(blueprint_id: int):
        tracking_service = app.extensions["delivery_tracking_service"]
        data = request.get_json(force=True)

        try:
            execution = tracking_service.create_task_execution(
                blueprint_id=blueprint_id,
                delivery_task_id=data["delivery_task_id"],
                agent_run_id=data.get("agent_run_id"),
                status=data.get("status", "queued"),
                attempt_number=data.get("attempt_number", 1),
                summary=data.get("summary"),
                error_message=data.get("error_message"),
                completed=data.get("completed", False),
            )
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except (KeyError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400

        return jsonify(execution.to_dict()), 201

    @app.route("/api/blueprints/<int:blueprint_id>/artifacts", methods=["POST"])
    def create_artifact(blueprint_id: int):
        tracking_service = app.extensions["delivery_tracking_service"]
        data = request.get_json(force=True)

        try:
            artifact = tracking_service.create_artifact(
                blueprint_id=blueprint_id,
                name=data["name"],
                artifact_type=data["artifact_type"],
                uri=data["uri"],
                agent_run_id=data.get("agent_run_id"),
                task_execution_id=data.get("task_execution_id"),
                document_id=data.get("document_id"),
                metadata=data.get("metadata"),
            )
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except (KeyError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400

        return jsonify(artifact.to_dict()), 201

    @app.route("/api/blueprints/<int:blueprint_id>/handoffs", methods=["POST"])
    def create_handoff(blueprint_id: int):
        tracking_service = app.extensions["delivery_tracking_service"]
        data = request.get_json(force=True)

        try:
            handoff = tracking_service.create_handoff(
                blueprint_id=blueprint_id,
                from_agent=data["from_agent"],
                to_agent=data["to_agent"],
                status=data.get("status", "requested"),
                reason=data["reason"],
                task_execution_id=data.get("task_execution_id"),
                context=data.get("context"),
            )
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except (KeyError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400

        return jsonify(handoff.to_dict()), 201

    @app.route("/api/blueprints/<int:blueprint_id>/llm-invocations", methods=["POST"])
    def create_llm_invocation(blueprint_id: int):
        tracking_service = app.extensions["delivery_tracking_service"]
        data = request.get_json(force=True)

        try:
            invocation = tracking_service.create_llm_invocation(
                blueprint_id=blueprint_id,
                provider=data["provider"],
                model=data["model"],
                purpose=data["purpose"],
                status=data.get("status", "completed"),
                agent_run_id=data.get("agent_run_id"),
                prompt_tokens=data.get("prompt_tokens", 0),
                completion_tokens=data.get("completion_tokens", 0),
                latency_ms=data.get("latency_ms"),
                cost_usd=data.get("cost_usd", 0.0),
                metadata=data.get("metadata"),
            )
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except (KeyError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400

        return jsonify(invocation.to_dict()), 201

    @app.route("/api/blueprints/<int:blueprint_id>/timeline", methods=["GET"])
    def blueprint_timeline(blueprint_id: int):
        tracking_service = app.extensions["delivery_tracking_service"]
        try:
            timeline = tracking_service.build_timeline(blueprint_id)
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        return jsonify({"blueprint_id": blueprint_id, "timeline": timeline})

    @app.route("/api/blueprints/<int:blueprint_id>/report", methods=["GET"])
    def blueprint_report(blueprint_id: int):
        tracking_service = app.extensions["delivery_tracking_service"]
        try:
            report = tracking_service.build_report(blueprint_id)
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        return jsonify(report)

    @app.route("/api/blueprints/<int:blueprint_id>/scrum-plans", methods=["GET"])
    def list_scrum_plans(blueprint_id: int):
        planner_service = app.extensions["autonomous_scrum_service"]
        try:
            plans = planner_service.list_plans(blueprint_id)
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        return jsonify([plan.to_dict() for plan in plans])

    @app.route("/api/blueprints/<int:blueprint_id>/scrum-plan", methods=["GET", "POST"])
    def scrum_plan(blueprint_id: int):
        planner_service = app.extensions["autonomous_scrum_service"]

        if request.method == "GET":
            try:
                plan = planner_service.get_plan(
                    blueprint_id,
                    plan_id=request.args.get("plan_id", type=int),
                    status=request.args.get("status", default="active", type=str),
                )
            except LookupError as exc:
                return jsonify({"error": str(exc)}), 404
            return jsonify(planner_service.serialize_plan(plan))

        data = request.get_json(silent=True) or {}
        try:
            plan = planner_service.generate_plan(
                blueprint_id=blueprint_id,
                sprint_capacity=data.get("sprint_capacity", 16),
                sprint_length_days=data.get("sprint_length_days", 7),
                start_date=data.get("start_date"),
                velocity_factor=data.get("velocity_factor", 1.0),
                blocked_ticket_ids=data.get("blocked_ticket_ids"),
                changed_ticket_ids=data.get("changed_ticket_ids"),
                planning_mode=data.get("planning_mode", "autonomous"),
                replan_reason=data.get("replan_reason"),
                source=data.get("source", "heuristic"),
            )
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except (TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 409
        return jsonify(planner_service.serialize_plan(plan)), 201

    @app.route("/api/blueprints/<int:blueprint_id>/scrum-plan/replan", methods=["POST"])
    def scrum_replan(blueprint_id: int):
        planner_service = app.extensions["autonomous_scrum_service"]
        data = request.get_json(silent=True) or {}

        try:
            plan = planner_service.generate_plan(
                blueprint_id=blueprint_id,
                sprint_capacity=data.get("sprint_capacity", 16),
                sprint_length_days=data.get("sprint_length_days", 7),
                start_date=data.get("start_date"),
                velocity_factor=data.get("velocity_factor", 1.0),
                blocked_ticket_ids=data.get("blocked_ticket_ids"),
                changed_ticket_ids=data.get("changed_ticket_ids"),
                planning_mode="replan",
                replan_reason=data.get("reason") or data.get("replan_reason"),
                source=data.get("source", "heuristic"),
            )
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except (TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 409
        return jsonify(planner_service.serialize_plan(plan)), 201

    @app.route("/api/blueprints/<int:blueprint_id>/scrum-plan/<int:plan_id>/approve", methods=["POST"])
    def approve_scrum_plan(blueprint_id: int, plan_id: int):
        planner_service = app.extensions["autonomous_scrum_service"]
        data = request.get_json(silent=True) or {}
        try:
            plan = planner_service.approve_plan(
                blueprint_id,
                plan_id=plan_id,
                source=data.get("source", "manual"),
                feedback_text=data.get("feedback_text"),
            )
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except (TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(planner_service.serialize_plan(plan))

    @app.route("/api/blueprints/<int:blueprint_id>/scrum-plan/sprint-view", methods=["GET"])
    def scrum_plan_sprint_view(blueprint_id: int):
        planner_service = app.extensions["autonomous_scrum_service"]
        try:
            payload = planner_service.build_sprint_view(
                blueprint_id,
                plan_id=request.args.get("plan_id", type=int),
                status=request.args.get("status", default="latest", type=str),
            )
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        return jsonify(payload)

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
        dispatcher = app.extensions["queue_dispatcher"]
        for agent_label in app.config["SUPPORTED_AGENT_LABELS"]:
            if agent_label in content_lower:
                dispatcher.enqueue_message(message=message, target_agent=agent_label)

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
        project_blueprint_id = data.get("project_blueprint_id")
        delivery_task_id = data.get("delivery_task_id")
        crew_seed = data.get("crew_seed")

        if not target_agent or not message_content:
            return jsonify({"error": "Missing target_agent or message"}), 400

        if target_agent not in app.config["SUPPORTED_AGENT_LABELS"]:
            return jsonify({"error": f"Unsupported target_agent: {target_agent}"}), 400

        if crew_seed is not None:
            available_seeds = app.extensions["mission_control_runtime"].describe_crew_seeds()
            if crew_seed not in available_seeds:
                return jsonify({"error": f"Unsupported crew_seed: {crew_seed}"}), 400

        if project_blueprint_id is not None:
            try:
                project_blueprint_id = int(project_blueprint_id)
            except (TypeError, ValueError):
                return jsonify({"error": "project_blueprint_id must be numeric"}), 400
            if db.session.get(ProjectBlueprintRecord, project_blueprint_id) is None:
                return jsonify({"error": "Blueprint not found"}), 404

        if delivery_task_id is not None:
            try:
                delivery_task_id = int(delivery_task_id)
            except (TypeError, ValueError):
                return jsonify({"error": "delivery_task_id must be numeric"}), 400
            delivery_task = db.session.get(DeliveryTaskRecord, delivery_task_id)
            if delivery_task is None:
                return jsonify({"error": "Delivery task not found"}), 404
            if (
                project_blueprint_id is not None
                and delivery_task.epic is not None
                and delivery_task.epic.project_blueprint_id != project_blueprint_id
            ):
                return jsonify({"error": "Delivery task does not belong to blueprint"}), 400

        _, queue_entry = app.extensions["queue_dispatcher"].create_message_and_enqueue(
            target_agent=target_agent,
            message_content=message_content,
            from_agent=data.get("from_agent", "Victor"),
            task_id=task_id,
            priority=data.get("priority", "normal"),
            project_blueprint_id=project_blueprint_id,
            delivery_task_id=delivery_task_id,
            crew_seed=crew_seed,
        )

        return (
            jsonify(
                {
                    "status": "queued",
                    "target_agent": target_agent,
                    "message": message_content,
                    "message_id": str(queue_entry.id),
                    "queue_entry_id": queue_entry.id,
                    "project_blueprint_id": queue_entry.project_blueprint_id,
                    "delivery_task_id": queue_entry.delivery_task_id,
                    "crew_seed": queue_entry.crew_seed,
                    "info": "Mensaje en cola en base de datos. Mission Control lo deja disponible para el runtime interno.",
                }
            ),
            200,
        )

    @app.route("/api/message-queue", methods=["GET"])
    def get_message_queue():
        statuses = request.args.getlist("status")
        if not statuses:
            statuses = ["pending", "processing"]
        queue_entries = app.extensions["queue_dispatcher"].list_entries(
            statuses=tuple(statuses),
            limit=min(int(request.args.get("limit", 100)), 200),
        )
        return jsonify(
            [
                app.extensions["queue_dispatcher"].serialize(queue_entry)
                for queue_entry in queue_entries
            ]
        )

    @app.route("/api/message-queue/<message_id>", methods=["DELETE"])
    def delete_queued_message(message_id: str):
        try:
            queue_entry_id = int(message_id)
        except ValueError:
            return jsonify({"error": "Message id must be numeric"}), 400

        deleted = app.extensions["queue_dispatcher"].delete_entry(queue_entry_id)
        if deleted:
            return jsonify({"status": "deleted", "message_id": message_id})
        return jsonify({"error": "Message not found"}), 404

    @app.route("/api/runtime/health", methods=["GET"])
    def runtime_health():
        runtime = app.extensions["mission_control_runtime"]
        return jsonify(runtime.healthcheck())

    @app.route("/api/runtime/model-profiles", methods=["GET"])
    def runtime_model_profiles():
        runtime = app.extensions["mission_control_runtime"]
        return jsonify(runtime.model_registry.describe())

    @app.route("/api/runtime/tools", methods=["GET"])
    def runtime_tools():
        runtime = app.extensions["mission_control_runtime"]
        return jsonify(runtime.describe_tools())

    @app.route("/api/runtime/crew-seeds", methods=["GET"])
    def runtime_crew_seeds():
        runtime = app.extensions["mission_control_runtime"]
        return jsonify(runtime.describe_crew_seeds())

    @app.route("/api/runtime/recover-queue", methods=["POST"])
    def runtime_recover_queue():
        runtime = app.extensions["mission_control_runtime"]
        payload = request.get_json(silent=True) or {}
        recovered_entries = runtime.recover_stale_processing(
            stale_after_seconds=payload.get("stale_after_seconds"),
            target_agent=payload.get("target_agent"),
        )
        return jsonify(
            {
                "status": "ok",
                "recovered_count": len(recovered_entries),
                "recovered_entries": recovered_entries,
            }
        )

    @app.route("/api/runtime/dispatch", methods=["POST"])
    def runtime_dispatch():
        runtime = app.extensions["mission_control_runtime"]
        if not runtime.dispatch_ready:
            return (
                jsonify(
                    {
                        "status": "disabled",
                        "dispatch_ready": False,
                        "results": [],
                    }
                ),
                409,
            )

        payload = request.get_json(silent=True) or {}
        if payload.get("queue_entry_id") is not None:
            try:
                queue_entry_id = int(payload["queue_entry_id"])
            except (TypeError, ValueError):
                return jsonify({"error": "queue_entry_id must be numeric"}), 400
        else:
            queue_entry_id = None

        results = runtime.process_pending(
            limit=payload.get("limit"),
            target_agent=payload.get("target_agent"),
            queue_entry_id=queue_entry_id,
        )
        return jsonify(
            {
                "status": "ok",
                "dispatch_ready": True,
                "dispatched_count": len(results),
                "results": results,
            }
        )

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
