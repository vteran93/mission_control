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

### 4. Dependencias y testing estaban incompletos

Este hallazgo era correcto al momento del review inicial, pero Fase 1 ya corrigió una parte importante:

- `requirements.txt` ya declara `requests`, `alembic` y `psycopg[binary]`.
- `requirements-dev.txt` ya declara `pytest` y `pytest-cov`.
- `tests/` ya incluye cobertura mínima para Fase 0 y Fase 1.

Lo que sigue pendiente no es tener "cero tests", sino ampliar cobertura sobre contratos API, runtime y migraciones futuras.

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

Si quieres levantar el dashboard/API localmente sin pelear con versiones de Python, el flujo validado ahora es este:

```bash
bash scripts/bootstrap_local_env.sh
PORT=5001 bash ./start_mission_control.sh
```

Abrir:

- Dashboard: `http://localhost:5001`
- API: `http://localhost:5001/api/agents`

Base de datos usada por Flask:

- `instance/mission_control.db`

Puntos operativos:

- El repo fija Python local en `3.12` vía `.python-version` para evitar el choque con `crewai` en Python `3.14`.
- Si existe una `.venv` con otra versión, `scripts/bootstrap_local_env.sh` la mueve a un backup temporal y recrea la venv correcta.
- `start_mission_control.sh` ya auto-bootstrappea la `.venv` local si falta o si quedó en una versión incompatible.
- El arranque local usa `MISSION_CONTROL_INSTANCE_PATH=.instance-local` y `MISSION_CONTROL_RUNTIME_DIR=.runtime-local` por defecto para no chocar con la SQLite legacy ni con permisos/estado del `runtime/` que usa Docker.
- El host local arranca con `MISSION_CONTROL_DISPATCHER_EXECUTOR=crewai` por defecto para que el runtime quede en la misma modalidad agentic del contenedor.

Nota: levantar la UI no significa que toda la orquestación quede lista. El runtime híbrido ya corre por DB + CrewAI, pero las integraciones externas siguen dependiendo de configuración explícita de providers.

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

## Proceso de prueba local

Este es el flujo local validado para la Fase 1 con Postgres en Docker Compose.

### 1. Preparar entorno Python local

```bash
bash scripts/bootstrap_local_env.sh
./.venv/bin/python --version
```

Resultado esperado:

- `Python 3.12.x`

Atajo equivalente:

```bash
make bootstrap-local
```

### 2. Ejecutar suite local

```bash
./.venv/bin/python -m pytest tests -q
```

Atajo equivalente:

```bash
make test
```

### 3. Smoke local del backend

```bash
bash scripts/smoke_local.sh
```

Valida:

- arranque de `app.py` con la `.venv` local
- `GET /api/health`
- `GET /api/runtime/health`
- `GET /api/runtime/tools`

Atajo equivalente:

```bash
make smoke-local
```

### 4. Levantar servicios en Docker Compose

```bash
docker compose up -d --build
```

Servicios esperados:

- App Flask: `http://localhost:5001`
- API health: `http://localhost:5001/api/health`
- Postgres: `localhost:54325`

### 5. Smoke docker-compose

```bash
bash scripts/smoke_docker.sh
```

Valida:

- `docker compose up -d --build app`
- `docker compose ps -a`
- `GET /api/health`
- `GET /api/runtime/health`
- `GET /api/runtime/crew-seeds`

Atajo equivalente:

```bash
make smoke-docker
```

### 6. Verificar healthcheck manual si hace falta

```bash
curl -fsS http://localhost:5001/api/health
```

Respuesta esperada:

```json
{
  "agent_wakeups_enabled": false,
  "database": {
    "scheme": "postgresql+psycopg"
  },
  "service": "mission-control",
  "status": "ok"
}
```

Resultado validado en el estado actual del repo:

- `38 passed`

Nota: el warning actual viene de defaults heredados con `datetime.utcnow()` en el modelo legacy.

### 7. Migrar datos legacy desde SQLite a Postgres

Si quieres cargar el contenido de `instance/mission_control.db` en la base Postgres principal local:

```bash
docker compose stop app
docker compose exec -T postgres psql -U mission_control -d postgres \
  -c "DROP DATABASE IF EXISTS mission_control;" \
  -c "CREATE DATABASE mission_control;"
.venv/bin/python -c "from db_bootstrap import run_migrations; run_migrations(database_url='postgresql+psycopg://mission_control:mission_control@localhost:54325/mission_control', alembic_ini_path='alembic.ini')"
.venv/bin/python scripts/migrate_sqlite_to_postgres.py \
  --source-sqlite instance/mission_control.db \
  --target-url postgresql+psycopg://mission_control:mission_control@localhost:54325/mission_control
docker compose start app
```

### 8. Validar datos migrados

```bash
docker compose exec -T postgres psql -U mission_control -d mission_control -c "
select 'agents' as table_name, count(*) from agents
union all select 'projects', count(*) from projects
union all select 'sprints', count(*) from sprints
union all select 'tasks', count(*) from tasks
union all select 'documents', count(*) from documents
union all select 'messages', count(*) from messages
union all select 'notifications', count(*) from notifications
union all select 'task_queue', count(*) from task_queue
union all select 'daemon_logs', count(*) from daemon_logs
order by table_name;"
```

Conteos validados durante esta fase:

- `agents=3`
- `projects=2`
- `sprints=3`
- `tasks=40`
- `documents=0`
- `messages=391`
- `notifications=0`
- `task_queue=62`
- `daemon_logs=456`

Dato importante:

- La migración normaliza a `NULL` referencias legacy inválidas en columnas nullable como `messages.task_id`, en vez de romper integridad referencial en Postgres.
