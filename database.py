# database.py - SQLAlchemy Models para Mission Control
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Project(db.Model):
    """Proyectos con múltiples tareas"""
    __tablename__ = 'projects'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text)
    status = db.Column(db.String(50), default='active')  # active, paused, completed, archived
    repository_path = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'status': self.status,
            'repository_path': self.repository_path,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Agent(db.Model):
    """Agentes trabajando en el proyecto"""
    __tablename__ = 'agents'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    role = db.Column(db.String(50), nullable=False)  # dev, qa, pm
    session_key = db.Column(db.String(200))
    status = db.Column(db.String(50), default='idle')  # idle, working, blocked, offline
    last_seen_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'role': self.role,
            'session_key': self.session_key,
            'status': self.status,
            'last_seen_at': self.last_seen_at.isoformat() if self.last_seen_at else None
        }


class Sprint(db.Model):
    """Sprints para organización de tareas"""
    __tablename__ = 'sprints'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    goal = db.Column(db.Text)
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)
    status = db.Column(db.String(50), default='active')  # active, completed, archived
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'goal': self.goal,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Task(db.Model):
    """Tareas/Tickets del sprint"""
    __tablename__ = 'tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=True)
    sprint_id = db.Column(db.Integer, db.ForeignKey('sprints.id'), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(50), default='todo')  # todo, in_progress, review, done, blocked
    priority = db.Column(db.String(20), default='medium')  # low, medium, high, critical
    assignee_agent_ids = db.Column(db.String(200))  # Comma-separated IDs
    created_by = db.Column(db.String(100), default='Victor')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    project = db.relationship('Project', backref='tasks')
    sprint = db.relationship('Sprint', backref='tasks')
    
    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'sprint_id': self.sprint_id,
            'title': self.title,
            'description': self.description,
            'status': self.status,
            'priority': self.priority,
            'assignee_agent_ids': self.assignee_agent_ids,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'sprint_name': self.sprint.name if self.sprint else None
        }


class Message(db.Model):
    """Mensajes entre agentes sobre tareas"""
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=True)
    from_agent = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    attachments = db.Column(db.Text)  # JSON string con paths
    visible = db.Column(db.Boolean, default=True)  # Sprint context visibility
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    task = db.relationship('Task', backref='messages')
    
    def to_dict(self):
        return {
            'id': self.id,
            'task_id': self.task_id,
            'from_agent': self.from_agent,
            'content': self.content,
            'attachments': self.attachments,
            'visible': self.visible,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Document(db.Model):
    """Documentos/Artefactos generados"""
    __tablename__ = 'documents'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content_md = db.Column(db.Text)
    type = db.Column(db.String(50))  # code, spec, test, report
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    task = db.relationship('Task', backref='documents')
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'content_md': self.content_md,
            'type': self.type,
            'task_id': self.task_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Notification(db.Model):
    """Notificaciones para agentes o Scrum Master"""
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'), nullable=True)
    content = db.Column(db.Text, nullable=False)
    delivered = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    agent = db.relationship('Agent', backref='notifications')
    
    def to_dict(self):
        return {
            'id': self.id,
            'agent_id': self.agent_id,
            'content': self.content,
            'delivered': self.delivered,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class DaemonLog(db.Model):
    """Logs de daemons en tiempo real"""
    __tablename__ = 'daemon_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    agent_name = db.Column(db.String(50), nullable=False, index=True)  # 'dev', 'qa', 'pm'
    level = db.Column(db.String(20), nullable=False)  # DEBUG, INFO, WARNING, ERROR
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'agent_name': self.agent_name,
            'level': self.level,
            'message': self.message,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }


class TaskQueue(db.Model):
    """Cola de dispatch del runtime interno"""
    __tablename__ = 'task_queue'
    
    id = db.Column(db.Integer, primary_key=True)
    target_agent = db.Column(db.String(50), nullable=False, index=True)  # 'jarvis-dev', 'jarvis-qa', etc.
    message_id = db.Column(db.Integer, db.ForeignKey('messages.id'), nullable=False, index=True)
    project_blueprint_id = db.Column(db.Integer, db.ForeignKey('project_blueprints.id'), nullable=True, index=True)
    delivery_task_id = db.Column(db.Integer, db.ForeignKey('delivery_tasks.id'), nullable=True, index=True)
    from_agent = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text, nullable=False)
    priority = db.Column(db.String(20), default='normal')  # 'urgent', 'high', 'normal', 'low'
    crew_seed = db.Column(db.String(50), nullable=True, index=True)
    status = db.Column(db.String(20), default='pending', index=True)  # 'pending', 'processing', 'completed', 'failed'
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    
    # Legacy field kept for schema compatibility; Phase 0 uses it as generic runtime session key.
    clawdbot_session_key = db.Column(db.Text)
    error_message = db.Column(db.Text)
    retry_count = db.Column(db.Integer, default=0)
    runtime_metadata_json = db.Column(db.JSON, default=dict)
    
    # Relationship
    message = db.relationship('Message', backref='queued_tasks')
    project_blueprint = db.relationship('ProjectBlueprintRecord', backref='queued_tasks')
    delivery_task = db.relationship('DeliveryTaskRecord', backref='queued_tasks')
    
    def to_dict(self):
        return {
            'id': self.id,
            'target_agent': self.target_agent,
            'message_id': self.message_id,
            'project_blueprint_id': self.project_blueprint_id,
            'delivery_task_id': self.delivery_task_id,
            'from_agent': self.from_agent,
            'content': self.content[:200] + '...' if len(self.content) > 200 else self.content,
            'priority': self.priority,
            'crew_seed': self.crew_seed,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'runtime_session_key': self.clawdbot_session_key,
            'clawdbot_session_key': self.clawdbot_session_key,
            'error_message': self.error_message,
            'retry_count': self.retry_count,
            'runtime_metadata': self.runtime_metadata_json or {},
        }


class SpecDocumentRecord(db.Model):
    """Documento fuente ingerido para construir un blueprint"""
    __tablename__ = 'spec_documents'

    id = db.Column(db.Integer, primary_key=True)
    project_name = db.Column(db.String(200), nullable=False, index=True)
    doc_type = db.Column(db.String(50), nullable=False, index=True)
    path = db.Column(db.String(1000), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    metadata_json = db.Column(db.JSON, default=dict)
    content_hash = db.Column(db.String(64), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'project_name': self.project_name,
            'doc_type': self.doc_type,
            'path': self.path,
            'title': self.title,
            'metadata': self.metadata_json or {},
            'content_hash': self.content_hash,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class SpecSectionRecord(db.Model):
    """Seccion parseada de un documento fuente"""
    __tablename__ = 'spec_sections'

    id = db.Column(db.Integer, primary_key=True)
    spec_document_id = db.Column(db.Integer, db.ForeignKey('spec_documents.id'), nullable=False, index=True)
    heading_level = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    order_index = db.Column(db.Integer, nullable=False)

    spec_document = db.relationship('SpecDocumentRecord', backref='sections')

    def to_dict(self):
        return {
            'id': self.id,
            'spec_document_id': self.spec_document_id,
            'heading_level': self.heading_level,
            'title': self.title,
            'body': self.body,
            'order_index': self.order_index,
        }


class ProjectBlueprintRecord(db.Model):
    """Blueprint persistido generado desde el intake de specs"""
    __tablename__ = 'project_blueprints'

    id = db.Column(db.Integer, primary_key=True)
    project_name = db.Column(db.String(200), nullable=False, index=True)
    source_requirements_document_id = db.Column(db.Integer, db.ForeignKey('spec_documents.id'), nullable=False)
    source_roadmap_document_id = db.Column(db.Integer, db.ForeignKey('spec_documents.id'), nullable=False)
    capabilities_json = db.Column(db.JSON, default=list)
    acceptance_items_json = db.Column(db.JSON, default=list)
    issues_json = db.Column(db.JSON, default=list)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    requirements_document = db.relationship(
        'SpecDocumentRecord',
        foreign_keys=[source_requirements_document_id],
        backref='requirement_blueprints',
    )
    roadmap_document = db.relationship(
        'SpecDocumentRecord',
        foreign_keys=[source_roadmap_document_id],
        backref='roadmap_blueprints',
    )

    def to_dict(self):
        return {
            'id': self.id,
            'project_name': self.project_name,
            'source_requirements_document_id': self.source_requirements_document_id,
            'source_roadmap_document_id': self.source_roadmap_document_id,
            'capabilities': self.capabilities_json or [],
            'acceptance_items': self.acceptance_items_json or [],
            'issues': self.issues_json or [],
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class BlueprintRequirementRecord(db.Model):
    """Requirement normalizado dentro de un blueprint"""
    __tablename__ = 'blueprint_requirements'

    id = db.Column(db.Integer, primary_key=True)
    project_blueprint_id = db.Column(db.Integer, db.ForeignKey('project_blueprints.id'), nullable=False, index=True)
    requirement_id = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    source_section = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(50), nullable=False, index=True)
    summary = db.Column(db.Text, nullable=False)
    constraints_json = db.Column(db.JSON, default=list)
    acceptance_hints_json = db.Column(db.JSON, default=list)
    order_index = db.Column(db.Integer, nullable=False)

    blueprint = db.relationship('ProjectBlueprintRecord', backref='requirements')

    def to_dict(self):
        return {
            'id': self.id,
            'project_blueprint_id': self.project_blueprint_id,
            'requirement_id': self.requirement_id,
            'title': self.title,
            'source_section': self.source_section,
            'category': self.category,
            'summary': self.summary,
            'constraints': self.constraints_json or [],
            'acceptance_hints': self.acceptance_hints_json or [],
            'order_index': self.order_index,
        }


class DeliveryEpicRecord(db.Model):
    """Epic de entrega normalizado desde el roadmap"""
    __tablename__ = 'delivery_epics'

    id = db.Column(db.Integer, primary_key=True)
    project_blueprint_id = db.Column(db.Integer, db.ForeignKey('project_blueprints.id'), nullable=False, index=True)
    epic_id = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    objective = db.Column(db.Text, default='')
    order_index = db.Column(db.Integer, nullable=False)

    blueprint = db.relationship('ProjectBlueprintRecord', backref='delivery_epics')

    def to_dict(self):
        return {
            'id': self.id,
            'project_blueprint_id': self.project_blueprint_id,
            'epic_id': self.epic_id,
            'name': self.name,
            'objective': self.objective,
            'order_index': self.order_index,
        }


class DeliveryTaskRecord(db.Model):
    """Ticket de entrega persistido desde el roadmap"""
    __tablename__ = 'delivery_tasks'

    id = db.Column(db.Integer, primary_key=True)
    delivery_epic_id = db.Column(db.Integer, db.ForeignKey('delivery_epics.id'), nullable=False, index=True)
    ticket_id = db.Column(db.String(50), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    ticket_type = db.Column(db.String(50))
    priority = db.Column(db.String(50), index=True)
    estimate = db.Column(db.String(50))
    dependencies_json = db.Column(db.JSON, default=list)
    description = db.Column(db.Text, default='')
    acceptance_criteria_json = db.Column(db.JSON, default=list)
    order_index = db.Column(db.Integer, nullable=False)

    epic = db.relationship('DeliveryEpicRecord', backref='delivery_tasks')

    def to_dict(self):
        return {
            'id': self.id,
            'delivery_epic_id': self.delivery_epic_id,
            'ticket_id': self.ticket_id,
            'title': self.title,
            'ticket_type': self.ticket_type,
            'priority': self.priority,
            'estimate': self.estimate,
            'dependencies': self.dependencies_json or [],
            'description': self.description,
            'acceptance_criteria': self.acceptance_criteria_json or [],
            'order_index': self.order_index,
        }


class StageFeedbackRecord(db.Model):
    """Feedback producido en una etapa SCRUM del blueprint"""
    __tablename__ = 'stage_feedback'

    id = db.Column(db.Integer, primary_key=True)
    project_blueprint_id = db.Column(db.Integer, db.ForeignKey('project_blueprints.id'), nullable=False, index=True)
    stage_name = db.Column(db.String(50), nullable=False, index=True)
    status = db.Column(db.String(50), nullable=False, default='captured')
    source = db.Column(db.String(100), nullable=False, default='system')
    feedback_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    blueprint = db.relationship('ProjectBlueprintRecord', backref='stage_feedback')

    def to_dict(self):
        return {
            'id': self.id,
            'project_blueprint_id': self.project_blueprint_id,
            'stage_name': self.stage_name,
            'status': self.status,
            'source': self.source,
            'feedback_text': self.feedback_text,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class RetrospectiveItemRecord(db.Model):
    """Item de retrospective asociado a un blueprint"""
    __tablename__ = 'retrospective_items'

    id = db.Column(db.Integer, primary_key=True)
    project_blueprint_id = db.Column(db.Integer, db.ForeignKey('project_blueprints.id'), nullable=False, index=True)
    category = db.Column(db.String(50), nullable=False, index=True)
    summary = db.Column(db.Text, nullable=False)
    action_item = db.Column(db.Text)
    owner = db.Column(db.String(100))
    status = db.Column(db.String(50), nullable=False, default='open')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    blueprint = db.relationship('ProjectBlueprintRecord', backref='retrospective_items')

    def to_dict(self):
        return {
            'id': self.id,
            'project_blueprint_id': self.project_blueprint_id,
            'category': self.category,
            'summary': self.summary,
            'action_item': self.action_item,
            'owner': self.owner,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class SprintCycleRecord(db.Model):
    """Sprint persistido para un blueprint"""
    __tablename__ = 'sprint_cycles'

    id = db.Column(db.Integer, primary_key=True)
    project_blueprint_id = db.Column(db.Integer, db.ForeignKey('project_blueprints.id'), nullable=False, index=True)
    scrum_plan_id = db.Column(db.Integer, db.ForeignKey('scrum_plans.id'), nullable=True, index=True)
    name = db.Column(db.String(100), nullable=False)
    goal = db.Column(db.Text, default='')
    capacity = db.Column(db.Integer)
    status = db.Column(db.String(50), nullable=False, default='planned', index=True)
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)
    metadata_json = db.Column(db.JSON, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    blueprint = db.relationship('ProjectBlueprintRecord', backref='sprint_cycles')
    scrum_plan = db.relationship('ScrumPlanRecord', backref='sprint_cycles')

    def to_dict(self):
        return {
            'id': self.id,
            'project_blueprint_id': self.project_blueprint_id,
            'scrum_plan_id': self.scrum_plan_id,
            'name': self.name,
            'goal': self.goal,
            'capacity': self.capacity,
            'status': self.status,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'metadata': self.metadata_json or {},
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class SprintStageEventRecord(db.Model):
    """Evento canonico de etapas SCRUM sobre un blueprint"""
    __tablename__ = 'sprint_stage_events'

    id = db.Column(db.Integer, primary_key=True)
    project_blueprint_id = db.Column(db.Integer, db.ForeignKey('project_blueprints.id'), nullable=False, index=True)
    stage_name = db.Column(db.String(50), nullable=False, index=True)
    status = db.Column(db.String(50), nullable=False, index=True)
    source = db.Column(db.String(100), nullable=False, default='system')
    summary = db.Column(db.Text, nullable=False)
    metadata_json = db.Column(db.JSON, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    blueprint = db.relationship('ProjectBlueprintRecord', backref='sprint_stage_events')

    def to_dict(self):
        return {
            'id': self.id,
            'project_blueprint_id': self.project_blueprint_id,
            'stage_name': self.stage_name,
            'status': self.status,
            'source': self.source,
            'summary': self.summary,
            'metadata': self.metadata_json or {},
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ScrumPlanRecord(db.Model):
    """Plan Scrum autonomo versionado para un blueprint"""
    __tablename__ = 'scrum_plans'

    id = db.Column(db.Integer, primary_key=True)
    project_blueprint_id = db.Column(db.Integer, db.ForeignKey('project_blueprints.id'), nullable=False, index=True)
    version = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(50), nullable=False, default='active', index=True)
    planning_mode = db.Column(db.String(50), nullable=False, default='autonomous', index=True)
    source = db.Column(db.String(100), nullable=False, default='heuristic')
    sprint_capacity = db.Column(db.Integer, nullable=False)
    sprint_length_days = db.Column(db.Integer, nullable=False)
    velocity_factor = db.Column(db.Float, nullable=False, default=1.0)
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)
    confidence_score = db.Column(db.Float, nullable=False, default=0.0)
    risk_score = db.Column(db.Integer, nullable=False, default=0)
    risk_level = db.Column(db.String(50), nullable=False, default='low', index=True)
    escalation_trigger = db.Column(db.String(100), nullable=False, default='none', index=True)
    replan_reason = db.Column(db.Text)
    summary_json = db.Column(db.JSON, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    blueprint = db.relationship('ProjectBlueprintRecord', backref='scrum_plans')

    __table_args__ = (
        db.UniqueConstraint('project_blueprint_id', 'version', name='uq_scrum_plans_blueprint_version'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'project_blueprint_id': self.project_blueprint_id,
            'version': self.version,
            'status': self.status,
            'planning_mode': self.planning_mode,
            'source': self.source,
            'sprint_capacity': self.sprint_capacity,
            'sprint_length_days': self.sprint_length_days,
            'velocity_factor': self.velocity_factor,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'confidence_score': self.confidence_score,
            'risk_score': self.risk_score,
            'risk_level': self.risk_level,
            'escalation_trigger': self.escalation_trigger,
            'replan_reason': self.replan_reason,
            'summary': self.summary_json or {},
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ScrumPlanItemRecord(db.Model):
    """Plan item canonico por ticket dentro de un Scrum plan"""
    __tablename__ = 'scrum_plan_items'

    id = db.Column(db.Integer, primary_key=True)
    scrum_plan_id = db.Column(db.Integer, db.ForeignKey('scrum_plans.id'), nullable=False, index=True)
    project_blueprint_id = db.Column(db.Integer, db.ForeignKey('project_blueprints.id'), nullable=False, index=True)
    delivery_task_id = db.Column(db.Integer, db.ForeignKey('delivery_tasks.id'), nullable=False, index=True)
    sprint_cycle_id = db.Column(db.Integer, db.ForeignKey('sprint_cycles.id'), nullable=True, index=True)
    plan_status = db.Column(db.String(50), nullable=False, default='planned', index=True)
    readiness_status = db.Column(db.String(50), nullable=False, default='needs_clarification', index=True)
    assignee_role = db.Column(db.String(50), nullable=True, index=True)
    sprint_order = db.Column(db.Integer)
    sequence_index = db.Column(db.Integer, nullable=False)
    dependency_depth = db.Column(db.Integer, nullable=False, default=0)
    story_points = db.Column(db.Integer, nullable=False, default=0)
    capacity_cost = db.Column(db.Integer, nullable=False, default=0)
    risk_score = db.Column(db.Integer, nullable=False, default=0)
    risk_level = db.Column(db.String(50), nullable=False, default='low', index=True)
    depends_on_json = db.Column(db.JSON, default=list)
    blocked_by_json = db.Column(db.JSON, default=list)
    definition_of_ready_json = db.Column(db.JSON, default=list)
    definition_of_done_json = db.Column(db.JSON, default=list)
    planning_notes = db.Column(db.Text)
    metadata_json = db.Column(db.JSON, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    scrum_plan = db.relationship('ScrumPlanRecord', backref='items')
    blueprint = db.relationship('ProjectBlueprintRecord', backref='scrum_plan_items')
    delivery_task = db.relationship('DeliveryTaskRecord', backref='scrum_plan_items')
    sprint_cycle = db.relationship('SprintCycleRecord', backref='scrum_plan_items')

    __table_args__ = (
        db.UniqueConstraint('scrum_plan_id', 'delivery_task_id', name='uq_scrum_plan_items_plan_task'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'scrum_plan_id': self.scrum_plan_id,
            'project_blueprint_id': self.project_blueprint_id,
            'delivery_task_id': self.delivery_task_id,
            'sprint_cycle_id': self.sprint_cycle_id,
            'ticket_id': self.delivery_task.ticket_id if self.delivery_task else None,
            'title': self.delivery_task.title if self.delivery_task else None,
            'sprint_name': self.sprint_cycle.name if self.sprint_cycle else None,
            'plan_status': self.plan_status,
            'readiness_status': self.readiness_status,
            'assignee_role': self.assignee_role,
            'sprint_order': self.sprint_order,
            'sequence_index': self.sequence_index,
            'dependency_depth': self.dependency_depth,
            'story_points': self.story_points,
            'capacity_cost': self.capacity_cost,
            'risk_score': self.risk_score,
            'risk_level': self.risk_level,
            'depends_on': self.depends_on_json or [],
            'blocked_by': self.blocked_by_json or [],
            'definition_of_ready': self.definition_of_ready_json or [],
            'definition_of_done': self.definition_of_done_json or [],
            'planning_notes': self.planning_notes,
            'metadata': self.metadata_json or {},
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class AgentRunRecord(db.Model):
    """Corrida de un agente dentro del flujo agentic"""
    __tablename__ = 'agent_runs'

    id = db.Column(db.Integer, primary_key=True)
    project_blueprint_id = db.Column(db.Integer, db.ForeignKey('project_blueprints.id'), nullable=False, index=True)
    agent_name = db.Column(db.String(100), nullable=False, index=True)
    agent_role = db.Column(db.String(50), nullable=True, index=True)
    provider = db.Column(db.String(50), nullable=True, index=True)
    model = db.Column(db.String(200), nullable=True)
    status = db.Column(db.String(50), nullable=False, default='queued', index=True)
    input_summary = db.Column(db.Text)
    output_summary = db.Column(db.Text)
    error_message = db.Column(db.Text)
    runtime_name = db.Column(db.String(100))
    started_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    completed_at = db.Column(db.DateTime)

    blueprint = db.relationship('ProjectBlueprintRecord', backref='agent_runs')

    def to_dict(self):
        return {
            'id': self.id,
            'project_blueprint_id': self.project_blueprint_id,
            'agent_name': self.agent_name,
            'agent_role': self.agent_role,
            'provider': self.provider,
            'model': self.model,
            'status': self.status,
            'input_summary': self.input_summary,
            'output_summary': self.output_summary,
            'error_message': self.error_message,
            'runtime_name': self.runtime_name,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }


class TaskExecutionRecord(db.Model):
    """Intento de ejecucion sobre un ticket derivado del roadmap"""
    __tablename__ = 'task_executions'

    id = db.Column(db.Integer, primary_key=True)
    project_blueprint_id = db.Column(db.Integer, db.ForeignKey('project_blueprints.id'), nullable=False, index=True)
    delivery_task_id = db.Column(db.Integer, db.ForeignKey('delivery_tasks.id'), nullable=False, index=True)
    agent_run_id = db.Column(db.Integer, db.ForeignKey('agent_runs.id'), nullable=True, index=True)
    status = db.Column(db.String(50), nullable=False, default='queued', index=True)
    attempt_number = db.Column(db.Integer, nullable=False, default=1)
    summary = db.Column(db.Text)
    error_message = db.Column(db.Text)
    started_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    completed_at = db.Column(db.DateTime)

    blueprint = db.relationship('ProjectBlueprintRecord', backref='task_executions')
    delivery_task = db.relationship('DeliveryTaskRecord', backref='task_executions')
    agent_run = db.relationship('AgentRunRecord', backref='task_executions')

    def to_dict(self):
        return {
            'id': self.id,
            'project_blueprint_id': self.project_blueprint_id,
            'delivery_task_id': self.delivery_task_id,
            'agent_run_id': self.agent_run_id,
            'status': self.status,
            'attempt_number': self.attempt_number,
            'summary': self.summary,
            'error_message': self.error_message,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'ticket_id': self.delivery_task.ticket_id if self.delivery_task else None,
        }


class ArtifactRecord(db.Model):
    """Artefacto generado durante una corrida o ejecucion"""
    __tablename__ = 'artifacts'

    id = db.Column(db.Integer, primary_key=True)
    project_blueprint_id = db.Column(db.Integer, db.ForeignKey('project_blueprints.id'), nullable=False, index=True)
    agent_run_id = db.Column(db.Integer, db.ForeignKey('agent_runs.id'), nullable=True, index=True)
    task_execution_id = db.Column(db.Integer, db.ForeignKey('task_executions.id'), nullable=True, index=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=True, index=True)
    name = db.Column(db.String(255), nullable=False)
    artifact_type = db.Column(db.String(50), nullable=False, index=True)
    uri = db.Column(db.String(1000), nullable=False)
    metadata_json = db.Column(db.JSON, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    blueprint = db.relationship('ProjectBlueprintRecord', backref='artifacts')
    agent_run = db.relationship('AgentRunRecord', backref='artifacts')
    task_execution = db.relationship('TaskExecutionRecord', backref='artifacts')
    document = db.relationship('Document', backref='artifacts')

    def to_dict(self):
        return {
            'id': self.id,
            'project_blueprint_id': self.project_blueprint_id,
            'agent_run_id': self.agent_run_id,
            'task_execution_id': self.task_execution_id,
            'document_id': self.document_id,
            'name': self.name,
            'artifact_type': self.artifact_type,
            'uri': self.uri,
            'metadata': self.metadata_json or {},
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class HandoffRecord(db.Model):
    """Traspaso entre agentes con contexto de decision"""
    __tablename__ = 'handoffs'

    id = db.Column(db.Integer, primary_key=True)
    project_blueprint_id = db.Column(db.Integer, db.ForeignKey('project_blueprints.id'), nullable=False, index=True)
    task_execution_id = db.Column(db.Integer, db.ForeignKey('task_executions.id'), nullable=True, index=True)
    from_agent = db.Column(db.String(100), nullable=False, index=True)
    to_agent = db.Column(db.String(100), nullable=False, index=True)
    status = db.Column(db.String(50), nullable=False, default='requested', index=True)
    reason = db.Column(db.Text, nullable=False)
    context_json = db.Column(db.JSON, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    blueprint = db.relationship('ProjectBlueprintRecord', backref='handoffs')
    task_execution = db.relationship('TaskExecutionRecord', backref='handoffs')

    def to_dict(self):
        return {
            'id': self.id,
            'project_blueprint_id': self.project_blueprint_id,
            'task_execution_id': self.task_execution_id,
            'from_agent': self.from_agent,
            'to_agent': self.to_agent,
            'status': self.status,
            'reason': self.reason,
            'context': self.context_json or {},
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class LLMInvocationRecord(db.Model):
    """Invocacion de modelo LLM con trazabilidad de costo y latencia"""
    __tablename__ = 'llm_invocations'

    id = db.Column(db.Integer, primary_key=True)
    project_blueprint_id = db.Column(db.Integer, db.ForeignKey('project_blueprints.id'), nullable=False, index=True)
    agent_run_id = db.Column(db.Integer, db.ForeignKey('agent_runs.id'), nullable=True, index=True)
    provider = db.Column(db.String(50), nullable=False, index=True)
    model = db.Column(db.String(200), nullable=False, index=True)
    purpose = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(50), nullable=False, default='completed', index=True)
    prompt_tokens = db.Column(db.Integer, nullable=False, default=0)
    completion_tokens = db.Column(db.Integer, nullable=False, default=0)
    latency_ms = db.Column(db.Integer)
    cost_usd = db.Column(db.Float, nullable=False, default=0.0)
    metadata_json = db.Column(db.JSON, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    blueprint = db.relationship('ProjectBlueprintRecord', backref='llm_invocations')
    agent_run = db.relationship('AgentRunRecord', backref='llm_invocations')

    def to_dict(self):
        return {
            'id': self.id,
            'project_blueprint_id': self.project_blueprint_id,
            'agent_run_id': self.agent_run_id,
            'provider': self.provider,
            'model': self.model,
            'purpose': self.purpose,
            'status': self.status,
            'prompt_tokens': self.prompt_tokens,
            'completion_tokens': self.completion_tokens,
            'latency_ms': self.latency_ms,
            'cost_usd': self.cost_usd,
            'metadata': self.metadata_json or {},
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
