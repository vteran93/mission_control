# app.py - Flask Backend para Mission Control
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from database import db, Agent, Task, Message, Document, Notification, DaemonLog, TaskQueue, Sprint
from datetime import datetime
import os
import subprocess
import threading

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mission_control.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
CORS(app)

db.init_app(app)


# ============================================
# AGENT WAKE-UP LOGIC
# ============================================

import fcntl
import tempfile

def trigger_agent_wake(agent_label):
    """Trigger agent heartbeat script asynchronously with lock"""
    def run_heartbeat():
        lock_file = f"/home/victor/clawd/agents/{agent_label}/locks/heartbeat.lock"
        
        # Try to acquire lock
        try:
            with open(lock_file, 'w') as lock:
                # Non-blocking lock
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                
                # Lock acquired, run heartbeat
                script_path = f"/home/victor/.local/bin/{agent_label}-heartbeat.sh"
                if os.path.exists(script_path):
                    try:
                        subprocess.run(['/bin/bash', script_path], timeout=60)
                    except Exception as e:
                        print(f"Error triggering {agent_label}: {e}")
                
                # Lock automatically released when file closes
        except BlockingIOError:
            # Another process is already running
            print(f"{agent_label} already running, skipping")
        except Exception as e:
            print(f"Error with lock for {agent_label}: {e}")
    
    # Run in background thread to not block API response
    thread = threading.Thread(target=run_heartbeat)
    thread.daemon = True
    thread.start()


# ============================================
# API ENDPOINTS
# ============================================

@app.route('/')
def index():
    """Dashboard principal"""
    import time
    cache_bust = int(time.time())
    return render_template('index.html', cache_bust=cache_bust)


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
        sprint_filter = request.args.get('sprint_id', type=int)
        
        query = Task.query
        if status_filter:
            query = query.filter_by(status=status_filter)
        if sprint_filter:
            query = query.filter_by(sprint_id=sprint_filter)
            
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
            sprint_id=data.get('sprint_id'),
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
        if 'sprint_id' in data:
            task.sprint_id = data['sprint_id']
        
        task.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify(task.to_dict())


@app.route('/api/sprints', methods=['GET', 'POST'])
def sprints():
    """Listar o crear sprints"""
    if request.method == 'GET':
        sprints = Sprint.query.order_by(Sprint.created_at.desc()).all()
        return jsonify([s.to_dict() for s in sprints])
    
    elif request.method == 'POST':
        data = request.json
        sprint = Sprint(
            name=data['name'],
            goal=data.get('goal', ''),
            start_date=datetime.fromisoformat(data['start_date']) if data.get('start_date') else None,
            end_date=datetime.fromisoformat(data['end_date']) if data.get('end_date') else None,
            status=data.get('status', 'active')
        )
        db.session.add(sprint)
        db.session.commit()
        return jsonify(sprint.to_dict()), 201


@app.route('/api/sprints/<int:sprint_id>', methods=['GET', 'PUT'])
def sprint_detail(sprint_id):
    """Obtener o actualizar sprint"""
    sprint = Sprint.query.get_or_404(sprint_id)
    
    if request.method == 'GET':
        # Include tasks in response
        tasks = Task.query.filter_by(sprint_id=sprint_id).all()
        sprint_dict = sprint.to_dict()
        sprint_dict['tasks'] = [t.to_dict() for t in tasks]
        sprint_dict['task_count'] = len(tasks)
        return jsonify(sprint_dict)
    
    elif request.method == 'PUT':
        data = request.json
        if 'status' in data:
            sprint.status = data['status']
        if 'name' in data:
            sprint.name = data['name']
        if 'goal' in data:
            sprint.goal = data['goal']
        
        db.session.commit()
        return jsonify(sprint.to_dict())


@app.route('/api/messages', methods=['GET', 'POST'])
def messages():
    """Listar o crear mensajes"""
    if request.method == 'GET':
        task_id = request.args.get('task_id', type=int)
        show_hidden = request.args.get('show_hidden', 'false').lower() == 'true'
        
        query = Message.query
        
        if task_id:
            query = query.filter_by(task_id=task_id)
        
        # Filter by visibility (default: only visible messages)
        if not show_hidden:
            query = query.filter_by(visible=True)
        
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
        
        # Trigger agent wake-up if message mentions them
        content_lower = data['content'].lower()
        if 'jarvis-pm' in content_lower:
            trigger_agent_wake('jarvis-pm')
        if 'jarvis-dev' in content_lower:
            trigger_agent_wake('jarvis-dev')
        if 'jarvis-qa' in content_lower:
            trigger_agent_wake('jarvis-qa')
        
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
        content=f"📤 → {target_agent}: {message_content}"
    )
    db.session.add(message)
    db.session.commit()
    
    # Escribir a archivo para que Clawdbot lo procese (polling simple)
    queue_dir = os.path.expanduser('~/clawd/mission_control_queue')
    os.makedirs(queue_dir, exist_ok=True)
    
    import uuid
    message_id = str(uuid.uuid4())[:8]
    message_file = os.path.join(queue_dir, f"{message_id}_{target_agent}.json")
    
    import json
    with open(message_file, 'w') as f:
        json.dump({
            'target_agent': target_agent,
            'message': message_content,
            'task_id': task_id,
            'timestamp': datetime.utcnow().isoformat()
        }, f, indent=2)
    
    # Generar comando sessions_send (por si falla el polling)
    sessions_send_command = f"sessions_send(label='{target_agent}', message='''{message_content}''')"
    
    return jsonify({
        'status': 'queued',
        'target_agent': target_agent,
        'message': message_content,
        'message_id': message_id,
        'info': 'Mensaje en cola. Clawdbot lo procesará automáticamente.'
    }), 200


@app.route('/api/message-queue', methods=['GET'])
def get_message_queue():
    """
    Obtener mensajes pendientes de envío (para que Clawdbot los procese)
    
    Returns:
    [
        {
            "message_id": "abc123",
            "target_agent": "jarvis-qa",
            "message": "...",
            "task_id": 2,
            "timestamp": "..."
        }
    ]
    """
    queue_dir = os.path.expanduser('~/clawd/mission_control_queue')
    os.makedirs(queue_dir, exist_ok=True)
    
    import json
    import glob
    
    messages = []
    for filepath in glob.glob(os.path.join(queue_dir, '*.json')):
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                data['message_id'] = os.path.basename(filepath).replace('.json', '')
                data['filepath'] = filepath
                messages.append(data)
        except Exception as e:
            print(f"Error reading {filepath}: {e}")
    
    return jsonify(messages)


@app.route('/api/message-queue/<message_id>', methods=['DELETE'])
def delete_queued_message(message_id):
    """Eliminar mensaje de la cola (después de procesarlo)"""
    queue_dir = os.path.expanduser('~/clawd/mission_control_queue')
    
    import glob
    for filepath in glob.glob(os.path.join(queue_dir, f"{message_id}_*.json")):
        try:
            os.remove(filepath)
            return jsonify({'status': 'deleted', 'message_id': message_id})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    return jsonify({'error': 'Message not found'}), 404


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
    
    # Filter messages: only visible=True (Sprint 2 context)
    recent_messages = Message.query.filter_by(visible=True)\
        .order_by(Message.created_at.desc()).limit(10).all()
    
    unread_notifications = Notification.query.filter_by(delivered=False).count()
    
    return jsonify({
        'agents': [a.to_dict() for a in agents],
        'tasks_summary': tasks_by_status,
        'recent_messages': [m.to_dict() for m in recent_messages],
        'unread_notifications': unread_notifications
    })


@app.route('/api/daemons/<agent_name>/logs', methods=['GET'])
def get_daemon_logs(agent_name):
    """
    Get recent daemon logs for an agent
    
    Query params:
    - limit: number of logs (default 50, max 200)
    - level: filter by log level (DEBUG, INFO, WARNING, ERROR)
    - since: timestamp to get logs since (ISO format)
    """
    from database import DaemonLog
    
    # Validate agent name
    valid_agents = ['dev', 'qa', 'pm']
    if agent_name not in valid_agents:
        return jsonify({'error': f'Invalid agent. Must be one of: {valid_agents}'}), 400
    
    # Parse query params
    limit = min(int(request.args.get('limit', 50)), 200)
    level = request.args.get('level', '').upper()
    since = request.args.get('since')
    
    # Build query
    query = DaemonLog.query.filter_by(agent_name=agent_name)
    
    if level and level in ['DEBUG', 'INFO', 'WARNING', 'ERROR']:
        query = query.filter_by(level=level)
    
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
            query = query.filter(DaemonLog.timestamp >= since_dt)
        except:
            pass
    
    logs = query.order_by(DaemonLog.timestamp.desc()).limit(limit).all()
    
    return jsonify({
        'agent_name': agent_name,
        'count': len(logs),
        'logs': [log.to_dict() for log in logs]
    })


@app.route('/api/daemons/logs/all', methods=['GET'])
def get_all_daemon_logs():
    """Get recent logs from all daemons (for overview)"""
    from database import DaemonLog
    
    limit = min(int(request.args.get('limit', 100)), 500)
    
    logs = DaemonLog.query.order_by(DaemonLog.timestamp.desc()).limit(limit).all()
    
    # Group by agent for easy rendering
    logs_by_agent = {'dev': [], 'qa': [], 'pm': []}
    for log in logs:
        if log.agent_name in logs_by_agent:
            logs_by_agent[log.agent_name].append(log.to_dict())
    
    return jsonify({
        'count': len(logs),
        'logs_by_agent': logs_by_agent
    })


# ============================================
# INITIALIZATION
# ============================================

@app.route('/api/queue', methods=['GET'])
def get_task_queue():
    """Get task queue status and recent tasks"""
    
    # Get queue summary
    summary = {
        'pending': TaskQueue.query.filter_by(status='pending').count(),
        'processing': TaskQueue.query.filter_by(status='processing').count(),
        'completed': TaskQueue.query.filter_by(status='completed').count(),
        'failed': TaskQueue.query.filter_by(status='failed').count(),
    }
    
    # Get recent tasks
    limit = min(int(request.args.get('limit', 20)), 100)
    recent_tasks = TaskQueue.query.order_by(TaskQueue.created_at.desc()).limit(limit).all()
    
    # Get pending tasks (detailed)
    pending_tasks = TaskQueue.query.filter_by(status='pending').order_by(TaskQueue.created_at.asc()).all()
    
    return jsonify({
        'summary': summary,
        'recent_tasks': [t.to_dict() for t in recent_tasks],
        'pending_tasks': [t.to_dict() for t in pending_tasks]
    })


@app.route('/api/queue/<int:task_id>', methods=['GET'])
def get_task_detail(task_id):
    """Get detailed info for a specific queued task"""
    task = TaskQueue.query.get_or_404(task_id)
    return jsonify(task.to_dict())


@app.route('/api/messages/visibility', methods=['POST'])
def toggle_messages_visibility():
    """
    Bulk update message visibility for sprint context management
    
    POST /api/messages/visibility
    {
        "action": "hide_sprint_1" | "show_all" | "hide_before_date",
        "date": "2026-02-03T17:00:00" (optional, for hide_before_date)
    }
    """
    data = request.json
    action = data.get('action')
    
    if action == 'hide_sprint_1':
        # Hide all messages from Sprint 1 tasks (1-10)
        result = db.session.execute(
            db.update(Message).where(Message.task_id.between(1, 10)).values(visible=False)
        )
        db.session.commit()
        return jsonify({
            'status': 'success',
            'action': 'hide_sprint_1',
            'rows_updated': result.rowcount
        })
    
    elif action == 'show_all':
        # Show all messages
        result = db.session.execute(
            db.update(Message).values(visible=True)
        )
        db.session.commit()
        return jsonify({
            'status': 'success',
            'action': 'show_all',
            'rows_updated': result.rowcount
        })
    
    elif action == 'hide_before_date':
        # Hide all messages before a specific date
        date_str = data.get('date')
        if not date_str:
            return jsonify({'error': 'date parameter required'}), 400
        
        cutoff_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        result = db.session.execute(
            db.update(Message).where(Message.created_at < cutoff_date).values(visible=False)
        )
        db.session.commit()
        return jsonify({
            'status': 'success',
            'action': 'hide_before_date',
            'cutoff': date_str,
            'rows_updated': result.rowcount
        })
    
    else:
        return jsonify({'error': f'Unknown action: {action}'}), 400


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
