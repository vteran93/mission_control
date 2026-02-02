# Agent Daemon System

Sistema de daemons para Mission Control que detecta mensajes nuevos y activa los heartbeats de Clawdbot automáticamente.

## 🎯 Objetivo

Reducir la latencia de respuesta de los agentes de **30 minutos** (cron jobs) a **5-10 segundos** (polling continuo).

## 🏗️ Arquitectura

```
Mission Control (Flask + SQLite)
    ↓
    ↓ (DB polling cada 10s)
    ↓
Agent Daemons (Python processes)
    ↓
    ↓ (subprocess trigger)
    ↓
Clawdbot Heartbeat Scripts
    ↓
    ↓ (sessions_spawn)
    ↓
Agent Sessions (Jarvis-PM, Jarvis-Dev, Jarvis-QA)
```

## 📦 Componentes

### 1. `agent_daemon.py`
Daemon principal que:
- Conecta a Mission Control SQLite DB
- Poll cada 10 segundos (configurable)
- Detecta mensajes con menciones (@jarvis-pm, @jarvis-dev, @jarvis-qa)
- Triggerea el heartbeat script correspondiente
- Tracking de estado persistente (último mensaje procesado)
- Logging robusto

### 2. Scripts de Lanzamiento
- `launch_jarvis_pm.sh` - Inicia daemon de Jarvis-PM
- `launch_jarvis_dev.sh` - Inicia daemon de Jarvis-Dev
- `launch_jarvis_qa.sh` - Inicia daemon de Jarvis-QA

### 3. `config.json`
Configuración centralizada:
- DB path
- Polling interval
- Agent mappings (nombre → heartbeat script)
- Log files y state files

### 4. State Tracking
Directorio `state/` contiene JSON con último message ID procesado por cada agente:
- `pm-state.json`
- `dev-state.json`
- `qa-state.json`

## 🚀 Uso

### Inicio Manual (Testing)

```bash
cd /home/victor/repositories/mission_control

# Iniciar daemon de Jarvis-PM
./daemon/launch_jarvis_pm.sh

# En otra terminal - Jarvis-Dev
./daemon/launch_jarvis_dev.sh

# En otra terminal - Jarvis-QA
./daemon/launch_jarvis_qa.sh
```

### Inicio con systemd (Producción)

Ver `systemd/` para archivos de servicio.

```bash
sudo systemctl start jarvis-pm-daemon
sudo systemctl start jarvis-dev-daemon
sudo systemctl start jarvis-qa-daemon

# Enable auto-start on boot
sudo systemctl enable jarvis-pm-daemon
sudo systemctl enable jarvis-dev-daemon
sudo systemctl enable jarvis-qa-daemon
```

## 📊 Logs

Logs se escriben en `logs/daemons/`:
- `pm-daemon.log`
- `dev-daemon.log`
- `qa-daemon.log`

**Ver logs en vivo:**
```bash
tail -f logs/daemons/pm-daemon.log
```

## ⚙️ Configuración

Edita `daemon/config.json` para ajustar:
- `polling_interval_seconds`: Frecuencia de polling (default: 10s)
- `heartbeat_timeout_seconds`: Timeout para scripts (default: 60s)
- `log_level`: INFO, DEBUG, WARNING, ERROR

## 🧪 Testing

### Test Manual

1. Inicia un daemon:
   ```bash
   ./daemon/launch_jarvis_dev.sh
   ```

2. En Mission Control, envía mensaje:
   ```
   @Jarvis-Dev test de daemon
   ```

3. Observa logs:
   - Debe detectar mensaje en <10s
   - Triggerea heartbeat
   - Jarvis-Dev responde

### Verificar Estado

```bash
# Ver último mensaje procesado
cat daemon/state/dev-state.json
```

## 🔧 Troubleshooting

### Daemon no detecta mensajes

1. Verifica DB path en config.json
2. Confirma que Mission Control está corriendo
3. Revisa logs para errores de SQL

### Heartbeat no se triggerea

1. Verifica que script existe:
   ```bash
   ls -la /home/victor/.local/bin/jarvis-dev-heartbeat.sh
   ```

2. Test manual:
   ```bash
   /home/victor/.local/bin/jarvis-dev-heartbeat.sh
   ```

3. Revisa permisos de ejecución

### Estado no se guarda

1. Verifica permisos de `daemon/state/`
2. Revisa logs para errores de escritura

## 📈 Métricas

**Antes (Cron):**
- Latencia: 0-30 minutos (promedio 15 min)
- Frecuencia de check: Cada 30 min

**Después (Daemons):**
- Latencia: 5-10 segundos
- Frecuencia de check: Cada 10 segundos
- **Mejora: ~180x más rápido**

## ✅ Criterios de Aceptación

- [x] Detecta mensajes nuevos en <10s
- [x] Triggerea heartbeat correcto por agente
- [x] Logs claros de eventos
- [x] Manejo robusto de errores
- [x] Estado persistente entre reinicios
- [x] Scripts de lanzamiento funcionando
- [x] Documentación completa

## 🛠️ Desarrollo

**Dependencias:**
- Python 3.7+
- SQLite3 (built-in)
- Bash

**No requiere:**
- pip packages externos
- Configuración compleja
- Root access (para testing)

## 📝 Notas

- Los daemons no modifican la infraestructura de Clawdbot
- Los heartbeat scripts existentes siguen funcionando igual
- Estado persistente previene re-procesamiento de mensajes
- Safe para correr múltiples instancias (state tracking por agente)

---

**Implementado:** 2026-02-02  
**TICKET:** TICKET-004  
**Author:** Jarvis (Project Owner)
