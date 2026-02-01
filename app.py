# app.py - Flask Backend para Mission Control
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from database import db, Agent, Task, Message, Document, Notification
from datetime import datetime
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mission_control.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
CORS(app)

db.init_app(app)


# ============================================
# API ENDPOINTS
# ============================================

@app.route('/')
def index():
    """Dashboard principal"""
    return render_template('index.html')


@app.route('/api/agents', methods=['GET', 'POST'])
def agents():
    """Listar o crear agentes"""
    if request.method == 'GET':
        agents = Agent.query.all()
        return jsonify([a.to_dict() for a in agents])
    
    elif request.method == 'POST':
        data = request.json
        agent = Agent(
            name=data['name'],
            role=data['role'],
            session_key=data.get('session_key'),
            status=data.get('status', 'idle')
        )
        db.session.add(agent)
        db.session.commit()
        return jsonify(agent.to_dict()), 201


@app.route('/api/agents/<int:agent_id>', methods=['PUT'])
def update_agent(agent_id):
    """Actualizar estado de agente"""
    agent = Agent.query.get_or_404(agent_id)
    data = request.json
    
    if 'status' in data:
        agent.status = data['status']
    if 'last_seen_at' in data:
        agent.last_seen_at = datetime.utcnow()
    
    db.session.commit()
    return jsonify(agent.to_dict())


@app.route('/api/tasks', methods=['GET', 'POST'])
def tasks():
    """Listar o crear tareas"""
    if request.method == 'GET':
        status_filter = request.args.get('status')
        query = Task.query
        if status_filter:
            query = query.filter_by(status=status_filter)
        tasks = query.order_by(Task.created_at.desc()).all()
        return jsonify([t.to_dict() for t in tasks])
    
    elif request.method == 'POST':
        data = request.json
        task = Task(
            title=data['title'],
            description=data.get('description', ''),
            status=data.get('status', 'todo'),
            priority=data.get('priority', 'medium'),
            assignee_agent_ids=data.get('assignee_agent_ids', ''),
            created_by=data.get('created_by', 'Victor')
        )
        db.session.add(task)
        db.session.commit()
        return jsonify(task.to_dict()), 201


@app.route('/api/tasks/<int:task_id>', methods=['GET', 'PUT'])
def task_detail(task_id):
    """Obtener o actualizar tarea"""
    task = Task.query.get_or_404(task_id)
    
    if request.method == 'GET':
        return jsonify(task.to_dict())
    
    elif request.method == 'PUT':
        data = request.json
        if 'status' in data:
            task.status = data['status']
        if 'assignee_agent_ids' in data:
            task.assignee_agent_ids = data['assignee_agent_ids']
        if 'priority' in data:
            task.priority = data['priority']
        
        task.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify(task.to_dict())


@app.route('/api/messages', methods=['GET', 'POST'])
def messages():
    """Listar o crear mensajes"""
    if request.method == 'GET':
        task_id = request.args.get('task_id', type=int)
        query = Message.query
        if task_id:
            query = query.filter_by(task_id=task_id)
        messages = query.order_by(Message.created_at.desc()).limit(50).all()
        return jsonify([m.to_dict() for m in messages])
    
    elif request.method == 'POST':
        data = request.json
        message = Message(
            task_id=data.get('task_id'),
            from_agent=data['from_agent'],
            content=data['content'],
            attachments=data.get('attachments')
        )
        db.session.add(message)
        db.session.commit()
        return jsonify(message.to_dict()), 201


@app.route('/api/documents', methods=['GET', 'POST'])
def documents():
    """Listar o crear documentos"""
    if request.method == 'GET':
        task_id = request.args.get('task_id', type=int)
        query = Document.query
        if task_id:
            query = query.filter_by(task_id=task_id)
        docs = query.order_by(Document.created_at.desc()).all()
        return jsonify([d.to_dict() for d in docs])
    
    elif request.method == 'POST':
        data = request.json
        doc = Document(
            title=data['title'],
            content_md=data.get('content_md', ''),
            type=data.get('type', 'code'),
            task_id=data.get('task_id')
        )
        db.session.add(doc)
        db.session.commit()
        return jsonify(doc.to_dict()), 201


@app.route('/api/notifications', methods=['GET', 'POST'])
def notifications():
    """Listar o crear notificaciones"""
    if request.method == 'GET':
        unread_only = request.args.get('unread', 'false').lower() == 'true'
        query = Notification.query
        if unread_only:
            query = query.filter_by(delivered=False)
        notifs = query.order_by(Notification.created_at.desc()).limit(20).all()
        return jsonify([n.to_dict() for n in notifs])
    
    elif request.method == 'POST':
        data = request.json
        notif = Notification(
            agent_id=data.get('agent_id'),
            content=data['content'],
            delivered=False
        )
        db.session.add(notif)
        db.session.commit()
        return jsonify(notif.to_dict()), 201


@app.route('/api/notifications/<int:notif_id>/mark-delivered', methods=['POST'])
def mark_notification_delivered(notif_id):
    """Marcar notificación como leída"""
    notif = Notification.query.get_or_404(notif_id)
    notif.delivered = True
    db.session.commit()
    return jsonify(notif.to_dict())


@app.route('/api/send-agent-message', methods=['POST'])
def send_agent_message():
    """
    Enviar mensaje a un agente via Clawdbot sessions_send
    
    Payload:
    {
        "target_agent": "jarvis-qa",  // label del agente
        "message": "Tu mensaje aquí",
        "task_id": 2  // opcional
    }
    
    Returns:
    {
        "status": "queued",
        "target_agent": "jarvis-qa",
        "message": "...",
        "command": "sessions_send(...)"  // comando para ejecutar
    }
    """
    data = request.json
    target_agent = data.get('target_agent')
    message_content = data.get('message')
    task_id = data.get('task_id')
    
    if not target_agent or not message_content:
        return jsonify({'error': 'Missing target_agent or message'}), 400
    
    # Log en Mission Control (para historial)
    message = Message(
        task_id=task_id,
        from_agent='Victor',
        content=f"📤 Enviando a {target_agent}: {message_content[:100]}..."
    )
    db.session.add(message)
    db.session.commit()
    
    # Generar comando sessions_send
    sessions_send_command = f"sessions_send(label='{target_agent}', message='''{message_content}''')"
    
    return jsonify({
        'status': 'queued',
        'target_agent': target_agent,
        'message': message_content,
        'command': sessions_send_command,
        'info': 'Mensaje preparado. Ejecutar comando en Clawdbot.'
    }), 200


@app.route('/api/dashboard', methods=['GET'])
def dashboard():
    """Dashboard summary para frontend"""
    agents = Agent.query.all()
    tasks_by_status = {
        'todo': Task.query.filter_by(status='todo').count(),
        'in_progress': Task.query.filter_by(status='in_progress').count(),
        'review': Task.query.filter_by(status='review').count(),
        'done': Task.query.filter_by(status='done').count(),
        'blocked': Task.query.filter_by(status='blocked').count(),
    }
    recent_messages = Message.query.order_by(Message.created_at.desc()).limit(10).all()
    unread_notifications = Notification.query.filter_by(delivered=False).count()
    
    return jsonify({
        'agents': [a.to_dict() for a in agents],
        'tasks_summary': tasks_by_status,
        'recent_messages': [m.to_dict() for m in recent_messages],
        'unread_notifications': unread_notifications
    })


# ============================================
# INITIALIZATION
# ============================================

def init_db():
    """Crear tablas y datos iniciales"""
    with app.app_context():
        db.create_all()
        
        # Crear agentes iniciales si no existen
        if Agent.query.count() == 0:
            jarvis_dev = Agent(name='Jarvis-Dev', role='dev', status='idle')
            jarvis_qa = Agent(name='Jarvis-QA', role='qa', status='idle')
            db.session.add_all([jarvis_dev, jarvis_qa])
            db.session.commit()
            print("✅ Agentes iniciales creados: Jarvis-Dev, Jarvis-QA")


if __name__ == '__main__':
    init_db()
    print("🚀 Mission Control Backend running on http://localhost:5001")
    app.run(debug=True, host='0.0.0.0', port=5001)
