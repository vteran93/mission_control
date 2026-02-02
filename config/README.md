# Mission Control - Configuración Portable

Este directorio contiene configuraciones **portables** de Mission Control que no dependen de un workspace específico de Clawdbot.

## Estructura

```
config/
├── agents/                     # Identidades de agentes (self-contained)
│   ├── IDENTITY_JARVIS_DEV.md  # Developer identity
│   └── IDENTITY_JARVIS_QA.md   # QA Engineer identity
└── README.md                   # Esta guía
```

## ¿Por Qué Esta Carpeta?

Mission Control debe ser **replicable** en cualquier instalación de Clawdbot sin depender de:
- Archivos en `~/clawd/` específicos del usuario
- Configuraciones hardcoded
- Paths absolutos personalizados

Todo lo necesario para inicializar los agentes está en este directorio.

## Uso

### Spawn Automático (Recomendado)

```bash
cd ~/repositories/mission_control
python3 scripts/spawn_agents.py
```

El script `spawn_agents.py` lee automáticamente las identidades de `config/agents/`.

### Spawn Manual

Si prefieres crear las sesiones manualmente:

```bash
# Jarvis-Dev
clawdbot sessions spawn \
  --label jarvis-dev \
  --cleanup keep \
  --task "$(cat config/agents/IDENTITY_JARVIS_DEV.md)"

# Jarvis-QA
clawdbot sessions spawn \
  --label jarvis-qa \
  --cleanup keep \
  --task "$(cat config/agents/IDENTITY_JARVIS_QA.md)"
```

### Personalización

Si quieres adaptar las identidades a tu workflow:

1. Edita `IDENTITY_JARVIS_DEV.md` o `IDENTITY_JARVIS_QA.md`
2. Re-spawn los agentes con `python3 scripts/spawn_agents.py`
3. Commit tus cambios (git)

**Ejemplo de personalización:**

```markdown
# En IDENTITY_JARVIS_DEV.md

## Tech Stack (Personalizado)
- **Languages:** Python 3.12+, Go, Rust  ← Cambiar según tu stack
- **Frameworks:** Django, FastAPI        ← Agregar los que uses
- **Tools:** k8s, Terraform, ArgoCD      ← DevOps tools específicos
```

## Integración con Clawdbot Existente

Mission Control **NO requiere** que tengas archivos en `~/clawd/`. Las identidades de agentes viven aquí.

**Si ya tienes un workspace Clawdbot (`~/clawd/`):**
- Mission Control funciona en paralelo
- Los agentes (jarvis-dev, jarvis-qa) son independientes
- Puedes tener tu agente principal (Jarvis) en `~/clawd/` y los workers en Mission Control

**Si estás empezando desde cero:**
- Solo necesitas clonar Mission Control
- Las identidades ya están incluidas
- Run `scripts/spawn_agents.py` y listo

## Archivos de Identidad

### `IDENTITY_JARVIS_DEV.md`

Define comportamiento de **Jarvis-Dev** (Python Senior Developer):
- Workflow TDD (tests primero)
- Coverage >80% mandatorio
- Comunicación vía Mission Control API
- Post "[QA READY]" cuando completa ticket

### `IDENTITY_JARVIS_QA.md`

Define comportamiento de **Jarvis-QA** (Quality Assurance):
- QA checklist exhaustivo
- Security review (OWASP Top 10)
- Coverage analysis (>80%)
- Post verdict: APPROVED/REJECTED/CONDITIONAL

## Versionado

**Importante:** Estos archivos están en git. Si haces cambios:

```bash
cd ~/repositories/mission_control
git add config/agents/IDENTITY_*.md
git commit -m "config: Customize agent identities for <project>"
git push
```

Esto permite:
- Rastrear cambios en comportamiento de agentes
- Replicar setup en otras máquinas
- Rollback si algo no funciona

## Troubleshooting

### Problema: Spawn falla con "identity file not found"

**Solución:**
```bash
# Verificar que archivos existen
ls -la config/agents/

# Deben estar presentes:
# IDENTITY_JARVIS_DEV.md
# IDENTITY_JARVIS_QA.md
```

### Problema: Agentes no siguen instrucciones de identity

**Causa:** Context window lleno, agente no lee identity file completo.

**Solución:**
```bash
# Opción 1: Restart sesión
clawdbot sessions list
# Identificar session_key de jarvis-dev
clawdbot sessions reset <session_key>

# Opción 2: Re-spawn (crea nueva sesión)
python3 scripts/spawn_agents.py
```

---

**Última actualización:** 2026-02-02  
**Maintainer:** Victor
