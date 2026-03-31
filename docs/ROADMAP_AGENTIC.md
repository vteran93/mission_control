# Roadmap Agentic de Mission Control

**Fecha base**: 2026-03-21  
**Estado base**: `mission_control` ya tiene Flask + Postgres operativos, pero el runtime sigue acoplado a OpenClaw/Clawbot.  
**Objetivo macro**: convertir `mission_control` en una software factory `CrewAI-only` capaz de ingerir desde un par formal `requirements.md` + `roadmap.md` hasta una idea expresada en lenguaje natural por chat web, cerrar gaps con un agente arquitecto aguas arriba y producir un paquete formal de requerimientos listo para planificar, ejecutar y cerrar el ciclo SCRUM completo de forma desatendida.

## Estado de ejecucion

- [x] Fase 0 - Foundation Cleanup
- [x] Fase 1 - Spec Intake Engine (slice ampliado entregado: parser, intake flexible, `input certificado`, dossier-to-certified-input y `architecture synthesizer` MVP)
- [x] Fase 2 - Postgres Delivery Model (blueprints, sprints, tracking de ejecucion, timeline y reporting en Postgres)
- [ ] Fase 3 - CrewAI Runtime Hybrid (runtime operativo validado; escalamiento real a Bedrock sigue pendiente)
- [x] Fase 4 - Autonomous Scrum Planner (plan versionado, aprobacion, escalamiento Bedrock y vista operativa por sprint)
- [x] Fase 5 - Autonomous Delivery Loop (delivery, review, QA gate, artifacts, autocorreccion, release candidate local, retrospective y architecture guardrails por workspace)
- [ ] Fase 6 - GitHub + Operator UX
- [ ] Fase 7 - Hardening & Benchmark

## Cobertura actual del intake

- [x] Nivel A - `requirements.md` + `roadmap.md` con estructura canonica y tickets parseables.
- [x] Nivel B - dossier semiestructurado como `docs/example_project_2/VEO3_CLAUDE_INTEGRATION_ROADMAP.md` mas anexos.
- [x] Nivel C - conjunto variable de artefactos (`notes`, `adr`, diagramas, roadmap-only, brief tecnico).
- [x] Nivel D - solo casos de uso, restricciones de negocio y objetivos.
- [ ] Nivel E - conversacion iterativa por chat web con el operador.
- [x] Modo `architect close-the-gap` para emitir `requirements.generated.md`, `roadmap.generated.md`, `assumptions.md`, `open_questions.md` y `confidence_score` en un slice MVP no conversacional.

Conclusion de esta revision: el roadmap ya cubre bien los niveles A-D con `input_artifacts[]`, normalizacion y un arquitecto MVP; el salto pendiente queda concentrado en el Nivel E y en los guardrails de `confidence_score` / `question_budget`.

## Resultado esperado

Al terminar este roadmap, Mission Control debe poder:

1. Ingerir documentos de requerimientos y roadmap en Markdown.
2. O, si esos documentos no existen aun, ingerir un set variable de artefactos o una conversacion de chat y convertirlo en un paquete formal derivado con trazabilidad.
3. Normalizarlos a un `Project Blueprint` persistido en Postgres.
4. Generar backlog, epics, sprints, criterios de aceptacion y dependencias.
5. Ejecutar crews de CrewAI para arquitectura, desarrollo, QA, code review, documentacion y release.
6. Usar modelos locales de Ollama como fuerza de trabajo principal.
7. Usar modelos Bedrock como orquestadores, senior reviewers, tomadores de decision y desbloqueadores.
8. Sincronizar repositorio, issues, branches, PRs y artifacts con GitHub.
9. Registrar en Postgres el tracking completo de ejecucion, feedback por etapa SCRUM y retrospectivas.
10. Operar sin intervencion humana continua; el humano solo configura credenciales, proveedores y conectores como GitHub, Ollama y Bedrock, y responde preguntas abiertas cuando el `confidence_score` del intake no alcance el umbral.
11. Usar un agente arquitecto para hacer `close-the-gap` entre casos de uso, restricciones, decisiones implicitas y un documento formal de requerimientos.
12. Permitir que ese `close-the-gap` empiece desde una interfaz de chat web en la que el usuario describe la idea del producto en lenguaje natural.

## Principios no negociables

- Toda la orquestacion agentic corre sobre CrewAI.
- `mission_control` conserva el rol de sistema de registro y observabilidad.
- Postgres es la fuente de verdad para planes, ejecuciones, handoffs, artifacts, feedback y retrospectives.
- Estrategia `local-first`: Ollama ejecuta los workers por defecto; Bedrock entra por complejidad, ambiguedad, desbloqueo, revision o escalamiento.
- No se depende de OpenClaw, Clawbot ni colas filesystem en el camino principal.
- El sistema debe poder correr sin prompts hardcodeados por proyecto; los insumos vienen de documentos y configuracion.
- El contrato de entrada es progresivo: el sistema no exige un `shape` unico mientras exista suficiente senal para formalizar.
- Cuando falten artefactos canonicos, el intake debe generar borradores estructurados, supuestos explicitos y preguntas abiertas antes de planificar entrega.
- El agente arquitecto no inventa silenciosamente: toda inferencia debe quedar marcada con trazabilidad a fuente, `confidence_score` y posibilidad de aprobacion humana.
- El intake debe poder operar en modo conversacional: preguntar, refinar y confirmar alcance antes de congelar `requirements.generated.md` y `roadmap.generated.md`.
- Cada etapa debe dejar evidencia reproducible: entrada, decision, output, validacion y costo/latencia del modelo.

## Contratos de entrada soportados

Mission Control debe soportar una escala de inputs, no un unico formato duro:

- Nivel A - Par formal: `docs/example_input_project/requirements.md` + `docs/example_input_project/roadmap.md`.
  Aqui los artefactos ya vienen casi listos para parsing estructurado.
- Nivel B - Dossier semiestructurado: `docs/example_project_2/VEO3_CLAUDE_INTEGRATION_ROADMAP.md` + anexos como `AGENTIC_WORKFLOW_CLASS_DIAGRAM.md`.
  Aqui hay decisiones, hallazgos, fases, restricciones y arquitectura, pero no necesariamente `EP-*` o `TICKET-*` parseables.
- Nivel C - Brief acotado: una combinacion de casos de uso, integraciones, restricciones, objetivos de negocio y notas tecnicas.
- Nivel D - Idea abierta: solo casos de uso, actores, outcomes esperados y limites operativos.
- Nivel E - Chat web: una conversacion iterativa entre operador y agente arquitecto, donde el sistema extrae requerimientos, detecta vacios y hace preguntas de aclaracion.

El flujo correcto para todos los niveles es:

1. Clasificar el `shape` del input y medir completitud.
2. Extraer evidencia estructurable por seccion, documento y fragmento.
3. Activar un agente arquitecto cuando falte informacion formal o haya decisiones implicitas.
4. Emitir un `input certificado` consumible por planning, delivery y los contratos internos del sistema.

Ese `input certificado` debe incluir:

- `Project Blueprint`
- `Capability Map`
- `Formal Requirements Document`
- `Formal Roadmap Document`
- `Execution Plan`
- `Backlog`
- `Sprint Plan`
- `Acceptance Matrix`
- `Assumptions Register`
- `Open Questions`
- `Traceability Map`
- `confidence_score`
- `certification_status`

`certification_status` debe ser uno de:

- `ready_for_planning`
- `needs_operator_review`
- `insufficient_input`

Estado actual del repositorio: el slice implementado cubre sobre todo el Nivel A. Los niveles B-E requieren una ampliacion explicita del intake, el contrato API y el rol del arquitecto para cerrar cada input hacia este `input certificado`.

## Flujo conversacional objetivo

El modo objetivo de intake debe permitir este patron:

1. El operador abre una interfaz de chat web y describe la idea en lenguaje natural.
2. El agente arquitecto clasifica dominio, actores, modulos, restricciones y vacios.
3. Si faltan datos criticos, hace preguntas de aclaracion dentro del mismo chat.
4. Cuando la confianza sea suficiente, genera:
   - `requirements.generated.md`
   - `roadmap.generated.md`
   - `assumptions.md`
   - `open_questions.md`
5. El sistema consolida esos artefactos en un `input certificado`.
6. El operador revisa y aprueba ese paquete antes de pasar a planning.

Ejemplo objetivo:

- Input via chat:
  `Quiero un sistema de gestion de firmas de recursos humanos donde puedan contratar, firmar contrato usando ethereum contracts, que los empleados registren su asistencia, hora de inicio de labores en una aplicacion windows/linux/mac os, que registren tareas y calcular salarios por hora para cada empleado de acuerdo a tarifas por individuo.`
- Output esperado:
  un `requirements.generated.md` formal con modulos como reclutamiento/contratacion, firma de contratos on-chain, desktop attendance app multiplataforma, task tracking y payroll por tarifa individual; un `roadmap.generated.md` ejecutable con epics, tickets, dependencias y criterios de aceptacion; y un `input certificado` listo para nuestros contratos internos de planning.

Flujo adicional obligatorio:

- Si el input es un dossier como `docs/example_project_2/*`, el sistema no debe limitarse a resumirlo.
- Debe hacer `close-the-gap` hasta producir exactamente el mismo tipo de `input certificado` que produciria desde un chat o desde un par formal.

## Arquitectura target

```text
                           +----------------------------------+
                           |  UI de configuracion minima      |
                           |  + chat de discovery/spec intake |
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
- `conversation_intake_facilitator` (Bedrock): conduce la conversacion inicial, resume cada turno, detecta vacios y decide cuando pedir aclaraciones.
- `spec_analyst` (Bedrock): clasifica el `shape` de entrada, interpreta uno o varios artefactos, extrae requerimientos funcionales/no funcionales y detecta contradicciones.
- `requirements_normalizer` (Bedrock): convierte insumos abiertos o desbalanceados en un `requirements formal` con trazabilidad, constraints y acceptance hints.
- `delivery_analyst` (Bedrock): transforma el roadmap fuente o el roadmap generado en backlog ejecutable con dependencias, estimaciones y Definition of Done.
- `architecture_synthesizer` (Bedrock): hace `close-the-gap`, explicita supuestos, contratos tecnicos iniciales, ADRs bootstrap y preguntas abiertas antes de pasar a planning.

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

- Dado un set de artefactos de entrada, desde `requirements.md` + `roadmap.md` hasta un roadmap narrativo con anexos o solo casos de uso, genera un `Project Blueprint` y un paquete formal derivado sin edicion manual obligatoria.
- Dada una idea expresada por chat web, el sistema puede conducir discovery, aclarar vacios y producir `requirements.generated.md` + `roadmap.generated.md` antes de planificar.
- Dado un dossier semiestructurado como `docs/example_project_2/*`, el sistema puede cerrarlo hasta el mismo `input certificado` que consumen los contratos internos de Mission Control.
- Si faltan `requirements.md` o `roadmap.md`, el sistema puede generarlos de forma trazable antes de planificar.
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

Objetivo: que Mission Control entienda documentos formales, dossiers semiestructurados y briefs mas abiertos o mas cerrados, y genere tanto un modelo canonico del proyecto como un `input certificado` derivado cuando el input venga incompleto.

Estado actual de la fase:

- [x] Intake canonico desde `requirements.md` + `roadmap.md`.
- [ ] Clasificador de `shape` y completitud del input.
- [ ] Formalizacion derivada por agente arquitecto.
- [ ] Soporte real para `roadmap-only`, `multi-artifact brief` y `use-case-only`.
- [ ] Soporte real para intake conversacional desde chat web.

Tickets:

- `AG-101` Definir `ProjectBlueprint`, `RequirementItem`, `AcceptanceItem`, `RoadmapEpic`, `RoadmapTicket`.
- `AG-102` Implementar parser de Markdown estructurado para `requirements.md`.
- `AG-103` Implementar parser de Markdown estructurado para `roadmap.md`.
- `AG-104` Implementar reconciliacion entre documentos: inconsistencias, gaps, dependencias faltantes, duplicados.
- `AG-105` Crear `Intake Crew` en CrewAI para producir blueprint validado y score de confianza.
- `AG-106` Persistir versionado de specs y blueprint derivado.
- `AG-107` Exponer endpoint/UI para cargar o registrar documentos fuente por proyecto.
- [x] `AG-108` Implementar `input shape classifier` para distinguir `formal_pair`, `roadmap_dossier`, `multi_artifact_brief` y `use_case_only`.
- [x] `AG-109` Crear `Requirements Normalizer` que genere `requirements.generated.md` cuando el input no traiga un documento canonico.
- [x] `AG-110` Crear `Architecture Synthesizer` para hacer `close-the-gap`: supuestos, NFRs candidatos, contratos tecnicos iniciales, ADR bootstrap y preguntas abiertas.
- [x] `AG-111` Cambiar el contrato logico de intake desde `requirements_path + roadmap_path` hacia `input_artifacts[]`, aunque el adapter inicial siga aceptando ambos campos para compatibilidad.
- [ ] `AG-112` Definir `confidence_score`, `question_budget` y criterio de escalamiento humano para evitar que el arquitecto invente detalles sin evidencia suficiente.
- `AG-113` Crear `conversation intake session` persistida: transcript, turnos, resumenes, preguntas abiertas, respuestas y estado de confianza.
- `AG-114` Crear `Conversational Architect` aguas arriba para transformar chat web en `requirements.generated.md` y `roadmap.generated.md`.
- `AG-115` Permitir ciclo iterativo de aclaraciones dentro del chat antes de congelar artefactos formales.
- `AG-116` Exponer preview/diff y aprobacion de documentos generados desde chat antes de pasar a planning.
- [x] `AG-117` Definir el contrato canonico de `input certificado` para intake derivado, incluyendo `certification_status`, `confidence_score`, trazabilidad y paquete documental minimo.
- [x] `AG-118` Implementar `dossier-to-certified-input` para inputs como `docs/example_project_2/*`, cerrando gaps hasta el contrato canonico consumido por planning.

Criterios de aceptacion:

- El sistema puede leer los dos documentos de `docs/example_input_project/` y producir un blueprint unico.
- El sistema puede leer `docs/example_project_2/` y derivar `requirements formal` + `roadmap estructurado` + `blueprint` con trazabilidad.
- El sistema puede convertir `docs/example_project_2/*` en el mismo `input certificado` que produciria el intake desde un par formal o desde chat.
- El sistema puede aceptar un input mas abierto o mas cerrado sin romper el intake; cuando falte informacion, deja supuestos y preguntas explicitas en vez de inventar silenciosamente.
- El sistema puede partir de una idea escrita en chat web y convertirla en `requirements.generated.md` + `roadmap.generated.md` aprobables por operador.
- El blueprint conserva trazabilidad a seccion y documento de origen.
- Los conflictos, lagunas e inferencias quedan marcados con `confidence_score` y pueden disparar escalamiento Bedrock u operador humano.

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

Cierre de Fase 5:

- `AG-501` cumplido: el pipeline toma tickets `planned` + `ready` desde un `scrum_plan` aprobado, ejecuta delivery y escribe artefactos reales en un `workspace_root`.
- `AG-502` cumplido: existe etapa de `review` con findings estructurados, veredicto y trazabilidad en `stage_feedback`, `handoffs` y `agent_runs`.
- `AG-503` cumplido: el `QA Gate` evalua reglas canonicas sobre ejecucion, validaciones y aprobacion de review antes de liberar.
- `AG-504` cumplido: `Artifact Builder` genera evidencia operativa (`delivery_summary`, `review_report`, `qa_gate`, `test_evidence`, `release_candidate`, `retrospective`) y la registra en `artifacts`.
- `AG-505` cumplido: hay loop de autocorreccion con reintento cuando una validacion falla y evidencia de retry en `task_executions` / `handoffs`.
- `AG-506` cumplido: el flujo crea `release candidate` local sobre git, soporta merge `ff-only` al branch actual y deja metadata reproducible.
- `AG-507` cumplido: el cierre registra `review`, `release`, `retrospective`, actualiza `sprint_cycles` y alimenta `retrospective_items`.

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
- El sistema crea commits y branches locales con trazabilidad a ticket y sprint; la sincronizacion con PRs remotos queda opcional.
- Si un intento falla, el sistema reintenta, escala o replantea sin requerir operador humano.

### Fase 6 - GitHub + Operator UX

Objetivo: reducir el rol humano a configuracion y supervision.

Estado actual:

- Modo operativo actual: `git local` como camino principal. GitHub queda opcional y no hay dependencia de webhooks de pull requests para operar Mission Control.
- Slice operador ampliado entregado: `operator_settings` persistidos, endpoints `/api/operator/settings`, `/api/operator/dashboard`, `/api/operator/github/*` y `/api/blueprints/<id>/operator-dashboard`, health consolidado de `crewai`, `ollama`, `bedrock` y `github`, y panel operador embebido en `/`.
- GitHub ya soporta `token` o GitHub App real con `app_id`, `installation_id` y private key; si se habilita, el operador puede sincronizar protected branches, importar snapshots de pull requests y revisar timeline GitHub desde la UI.
- El dashboard profundo por blueprint ya expone `latest_plan`, `agent_runs`, `artifacts`, `stage_feedback`, `retrospective_items` y PRs vinculados por branch naming.
- Existe trazabilidad persistida en `github_sync_events` y cobertura E2E para branch protection sync, PR sync y observabilidad de blueprint, todo en modo manual/pull-based.
- El siguiente salto de UX debe ser un `chat intake workspace` en la web para pasar de idea -> requisitos formales -> roadmap sin salir de Mission Control.

Tickets:

- `AG-601` Crear wizard/UI para registrar `GITHUB_TOKEN` o GitHub App, `OLLAMA_HOST`, `AWS_REGION`, credenciales Bedrock y perfiles de modelos.
- `AG-602` Crear UI para vincular repositorios, ramas protegidas y politicas de merge.
- `AG-603` Crear dashboard de blueprint, backlog, sprints, agent runs, stage feedback y retrospective.
- `AG-604` Crear timeline unificado de artifacts, runs, PRs, bloqueos y decisiones.
- `AG-605` Crear health dashboard de providers: Ollama models instalados, latencia y disponibilidad Bedrock.
- `AG-606` Crear interfaz de chat web para `conversational intake`, ligada a proyecto, transcript persistido y estado de confianza.
- `AG-607` Crear vista de aprobacion para `requirements.generated.md` y `roadmap.generated.md`, con diff entre borrador generado y version aprobada.

Criterios de aceptacion:

- El operador solo necesita configurar credenciales e integraciones.
- El estado operativo del sistema se puede monitorear desde Mission Control.
- La UI permite diagnosticar donde fallo una corrida sin entrar a logs manuales.
- No existen dependencias obligatorias en webhooks o eventos de PR remotos para el flujo base.
- El operador puede iniciar un proyecto nuevo describiendo la idea en chat web y aprobar los artefactos formales generados sin usar herramientas externas.

### Fase 7 - Hardening & Benchmark

Objetivo: volver confiable el piloto y validar el caso de uso con el proyecto de ejemplo.

Tickets:

- `AG-701` Implementar politicas de seguridad para comandos, paths, secretos y acceso GitHub.
- `AG-702` Implementar budget controls por proyecto, sprint, provider y modelo.
- `AG-703` Añadir modo `simulation` y `dry-run` para intake, planning y delivery.
- `AG-704` Crear benchmark automatizado usando `docs/example_input_project/requirements.md` y `docs/example_input_project/roadmap.md`.
- `AG-705` Medir KPIs: lead time por ticket, retry rate, porcentaje de tickets completados, defectos encontrados en review, costo por sprint.
- `AG-706` Cerrar rollout eliminando adapter legacy restante y documentando runbooks.
- `AG-707` Crear benchmark automatizado de intake semiestructurado usando `docs/example_project_2/*` y medir cuanto del paquete formal se genera sin intervencion humana.
- `AG-708` Crear benchmark de `use-case-only` con un brief minimo y medir `confidence_score`, preguntas abiertas y calidad del `close-the-gap`.
- `AG-709` Medir KPIs del intake flexible: porcentaje de requerimientos trazables, cantidad de supuestos no resueltos, retrabajo posterior al planning y precision del backlog derivado.
- `AG-710` Crear benchmark `chat-to-spec` con escenarios reales, incluyendo un caso de RRHH + contratos Ethereum + attendance desktop + payroll por hora.
- `AG-711` Validar que `docs/example_project_2/*` cierre al mismo `input certificado` esperado por nuestros contratos internos, sin bypasses o adapters manuales.

Criterios de aceptacion:

- El benchmark formal del proyecto de ejemplo corre de punta a punta.
- El benchmark semiestructurado sobre `docs/example_project_2/` produce un paquete formal usable antes del planning.
- El benchmark semiestructurado sobre `docs/example_project_2/` produce el `input certificado` canonico esperado por los contratos internos.
- Existe un benchmark `use-case-only` con salida controlada, supuestos explicitos y criterio de escalamiento humano.
- Existe un benchmark `chat-to-spec` donde una descripcion conversacional produce documentos formales aprobables.
- Existen metricas objetivas de autonomia, calidad y costo.
- El runtime legacy queda retirado del camino principal.

## Secuencia recomendada

1. Limpiar el runtime actual y fijar el contrato de providers.
2. Construir primero intake + blueprint + backlog antes de automatizar desarrollo.
3. Modelar persistencia y trazabilidad en Postgres antes de aumentar autonomia.
4. Montar el runtime CrewAI con Ollama workers y Bedrock escalations.
5. Automatizar GitHub y gates de QA solo cuando haya evidencia persistida suficiente.
6. Ejecutar benchmarks formal, semiestructurado, `use-case-only` y `chat-to-spec` como criterio de salida real.

## Riesgos principales y mitigaciones

- **Riesgo: parsing fragil de documentos Markdown o dependencia excesiva de un formato unico.**  
  Mitigacion: `shape classifier` + parser estructurado donde aplique + formalizacion con arquitecto + `confidence_score` + trazabilidad por seccion.

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
- O subir un set de artefactos mas abierto para que el arquitecto genere esos documentos primero.
- O describir la idea en un chat web para que el arquitecto produzca esos documentos antes de planning.
- Obtener blueprint y backlog listos en Postgres.
- Lanzar un sprint automatico sobre un repo GitHub.
- Ejecutar CrewAI con workers Ollama y revisores Bedrock.
- Ver en Mission Control el tracking de tickets, artifacts, QA, sprint review y retrospective.

Cuando ese flujo exista de punta a punta, `mission_control` ya habra dejado de ser solo un dashboard y se habra convertido en una software factory agentic operable.
