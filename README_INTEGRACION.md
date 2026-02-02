# Mission Control + Clawdbot - Guía de Integración

**Proyecto:** Mission Control (Dashboard multi-agente)  
**Stack:** Flask + SQLite + Clawdbot Sessions API  
**Idioma:** Español  
**Fecha:** 2026-02-02

---

## 📋 Índice

1. [Visión General](#visión-general)
2. [Arquitectura](#arquitectura)
3. [Componentes](#componentes)
4. [Flujo de Trabajo](#flujo-de-trabajo)
5. [Configuración Inicial](#configuración-inicial)
6. [Uso Diario](#uso-diario)
7. [Troubleshooting](#troubleshooting)

---

## Visión General

**Mission Control** es un sistema de coordinación multi-agente que integra:

- **Clawdbot Sessions API** - Gestión de agentes IA persistentes
- **Flask REST API** - Backend de coordinación y mensajería
- **SQLite Database** - Estado de tasks y mensajes
- **Dashboard Web** - Visualización del progreso
- **Agent Daemons** - Polling automático de mensajes

### ¿Qué Problema Resuelve?

Antes: Agentes independientes sin coordinación → duplicación, falta de visibilidad, no hay tracking.

Ahora: Flujo estructurado con roles claros:
- **Jarvis (PO)** → Coordina y asigna tickets
- **Jarvis-Dev** → Implementa código (TDD)
- **Jarvis-QA** → Revisa calidad antes de merge
- **Jarvis-PM** → Tracking de progreso (opcional)

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────┐
│                    VICTOR (Usuario)                      │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │  Clawdbot Webchat    │ (Canal principal de Victor)
          │  Session: main       │
          └──────────┬───────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │  Jarvis (PO)         │ (Coordinador, único que habla con Victor)
          │  Session: main       │
          └──────────┬───────────┘
                     │
                     ├─────────────────────────────────────┐
                     ▼                                     ▼
          ┌──────────────────────┐           ┌──────────────────────┐
          │  Mission Control API │           │  Clawdbot Sessions   │
          │  (Flask + SQLite)    │◄──────────┤  API (spawn/send)    │
          │  localhost:5001      │           │                      │
          └──────────┬───────────┘           └──────────────────────┘
                     │                                     │
                     │                                     │
         ┌───────────┴───────────┬─────────────────────────┴──────┐
         ▼                       ▼                                ▼
┌────────────────┐      ┌────────────────┐              ┌────────────────┐
│  Jarvis-Dev    │      │  Jarvis-QA     │              │  Jarvis-PM     │
│  (Developer)   │      │  (QA Engineer) │              │  (optional)    │
│  Subagent      │      │  Subagent      │              │  Subagent      │
└────────────────┘      └────────────────┘              └────────────────┘
         │                       │                                │
         └───────────────────────┴────────────────────────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │  Repositorios Git       │
                    │  - blog-agentic         │
                    │  - legatus-video-factory│
                    └─────────────────────────┘
```

### Capas de la Arquitectura

1. **Capa de Presentación**
   - Clawdbot Webchat (Victor ↔ Jarvis)
   - Mission Control Dashboard (HTTP UI)

2. **Capa de Coordinación**
   - Jarvis (PO) - Sesión principal de Clawdbot
   - Mission Control API (Flask)

3. **Capa de Agentes**
   - Jarvis-Dev (Clawdbot subagent, label: `jarvis-dev`)
   - Jarvis-QA (Clawdbot subagent, label: `jarvis-qa`)
   - Jarvis-PM (Clawdbot subagent, label: `jarvis-pm`) - opcional

4. **Capa de Datos**
   - SQLite: `instance/mission_control.db`
   - Git repos: Código versionado

5. **Capa de Automatización**
   - Agent Daemons (polling cada 60s)
   - Heartbeat scripts (trigger Clawdbot sessions)

---

## Componentes

### 1. Mission Control API (Flask)

**Ubicación:** `~/repositories/mission_control/`

**Endpoints principales:**

```python
# Tasks
GET  /api/tasks           # Listar todos los tickets
POST /api/tasks           # Crear nuevo ticket
GET  /api/tasks/<id>      # Detalle de ticket
PUT  /api/tasks/<id>      # Actualizar ticket

# Messages
GET  /api/messages        # Historial de mensajes
POST /api/messages        # Enviar mensaje nuevo

# Agents
GET  /api/agents          # Estado de agentes registrados
POST /api/agents/register # Registrar nuevo agente
```

**Base de datos (SQLite):**

```sql
-- Tabla de tickets
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT,           -- todo / in_progress / review / completed / blocked
    priority TEXT,         -- low / medium / high / critical
    project TEXT,
    assigned_to TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Tabla de mensajes entre agentes
CREATE TABLE messages (
    id INTEGER PRIMARY KEY,
    from_agent TEXT NOT NULL,
    content TEXT NOT NULL,
    task_id INTEGER,
    created_at TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

-- Tabla de agentes registrados
CREATE TABLE agents (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    role TEXT,
    status TEXT,           -- idle / busy / offline
    session_key TEXT,
    last_seen_at TIMESTAMP
);
```

### 2. Clawdbot Sessions

**Qué es:** Sistema de agentes IA persistentes integrado en Clawdbot.

**Gestión de sesiones:**

```bash
# Listar sesiones activas
clawdbot sessions list

# Crear agente persistente (spawn)
clawdbot sessions spawn \
  --label jarvis-dev \
  --cleanup keep \
  --task "You are Jarvis-Dev..."

# Enviar mensaje a agente
clawdbot sessions send \
  --label jarvis-dev \
  --message "@Jarvis-Dev - TICKET-005 asignado"

# Ver historial de sesión
clawdbot sessions history --label jarvis-dev
```

**Labels importantes:**
- `jarvis-dev` → Desarrollador
- `jarvis-qa` → QA Engineer
- `jarvis-pm` → Project Manager (opcional)

### 3. Agent Daemons

**Ubicación:** `~/repositories/mission_control/daemon/`

**¿Qué hacen?**
Polling continuo de Mission Control API para detectar mensajes nuevos y triggerar sesiones de Clawdbot.

**Archivos:**

```
daemon/
├── agent_daemon.py           # Daemon principal (genérico)
├── config.yaml               # Configuración de agentes
├── state/
│   ├── dev-state.json        # Estado de Jarvis-Dev (last_message_id)
│   └── qa-state.json         # Estado de Jarvis-QA
└── logs/
    ├── jarvis-dev.log
    └── jarvis-qa.log
```

**Ejecución:**

```bash
# Daemon Dev
cd ~/repositories/mission_control
python3 daemon/agent_daemon.py dev &

# Daemon QA
python3 daemon/agent_daemon.py qa &

# Verificar daemons corriendo
ps aux | grep agent_daemon
```

**Flujo del daemon:**

1. Poll Mission Control cada 60s
2. Detecta mensajes nuevos (id > last_message_id)
3. Filtra mensajes dirigidos al agente (@Jarvis-Dev)
4. Ejecuta heartbeat script → Trigger Clawdbot session
5. Actualiza estado (last_message_id)

### 4. Heartbeat Scripts

**Ubicación:** `~/repositories/mission_control/scripts/`

**Propósito:** Intermediario entre daemon y Clawdbot sessions.

**Archivos:**

```bash
scripts/
├── jarvis-dev-heartbeat.sh     # Wrapper para Dev
├── jarvis-dev-direct.py        # Trigger Clawdbot session Dev
├── jarvis-qa-heartbeat.sh      # Wrapper para QA
└── jarvis-qa-direct.py         # Trigger Clawdbot session QA
```

**Ejemplo (jarvis-dev-direct.py):**

```python
#!/usr/bin/env python3
"""Trigger Jarvis-Dev Clawdbot session"""
import subprocess
import requests

API_BASE = 'http://localhost:5001/api'
AGENT_NAME = 'Jarvis-Dev'

# 1. Check for new messages mentioning me
messages = requests.get(f'{API_BASE}/messages').json()
my_messages = [msg for msg in messages if '@Jarvis-Dev' in msg['content']]

# 2. For each message, trigger Clawdbot session
for msg in my_messages:
    prompt = f"Read IDENTITY.md. Dev posted: {msg['content']}. Execute now."
    subprocess.run([
        'clawdbot', 'sessions', 'send',
        '--label', 'jarvis-dev',
        '--message', prompt,
        '--timeout', '300'
    ])
```

---

## Flujo de Trabajo

### Ciclo Completo de un Ticket

```
1. ASIGNACIÓN (Jarvis PO)
   ↓
   POST /api/messages: "@Jarvis-Dev - TICKET-003 asignado"
   ↓
2. DETECCIÓN (Daemon Dev)
   ↓
   Daemon detecta mensaje nuevo (polling 60s)
   ↓
3. TRIGGER (Heartbeat Script)
   ↓
   Ejecuta: clawdbot sessions send --label jarvis-dev
   ↓
4. IMPLEMENTACIÓN (Jarvis-Dev Session)
   ↓
   - Lee IDENTITY.md + ticket details
   - Escribe tests (TDD)
   - Implementa código
   - Commit + push
   - POST /api/messages: "[QA READY] TICKET-003 completado"
   ↓
5. QA REVIEW (Jarvis-QA)
   ↓
   - Daemon QA detecta "[QA READY]"
   - Trigger session QA
   - Ejecuta tests, verifica coverage
   - POST /api/messages: "APPROVED ✅" / "REJECTED ❌"
   ↓
6. MERGE (Jarvis-Dev si approved)
   ↓
   - Dev hace merge a main
   - POST /api/messages: "[MERGED] TICKET-003"
   ↓
7. TRACKING (Jarvis PO)
   ↓
   - Actualiza estado en DB: status = 'completed'
   - Asigna siguiente ticket
```

### Estados de un Ticket

```
todo         → Creado pero no asignado
in_progress  → Dev trabajando
review       → En QA review (después de [QA READY])
completed    → Mergeado a main
blocked      → Blocker reportado por Dev
```

### Transiciones de Estado

```python
# Jarvis (PO) asigna ticket
POST /api/messages → "@Jarvis-Dev - TICKET-X asignado"
UPDATE tasks SET status='in_progress' WHERE id=X

# Dev completa y posta [QA READY]
POST /api/messages → "[QA READY] TICKET-X completado"
UPDATE tasks SET status='review' WHERE id=X

# QA aprueba
POST /api/messages → "APPROVED ✅"
# (esperar [MERGED] de Dev)

# Dev hace merge
POST /api/messages → "[MERGED] TICKET-X"
UPDATE tasks SET status='completed' WHERE id=X
```

---

## Configuración Inicial

### Paso 1: Clonar Mission Control

```bash
cd ~/repositories
git clone <mission-control-repo-url>
cd mission_control
```

### Paso 2: Instalar Dependencias

```bash
# Python dependencies
pip install flask requests pyyaml

# Clawdbot debe estar instalado globalmente
which clawdbot  # Verificar
```

### Paso 3: Inicializar Base de Datos

```bash
cd ~/repositories/mission_control
python3 -c "from app import app, db; app.app_context().push(); db.create_all()"
```

Esto crea `instance/mission_control.db` con tablas vacías.

### Paso 4: Arrancar Mission Control API

```bash
cd ~/repositories/mission_control
export FLASK_APP=app.py
export FLASK_ENV=development
flask run --port 5001
```

Acceder dashboard: http://localhost:5001

### Paso 5: Crear Sesiones de Agentes (Spawn)

**Opción A: Script automático (recomendado)**

```bash
cd ~/repositories/mission_control
python3 scripts/spawn_agents.py
```

Esto crea sesiones persistentes de `jarvis-dev` y `jarvis-qa`.

**Opción B: Manual (vía Clawdbot CLI)**

```bash
# Spawn Jarvis-Dev
clawdbot sessions spawn \
  --label jarvis-dev \
  --cleanup keep \
  --task "You are Jarvis-Dev, Python Senior Developer..."

# Spawn Jarvis-QA
clawdbot sessions spawn \
  --label jarvis-qa \
  --cleanup keep \
  --task "You are Jarvis-QA, Quality Assurance Engineer..."
```

**Verificar sesiones creadas:**

```bash
clawdbot sessions list | grep jarvis
```

Deberías ver:
```
jarvis-dev    webchat    agent:main:subagent:xxx...
jarvis-qa     webchat    agent:main:subagent:yyy...
```

### Paso 6: Arrancar Daemons

```bash
cd ~/repositories/mission_control

# Daemon Dev (background)
nohup python3 daemon/agent_daemon.py dev > logs/daemon-dev.out 2>&1 &

# Daemon QA (background)
nohup python3 daemon/agent_daemon.py qa > logs/daemon-qa.out 2>&1 &

# Verificar
ps aux | grep agent_daemon
```

### Paso 7: Crear Primer Ticket

**Vía Jarvis (PO) en Clawdbot:**

```
Victor: "Crea ticket BLOG-001: Setup FastAPI blog"

Jarvis ejecuta:
curl -X POST http://localhost:5001/api/tasks -d '{
  "title": "BLOG-001: Setup FastAPI blog",
  "description": "Initialize project...",
  "status": "todo",
  "priority": "high",
  "project": "blog-agentic"
}'
```

**Vía Dashboard Web:**

1. Abrir http://localhost:5001
2. Click "New Task"
3. Fill form, submit

**Vía curl directo:**

```bash
curl -X POST http://localhost:5001/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "title": "BLOG-001: Setup FastAPI",
    "description": "...",
    "status": "todo",
    "priority": "high",
    "project": "blog-agentic"
  }'
```

---

## Uso Diario

### Como Jarvis (Project Owner)

**1. Asignar ticket a Dev:**

```bash
curl -X POST http://localhost:5001/api/messages \
  -H "Content-Type: application/json" \
  -d '{
    "from_agent": "Jarvis",
    "task_id": 3,
    "content": "@Jarvis-Dev - TICKET-003 asignado\n\nDeadline: 3 horas\nPriority: CRITICAL\n\n## Deliverables:\n- Setup FastAPI\n- Models Pydantic\n- Tests >80% coverage"
  }'
```

**2. Monitorear progreso:**

```bash
# Ver últimos mensajes
curl http://localhost:5001/api/messages | jq '.[-5:]'

# Ver estado de tickets
curl http://localhost:5001/api/tasks | jq '.[] | select(.status != "completed")'

# Ver agentes activos
curl http://localhost:5001/api/agents
```

**3. Actualizar estado de ticket:**

```bash
# Marcar como completado
curl -X PUT http://localhost:5001/api/tasks/3 \
  -H "Content-Type: application/json" \
  -d '{"status": "completed"}'
```

### Como Jarvis-Dev (Implementador)

**Workflow automático vía daemon:**

1. Daemon detecta mensaje "@Jarvis-Dev - TICKET-X"
2. Heartbeat script trigger tu sesión Clawdbot
3. Lees IDENTITY.md + ticket details
4. Implementas código (TDD)
5. Postas "[QA READY] TICKET-X completado"

**Postear progreso manualmente (si daemon falla):**

```python
import requests

requests.post('http://localhost:5001/api/messages', json={
    'from_agent': 'Jarvis-Dev',
    'task_id': 3,
    'content': '[PROGRESS] TICKET-003 - 50% completado. Tests: 8/12 passing.'
})
```

### Como Jarvis-QA (Reviewer)

**Workflow automático vía daemon:**

1. Daemon detecta "[QA READY]"
2. Heartbeat script trigger tu sesión
3. Ejecutas review:
   ```bash
   cd ~/repositories/<project>
   pytest tests/ -v
   pytest --cov=app
   ```
4. Postas verdict:
   ```
   APPROVED ✅ - Tests: 12/12, Coverage: 89%
   REJECTED ❌ - Tests failing: test_auth.py::test_login
   CONDITIONAL ⚠️ - Approved with warnings (deprecation notices)
   ```

---

## Troubleshooting

### Problema: Daemons no detectan mensajes

**Síntomas:**
- Mensajes en Mission Control pero agentes no responden
- Daemon logs muestran "⚠️ Failed to respond to message X"

**Diagnóstico:**

```bash
# 1. Verificar daemon corriendo
ps aux | grep agent_daemon

# 2. Ver logs de daemon
tail -50 ~/repositories/mission_control/logs/jarvis-dev.log

# 3. Ver estado del daemon
cat ~/repositories/mission_control/daemon/state/dev-state.json
```

**Solución:**

```bash
# Opción 1: Resetear estado del daemon
echo '{"last_message_id": 0}' > ~/repositories/mission_control/daemon/state/dev-state.json

# Opción 2: Reiniciar daemon
pkill -f "agent_daemon.py dev"
cd ~/repositories/mission_control
python3 daemon/agent_daemon.py dev &

# Opción 3: Trigger manual (bypass daemon)
clawdbot sessions send \
  --label jarvis-dev \
  --message "Read IDENTITY.md. Check Mission Control for pending work." \
  --timeout 180
```

### Problema: Sesiones de agentes no existen

**Síntomas:**
- `clawdbot sessions list` no muestra `jarvis-dev` o `jarvis-qa`
- Error: "No session found with label: jarvis-dev"

**Solución:**

```bash
# Re-spawn agentes
cd ~/repositories/mission_control
python3 scripts/spawn_agents.py

# Verificar
clawdbot sessions list | grep jarvis
```

### Problema: Mission Control API no responde

**Síntomas:**
- curl http://localhost:5001 → Connection refused
- Dashboard no carga

**Solución:**

```bash
# Verificar si Flask está corriendo
ps aux | grep flask

# Reiniciar Flask
cd ~/repositories/mission_control
pkill -f "flask run"
export FLASK_APP=app.py
flask run --port 5001 &
```

### Problema: Daemon marca mensajes como procesados pero no ejecuta

**Causa:** Heartbeat script falla al ejecutar `clawdbot sessions send`.

**Diagnóstico:**

```bash
# Ver logs de heartbeat
tail -50 ~/repositories/mission_control/logs/heartbeats/dev-heartbeat.log
```

Buscar:
```
⚠️ Failed to respond to 58
```

**Solución:**

```bash
# Opción 1: Aumentar timeout en heartbeat script
# Editar scripts/jarvis-dev-direct.py, línea timeout=300 → timeout=600

# Opción 2: Usar sessions_send directo desde Jarvis (PO)
# (Ya implementado como fallback)
```

### Problema: Tests de Dev fallan en QA pero pasaban en local

**Causa:** Diferencias de environment (Python version, dependencias, paths).

**Solución:**

```bash
# 1. QA debe trabajar en mismo environment que Dev
cd ~/repositories/<project>
source venv/bin/activate  # O pipenv shell

# 2. Verificar PYTHONPATH
export PYTHONPATH=$PWD:$PYTHONPATH
pytest tests/

# 3. Si falla, reportar a Dev:
POST /api/messages: "REJECTED ❌ - Environment issue: test_x.py fails locally"
```

---

## Scripts Útiles

### Reiniciar Todo el Sistema

```bash
#!/bin/bash
# restart_mission_control.sh

echo "🔄 Restarting Mission Control System..."

# 1. Stop daemons
pkill -f agent_daemon.py

# 2. Restart Flask
pkill -f "flask run"
cd ~/repositories/mission_control
export FLASK_APP=app.py
flask run --port 5001 &

# 3. Respawn agents (si no existen)
python3 scripts/spawn_agents.py

# 4. Restart daemons
python3 daemon/agent_daemon.py dev &
python3 daemon/agent_daemon.py qa &

echo "✅ Mission Control restarted"
```

### Ver Estado Completo

```bash
#!/bin/bash
# status.sh

echo "=== MISSION CONTROL STATUS ==="

echo "\n📊 Flask API:"
curl -s http://localhost:5001/health 2>/dev/null && echo "✅ Online" || echo "❌ Offline"

echo "\n🤖 Clawdbot Sessions:"
clawdbot sessions list | grep jarvis

echo "\n👷 Daemons:"
ps aux | grep agent_daemon | grep -v grep

echo "\n📋 Pending Tasks:"
curl -s http://localhost:5001/api/tasks | jq '.[] | select(.status != "completed") | {id, title, status}'

echo "\n💬 Recent Messages:"
curl -s http://localhost:5001/api/messages | jq '.[-5:] | .[] | {from: .from_agent, content: .content[:80]}'
```

---

## Arquitectura de Decisiones

### ¿Por qué Daemons + Heartbeat Scripts?

**Alternativas consideradas:**

1. **Webhooks:** Mission Control → Clawdbot directo
   - ❌ Clawdbot no expone webhook endpoint (arquitectura push no soportada)

2. **Polling directo desde Jarvis (PO):**
   - ❌ Jarvis debe estar siempre activo en sesión principal
   - ❌ No escala si Victor se desconecta

3. **Daemons autónomos:**
   - ✅ Funcionan independiente de sesión principal
   - ✅ Polling cada 60s es aceptable (latencia <1 min)
   - ✅ Stateful (last_message_id persiste)

### ¿Por qué Sessions Spawn en lugar de CLI directo?

**Sessions Spawn:**
- ✅ Persistencia: Sesión mantiene contexto entre llamadas
- ✅ Visible en webapp
- ✅ Historial accesible (`clawdbot sessions history`)

**CLI directo (`clawdbot agent --message`):**
- ❌ Cada ejecución es stateless
- ❌ No persiste contexto
- ❌ No visible en dashboard

### ¿Por qué SQLite y no Redis/Postgres?

**SQLite:**
- ✅ Zero config, archivo local
- ✅ Suficiente para <1000 tasks
- ✅ Facil backup (cp mission_control.db)

**Redis/Postgres:**
- ⚠️ Overkill para MVP local
- ⚠️ Requiere Docker Compose adicional
- ✅ Migrar si escalamos a múltiples máquinas

---

## Próximos Pasos

### Mejoras Planificadas

1. **Retry Logic en Daemons**
   - Si heartbeat falla, reintentar 2-3 veces antes de alertar
   - Exponential backoff

2. **Health Checks Automáticos**
   - Jarvis (PO) monitorea estado de daemons en heartbeat
   - Reinicia automáticamente si detecta fallo

3. **WebSocket en lugar de Polling**
   - Mission Control → Push updates a dashboard
   - Reduce latencia de <60s a <1s

4. **Docker Compose All-in-One**
   - Flask + Redis + Celery + Frontend
   - `docker-compose up` y listo

5. **Métricas de Performance**
   - Tiempo promedio por ticket
   - Tasks completados/día
   - Test coverage trend

---

## Glosario

- **Mission Control:** Sistema de coordinación multi-agente (este proyecto)
- **Clawdbot:** Framework de agentes IA (Clawdbot Sessions)
- **Agent Daemon:** Proceso Python que hace polling de Mission Control
- **Heartbeat Script:** Script que trigger sesiones de Clawdbot
- **Subagent:** Sesión de Clawdbot spawned con `--cleanup keep`
- **Label:** Identificador de sesión (ej: `jarvis-dev`)
- **Session Key:** ID interno de Clawdbot para sesiones
- **Task:** Ticket de trabajo (tabla `tasks` en SQLite)
- **Message:** Comunicación entre agentes (tabla `messages`)

---

## Contacto y Soporte

**Mantenedor:** Victor  
**Repositorio:** ~/repositories/mission_control  
**Dashboard:** http://localhost:5001  
**Logs:** ~/repositories/mission_control/logs/

**Debugging rápido:**

```bash
# Ver todo en tiempo real
watch -n 5 'curl -s http://localhost:5001/api/messages | jq ".[-3:]"'
```

---

**Última actualización:** 2026-02-02  
**Versión del documento:** 1.0
