# Evaluación: Workflow Iterativo con Claude CLI

**Fecha**: 2026-03-31  
**Contexto**: Cruce entre la propuesta en `code-cli-idea.md` y el estado actual de Mission Control.

---

## TL;DR

La propuesta del workflow iterativo (plan → implement → review → fix → decide) tiene **valor real** pero no como pieza independiente. Mission Control ya resuelve una parte del problema (orquestación multi-agente, queue, dispatch, QA gates) y tiene gaps concretos que el patrón iterativo cubriría. Lo que hay que salvar no es el script bash, sino **el modelo mental y los prompts**, adaptados al runtime que ya existe.

---

## Qué ya existe en Mission Control y hace innecesario parte de la propuesta

| Capacidad de la propuesta | Ya existe en el repo | Dónde |
|---|---|---|
| Planificación de tareas | ✅ `autonomous_scrum/service.py` genera sprint plans versionados con story points, riesgos, dependencias | `ScrumPlanRecord` + approval workflow |
| Ejecución por pasos | ✅ `autonomous_delivery/service.py` ejecuta en stages (prepare → execute → review → QA → release) | `execute_plan()` con 8 stages |
| Cola de tareas priorizadas | ✅ `task_queue` table con prioridades (URGENT→LOW), reintentos, claim/release | `crew_runtime/dispatcher.py` |
| Dispatch a agentes específicos | ✅ `DatabaseQueueDispatcher` con `claim_pending_entries()` y row locking | dispatcher + daemon |
| Comunicación inter-agente | ✅ Mensajes via API con keywords (`[QA READY]`, `@jarvis-dev`) | `WORKFLOW.md` protocol |
| Sistema de roles | ✅ PM, Dev, QA con responsabilidades definidas | `daemon/` + `WORKFLOW.md` |
| Tracking de ejecución | ✅ `delivery_stage_events` con status, summary, metadata por stage | `delivery_tracking/service.py` |

**Conclusión**: El andamiaje de orquestación ya está. No necesitamos un `run.sh` externo controlando un loop bash.

---

## Qué NO existe y la propuesta sí cubre (los gaps reales)

### 1. Loop de auto-corrección dentro de una tarea

**Problema actual**: Si un stage falla en `autonomous_delivery`, la ejecución se detiene. No hay retry inteligente que modifique el approach.

**Lo que salvar de la propuesta**: El patrón `implement → review → decide(CONTINUE|FIX|FINALIZE|BLOCKED)` como máquina de estados interna al `CrewAIExecutor` o como lógica envolvente en el dispatcher.

**Forma de integrarlo**: Wrappear la ejecución de cada `DispatchTask` en un mini-loop con budget de reintentos donde:
- Se ejecuta la tarea
- Se evalúa el resultado (review adversarial)
- Se decide: reintentar con corrección, escalar, o marcar completado
- Máximo N iteraciones (configurable en `operator_control`)

### 2. Review adversarial automatizado

**Problema actual**: La revisión QA requiere que un agente externo (Jarvis-QA) detecte el keyword `[QA READY]`, y el ciclo tarda entre 1-16 minutos. No hay auto-review inline.

**Lo que salvar**: El prompt de `review.txt` — específicamente el formato `HALLAZGOS_CRÍTICOS / HALLAZGOS_MEDIOS / PRUEBAS_FALTANTES / VEREDICTO(REVISE|APPROVE)`. Esto puede ser un crew_seed o un paso dentro del executor.

**Forma de integrarlo**: Agregar un `ReviewStage` al pipeline de delivery que corra inmediatamente después del `ExecuteStage`, usando el mismo contexto, sin pasar por el loop de mensajes/daemon.

### 3. Decisión estructurada post-revisión

**Problema actual**: Las decisiones de "qué hacer después" son implícitas (keywords en mensajes) o manuales (approval workflow). No hay un decision engine que parsee el resultado y elija la rama.

**Lo que salvar**: El prompt de `decide.txt` con outputs de control (`CONTINUE|FIX|FINALIZE|BLOCKED`) y la lógica de branching del script bash (case statement).

**Forma de integrarlo**: Como campo en `DispatchResult` — agregar un `next_action` enum que el executor determine, y que el dispatcher use para enrutar:
- `CONTINUE` → encolar siguiente tarea
- `FIX` → re-encolar misma tarea con metadata de corrección
- `FINALIZE` → cerrar ciclo
- `BLOCKED` → escalar (Bedrock, o notificación)

### 4. Prompts de sistema con disciplina operativa

**Problema actual**: Los crew_seeds definen roles y herramientas, pero no tienen las restricciones operativas tipo "no replanifiques todo desde cero", "prefiere cambios pequeños", "declara supuestos explícitos".

**Lo que salvar**: El `global_system.md` completo. Es el prompt más valioso de toda la propuesta. Las reglas de disciplina (iteratividad, cambios pequeños, compatibilidad, no inventar requisitos) deberían ser parte del system prompt de todo agente.

**Forma de integrarlo**: Incorporar como prefijo en `crew_runtime/crew_seeds.py` o como template base en `config/agents/`.

---

## Qué NO salvar

| Elemento | Por qué descartarlo |
|---|---|
| **El script `run.sh` completo** | Mission Control ya tiene un runtime (Flask + dispatcher + daemon). Meter un loop bash externo crea una segunda fuente de verdad para el estado de ejecución. |
| **`--continue --print` como mecanismo de estado** | La memoria conversacional de Claude CLI no reemplaza una DB. El repo ya tiene `task_queue`, `delivery_stage_events`, y `artifacts` para tracking. |
| **El parseo de palabras con grep/awk** | Frágil. El dispatcher ya tiene `DispatchResult` tipado. Usar respuestas estructuradas dentro del executor, no parseo de texto externo. |
| **Worktrees automáticos desde bash** | La integración GitHub (`github_operator.py`) ya maneja branches. Worktrees son útiles pero como feature del daemon, no de un script independiente. |
| **Ejecución de `pytest/ruff` desde bash** | Los guardrails (`architecture_guardrails.py`) ya definen comandos permitidos. La validación debe correr dentro del stage pipeline, no fuera. |

---

## Propuesta de integración concreta

### Fase 1: Micro-loop de corrección en el executor

```
DispatchTask entra al executor
  └─ for i in range(max_retries):
       resultado = ejecutar(task)
       review = revisar(resultado)  # prompt adversarial
       if review.veredicto == APPROVE:
           return DispatchResult(success=True, next_action=CONTINUE)
       elif i < max_retries - 1:
           task.context += review.hallazgos  # feedback in-context
       else:
           return DispatchResult(success=False, next_action=BLOCKED)
```

**Dónde**: `crew_runtime/crewai_executor.py` (wrapping `_execute_task`)  
**Config**: `max_retries` en `operator_control` settings  
**Tracking**: Cada iteración registra un `delivery_stage_event`

### Fase 2: Prompts de disciplina como base de agentes

Extraer de `global_system.md` y `review.txt` los principios operativos y embederlos en:
- `crew_runtime/crew_seeds.py` como `OPERATIONAL_DISCIPLINE_PROMPT`
- Los templates de `config/agents/` como sección estándar
- El `kickoff.txt` adaptado como template para `spec_intake` cuando el input es Level D/E

### Fase 3: Decision routing en el dispatcher

Agregar al `DatabaseQueueDispatcher`:
- Campo `next_action` en `task_queue`
- Lógica en `apply_result()` que, según `next_action`:
  - `CONTINUE` → marca completado, deja que el daemon detecte la siguiente tarea natural
  - `FIX` → re-encola con prioridad elevada y `retry_context`
  - `FINALIZE` → trigger de cierre de sprint/release candidate
  - `BLOCKED` → escalación a Bedrock o notificación al operador

---

## Resumen de valor rescatado

| Elemento | Valor | Prioridad |
|---|---|---|
| `global_system.md` (disciplina operativa) | Alto — mejora calidad de output de todos los agentes | P1 |
| Patrón implement→review→decide como loop interno | Alto — cierra el gap #1 (auto-corrección) | P1 |
| `review.txt` (formato adversarial) | Medio-Alto — estructura de review reusable | P1 |
| `decide.txt` (decisión de control flow) | Medio — complementa el dispatch existente | P2 |
| `kickoff.txt` (planning estructurado) | Bajo — `autonomous_scrum` ya planifica | P3 |
| `finalize.txt` (cierre) | Bajo — delivery service ya tiene release stage | P3 |
| `run.sh` (orquestación bash) | Nulo — reemplazado por el runtime existente | Descartar |

---

## Riesgos

1. **Costo del review loop**: Cada iteración de revisión consume tokens. Con el budget de $50 USD, permitir 3 retries por tarea puede duplicar el costo de ejecución. Mitigación: review con modelo local (Ollama) y solo escalar a Bedrock si el review local da REVISE.

2. **Loops infinitos**: Si el review nunca aprueba, el executor se queda atrapado. Mitigación: hard cap de iteraciones + decay de exigencia (tercera revisión es menos estricta que la primera).

3. **Drift de contexto**: Al inyectar hallazgos como contexto acumulativo, el prompt crece. Mitigación: solo inyectar `HALLAZGOS_CRÍTICOS` del último review, no el historial completo.
