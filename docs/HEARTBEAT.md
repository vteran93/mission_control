# HEARTBEAT.md

## Email Check (cada heartbeat)

1. Revisa los últimos 20 emails no leídos en INBOX
2. Para cada email, usa el script `/home/victor/.local/bin/classify-email.py`
3. El script clasifica automáticamente por palabras clave (ver `~/.config/himalaya/keywords.txt`)
4. Si el script no puede clasificar algo (devuelve "INBOX"), **aprende** y actualiza keywords.txt
5. **SOLO avísame** si hay algo en 🚨 Urgente o ⭐ Importante
6. Los spam/promo muévelos sin avisar

**Categorías:**
- **🚨 Urgente**: Seguridad, pagos pendientes, alertas críticas
- **⭐ Importante**: Confirmaciones de compra, notificaciones bancarias, trabajo/estudio
- **🗑️ Spam-Promo**: Marketing, publicidad, newsletters

**Estado último check:** 2026-02-01 23:10 - Silencioso (Victor trabajando con equipo)

---

## Team Monitoring + Task Status Updates (cada heartbeat)

**1. Revisar Mission Control mensajes:**

```python
import requests
import sqlite3

# Verificar mensajes nuevos
resp = requests.get('http://localhost:5001/api/messages')
msgs = resp.json()

# Últimos 5 mensajes
recent = sorted(msgs, key=lambda x: x['id'], reverse=True)[:5]

for msg in recent:
    print(f"{msg['from_agent']}: {msg['content'][:80]}...")
```

**2. Actualizar estados de tickets en DB:**

```python
conn = sqlite3.connect('/home/victor/repositories/mission_control/instance/mission_control.db')
c = conn.cursor()

# Detectar estado según mensajes
# Si Dev posta "[QA READY]" → status = 'review'
# Si QA posta "APPROVED" → esperar "[MERGED]" de Dev
# Si Dev posta "[MERGED]" → status = 'completed'

# Ejemplo:
# c.execute("UPDATE tasks SET status = 'review' WHERE id = ?", (task_id,))
conn.commit()
conn.close()
```

**Estados posibles:**
- `todo` - Asignado pero no iniciado
- `in_progress` - Dev trabajando (opcional, si Dev reporta progreso)
- `review` - En QA review (después de [QA READY])
- `completed` - Mergeado a main (después de [MERGED])
- `blocked` - Blocker reportado

**Alertar a Victor si:**
- ⚠️ Jarvis-Dev reporta blocker
- ⚠️ Jarvis-QA rechaza un ticket
- ⚠️ Cualquier agente silencioso >6 horas

**NO alertar por:**
- ✅ Status updates normales
- ✅ Transiciones de estado (todo→review→completed)
- ✅ Progreso según timeline

---

## Mission Control Message Queue (cada heartbeat)

**Procesamiento automático de mensajes pendientes:**

```python
import sys
sys.path.insert(0, '/home/victor/clawd')
from process_message_queue import get_pending_messages, mark_processed

messages = get_pending_messages()
if messages:
    for msg in messages:
        try:
            sessions_send(
                label=msg['target_agent'],
                message=msg['content'],
                timeoutSeconds=60
            )
            mark_processed(msg['message_id'])
            print(f"✅ Mensaje enviado a {msg['target_agent']}")
        except Exception as e:
            print(f"⚠️ Error enviando a {msg['target_agent']}: {e}")
```

**Silencioso si cola vacía**

---

## Agent Task Queue (cada heartbeat - OBLIGATORIO)

**⚠️ CRÍTICO: Este bloque DEBE ejecutarse en CADA heartbeat**

**Sistema event-driven con DB queue:**

```python
import subprocess
import json
import sqlite3

# Check task queue for pending work
result = subprocess.run(
    ['python3', '/home/victor/clawd/process_task_queue.py'],
    capture_output=True,
    text=True
)

if result.stdout.strip() != 'NO_TASKS':
    tasks = json.loads(result.stdout)
    
    # Connect to DB to mark tasks
    conn = sqlite3.connect('/home/victor/repositories/mission_control/instance/mission_control.db')
    cursor = conn.cursor()
    
    for task in tasks:
        agent_label = task['target_agent']
        task_id = task['id']
        
        # Mark task as processing
        cursor.execute("""
            UPDATE task_queue 
            SET status = 'processing', started_at = datetime('now')
            WHERE id = ?
        """, (task_id,))
        conn.commit()
        
        # Spawn sub-agent for this work
        try:
            spawn_result = sessions_spawn(
                label=agent_label,
                task=f"""[MISSION CONTROL WORK]

Message ID: {task['message_id']}
From: {task['from_agent']}

{task['content']}

---

**YOUR IDENTITY:** {agent_label.title().replace('-', ' ')}

**ACTION:** Execute the work described above. DO NOT just acknowledge.

**WORKFLOW:**
1. Understand the ticket/task
2. Write code + tests (if Dev) or execute review (if QA) or report status (if PM)
3. Commit to git (if code changes)
4. Report back to Mission Control API (POST http://localhost:5001/api/messages)

**IMPORTANT:** Post completion status to Mission Control.""",
                cleanup='keep',
                runTimeoutSeconds=7200
            )
            
            # Mark task as completed with session key
            session_key = spawn_result.get('childSessionKey', 'unknown')
            cursor.execute("""
                UPDATE task_queue 
                SET status = 'completed', 
                    completed_at = datetime('now'),
                    clawdbot_session_key = ?
                WHERE id = ?
            """, (session_key, task_id))
            conn.commit()
            
            print(f"✅ Spawned {agent_label} for task #{task_id} (message #{task['message_id']})")
            
        except Exception as e:
            # Mark as failed
            cursor.execute("""
                UPDATE task_queue 
                SET status = 'failed',
                    error_message = ?,
                    retry_count = retry_count + 1
                WHERE id = ?
            """, (str(e)[:500], task_id))
            conn.commit()
            print(f"⚠️ Failed to spawn {agent_label}: {e}")
    
    conn.close()
```

**This block ALWAYS runs. Silent only if NO_TASKS.**

---

## Proactive Monitoring (rotar cada 2-3 heartbeats)

**Verificaciones periódicas:**
- **Mission Control status** - Dashboard online? (http://localhost:5001/health)
- **Agent daemons** - ¿Los 3 daemons corriendo? (ps aux | grep agent_daemon)
- **Gateway status** - ¿Gateway respondiendo? (clawdbot gateway status)

**Trabajo autónomo (sin molestar a Victor):**
- Leer y organizar memory files
- Actualizar MEMORY.md con eventos significativos
- Commit cambios propios
- Review de roadmaps y documentación

---

## HEARTBEAT FREQUENCY: 15 MINUTOS

**Configuración actualizada:** 15 minutos (antes 30min) para monitoreo activo del equipo.

Victor delega coordinación completa. Reportar SOLO issues críticos.
