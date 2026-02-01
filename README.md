# Mission Control 🎯

**Dashboard Scrum para coordinar agentes AI en BlackForge MVP**

---

## 📋 Features

- **Agentes:** Visualiza estado de Jarvis-Dev y Jarvis-QA en tiempo real
- **Sprint Board:** Kanban board (TODO → IN PROGRESS → REVIEW → DONE → BLOCKED)
- **Comunicación:** Chat entre agentes sobre tareas
- **Documentos:** Artefactos generados (código, specs, tests, reports)
- **Notificaciones:** Alertas para Scrum Master
- **Auto-refresh:** Actualización cada 5 segundos

---

## 🚀 Quick Start

### 1. Instalar dependencias

```bash
cd /home/victor/repositories/mission_control
pip install -r requirements.txt
```

### 2. Iniciar backend

```bash
python app.py
```

**Output esperado:**
```
✅ Agentes iniciales creados: Jarvis-Dev, Jarvis-QA
🚀 Mission Control Backend running on http://localhost:5001
```

### 3. Abrir dashboard

Navega a: **http://localhost:5001**

---

## 📊 Arquitectura

```
┌─────────────┐
│   Browser   │  ← Frontend (HTML/CSS/JS)
└──────┬──────┘
       │ HTTP (auto-refresh 5s)
       ▼
┌─────────────┐
│   Flask     │  ← Backend REST API
└──────┬──────┘
       │ SQLAlchemy
       ▼
┌─────────────┐
│  SQLite DB  │  ← mission_control.db
└─────────────┘
```

---

## 🗄️ Database Schema

### `agents`
- name, role (dev/qa), session_key, status, last_seen_at

### `tasks`
- title, description, status, priority, assignee_agent_ids, created_by

### `messages`
- task_id, from_agent, content, attachments, created_at

### `documents`
- title, content_md, type (code/spec/test/report), task_id

### `notifications`
- agent_id, content, delivered, created_at

---

## 🔌 API Endpoints

### Agents
- `GET /api/agents` - Listar agentes
- `POST /api/agents` - Crear agente
- `PUT /api/agents/<id>` - Actualizar estado

### Tasks
- `GET /api/tasks` - Listar tareas
- `POST /api/tasks` - Crear tarea
- `PUT /api/tasks/<id>` - Actualizar tarea

### Messages
- `GET /api/messages?task_id=<id>` - Mensajes de tarea
- `POST /api/messages` - Enviar mensaje

### Documents
- `GET /api/documents?task_id=<id>` - Documentos
- `POST /api/documents` - Crear documento

### Notifications
- `GET /api/notifications?unread=true` - Notificaciones
- `POST /api/notifications` - Crear notificación
- `POST /api/notifications/<id>/mark-delivered` - Marcar leída

### Dashboard
- `GET /api/dashboard` - Resumen completo (agents + tasks + messages)

---

## 🤖 Uso desde Agentes (Jarvis)

### Registrar presencia

```python
import requests

# Actualizar "last seen"
requests.put('http://localhost:5001/api/agents/1', json={
    'status': 'working',
    'last_seen_at': True
})
```

### Crear tarea

```python
requests.post('http://localhost:5001/api/tasks', json={
    'title': 'TICKET-001: Pydantic Models',
    'description': 'Implementar schemas con TDD',
    'status': 'in_progress',
    'priority': 'critical',
    'assignee_agent_ids': '1',  # Jarvis-Dev
    'created_by': 'Victor'
})
```

### Enviar mensaje

```python
requests.post('http://localhost:5001/api/messages', json={
    'task_id': 1,
    'from_agent': 'Jarvis-Dev',
    'content': '🔴 RED: Tests escritos para DocumentaryScript. Esperando implementación.'
})
```

### Crear documento

```python
requests.post('http://localhost:5001/api/documents', json={
    'title': 'test_documentary_script.py',
    'content_md': '```python\n# Test code here\n```',
    'type': 'test',
    'task_id': 1
})
```

### Notificar a Scrum Master

```python
requests.post('http://localhost:5001/api/notifications', json={
    'agent_id': None,  # Para Victor
    'content': '✅ TICKET-001 completado con 100% coverage'
})
```

---

## 🎨 UI/UX

**Colores:**
- Background: GitHub Dark (`#0d1117`)
- Panels: `#161b22`
- Borders: `#30363d`
- Primary: `#58a6ff` (blue)
- Success: `#56d364` (green)
- Warning: `#f0883e` (orange)
- Error: `#f85149` (red)

**Auto-refresh:** 5 segundos (countdown visible)

---

## 📝 Workflow Scrum

1. **Victor (Scrum Master)** crea tareas en el dashboard
2. **Jarvis-Dev** toma tarea, actualiza status → `in_progress`
3. **Jarvis-Dev** escribe mensajes reportando avance
4. **Jarvis-Dev** genera documentos (código, tests)
5. **Jarvis-Dev** cambia status → `review`
6. **Jarvis-QA** revisa, ejecuta tests, reporta bugs
7. **Jarvis-QA** aprueba → status `done` o rechaza → `blocked`
8. **Victor** monitorea todo en tiempo real

---

## 🐛 Troubleshooting

### Backend no arranca
```bash
# Verificar puerto libre
lsof -i :5001

# Matar proceso si está ocupado
kill -9 <PID>
```

### Frontend no carga datos
- Verificar CORS habilitado en Flask
- Abrir consola del navegador (F12) → ver errores de red

### DB corrupta
```bash
rm mission_control.db
python app.py  # Recrea DB automáticamente
```

---

## 🚀 Próximos Pasos

1. ✅ Dashboard funcional (DONE)
2. 🔄 Integración con agentes (Jarvis escribe a DB)
3. 🎨 Mejorar UI (modals para task details)
4. 📊 Gráficos de velocity/burndown
5. 🔔 Notificaciones push (WebSockets)

---

**Autor:** Jarvis 🤖  
**Scrum Master:** Victor  
**Proyecto:** BlackForge MVP
