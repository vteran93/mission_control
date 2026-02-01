# Mission Control - Scrum Dashboard para BlackForge MVP

Dashboard web para coordinar agentes (Jarvis-Dev, Jarvis-QA) en el desarrollo de BlackForge.

## 🚀 Quick Start

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Inicializar base de datos
python3 init_db.py

# 3. Arrancar servidor
python3 app.py
```

Abre: **http://localhost:5001**

---

## 📡 Agent API

Los agentes usan `agent_api.py` para interactuar con Mission Control.

### Ejemplo Básico

```python
from agent_api import MissionControlAPI

# Inicializar agente
jarvis = MissionControlAPI("Jarvis-Dev")

# Actualizar estado
jarvis.update_status("working")

# Crear tarea
task_id = jarvis.create_task(
    title="TICKET-001: Pydantic Models",
    description="Implementar schemas con TDD",
    priority="critical",
    status="in_progress"
)

# Enviar mensaje
jarvis.send_message(
    content="🟢 GREEN: 39 tests passing, 99% coverage",
    task_id=task_id
)

# Crear documento
jarvis.create_document(
    title="test_models.py",
    content_md="```python\n# tests\n```",
    doc_type="test",
    task_id=task_id
)

# Actualizar tarea
jarvis.update_task(task_id, status="done")

# Notificar Scrum Master
jarvis.notify_scrum_master("✅ TICKET-001 completado")

# Enviar mensaje a otro agente
jarvis.send_message_to_agent(
    target_agent="Jarvis-QA",
    message="🔔 TICKET-002 listo para review",
    task_id=task_id
)

# Cambiar estado
jarvis.update_status("idle")
```

---

## 💬 Mensajes Entre Agentes

### Opción 1: Desde Python (API)

```python
from agent_api import MissionControlAPI

api = MissionControlAPI('Victor')
api.send_message_to_agent(
    target_agent='Jarvis-QA',
    message='Revisa TICKET-002 por favor'
)
```

Esto te dará el comando `sessions_send` que debes copiar en Clawdbot.

### Opción 2: Script Helper (Terminal)

```bash
cd /home/victor/repositories/mission_control

# Enviar mensaje a Jarvis-QA
python3 send_agent_message.py \
  --to Jarvis-QA \
  --message "Revisa TICKET-002 por favor"

# Con tarea asociada
python3 send_agent_message.py \
  --to Jarvis-Dev \
  --message "Excelente trabajo!" \
  --task 2

# Ayuda
python3 send_agent_message.py --help
```

El script te dará el comando `sessions_send` listo para copiar en Clawdbot.

### Opción 3: Directo desde Clawdbot

Si ya conoces el label del agente:

```
sessions_send(label='jarvis-qa', message='Tu mensaje aquí')
```

**Labels disponibles:**
- `jarvis-dev` → Jarvis-Dev
- `jarvis-qa` → Jarvis-QA

---

## 📊 API Endpoints

### Agents
- `GET /api/agents` - Listar agentes
- `POST /api/agents` - Crear agente
- `PUT /api/agents/:id` - Actualizar agente

### Tasks
- `GET /api/tasks` - Listar tareas
- `POST /api/tasks` - Crear tarea
- `PUT /api/tasks/:id` - Actualizar tarea
- `DELETE /api/tasks/:id` - Eliminar tarea

### Messages
- `GET /api/messages` - Listar mensajes
- `POST /api/messages` - Enviar mensaje

### Documents
- `GET /api/documents` - Listar documentos
- `POST /api/documents` - Crear documento

### Notifications
- `GET /api/notifications` - Listar notificaciones
- `POST /api/notifications` - Crear notificación

---

## 🗂️ Estructura

```
mission_control/
├── app.py                    # Flask app
├── agent_api.py              # Python client para agentes
├── send_agent_message.py     # Helper CLI para mensajes
├── init_db.py                # Database setup
├── requirements.txt
├── static/                   # CSS/JS
├── templates/                # HTML templates
└── mission_control.db        # SQLite database
```

---

## 🎯 Workflow Típico

1. **Jarvis-Dev** crea ticket y empieza trabajo
2. **Jarvis-Dev** envía updates vía `send_message()`
3. **Jarvis-Dev** cambia status a "review" y notifica **Jarvis-QA**
4. **Jarvis-QA** recibe mensaje, ejecuta tests, reporta findings
5. **Jarvis-Dev** corrige issues, notifica re-review
6. **Jarvis-QA** aprueba, **Jarvis-Dev** mergea y cierra ticket
7. **Scrum Master (Victor)** monitorea dashboard en tiempo real

---

## 🐛 Troubleshooting

**Dashboard no carga:**
```bash
# Verificar que el servidor esté corriendo
curl http://localhost:5001/api/agents

# Ver logs
tail -f app.log  # (si configuraste logging)
```

**Base de datos corrupta:**
```bash
rm mission_control.db
python3 init_db.py
```

**Agente no aparece en dashboard:**
```python
# Verificar que se creó correctamente
from agent_api import MissionControlAPI
api = MissionControlAPI("Jarvis-Dev")
print(f"Agent ID: {api.agent_id}")
```

---

**Estado:** ✅ v0.1.0 - Funcional  
**Próximo:** Integración con Clawdbot cron jobs
