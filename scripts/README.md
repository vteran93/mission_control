# Mission Control - Agent Scripts

Scripts ejecutados por los daemons de agentes para responder a Mission Control.

## Estructura

```
scripts/
├── jarvis-dev-direct.py       # Responder directo de Jarvis-Dev
├── jarvis-dev-heartbeat.sh    # Wrapper bash para Dev
├── jarvis-pm-direct.py        # Responder directo de Jarvis-PM
├── jarvis-pm-heartbeat.sh     # Wrapper bash para PM
├── jarvis-qa-direct.py        # Responder directo de Jarvis-QA
├── jarvis-qa-heartbeat.sh     # Wrapper bash para QA
├── e2e_validate_mission_control.py  # Test E2E local (PM/Dev/QA + Fase 4 Scrum + Fase 5 semiautomatica + orchestrator)
└── README.md                  # Este archivo
```

## Flujo de Operación

1. **Daemon** (`daemon/agent_daemon.py`) detecta mensaje nuevo en DB
2. **Daemon** ejecuta `scripts/jarvis-{agent}-heartbeat.sh`
3. **Heartbeat script** ejecuta `scripts/jarvis-{agent}-direct.py`
4. **Direct script**:
   - Detecta mensajes que mencionan al agente
   - Invoca `clawdbot agent --agent jarvis-{agent}` con el mensaje
   - Clawdbot responde y publica a Mission Control API
   - Marca mensaje como procesado

## Configuración

Los daemons leen rutas desde `daemon/config.json`:

```json
{
  "agents": {
    "dev": {
      "heartbeat_script": "scripts/jarvis-dev-heartbeat.sh",
      ...
    }
  }
}
```

**Rutas son relativas al directorio de Mission Control.**

## Logs

- **Daemon logs:** `logs/daemons/{agent}-daemon.log`
- **Heartbeat logs:** `logs/heartbeats/{agent}-heartbeat.log`
- **State files:** `daemon/state/{agent}-processed-messages.txt`

## Desarrollo

Para agregar nuevo agente:

1. Copiar `jarvis-dev-direct.py` → `jarvis-{new}-direct.py`
2. Reemplazar nombres y rutas
3. Copiar `jarvis-dev-heartbeat.sh` → `jarvis-{new}-heartbeat.sh`
4. Actualizar `daemon/config.json`
5. Reiniciar daemons

## Nota

**IMPORTANTE:** Estos scripts deben estar en Mission Control, NO en `~/.local/bin/`.

Mission Control es el orquestador central de comunicación entre agentes.


## Test E2E rápido

```bash
./.venv/bin/python scripts/e2e_validate_mission_control.py --allow-missing-langgraph
```

Este flujo ahora valida tambien:

- import real de blueprint via HTTP
- `Scrum Planning Crew` obligatorio antes de persistir el plan
- escalamiento `bedrock_review`
- `approval_status` + aprobacion manual
- vista consolidada `/scrum-plan/sprint-view`
- modo semiautomatico de delivery con escritura real a `examples/`, `frontend/` e `infra/`

Si quieres validación estricta de LangGraph (falla si falta dependencia):

```bash
./.venv/bin/python scripts/e2e_validate_mission_control.py
```

Para correr el flujo de Fase 4 contra un proyecto real con `requirements.md` y `roadmap.md`:

```bash
./.venv/bin/python scripts/e2e_validate_mission_control.py \
  --allow-missing-langgraph \
  --project-root /ruta/al/proyecto
```

## Delivery semiautomatico

Endpoint disponible:

```bash
POST /api/blueprints/<blueprint_id>/delivery/execute
```

Payload minimo:

```json
{
  "workspace_root": "/ruta/al/workspace",
  "execution_mode": "semi_automatic"
}
```

El slice actual ejecuta tickets `planned` + `ready` de un `scrum_plan` aprobado y soporta recetas deterministas para:

- `examples/holamundo.py`
- `frontend/index.html` con React
- `infra/*.tf` con un modulo S3 basico
