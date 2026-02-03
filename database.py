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


class Task(db.Model):
    """Tareas/Tickets del sprint"""
    __tablename__ = 'tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(50), default='todo')  # todo, in_progress, review, done, blocked
    priority = db.Column(db.String(20), default='medium')  # low, medium, high, critical
    assignee_agent_ids = db.Column(db.String(200))  # Comma-separated IDs
    created_by = db.Column(db.String(100), default='Victor')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    project = db.relationship('Project', backref='tasks')
    
    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'title': self.title,
            'description': self.description,
            'status': self.status,
            'priority': self.priority,
            'assignee_agent_ids': self.assignee_agent_ids,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Message(db.Model):
    """Mensajes entre agentes sobre tareas"""
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=True)
    from_agent = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    attachments = db.Column(db.Text)  # JSON string con paths
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    task = db.relationship('Task', backref='messages')
    
    def to_dict(self):
        return {
            'id': self.id,
            'task_id': self.task_id,
            'from_agent': self.from_agent,
            'content': self.content,
            'attachments': self.attachments,
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
