# Mission Control

Panel Flask para coordinar tareas, mensajes y estado de agentes.

## Estado actual

Este repositorio **no está listo como CrewAI-only**. El review muestra que la UI y la API base sí existen, pero la orquestación de agentes sigue fuertemente acoplada a `openclaw` / `clawbot`.

Fecha del review: `2026-03-20`

## Hallazgos del review

### 1. La ejecución de agentes sigue dependiendo de Clawbot/OpenClaw

El acoplamiento no es superficial ni solo de documentación:

- `app.py` dispara heartbeats usando rutas locales de Clawbot en `/home/victor/clawd/...` y scripts en `/home/victor/.local/bin/...`.
- `app.py` escribe mensajes a `~/clawd/mission_control_queue` para que Clawbot los procese.
- `daemon/spawner.py` usa `sessions_spawn` vía gateway HTTP y requiere `CLAWDBOT_GATEWAY_TOKEN`.
- `scripts/spawn_agents.py` llama directamente a `clawdbot sessions spawn`.
- `openclaw_orchestrator/` sigue siendo un subsistema específico de OpenClaw.

Conclusión: hoy el repo es un dashboard Flask con una capa de orquestación todavía dependiente de OpenClaw/Clawbot.

### 2. Hay una inconsistencia operativa de puerto

El backend arranca en `5000` por defecto, pero el frontend, `agent_api.py`, `start_mission_control.sh` y la documentación apuntan a `5001`.

- `app.py` usa `PORT=5000` por defecto.
- `static/script.js` consume `http://localhost:5001/api`.
- `agent_api.py` usa `http://localhost:5001/api`.
- `start_mission_control.sh` valida `http://localhost:5001/api/tasks`.

Impacto: un arranque “tal cual” puede dejar la UI y los clientes apuntando al puerto incorrecto.

### 3. El repo no es portable ni self-contained

Persisten rutas hardcodeadas del entorno personal:

- `/home/victor/clawd/...`
- `/home/victor/.local/bin/...`
- `~/clawd/mission_control_queue`

Además, la base real del proyecto está en `instance/mission_control.db`, mientras que el README anterior hablaba de `mission_control.db` en la raíz.

### 4. Dependencias y testing están incompletos

- `requirements.txt` no declara `requests`, aunque varios scripts y `agent_api.py` la importan.
- `tests/` está vacío.
- `python3 -m pytest -q` falla porque `pytest` no está instalado en el entorno actual y tampoco está declarado en dependencias.

Impacto: el proyecto no tiene una base mínima de validación automatizada ni un entorno reproducible completo.

### 5. Hay inconsistencias funcionales secundarias

- La UI permite seleccionar `TODOS`, pero el backend no expande ese valor: termina encolando el literal `all` como si fuera un agente válido.
- `MissionControlAPI` asigna rol `qa` a cualquier agente cuyo nombre no contenga `Dev`, por lo que actores como `Victor` o `Jarvis-PM` quedan mal clasificados al auto-crearse.

## Qué sí sirve hoy

La parte útil y rescatable del repo es esta:

- Dashboard Flask para visualizar agentes, tareas, mensajes, documentos y notificaciones.
- API REST básica para CRUD de agentes, tareas, mensajes, documentos, notificaciones y cola.
- Persistencia SQLite con modelos en `database.py`.
- Endpoints para logs de daemons y resumen del dashboard.

## Quick Start realista

Si solo quieres levantar el dashboard/API localmente, hoy lo más seguro es esto:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install requests
python3 init_db.py
PORT=5001 python3 app.py
```

Abrir:

- Dashboard: `http://localhost:5001`
- API: `http://localhost:5001/api/agents`

Base de datos usada por Flask:

- `instance/mission_control.db`

Nota: levantar la UI no significa que la orquestación de agentes funcione. Las rutas de wake-up, spawner y mensajería automática siguen dependiendo de Clawbot/OpenClaw.

## Qué hay que reemplazar para volverlo CrewAI-only

Estas piezas deberían salir o ser reescritas:

- `openclaw_orchestrator/`
- `daemon/spawner.py`
- `scripts/spawn_agents.py`
- El flujo de `/api/send-agent-message` que escribe en `~/clawd/mission_control_queue`
- La lógica `trigger_agent_wake()` en `app.py`
- Scripts `jarvis-*-direct.py`, `jarvis-*-notify.py`, `jarvis-*-gateway.py` si siguen usando `clawdbot`

## Dirección recomendada

Mantener:

- `app.py`
- `database.py`
- `agent_api.py` como contrato de integración, pero limpiándolo
- `templates/` y `static/`

Reemplazar por CrewAI:

- Un runner interno que ejecute crews/tareas sin `sessions_spawn`
- Una cola basada solo en DB
- Configuración por variables de entorno, sin rutas hardcodeadas
- Roles PM/Dev/QA modelados como crews o workers propios

## Siguiente refactor recomendado

1. Unificar configuración en env vars: `PORT`, `MISSION_CONTROL_DB_PATH`, `MISSION_CONTROL_QUEUE_DIR`.
2. Separar claramente “dashboard/API” de “runtime de agentes”.
3. Sustituir la cola filesystem + gateway Clawbot por un dispatcher CrewAI.
4. Eliminar `openclaw_orchestrator/` y scripts `clawdbot` una vez exista el runner CrewAI.
5. Agregar smoke tests para API, cola y creación de agentes.

## Referencias del review

- `app.py`
- `agent_api.py`
- `daemon/spawner.py`
- `scripts/spawn_agents.py`
- `static/script.js`
- `templates/index.html`
- `requirements.txt`

En resumen: el dashboard es reutilizable, pero la capa de ejecución todavía está diseñada alrededor de Clawbot/OpenClaw. Si el objetivo es dejarlo en CrewAI solamente, la documentación ya quedó alineada con esa realidad; el siguiente paso es reemplazar la orquestación, no solo renombrarla.
