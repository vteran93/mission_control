# Roadmap Mission Control - Fases 0 a 3

Este documento traduce el roadmap acordado a un plan ejecutable sobre el repositorio actual, marcando lo ya realizado y detallando el trabajo pendiente para las fases siguientes.

## Restricciones de ingeniería

- TDD
- KISS
- DRY
- SOLID
- Docker Compose para local dev
- Infrastructure as Code cloud-first AWS: fuera de alcance en estas fases
- CI/CD con GitHub Actions: fuera de alcance en estas fases

## Estado de fases

- [x] Fase 0: estabilización técnica del backend actual
- [x] Fase 1: migración de base de datos a Postgres en Docker Compose (`54325`)
- [ ] Fase 2: comunicación API-first entre agentes con trazabilidad y estados
- [ ] Fase 3: reemplazo de Clawbot/OpenClaw por Ollama + CrewAI

## Tareas realizadas previamente

### Fase 0 completada

- [x] Centralizar configuración por variables de entorno en `config.py`
- [x] Introducir `create_app()` y desacoplar el arranque del backend de valores hardcodeados
- [x] Agregar endpoint `GET /api/health`
- [x] Hacer configurable `MISSION_CONTROL_QUEUE_DIR`
- [x] Dejar `ENABLE_AGENT_WAKEUPS=false` por defecto
- [x] Reemplazar rutas absolutas críticas del runtime central (`/home/victor/...`, `~/clawd/...`) por configuración
- [x] Corregir `agent_api.py` para usar `MISSION_CONTROL_API_URL`
- [x] Corregir el frontend legacy para consumir `/api` en vez de `http://localhost:5001/api`
- [x] Añadir `Dockerfile`, `docker-compose.yml` y `.env.example` para local dev
- [x] Añadir tests mínimos de Fase 0 en `tests/test_phase0_app.py` y `tests/test_phase0_agent_api.py`
- [x] Validar `pytest`
- [x] Validar `docker-compose config`
- [x] Validar `docker-compose up -d --build` + `GET /api/health`

### Deuda todavía existente tras Fase 0

- [ ] La persistencia sigue en SQLite
- [ ] El modelo de datos todavía no representa conversaciones entre agentes, eventos de estado ni ejecuciones
- [ ] El runtime heredado de Clawbot/OpenClaw sigue presente en módulos y scripts no removidos
- [ ] La UI principal sigue siendo la legacy server-rendered

### Fase 1 completada

- [x] Añadir dependencias `alembic` y `psycopg[binary]`
- [x] Introducir `ALEMBIC_INI_PATH` en la configuración central
- [x] Reemplazar `db.create_all()` por bootstrap con migraciones en `db_bootstrap.py`
- [x] Crear configuración de Alembic en `alembic.ini`
- [x] Crear scripts de migración en `alembic_scripts/`
- [x] Crear migración inicial `0001_initial_schema`
- [x] Configurar `docker-compose.yml` con Postgres en `54325`
- [x] Ajustar `Dockerfile` y `.env.example` para Postgres
- [x] Crear utilidades de migración en `data_migration.py`
- [x] Crear CLI `scripts/migrate_sqlite_to_postgres.py`
- [x] Añadir tests de Fase 1 en `tests/test_phase1_db_bootstrap.py`
- [x] Añadir tests de Fase 1 en `tests/test_phase1_data_migration.py`
- [x] Validar `pytest`
- [x] Validar `docker-compose up -d --build`
- [x] Validar `GET /api/health` usando Postgres
- [x] Validar migración SQLite -> Postgres en base temporal
- [x] Ejecutar cutover local de `mission_control` hacia Postgres

### Evidencia de cierre de Fase 1

- [x] `docker-compose` levanta `postgres:16` en `localhost:54325`
- [x] La app responde `database.scheme = postgresql+psycopg`
- [x] Alembic quedó en revisión `0001_initial_schema`
- [x] La base principal `mission_control` quedó cargada con los datos legacy:
- [x] `agents=3`
- [x] `projects=2`
- [x] `sprints=3`
- [x] `tasks=40`
- [x] `messages=391`
- [x] `task_queue=62`
- [x] `daemon_logs=456`
- [x] Se sanearon 4 referencias legacy inválidas en `messages.task_id` (`93`, `162`, `226`, `228`) normalizándolas a `NULL` para respetar integridad referencial en Postgres

### Deuda todavía existente tras Fase 1

- [ ] Persisten warnings heredados por `datetime.utcnow()` en defaults del modelo actual
- [ ] El esquema actual todavía no cubre threads, state events, agent runs ni artifacts
- [ ] El runtime heredado de Clawbot/OpenClaw sigue presente y es el próximo objetivo de Fase 2 y 3

## Dependencia crítica antes de Fase 2 y Fase 3

La Fase 1 ya quedó resuelta, así que Fase 2 y Fase 3 pueden arrancar sobre Postgres sin doble migración de esquema.

Razón:

- Fase 2 va a introducir tablas nuevas de conversaciones, eventos, estados y ejecuciones.
- Hacer ese trabajo todavía sobre SQLite implicaría migrar el modelo dos veces.
- Fase 3 necesita persistencia más robusta para `agent_runs`, `state_events`, colas y auditoría.

Conclusión: el roadmap de Fase 2 y 3 ya puede ejecutarse sobre la base nueva sin repetir trabajo de persistencia.

## Fase 2 - Comunicación API-first entre agentes

### Objetivo

Hacer que la comunicación y el seguimiento de estado entre agentes pase exclusivamente por la API de Mission Control, quedando todo visible y auditable desde el sistema.

### Resultado esperado

- Cada agente publica estado, mensajes, handoffs y artefactos vía API
- Se puede consultar la conversación entre agentes por thread
- Se puede ver la línea de tiempo de estados por agente
- La observabilidad ya no depende de colas filesystem ni tooling externo

### Módulos principales a tocar

- `database.py`
- `app.py`
- `agent_api.py`
- `templates/` y `static/` solo lo mínimo para visualización temporal

### Tareas

- [ ] Diseñar el modelo de datos para `conversation_threads`
- [ ] Diseñar el modelo de datos para `conversation_messages`
- [ ] Diseñar el modelo de datos para `agent_state_events`
- [ ] Diseñar el modelo de datos para `agent_runs`
- [ ] Diseñar el modelo de datos para `artifacts` o reutilizar/extender `documents`
- [ ] Agregar migraciones para las nuevas tablas
- [ ] Definir estados canónicos de agente: `idle`, `planning`, `working`, `blocked`, `review`, `done`, `failed`
- [ ] Crear endpoint `POST /api/agents/<agent>/status`
- [ ] Crear endpoint `GET /api/agents/<agent>/timeline`
- [ ] Crear endpoint `POST /api/threads`
- [ ] Crear endpoint `GET /api/threads`
- [ ] Crear endpoint `POST /api/threads/<thread_id>/messages`
- [ ] Crear endpoint `GET /api/threads/<thread_id>/messages`
- [ ] Crear endpoint `POST /api/tasks/<task_id>/handoffs`
- [ ] Crear endpoint `GET /api/tasks/<task_id>/handoffs`
- [ ] Reemplazar gradualmente el uso de `/api/send-agent-message`
- [ ] Mantener compatibilidad temporal mientras se migra el runtime
- [ ] Exponer feed en tiempo real por SSE para estados y mensajes
- [ ] Mostrar timeline de mensajes y estados en la UI legacy hasta que llegue React

### Criterios de aceptación

- [ ] Dos agentes pueden enviarse mensajes sin usar filesystem queue
- [ ] Los mensajes quedan persistidos con `from_agent`, `to_agent`, `thread_id`, `task_id`, timestamp y estado de entrega
- [ ] Cada cambio de estado genera un `agent_state_event`
- [ ] Se puede reconstruir la conversación completa de una tarea desde la API
- [ ] Se puede visualizar quién habló con quién y en qué orden

### Notas de diseño

- KISS: no introducir buses ni colas externas en esta fase
- DRY: el contrato de comunicación debe ser único para UI, CrewAI y cualquier worker futuro
- SOLID: separar claramente capas de API, dominio y persistencia
- TDD: empezar por tests de modelo y tests de contrato API

## Fase 3 - Reemplazo Clawbot/OpenClaw por Ollama + CrewAI

### Objetivo

Sustituir el runtime heredado de Clawbot/OpenClaw por un runtime propio basado en CrewAI y Ollama, usando la API de Mission Control como único canal de coordinación.

### Resultado esperado

- No hay dependencia operativa a `clawdbot` ni `openclaw`
- Los agentes trabajan con tools propias que llaman a Mission Control API
- El estado de ejecución queda persistido y visible
- Los mensajes entre agentes pasan por threads reales del sistema

### Módulos principales a reemplazar o retirar

- `daemon/spawner.py`
- `openclaw_orchestrator/`
- `scripts/spawn_agents.py`
- `scripts/jarvis-*-direct.py`
- `scripts/jarvis-*-notify.py`
- `scripts/jarvis-*-gateway.py`
- Partes heredadas de `app.py` ligadas a queue filesystem y wakeups shell

### Tareas

- [ ] Definir servicio `agent_runtime` o `crew_runtime`
- [ ] Integrar Ollama como proveedor local de inferencia
- [ ] Definir matriz de modelos por rol
- [ ] Integrar CrewAI como motor de roles y handoffs
- [ ] Crear tools API-first para agentes:
- [ ] `get_assigned_work`
- [ ] `get_thread_context`
- [ ] `post_status`
- [ ] `send_message`
- [ ] `create_artifact`
- [ ] `mark_task_state`
- [ ] `handoff_task`
- [ ] Crear `agent_runs` con trazabilidad por ejecución
- [ ] Registrar errores, reintentos y duración de ejecución
- [ ] Eliminar dependencia a `sessions_spawn`
- [ ] Eliminar dependencia a `~/clawd/mission_control_queue`
- [ ] Eliminar dependencia a scripts heartbeat externos
- [ ] Reemplazar `trigger_agent_wake()` por activación interna del runtime
- [ ] Crear adapter de compatibilidad temporal para transición controlada

### Criterios de aceptación

- [ ] Se puede lanzar un agente sin `clawdbot`
- [ ] Se puede ejecutar un handoff entre roles usando solo Mission Control API
- [ ] El runtime puede registrar `planning`, `working`, `blocked`, `done`, `failed`
- [ ] La conversación entre agentes queda visible en Mission Control
- [ ] No quedan referencias operativas a OpenClaw/Clawbot en el camino principal

### Notas de diseño

- KISS: no distribuir el runtime en múltiples procesos si no hace falta
- DRY: las tools de agentes deben usar el mismo cliente API y el mismo contrato
- SOLID: separar proveedor de modelo, runtime de agentes y capa de dominio Mission Control
- TDD: tests por tool, tests de runtime y tests de integración API-first

## Fase 3.5 - Loop iterativo de auto-corrección en el executor (AG-712)

### Objetivo

Integrar un ciclo interno de implement → review → decide dentro del executor para que las tareas puedan auto-corregirse sin intervención humana ni esperar el loop completo del daemon (1-16 min).

### Origen

Evaluación de la propuesta `code-cli-idea.md` cruzada con los gaps del runtime actual. Documento de análisis: `docs/EVAL_ITERATIVE_CLI_WORKFLOW.md`.

### Resultado esperado

- Cada `DispatchTask` ejecutada puede re-intentarse con feedback adversarial inline
- El review no requiere pasar por el ciclo de mensajes/daemon
- El dispatcher enruta según un `next_action` estructurado (CONTINUE|FIX|FINALIZE|BLOCKED)
- Los prompts de disciplina operativa están incorporados como base de todos los agentes

### Tareas

- [ ] **AG-712a**: Micro-loop de corrección en `crewai_executor.py`
  - Wrappear `_execute_task` en un retry loop con budget configurable
  - Ejecutar review adversarial inline tras cada intento
  - Inyectar solo `HALLAZGOS_CRÍTICOS` como contexto de corrección
  - Hard cap de iteraciones + decay de exigencia en revisiones sucesivas
  - Cada iteración registra un `delivery_stage_event`
- [ ] **AG-712b**: Review adversarial como crew_seed
  - Crear prompt de review estructurado (HALLAZGOS_CRÍTICOS / MEDIOS / PRUEBAS_FALTANTES / VEREDICTO)
  - Integrar como `ReviewStage` en el pipeline de delivery
  - Review con modelo local (Ollama) por defecto, escalación a Bedrock solo si REVISE
- [ ] **AG-712c**: Decision routing en el dispatcher
  - Agregar campo `next_action` en `task_queue` y `DispatchResult`
  - Lógica en `apply_result()`: CONTINUE→siguiente, FIX→re-encolar con prioridad elevada, FINALIZE→cierre, BLOCKED→escalar
- [ ] **AG-712d**: Prompts de disciplina operativa como base de agentes
  - Extraer principios de `global_system.md` (iteratividad, cambios pequeños, no inventar requisitos, declarar supuestos)
  - Incorporar en `crew_runtime/crew_seeds.py` como `OPERATIONAL_DISCIPLINE_PROMPT`
  - Aplicar como prefijo en templates de `config/agents/`
- [ ] **AG-712e**: Configuración en operator_control
  - `max_review_retries` (default: 3)
  - `review_model` (default: ollama, escalación: bedrock)
  - `review_strictness_decay` (boolean, default: true)

### Dependencias

- Fase 3 operativa (CrewAI executor + Ollama funcionales)
- `DispatchResult` y `DatabaseQueueDispatcher` estables

### Criterios de aceptación

- [ ] Una tarea que falla en su primer intento se re-ejecuta con feedback del review
- [ ] El review inline no pasa por el ciclo de mensajes/daemon
- [ ] El dispatcher enruta correctamente según `next_action`
- [ ] Las iteraciones de corrección quedan registradas como `delivery_stage_event`
- [ ] El costo de tokens del loop de review es monitoreable desde el dashboard
- [ ] El hard cap de iteraciones previene loops infinitos

### Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Costo de tokens con budget $50 | Review con Ollama, solo escalar a Bedrock si REVISE |
| Loops infinitos | Hard cap + decay de exigencia |
| Drift de contexto por acumulación | Solo inyectar hallazgos críticos del último review |

### Notas de diseño

- KISS: es un wrapper alrededor de la ejecución existente, no un rewrite
- DRY: el prompt de review se reutiliza como crew_seed, no se duplica
- TDD: tests de retry loop con mocks de executor y review
- Presupuesto: el review local es gratuito (Ollama), la escalación tiene gate explícito

## Secuencia recomendada de ejecución

1. Implementar primero el modelo de datos y contratos API de Fase 2.
2. Montar el runtime CrewAI/Ollama de Fase 3 encima de esos contratos.
3. Retirar el runtime heredado solo cuando exista paridad funcional mínima.
4. Integrar el loop de auto-corrección de Fase 3.5 sobre el executor estable.

## Definition of Done para Fase 2 + 3

- [ ] Comunicación entre agentes exclusivamente por API
- [ ] Estados y transiciones visibles por agente
- [ ] Threads y mensajes persistidos por tarea
- [ ] Runtime propio con Ollama + CrewAI operativo en local dev
- [ ] Sin dependencia operativa a Clawbot/OpenClaw en el camino principal
- [ ] Tests automatizados cubriendo contratos críticos
