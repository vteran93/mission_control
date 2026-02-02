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
