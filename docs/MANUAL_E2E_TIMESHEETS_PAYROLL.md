# Manual E2E - Demo de Timesheets y Payroll

Este manual sirve para levantar `mission_control`, importar un caso de uso pequeno y recorrer el MVP de punta a punta.

El flujo se divide en dos partes:

1. `E2E de negocio`: idea abierta -> `input certificado` -> documentos formales -> planning.
2. `E2E tecnico del delivery`: ejecutar el motor semiautomatico actual sobre tickets con recipes soportadas.

Importante: hoy el MVP ya hace bien el tramo `idea -> arquitectura inicial -> documentos -> backlog -> scrum plan`, pero el delivery semiautomatico todavia es `recipe-backed`. Eso significa que el caso de uso de timesheets/payroll sirve para validar intake y planning, pero no para generar todavia una aplicacion real del dominio completo en modo automatico.

## 1. Prerrequisitos

- Estar en el repo `mission_control`.
- Tener `python3.12` o `uv`.
- Tener `git`.
- Tener `curl`.
- Tener `jq` ayuda, pero no es obligatorio.

Si quieres que el planning use runtime real en vez de mocks de tests:

- CrewAI instalado en la `.venv`.
- Al menos un provider operativo:
  - Ollama local, o
  - Bedrock configurado.

Variables utiles si usas runtime real:

```bash
export OLLAMA_BASE_URL=http://localhost:11434
export OLLAMA_DEFAULT_MODEL=qwen2.5-coder:latest
export BEDROCK_REGION=us-east-1
export BEDROCK_PLANNER_MODEL=anthropic.claude-3-7-sonnet
export BEDROCK_REVIEWER_MODEL=anthropic.claude-3-5-sonnet
```

## 2. Bootstrap local

Desde la raiz del repo:

```bash
bash scripts/bootstrap_local_env.sh
```

Verifica:

```bash
./.venv/bin/python --version
```

Resultado esperado:

```text
Python 3.12.x
```

## 3. Arrancar Mission Control

```bash
PORT=5001 bash ./start_mission_control.sh
```

Verifica health:

```bash
curl -fsS http://localhost:5001/api/health | jq
curl -fsS http://localhost:5001/api/runtime/health | jq
```

La segunda llamada te dice si el runtime ve `crewai`, `ollama`, `bedrock` y GitHub.

Si no quieres usar `jq`:

```bash
curl -fsS http://localhost:5001/api/health | python3 -m json.tool
```

## 4. Usar el caso de uso demo

El repo ya incluye un brief listo en:

- [USE_CASE_TIMESHEETS_PAYROLL.md](/home/victor/repositories/mission_control/docs/example_project_timesheets/USE_CASE_TIMESHEETS_PAYROLL.md)

Ruta absoluta:

```bash
BRIEF_PATH=/home/victor/repositories/mission_control/docs/example_project_timesheets/USE_CASE_TIMESHEETS_PAYROLL.md
```

## 5. Preview del intake

Primero valida como Mission Control entiende el caso:

```bash
curl -sS -X POST http://localhost:5001/api/spec-intake/preview \
  -H 'Content-Type: application/json' \
  -d "{
    \"input_artifacts\": [
      {\"path\": \"${BRIEF_PATH}\"}
    ]
  }" | jq
```

Que deberias revisar en la respuesta:

- `project_name`
- `summary`
- `certified_input.source_input_kind`
- `certified_input.certification_status`
- `certified_input.technology_guidance`
- `certified_input.architecture_synthesis`

Chequeo rapido:

```bash
curl -sS -X POST http://localhost:5001/api/spec-intake/preview \
  -H 'Content-Type: application/json' \
  -d "{
    \"input_artifacts\": [
      {\"path\": \"${BRIEF_PATH}\"}
    ]
  }" | jq '{
    project_name,
    source_input_kind: .certified_input.source_input_kind,
    certification_status: .certified_input.certification_status,
    generated_docs: [.certified_input.documents[].doc_type],
    nfr_count: (.certified_input.architecture_synthesis.nfr_candidates | length),
    contract_count: (.certified_input.architecture_synthesis.technical_contracts | length),
    adr_count: (.certified_input.architecture_synthesis.adr_bootstrap | length)
  }'
```

Resultado esperado:

- `source_input_kind = "use_case_only"`
- `certification_status = "needs_operator_review"`
- documentos generados como:
  - `requirements.generated.md`
  - `roadmap.generated.md`
  - `assumptions.md`
  - `nfrs.candidates.md`
  - `technical_contracts.initial.md`
  - `adr_bootstrap.md`
  - `open_questions.md`

## 6. Importar el blueprint

Cuando el preview te convenza, persistelo:

```bash
IMPORT_RESPONSE=$(
  curl -sS -X POST http://localhost:5001/api/blueprints/import \
    -H 'Content-Type: application/json' \
    -d "{
      \"input_artifacts\": [
        {\"path\": \"${BRIEF_PATH}\"}
      ]
    }"
)
```

Extrae el `blueprint_id`:

```bash
BLUEPRINT_ID=$(printf '%s' "$IMPORT_RESPONSE" | jq -r '.id')
echo "$BLUEPRINT_ID"
```

Verifica el detalle:

```bash
curl -sS "http://localhost:5001/api/blueprints/${BLUEPRINT_ID}" | jq '{
  id,
  project_name,
  requirements: (.requirements | length),
  epics: (.roadmap_epics | length),
  certification_status: .certified_input.certification_status,
  open_questions: .certified_input.open_questions
}'
```

## 7. Leer los documentos generados

Puedes inspeccionar directamente los documentos formales:

```bash
curl -sS "http://localhost:5001/api/blueprints/${BLUEPRINT_ID}" | jq -r '
  .certified_input.documents[]
  | select(.doc_type == "requirements.generated.md")
  | .content
'
```

Roadmap:

```bash
curl -sS "http://localhost:5001/api/blueprints/${BLUEPRINT_ID}" | jq -r '
  .certified_input.documents[]
  | select(.doc_type == "roadmap.generated.md")
  | .content
'
```

Arquitectura inicial:

```bash
curl -sS "http://localhost:5001/api/blueprints/${BLUEPRINT_ID}" | jq -r '
  .certified_input.documents[]
  | select(.doc_type == "technical_contracts.initial.md" or .doc_type == "adr_bootstrap.md")
  | "\n===== \(.doc_type) =====\n\n\(.content)"
'
```

## 8. Generar scrum plan

Este paso ya usa el runtime agentic real del planner.

```bash
PLAN_RESPONSE=$(
  curl -sS -X POST "http://localhost:5001/api/blueprints/${BLUEPRINT_ID}/scrum-plan" \
    -H 'Content-Type: application/json' \
    -d '{
      "sprint_capacity": 8,
      "sprint_length_days": 7,
      "planning_mode": "autonomous",
      "source": "manual_e2e"
    }'
)
```

Inspecciona:

```bash
printf '%s' "$PLAN_RESPONSE" | jq '{
  id,
  version,
  approval_status,
  sprint_count: (.sprints | length),
  execution_ready: .summary.execution_ready,
  planning_crew: .summary.planning_crew
}'
```

Si el planner devuelve `approval_status = "review_required"`, apruebalo manualmente:

```bash
PLAN_ID=$(printf '%s' "$PLAN_RESPONSE" | jq -r '.id')

curl -sS -X POST \
  "http://localhost:5001/api/blueprints/${BLUEPRINT_ID}/scrum-plan/${PLAN_ID}/approve" \
  -H 'Content-Type: application/json' \
  -d '{
    "source": "manual_e2e",
    "feedback_text": "Aprobado para demo local."
  }' | jq
```

Vista por sprint:

```bash
curl -sS "http://localhost:5001/api/blueprints/${BLUEPRINT_ID}/scrum-plan/sprint-view" | jq
```

Con esto ya validaste el tramo de negocio principal del MVP:

- caso de uso abierto;
- `close-the-gap` arquitectonico;
- documentos formales;
- backlog estructurado;
- scrum planning;
- aprobacion manual si hace falta.

## 9. Limite actual del MVP

El caso de timesheets/payroll **no entra todavia** al delivery semiautomatico de forma automatica, porque hoy el executor solo soporta tickets con recipes deterministas.

Recipes soportadas hoy:

- `examples/holamundo.py`
- `frontend/index.html` con React Hola Mundo
- `infra/main.tf`, `infra/variables.tf`, `infra/outputs.tf` con modulo S3 basico

Eso no invalida la demo de negocio; solo significa que el tramo `planning -> escribir codigo real del producto de payroll` todavia no esta generalizado.

## 10. Delivery engine smoke separado

Si quieres probar tambien el motor de delivery de punta a punta, usa el harness oficial:

```bash
./.venv/bin/python scripts/e2e_validate_mission_control.py --allow-missing-langgraph
```

O contra el dossier real del repo:

```bash
./.venv/bin/python scripts/e2e_validate_mission_control.py \
  --allow-missing-langgraph \
  --project-root docs/example_project_2
```

Ese flujo si valida:

- import via HTTP;
- scrum planning;
- approval status;
- guardrails;
- delivery semiautomatico;
- review;
- QA gate;
- release candidate local;
- retrospective.

## 11. Flujo recomendado para demo manual

Si quieres una demo corta y creible frente a alguien:

1. Arranca Mission Control.
2. Corre el preview con el brief de timesheets/payroll.
3. Muestra `requirements.generated.md`.
4. Muestra `technical_contracts.initial.md` y `adr_bootstrap.md`.
5. Importa el blueprint.
6. Genera el scrum plan.
7. Muestra la vista por sprint.
8. Cierra mostrando el E2E oficial del delivery con `scripts/e2e_validate_mission_control.py`.

Ese orden enseña la vision real sin prometer que el executor ya construye automaticamente toda la app de negocio.

## 12. Comandos de cierre

Ver blueprints persistidos:

```bash
curl -sS http://localhost:5001/api/blueprints | jq
```

Ver reporte consolidado:

```bash
curl -sS "http://localhost:5001/api/blueprints/${BLUEPRINT_ID}/report" | jq
```

Parar Mission Control:

```bash
kill "$(cat mission_control.pid)"
rm -f mission_control.pid
```
