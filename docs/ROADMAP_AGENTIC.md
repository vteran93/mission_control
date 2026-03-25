# Roadmap Agentic de Mission Control

**Fecha base**: 2026-03-21  
**Estado base**: `mission_control` ya tiene Flask + Postgres operativos, pero el runtime sigue acoplado a OpenClaw/Clawbot.  
**Objetivo macro**: convertir `mission_control` en una software factory `CrewAI-only` capaz de leer documentos de especificacion como `docs/example_input_project/requirements.md` y `docs/example_input_project/roadmap.md`, construir el plan de entrega, ejecutar el desarrollo y cerrar el ciclo SCRUM completo de forma desatendida.

## Estado de ejecucion

- [x] Fase 0 - Foundation Cleanup
- [x] Fase 1 - Spec Intake Engine (slice inicial entregado: parser, servicio y preview API)
- [x] Fase 2 - Postgres Delivery Model (blueprints, sprints, tracking de ejecucion, timeline y reporting en Postgres)
- [ ] Fase 3 - CrewAI Runtime Hybrid (runtime operativo validado; escalamiento real a Bedrock sigue pendiente)
- [ ] Fase 4 - Autonomous Scrum Planner (slice inicial entregado: scrum plan versionado, replanificacion, ceremonias y score de riesgo)
- [ ] Fase 5 - Autonomous Delivery Loop
- [ ] Fase 6 - GitHub + Operator UX
- [ ] Fase 7 - Hardening & Benchmark

## Resultado esperado

Al terminar este roadmap, Mission Control debe poder:

1. Ingerir documentos de requerimientos y roadmap en Markdown.
2. Normalizarlos a un `Project Blueprint` persistido en Postgres.
3. Generar backlog, epics, sprints, criterios de aceptacion y dependencias.
4. Ejecutar crews de CrewAI para arquitectura, desarrollo, QA, code review, documentacion y release.
5. Usar modelos locales de Ollama como fuerza de trabajo principal.
6. Usar modelos Bedrock como orquestadores, senior reviewers, tomadores de decision y desbloqueadores.
7. Sincronizar repositorio, issues, branches, PRs y artifacts con GitHub.
8. Registrar en Postgres el tracking completo de ejecucion, feedback por etapa SCRUM y retrospectivas.
9. Operar sin intervencion humana continua; el humano solo configura credenciales, proveedores y conectores como GitHub, Ollama y Bedrock.

## Principios no negociables

- Toda la orquestacion agentic corre sobre CrewAI.
- `mission_control` conserva el rol de sistema de registro y observabilidad.
- Postgres es la fuente de verdad para planes, ejecuciones, handoffs, artifacts, feedback y retrospectives.
- Estrategia `local-first`: Ollama ejecuta los workers por defecto; Bedrock entra por complejidad, ambiguedad, desbloqueo, revision o escalamiento.
- No se depende de OpenClaw, Clawbot ni colas filesystem en el camino principal.
- El sistema debe poder correr sin prompts hardcodeados por proyecto; los insumos vienen de documentos y configuracion.
- Cada etapa debe dejar evidencia reproducible: entrada, decision, output, validacion y costo/latencia del modelo.

## Lectura del caso de ejemplo

Los documentos de `docs/example_input_project/` dejan claro el contrato de entrada que Mission Control debe soportar:

- `requirements.md` describe arquitectura objetivo, agentes, tools, modelos de datos, flujo de ejecucion y criterios de negocio.
- `roadmap.md` describe la descomposicion de entrega en epics, tickets, dependencias, estimaciones y criterios de aceptacion.

Mission Control debe convertir ambos documentos en una estructura canonica unica:

- `Project Blueprint`
- `Capability Map`
- `Execution Plan`
- `Backlog`
- `Sprint Plan`
- `Acceptance Matrix`

## Arquitectura target

```text
                           +----------------------------------+
                           |  UI de configuracion minima      |
                           |  - API keys                      |
                           |  - GitHub repo / org             |
                           |  - perfiles de modelos           |
                           +----------------+-----------------+
                                            |
                                            v
+-------------------+      +----------------+------------------+
| Spec Intake Crew  | ---> |  Mission Control API + Postgres  |
| Bedrock planner   |      |  source of truth                 |
| parsea docs       |      |  blueprints / backlog / runs     |
+---------+---------+      +----------------+------------------+
          |                                   |
          v                                   v
+---------+---------+      +------------------+----------------+
| Planning Crew     | ---> |  Crew Runtime (CrewAI)            |
| Bedrock PM/SM     |      |  Process.hierarchical             |
| genera backlog    |      |  routing local/cloud              |
+---------+---------+      +------+---------------+------------+
          |                       |               |
          |                       |               |
          v                       v               v
+---------+---------+   +---------+------+  +-----+----------------+
| Delivery Crew     |   | Review Crew    |  | Retro Crew           |
| Ollama workers    |   | Bedrock senior |  | Bedrock facilitator  |
| junior/senior dev |   | QA / unblocker |  | feedback y mejoras   |
+---------+---------+   +---------+------+  +-----------+----------+
          |                         |                     |
          +------------+------------+---------------------+
                       |
                       v
              +--------+---------+
              | GitHub / Workspace|
              | code / tests / PR |
              +-------------------+
```

## Crew topology objetivo

### 1. Intake Crew
- `spec_analyst` (Bedrock): interpreta `requirements.md`, `roadmap.md`, extrae requerimientos funcionales/no funcionales y detecta contradicciones.
- `delivery_analyst` (Bedrock): transforma el roadmap fuente en backlog ejecutable con dependencias, estimaciones y Definition of Done.

### 2. Planning Crew
- `product_manager` (Bedrock): define alcance, roadmap ejecutable y prioridades.
- `scrum_master` (Bedrock): arma sprint goals, capacidad, riesgos y ceremonias automáticas.
- `solution_architect` (Bedrock): genera arquitectura target, contratos tecnicos y ADRs iniciales.

### 3. Delivery Crew
- `junior_dev_local` (Ollama, ejemplo `qwen2.5-coder:latest`): implementacion de tickets acotados.
- `senior_dev_local` (Ollama o Bedrock segun complejidad): integracion, refactor, tareas transversales.
- `test_engineer_local` (Ollama): pruebas unitarias, integracion y fixes derivados.
- `tech_writer_local` (Ollama): README, docs tecnicas y changelogs de artifacts.

### 4. Review and Unblock Crew
- `senior_reviewer` (Bedrock): code review, evaluacion de riesgos, consistencia arquitectonica.
- `qa_lead` (Bedrock): decide si una entrega pasa, vuelve a desarrollo o requiere replanning.
- `blocker_resolver` (Bedrock): entra cuando fallan workers locales, hay ambiguedad en specs o regresiones repetidas.

### 5. Retro and Learning Crew
- `sprint_reviewer` (Bedrock): resume resultados del sprint y compara contra acceptance criteria.
- `retro_facilitator` (Bedrock): genera retrospective, acciones correctivas y ajustes de prompts/model routing.

## Estrategia de modelos

| Perfil | Proveedor | Modelo default | Responsabilidad |
|---|---|---|---|
| Worker coder local | Ollama | `qwen2.5-coder:latest` | Implementacion de tickets, tests, refactors y docs |
| Planner / PM | Bedrock | configurable | Interpretacion de specs, backlog, decisiones de prioridad |
| Architect / Senior reviewer | Bedrock | configurable | Diseño, decisiones tecnicas, review y desbloqueos |
| QA escalado | Bedrock | configurable | Diagnostico de fallas complejas y gating final |

Reglas de routing:

- Ollama es el camino por defecto para produccion de codigo.
- Bedrock se activa para tareas con alta ambiguedad, fallas repetidas, conflictos entre documentos, redefinicion de alcance o reviews finales.
- El mapeo `rol -> proveedor -> modelo -> temperatura -> max_tokens` vive en Postgres y es editable desde UI/API.
- El ejemplo `qwen2.5-coder:latest` no queda hardcodeado; debe ser el perfil seed inicial del sistema.

## Modelo de datos target en Postgres

El esquema actual debe ampliarse para soportar planeacion, ejecucion agentic y feedback SCRUM. Tablas nuevas o equivalentes:

- `spec_documents`: documento fuente, version, hash, tipo (`requirements`, `roadmap`, `adr`, `notes`).
- `spec_sections`: secciones parseadas y vinculadas al documento original.
- `project_blueprints`: representacion normalizada del proyecto objetivo.
- `blueprint_requirements`: requerimientos funcionales, no funcionales y restricciones.
- `blueprint_capabilities`: capacidades y modulos detectados.
- `blueprint_acceptance_criteria`: criterios de aceptacion atomicos.
- `blueprint_dependencies`: dependencias y precedencias entre items.
- `delivery_epics`, `delivery_stories`, `delivery_tasks`: backlog canonico persistido.
- `sprint_cycles`: sprint, objetivo, capacidad, fechas, estado.
- `sprint_stage_events`: planning, execution, review, qa_gate, release, retrospective.
- `stage_feedback`: hallazgos y feedback por etapa SCRUM.
- `retrospective_items`: que salio bien, que salio mal, accion, owner, fecha objetivo.
- `crew_definitions`: crews, roles, prompts, tools y politicas.
- `model_profiles`: proveedor, modelo, parametros, uso previsto, fallback.
- `agent_runs`: corrida por agente, input, output, estado, duracion, costo y proveedor.
- `task_executions`: intento por ticket con retries, resultado y artifacts.
- `handoffs`: traspasos entre agentes, razones y contexto.
- `artifacts`: archivos generados, ruta, hash, tipo, relacion con task/run/PR.
- `test_runs`: suites ejecutadas, coverage, estado, logs y regresiones.
- `review_findings`: findings de review, severidad, estado y resolucion.
- `github_sync_events`: repo, branch, commit, issue, PR, merge, comentario, check status.
- `llm_invocations`: trazabilidad fina por invocacion de modelo.

## Integraciones obligatorias

- `Ollama`: discovery de modelos, healthcheck, ejecucion local y control de timeouts.
- `AWS Bedrock`: clientes para roles de orquestacion, revision y desbloqueo.
- `GitHub`: repositorio, branches, pull requests, checks, comments, labels y releases.
- `Workspace local`: clonacion, ramas efimeras, ejecucion de tests, linters, builds y empaquetado.
- `Mission Control UI`: configuracion minima y monitoreo de corridas.

## Impacto sobre el repositorio actual

Reutilizar:

- `app.py` y la API Flask como superficie de control y consulta.
- `database.py`, migraciones y bootstrap Postgres como base de persistencia.
- `templates/` y `static/` como base del panel operador.

Reemplazar o retirar del camino principal:

- `openclaw_orchestrator/`
- `daemon/spawner.py`
- la cola filesystem y la logica asociada a `trigger_agent_wake()`
- scripts heredados ligados a OpenClaw/Clawbot
- cualquier integracion que dependa de `sessions_spawn` o rutas locales externas

## Definition of Done del producto agentic

Mission Control solo se considera listo cuando cumple todo esto:

- Dado un `requirements.md` y un `roadmap.md`, genera un `Project Blueprint` sin edicion manual.
- Crea backlog, sprints y asignaciones de agentes en Postgres.
- Ejecuta desarrollo, testing y review usando CrewAI sin depender de OpenClaw/Clawbot.
- Usa Ollama como workforce principal y Bedrock como capa de orquestacion/escalamiento.
- Registra tracking completo de ejecucion, feedback SCRUM y retrospective en Postgres.
- Sincroniza artifacts y progreso con GitHub.
- Un humano nuevo puede operar el sistema solo configurando credenciales, modelos y repo.

## Epicas

| Epic | Nombre | Objetivo | Estimacion |
|---|---|---|---|
| EP-0 | Foundation Cleanup | retirar runtime heredado y preparar base CrewAI-only | 1.5 semanas |
| EP-1 | Spec Intake Engine | convertir documentos de especificacion a blueprint canonico | 2 semanas |
| EP-2 | Postgres Delivery Model | persistir backlog, runs, feedback SCRUM y retrospectives | 1.5 semanas |
| EP-3 | CrewAI Runtime Hybrid | runtime CrewAI con Ollama workers y Bedrock orchestrators | 2 semanas |
| EP-4 | Autonomous Scrum Planner | planificacion automatica de epics, stories, sprints y gates | 1.5 semanas |
| EP-5 | Autonomous Delivery Loop | codificacion, testing, review, fixes y release desatendidos | 3 semanas |
| EP-6 | GitHub + Operator UX | setup minimo del humano y observabilidad operativa | 1.5 semanas |
| EP-7 | Hardening & Benchmark | robustez, seguridad y benchmark con proyecto de ejemplo | 1.5 semanas |
| **Total** |  |  | **~14.5 semanas** |

## Plan de ejecucion por fases

### Fase 0 - Foundation Cleanup

Objetivo: dejar el repositorio listo para soportar un runtime CrewAI-only sin arrastrar decisiones legacy.

Tickets:

- `AG-001` Reemplazar la cola filesystem y `trigger_agent_wake()` por un dispatcher interno basado en DB.
- `AG-002` Aislar el runtime heredado en una capa de compatibilidad temporal y sacarlo del camino principal.
- `AG-003` Definir modulo `crew_runtime/` y contratos internos para agentes, tools y providers.
- `AG-004` Centralizar configuracion de Ollama, Bedrock, GitHub y profiles de modelos.
- `AG-005` Crear smoke tests de arranque del runtime agentic y healthchecks de proveedores.

Criterios de aceptacion:

- No hay dependencia operativa obligatoria a OpenClaw/Clawbot en el flujo principal.
- Existe un runtime propio inicial consumible desde API/CLI.
- Los proveedores externos quedan modelados como configuracion y no como hardcodes.

### Fase 1 - Spec Intake Engine

Objetivo: que Mission Control entienda documentos como los del ejemplo y genere un modelo canonico del proyecto.

Tickets:

- `AG-101` Definir `ProjectBlueprint`, `RequirementItem`, `AcceptanceItem`, `RoadmapEpic`, `RoadmapTicket`.
- `AG-102` Implementar parser de Markdown estructurado para `requirements.md`.
- `AG-103` Implementar parser de Markdown estructurado para `roadmap.md`.
- `AG-104` Implementar reconciliacion entre documentos: inconsistencias, gaps, dependencias faltantes, duplicados.
- `AG-105` Crear `Intake Crew` en CrewAI para producir blueprint validado y score de confianza.
- `AG-106` Persistir versionado de specs y blueprint derivado.
- `AG-107` Exponer endpoint/UI para cargar o registrar documentos fuente por proyecto.

Criterios de aceptacion:

- El sistema puede leer los dos documentos de ejemplo y producir un blueprint unico.
- El blueprint conserva trazabilidad a seccion y documento de origen.
- Los conflictos entre documentos quedan marcados y pueden disparar escalamiento Bedrock.

### Fase 2 - Postgres Delivery Model

Objetivo: llevar a Postgres el modelo completo de ejecucion agentic, SCRUM y aprendizaje.

Estado actual de la fase:

- [x] Persistencia de `spec_documents`, `spec_sections` y `project_blueprints`
- [x] Persistencia de requirements, epics y tickets derivados del intake
- [x] Persistencia de `sprint_cycles`, `sprint_stage_events`, `stage_feedback` y `retrospective_items`
- [x] Persistencia de `agent_runs`, `task_executions`, `artifacts`, `handoffs` y `llm_invocations`
- [x] Endpoints API para importar, listar y consultar blueprints persistidos
- [x] Endpoints API para sprints, feedback, retrospective, timeline y reportes agregados
- [x] Migraciones `0002_phase2_blueprint_delivery_model` y `0003_phase2_execution_tracking`
- [x] Tests automatizados de Fases 0-2 (`25 passed` al cierre de esta actualizacion)

Validacion contra tickets de la fase:

- `AG-201` Cumplido. Quedaron persistidos blueprints, backlog derivado, `sprint_cycles`, `agent_runs`, `task_executions` y `artifacts`.
- `AG-202` Cumplido. `stage_feedback` y `retrospective_items` ya estan modelados, persistidos y expuestos por API.
- `AG-203` Cumplido. Existen estados canonicos validados por servicio para sprint cycle, sprint stage, agent run, task execution, handoff e invocation.
- `AG-204` Cumplido. La API ya expone blueprint, backlog, sprint cycles, timeline unificado y resultados agregados de corrida.
- `AG-205` Cumplido. Se persisten `llm_invocations`, `handoffs` y eventos de etapa que soportan decisiones de gating.
- `AG-206` Cumplido. El sistema ya entrega reportes agregados de costo, throughput, retry rate y defect leakage estimado.

Tickets:

- `AG-201` Crear migraciones para blueprints, backlog, sprints, agent_runs, task_executions y artifacts.
- `AG-202` Agregar tablas de `stage_feedback` y `retrospective_items`.
- `AG-203` Diseñar estados canonicos por sprint y por task execution.
- `AG-204` Crear APIs para consultar blueprint, backlog, timeline de sprint y resultados de corrida.
- `AG-205` Registrar invocaciones LLM, handoffs y decisiones de gating.
- `AG-206` Añadir vistas/reportes para costo, throughput, retry rate y defect leakage.

Criterios de aceptacion:

- [x] Todo el ciclo de planeacion y ejecucion queda persistido en Postgres.
- [x] Se puede reconstruir que agente hizo que, con que modelo, sobre que ticket y con que resultado.
- [x] El sistema soporta reportes de sprint review y retrospective sin fuentes externas.

Conclusion de validacion:

- La Fase 2 queda terminada en esta rama.
- Mission Control ya puede persistir blueprint, backlog, sprints, ejecucion agentic, feedback SCRUM, retrospective y evidencia LLM en Postgres.
- El siguiente salto real es Fase 3: conectar este modelo persistente con crews CrewAI, routing Ollama/Bedrock y tools operativas de workspace.

### Fase 3 - CrewAI Runtime Hybrid

Objetivo: materializar el runtime de crews, tools y model routing local/cloud.

Estado actual de la fase:

- [x] `CrewAIExecutor` operativo con `Process.hierarchical`
- [x] `ModelRegistry` con perfiles `worker_local`, `planner_bedrock` y `reviewer_bedrock`
- [x] Endpoint de runtime para health, dispatch dirigido, recovery de cola y consulta de perfiles
- [x] Smoke real validado con `CrewAI + Ollama qwen2.5-coder:latest`
- [x] Politica base de timeout, `retry_count`, fallback y recovery de `processing` abandonado
- [x] Tools API-first consumibles desde crews
- [x] Tools de workspace, incluyendo creacion de codigo, Unix, mypy y contexto multi-stack (`npm`, `NuGet/dotnet`, `pip`, `cargo`, `go`)
- [x] Seeds completos de `Intake`, `Planning`, `Delivery`, `Review` y `Retro`
- [x] Telemetria persistida en tablas canonicas de delivery tracking para dispatches enlazados a blueprint/task

Tickets:

- `AG-301` Cumplido. `CrewRuntime` ya ejecuta dispatch con `CrewAI` y `Process.hierarchical`.
- `AG-302` Cumplido. Existe `ModelRegistry` configurable para Ollama y Bedrock, expuesto por API.
- `AG-303` Cumplido. Existen tools API-first para blueprints, task context, execution report, feedback y artifacts/handoffs consumibles desde crews.
- `AG-304` Cumplido. Existen tools de workspace para lectura/escritura de codigo, Unix, mypy, tests y contexto operativo multi-stack.
- `AG-305` Cumplido. Existen seeds funcionales de `Intake`, `Planning`, `Delivery`, `Review` y `Retro`.
- `AG-306` Cumplido. Existe politica de fallback/escalamiento por `retry_count` con handoff persistido entre perfiles de modelo.
- `AG-307` Cumplido. Se persisten `agent_runs`, `task_executions`, `llm_invocations` y `handoffs` desde el runtime cuando el dispatch llega con blueprint/task asociados.

Criterios de aceptacion:

- [x] Un crew puede arrancar desde Mission Control usando solo CrewAI y providers configurados.
- [x] El worker local por defecto usa Ollama.
- [ ] Un bloqueo real puede escalar automaticamente a un rol Bedrock y volver con decision persistida.

Resultado de validacion 2026-03-22:

- `./.venv/bin/python -m pytest tests -q` paso con `39 passed`.
- El entorno local quedo alineado a `Python 3.12.13` con bootstrap reproducible via `scripts/bootstrap_local_env.sh`.
- `scripts/smoke_local.sh` paso con `dispatch_ready=true`, `dispatcher_executor=crewai` y `tool_count=12`.
- `scripts/smoke_docker.sh` paso con `mission-control-app` y `mission-control-postgres` en `healthy`, mas `GET /api/health` y `GET /api/runtime/health` correctos.
- El smoke agentic local sobre `The Barber Group` paso: `requirements.md` + `roadmap.md` produjeron `33` requirements, `5` epics, `20` tickets y `0` issues.
- Ese smoke agentic completo un dispatch `crew_seed=intake` con `Ollama qwen2.5-coder:latest`, dejo la entrada de cola en `completed` y persistio `agent_runs=1`, `task_executions=1` y `llm_invocations=1`.

Conclusion de validacion:

- La base de Fase 3 queda validada en host local, Docker Compose y flujo agentic real con specs externas.
- Mission Control ya puede ingerir un proyecto real de backend Python y ejecutar intake con telemetria canonica persistida.
- El trabajo restante de la fase se concentra en escalamiento Bedrock real y cierre del criterio de desbloqueo senior.

### Fase 4 - Autonomous Scrum Planner

Objetivo: convertir el blueprint en backlog ejecutable, sprints y ceremonias automaticas.

Estado actual:

- Entregado en `Phase4_automatic_scrum`: `scrum_plans` + `scrum_plan_items` persistidos, endpoint `/api/blueprints/<id>/scrum-plan`, `replan`, timeline/report extendidos y tool `mission_control_scrum_plan_context`.
- Validado con `42 passed` en `pytest`, smoke local OK sobre Python 3.12 y smoke Docker OK con `app` + `postgres` en `healthy`.

Tickets:

- `AG-401` cumplido: backlog inicial, orden por dependencias, estimacion heuristica a story points y asignacion de sprint.
- `AG-402` cumplido: el planner ejecuta un `Scrum Planning Crew` real sobre CrewAI antes de persistir y solo promueve a `active` los planes aprobados.
- `AG-403` cumplido: `Definition of Ready` y `Definition of Done` por ticket persistidos en `scrum_plan_items`.
- `AG-404` cumplido: endpoint de `replan` con versionado, supersede del plan activo y tratamiento de `blocked_ticket_ids` / `changed_ticket_ids`.
- `AG-405` cumplido: ceremonias persistidas en `sprint_stage_events` (`planning`, `daily_summary`, `review`, `retrospective`) y feedback de planning en `stage_feedback`.
- `AG-406` cumplido: score de riesgo por ticket y sprint, `confidence_score` del plan y `escalation_trigger` canonico.

Cierre de Fase 4:

- [x] Convertir `AG-402` en flujo obligatorio: ejecutar un `Scrum Planning Crew` real sobre CrewAI antes de persistir o aprobar el plan.
- [x] Conectar el escalamiento de `risk_level` / `confidence_score` a Bedrock como planner o reviewer senior cuando el trigger sea `bedrock_review`.
- [x] Añadir estado de aprobacion del plan (`draft`, `review_required`, `approved`) para separar plan heuristico de plan listo para ejecucion autonoma.
- [x] Exponer vista/API consolidada por sprint con capacidad consumida, tickets bloqueados y readiness del sprint para operar Fase 5 sin inspeccion manual.

Criterios de aceptacion:

- Desde specs se obtienen sprints listos para ejecucion sin crear tickets manualmente.
- Cada ticket tiene acceptance criteria y dependencias claras.
- El sistema puede replanificar si falla un bloque critico o si baja la confianza del blueprint.

### Fase 5 - Autonomous Delivery Loop

Objetivo: ejecutar implementacion end-to-end sin intervencion humana continua.

Tickets:

- `AG-501` Implementar `Delivery Crew` para tomar tickets listos, crear rama, editar codigo y correr validaciones.
- `AG-502` Implementar `Review Crew` para findings, severidad, retorno a desarrollo y aprobacion.
- `AG-503` Implementar `QA Gate` con reglas sobre tests, lint, coverage y regresiones.
- `AG-504` Implementar `Artifact Builder` para docs, changelog, ADRs y evidencias de test.
- `AG-505` Crear loop de autocorreccion: si fallan tests, abrir subtask, reintentar y cerrar evidencia.
- `AG-506` Integrar release candidate, merge automatizado y cierre de sprint.
- `AG-507` Registrar resultados del sprint review y alimentar la retrospective.

Criterios de aceptacion:

- Mission Control puede generar codigo a partir del backlog y dejar evidencia del cambio.
- El sistema crea commits, branches y PRs con trazabilidad a ticket y sprint.
- Si un intento falla, el sistema reintenta, escala o replantea sin requerir operador humano.

### Fase 6 - GitHub + Operator UX

Objetivo: reducir el rol humano a configuracion y supervision.

Tickets:

- `AG-601` Crear wizard/UI para registrar `GITHUB_TOKEN` o GitHub App, `OLLAMA_HOST`, `AWS_REGION`, credenciales Bedrock y perfiles de modelos.
- `AG-602` Crear UI para vincular repositorios, ramas protegidas y politicas de merge.
- `AG-603` Crear dashboard de blueprint, backlog, sprints, agent runs, stage feedback y retrospective.
- `AG-604` Crear timeline unificado de artifacts, runs, PRs, bloqueos y decisiones.
- `AG-605` Crear health dashboard de providers: Ollama models instalados, latencia y disponibilidad Bedrock.

Criterios de aceptacion:

- El operador solo necesita configurar credenciales e integraciones.
- El estado operativo del sistema se puede monitorear desde Mission Control.
- La UI permite diagnosticar donde fallo una corrida sin entrar a logs manuales.

### Fase 7 - Hardening & Benchmark

Objetivo: volver confiable el piloto y validar el caso de uso con el proyecto de ejemplo.

Tickets:

- `AG-701` Implementar politicas de seguridad para comandos, paths, secretos y acceso GitHub.
- `AG-702` Implementar budget controls por proyecto, sprint, provider y modelo.
- `AG-703` Añadir modo `simulation` y `dry-run` para intake, planning y delivery.
- `AG-704` Crear benchmark automatizado usando `docs/example_input_project/requirements.md` y `docs/example_input_project/roadmap.md`.
- `AG-705` Medir KPIs: lead time por ticket, retry rate, porcentaje de tickets completados, defectos encontrados en review, costo por sprint.
- `AG-706` Cerrar rollout eliminando adapter legacy restante y documentando runbooks.

Criterios de aceptacion:

- El benchmark del proyecto de ejemplo corre de punta a punta.
- Existen metricas objetivas de autonomia, calidad y costo.
- El runtime legacy queda retirado del camino principal.

## Secuencia recomendada

1. Limpiar el runtime actual y fijar el contrato de providers.
2. Construir primero intake + blueprint + backlog antes de automatizar desarrollo.
3. Modelar persistencia y trazabilidad en Postgres antes de aumentar autonomia.
4. Montar el runtime CrewAI con Ollama workers y Bedrock escalations.
5. Automatizar GitHub y gates de QA solo cuando haya evidencia persistida suficiente.
6. Ejecutar benchmark del proyecto de ejemplo como criterio de salida real.

## Riesgos principales y mitigaciones

- **Riesgo: parsing fragil de documentos Markdown.**  
  Mitigacion: parser estructurado + reconciliacion LLM + score de confianza + trazabilidad por seccion.

- **Riesgo: workers locales insuficientes para tickets complejos.**  
  Mitigacion: escalamiento automatico a Bedrock, split de tareas y politicas de retry.

- **Riesgo: falsa autonomia sin observabilidad suficiente.**  
  Mitigacion: todo run, artifact, feedback y decision queda persistido en Postgres.

- **Riesgo: loops agentic costosos o inestables.**  
  Mitigacion: budgets, max retries, circuit breakers, confidence thresholds y QA gates.

- **Riesgo: GitHub automation sin controles.**  
  Mitigacion: reglas por rama, merge gates, reviewers virtuales y dry-run obligatorio en bootstrap.

## Entregable minimo viable

El MVP correcto no es "un chat con agentes". El MVP correcto es este:

- Subir `requirements.md` y `roadmap.md`.
- Obtener blueprint y backlog listos en Postgres.
- Lanzar un sprint automatico sobre un repo GitHub.
- Ejecutar CrewAI con workers Ollama y revisores Bedrock.
- Ver en Mission Control el tracking de tickets, artifacts, QA, sprint review y retrospective.

Cuando ese flujo exista de punta a punta, `mission_control` ya habra dejado de ser solo un dashboard y se habra convertido en una software factory agentic operable.
