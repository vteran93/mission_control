#!/bin/bash

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

DEFAULT_PLANE_URL="http://localhost"
DEFAULT_PAGE_SIZE=200

TICKETS_JSON=$(cat <<'EOF'
[
  {
    "code": "AG-109",
    "phase": "Fase 1 - Spec Intake Engine",
    "priority": "high",
    "title": "Requirements Normalizer para inputs no canonicos",
    "depends_on": ["AG-108", "AG-111", "AG-117"],
    "summary": "Generar requirements.generated.md cuando el input venga como dossier, roadmap-only, brief tecnico o use-case-only sin documento canonico.",
    "scope": [
      "Normalizar inputs no canonicos a un requirements formal derivado.",
      "Preservar trazabilidad por artefacto y seccion de origen.",
      "Integrar la salida con certified_input y el pipeline de planning actual.",
      "Marcar needs_operator_review cuando la evidencia sea insuficiente."
    ],
    "acceptance": [
      "El intake produce requirements.generated.md consistente para input_artifacts semiestructurados.",
      "El documento derivado conserva source_paths y source_sections relevantes.",
      "No rompe compatibilidad con requirements.md + roadmap.md.",
      "Los gaps quedan explicitados como assumptions u open questions, no como invenciones silenciosas."
    ]
  },
  {
    "code": "AG-110",
    "phase": "Fase 1 - Spec Intake Engine",
    "priority": "urgent",
    "title": "Architecture Synthesizer para close-the-gap",
    "depends_on": ["AG-109", "AG-117"],
    "summary": "Crear el agente arquitecto que cierre gaps desde briefs, dossiers o inputs abiertos hacia un paquete formal listo para planning.",
    "scope": [
      "Explicitar supuestos, NFRs candidatos, contratos tecnicos iniciales y ADR bootstrap.",
      "Proponer stack tecnologico con filosofia python_first y excepciones justificadas por plataforma.",
      "Generar assumptions.md y open_questions.md junto al paquete formal derivado.",
      "Dejar trazabilidad y rationale por inferencia importante."
    ],
    "acceptance": [
      "El arquitecto produce artifacts formales consumibles por Mission Control.",
      "Cada decision tecnica importante queda justificada y trazable.",
      "Las excepciones a python_first se explican de forma explicita.",
      "El output puede pasar a planning sin adapters manuales."
    ]
  },
  {
    "code": "AG-112",
    "phase": "Fase 1 - Spec Intake Engine",
    "priority": "urgent",
    "title": "Confidence score, question budget y escalamiento humano",
    "depends_on": ["AG-110"],
    "summary": "Evitar que el arquitecto invente detalles sin evidencia suficiente mediante guardrails de decision y escalamiento.",
    "scope": [
      "Definir confidence_score y umbrales por tipo de input.",
      "Definir question_budget para intake conversacional y dossier-driven intake.",
      "Escalar a operador cuando falte evidencia critica o se agoten las preguntas permitidas.",
      "Persistir razones del escalamiento y campos insuficientes."
    ],
    "acceptance": [
      "El sistema no pasa a planning si la confianza cae por debajo del umbral.",
      "Los escalados a operador quedan trazados con razones concretas.",
      "El arquitecto reduce preguntas redundantes y evita loops infinitos.",
      "Las preguntas abiertas quedan visibles en el paquete formal."
    ]
  },
  {
    "code": "AG-113",
    "phase": "Fase 1 - Spec Intake Engine",
    "priority": "high",
    "title": "Conversation intake session persistida",
    "depends_on": ["AG-112"],
    "summary": "Persistir transcript, turnos, resumenes y estado de confianza para intake conversacional.",
    "scope": [
      "Modelar sesion conversacional por proyecto.",
      "Guardar transcript, turnos, preguntas abiertas, respuestas y resumen operativo.",
      "Persistir confidence_score y estado de avance de discovery.",
      "Preparar la base para chat web y aprobacion posterior."
    ],
    "acceptance": [
      "Una sesion conversacional se puede reconstruir completa desde Postgres.",
      "Cada turno deja evidencia y estado de confianza.",
      "El intake puede retomar una sesion sin perder contexto.",
      "El transcript se vincula al blueprint o draft en progreso."
    ]
  },
  {
    "code": "AG-114",
    "phase": "Fase 1 - Spec Intake Engine",
    "priority": "urgent",
    "title": "Conversational Architect aguas arriba",
    "depends_on": ["AG-110", "AG-112", "AG-113"],
    "summary": "Transformar una descripcion en chat web en requirements.generated.md y roadmap.generated.md aprobables.",
    "scope": [
      "Crear el flujo chat -> architect pass -> artifacts formales.",
      "Conectar la salida al contrato certified_input.",
      "Reusar judge y guardrails para validar estructura antes de aprobar.",
      "Preparar handoff directo a planning."
    ],
    "acceptance": [
      "Una idea escrita en lenguaje natural puede producir requirements.generated.md y roadmap.generated.md.",
      "La salida es estructurada, validable y persistida.",
      "El flujo no depende de editar archivos manualmente fuera de Mission Control.",
      "El resultado queda listo para revision del operador."
    ]
  },
  {
    "code": "AG-115",
    "phase": "Fase 1 - Spec Intake Engine",
    "priority": "high",
    "title": "Ciclo iterativo de aclaraciones en el chat",
    "depends_on": ["AG-113", "AG-114"],
    "summary": "Permitir discovery iterativo antes de congelar el paquete formal.",
    "scope": [
      "Generar preguntas de aclaracion basadas en gaps reales.",
      "Recalcular confidence_score y open questions tras cada respuesta.",
      "Cerrar el ciclo cuando haya senal suficiente o se requiera escalamiento humano.",
      "Evitar preguntas repetidas o de bajo valor."
    ],
    "acceptance": [
      "El chat puede hacer varias rondas de aclaracion sin perder trazabilidad.",
      "Cada respuesta cambia el estado del intake de forma observable.",
      "El sistema sabe cuando dejar de preguntar y pedir aprobacion.",
      "No se congelan artifacts formales hasta que la confianza sea suficiente."
    ]
  },
  {
    "code": "AG-116",
    "phase": "Fase 1 - Spec Intake Engine",
    "priority": "high",
    "title": "Preview, diff y aprobacion de documentos generados",
    "depends_on": ["AG-114", "AG-115"],
    "summary": "Permitir que el operador revise y apruebe requirements.generated.md y roadmap.generated.md antes de planning.",
    "scope": [
      "Exponer preview de artefactos generados.",
      "Mostrar diff entre borrador generado y version aprobada.",
      "Registrar aprobacion o rechazo por operador.",
      "Bloquear planning hasta que exista decision."
    ],
    "acceptance": [
      "El operador puede aprobar o rechazar artifacts generados desde la UI o API.",
      "El diff deja evidencia de lo que cambio.",
      "La aprobacion queda persistida y vinculada al blueprint.",
      "Planning solo usa artifacts aprobados."
    ]
  },
  {
    "code": "AG-606",
    "phase": "Fase 6 - GitHub + Operator UX",
    "priority": "high",
    "title": "Interfaz de chat web para conversational intake",
    "depends_on": ["AG-113", "AG-114", "AG-115"],
    "summary": "Crear la UI web para que el operador describa la idea del producto y conduzca el intake conversacional.",
    "scope": [
      "Crear workspace de chat ligado a proyecto.",
      "Mostrar transcript, preguntas abiertas y estado de confianza.",
      "Integrar llamadas a la sesion conversacional persistida.",
      "Preparar el flujo de aprobacion y handoff a planning."
    ],
    "acceptance": [
      "El operador puede iniciar un proyecto desde chat web.",
      "La UI muestra transcript y estado de confidence en tiempo real.",
      "Las preguntas abiertas son visibles y accionables.",
      "El flujo se conecta a los artifacts formales generados."
    ]
  },
  {
    "code": "AG-607",
    "phase": "Fase 6 - GitHub + Operator UX",
    "priority": "high",
    "title": "Vista de aprobacion para requirements.generated.md y roadmap.generated.md",
    "depends_on": ["AG-116", "AG-606"],
    "summary": "Exponer una UX clara para revisar, comparar y aprobar documentos derivados dentro de Mission Control.",
    "scope": [
      "Renderizar requirements.generated.md y roadmap.generated.md en la web.",
      "Mostrar diff entre draft y approved version.",
      "Registrar decisiones de aprobacion o rechazo con comentario opcional.",
      "Conectar la aprobacion con el desbloqueo de planning."
    ],
    "acceptance": [
      "El operador puede revisar los artifacts sin salir de Mission Control.",
      "La vista de diff es suficiente para detectar cambios importantes.",
      "La decision del operador queda auditada.",
      "La UI bloquea planning si falta aprobacion."
    ]
  },
  {
    "code": "AG-701",
    "phase": "Fase 7 - Hardening & Benchmark",
    "priority": "high",
    "title": "Politicas de seguridad para comandos, paths, secretos y acceso GitHub",
    "depends_on": [],
    "summary": "Completar el hardening operativo para que el piloto no dependa solo de buenas practicas implicitas.",
    "scope": [
      "Endurecer guardrails de comandos y paths.",
      "Agregar manejo de secretos y politicas mas estrictas para GitHub.",
      "Cerrar huecos entre runtime, delivery y operator settings.",
      "Documentar controles y fallos esperados."
    ],
    "acceptance": [
      "No se ejecutan comandos ni escrituras fuera de politica.",
      "Los secretos quedan protegidos y no expuestos en logs o prompts.",
      "GitHub opera con reglas explicitas y auditables.",
      "Existe cobertura automatizada de las politicas principales."
    ]
  },
  {
    "code": "AG-702",
    "phase": "Fase 7 - Hardening & Benchmark",
    "priority": "medium",
    "title": "Budget controls por proyecto, sprint, provider y modelo",
    "depends_on": [],
    "summary": "Controlar costo y autonomia con presupuestos duros y observabilidad de consumo.",
    "scope": [
      "Definir budgets por proyecto, sprint, provider y modelo.",
      "Bloquear o escalar cuando se excedan umbrales.",
      "Persistir costo estimado y real por corrida y etapa.",
      "Exponer estado del budget en API y UI."
    ],
    "acceptance": [
      "Cada proyecto tiene limites configurables de uso.",
      "El sistema deja evidencia cuando corta o degrada autonomia por presupuesto.",
      "Los costos por etapa quedan visibles en reportes.",
      "No hay loops agentic infinitos por falta de control de budget."
    ]
  },
  {
    "code": "AG-703",
    "phase": "Fase 7 - Hardening & Benchmark",
    "priority": "medium",
    "title": "Modo simulation y dry-run para intake, planning y delivery",
    "depends_on": [],
    "summary": "Poder evaluar el sistema sin tocar repos ni ejecutar cambios irreversibles.",
    "scope": [
      "Agregar dry-run para intake, planning y delivery.",
      "Emitir artefactos y decisiones simuladas sin efectos laterales.",
      "Diferenciar claramente modo simulation de ejecucion real.",
      "Persistir evidencia del modo usado."
    ],
    "acceptance": [
      "Se puede correr intake, planning y delivery en simulation.",
      "Los reportes indican claramente que no hubo efectos reales.",
      "Los modos no se mezclan accidentalmente.",
      "El operador puede validar flujos antes de abrir autonomia completa."
    ]
  },
  {
    "code": "AG-704",
    "phase": "Fase 7 - Hardening & Benchmark",
    "priority": "medium",
    "title": "Benchmark automatizado del proyecto formal de ejemplo",
    "depends_on": ["AG-703"],
    "summary": "Medir de punta a punta el caso formal usando docs/example_input_project.",
    "scope": [
      "Automatizar benchmark sobre requirements.md y roadmap.md formales.",
      "Capturar resultados, tiempos y artefactos.",
      "Integrar el benchmark a scripts reproducibles del repo.",
      "Usarlo como criterio de regresion."
    ],
    "acceptance": [
      "El benchmark formal corre sin intervencion manual.",
      "Produce un reporte repetible.",
      "Sirve para detectar regresiones del flujo base.",
      "Se documenta como criterio de salida del MVP."
    ]
  },
  {
    "code": "AG-705",
    "phase": "Fase 7 - Hardening & Benchmark",
    "priority": "medium",
    "title": "KPIs de lead time, retry rate, completion y defectos",
    "depends_on": [],
    "summary": "Medir autonomia, throughput y calidad con indicadores objetivos del sistema.",
    "scope": [
      "Calcular lead time por ticket y por sprint.",
      "Medir retry rate y porcentaje de tickets completados.",
      "Medir defectos encontrados en review y QA.",
      "Exponer KPIs por API y reportes."
    ],
    "acceptance": [
      "Existen KPIs objetivos del flujo agentic.",
      "Los datos salen de Postgres sin calculos manuales.",
      "El operador puede comparar corridas y sprints.",
      "Los KPIs ayudan a decidir hardening y rollout."
    ]
  },
  {
    "code": "AG-706",
    "phase": "Fase 7 - Hardening & Benchmark",
    "priority": "medium",
    "title": "Cerrar rollout legacy restante y documentar runbooks",
    "depends_on": [],
    "summary": "Retirar adapters o caminos legacy que sigan vivos y documentar la operacion real del sistema.",
    "scope": [
      "Identificar runtime legacy restante en el camino principal.",
      "Retirarlo o dejarlo aislado fuera del flujo base.",
      "Escribir runbooks operativos y de troubleshooting.",
      "Alinear README y docs a la arquitectura actual."
    ],
    "acceptance": [
      "El camino principal no depende de runtime legacy.",
      "Existen runbooks claros para operar el MVP.",
      "La documentacion refleja el estado real del sistema.",
      "El rollout se puede explicar sin contradicciones."
    ]
  },
  {
    "code": "AG-707",
    "phase": "Fase 7 - Hardening & Benchmark",
    "priority": "medium",
    "title": "Benchmark automatizado de intake semiestructurado",
    "depends_on": ["AG-109", "AG-110", "AG-118"],
    "summary": "Medir el intake sobre docs/example_project_2 para saber cuanto del paquete formal se genera sin intervencion humana.",
    "scope": [
      "Correr benchmark sobre example_project_2.",
      "Medir requisitos, roadmap y certified_input derivados.",
      "Comparar resultado contra expectativas del contrato interno.",
      "Persistir salida y metricas."
    ],
    "acceptance": [
      "El benchmark semiestructurado es reproducible.",
      "El reporte muestra calidad y gaps del close-the-gap.",
      "Se detectan regresiones en dossier-to-certified-input.",
      "El benchmark informa readiness antes de planning."
    ]
  },
  {
    "code": "AG-708",
    "phase": "Fase 7 - Hardening & Benchmark",
    "priority": "medium",
    "title": "Benchmark use-case-only con confidence score y preguntas abiertas",
    "depends_on": ["AG-110", "AG-112"],
    "summary": "Validar el comportamiento del intake cuando solo hay un brief minimo y el arquitecto debe cerrar gaps con prudencia.",
    "scope": [
      "Definir un caso de brief minimo.",
      "Medir confidence_score, assumptions y open questions.",
      "Validar criterio de escalamiento humano.",
      "Documentar calidad del close-the-gap."
    ],
    "acceptance": [
      "Existe un benchmark de input abierto reproducible.",
      "El sistema no inventa silenciosamente en inputs pobres.",
      "Las preguntas abiertas son utiles y trazables.",
      "El benchmark muestra si el sistema debe escalar a operador."
    ]
  },
  {
    "code": "AG-709",
    "phase": "Fase 7 - Hardening & Benchmark",
    "priority": "medium",
    "title": "KPIs del intake flexible",
    "depends_on": ["AG-707", "AG-708"],
    "summary": "Medir trazabilidad, supuestos no resueltos y precision del backlog derivado en inputs flexibles.",
    "scope": [
      "Medir porcentaje de requerimientos trazables.",
      "Medir supuestos no resueltos tras close-the-gap.",
      "Medir retrabajo posterior al planning.",
      "Medir precision del backlog derivado."
    ],
    "acceptance": [
      "Hay metricas objetivas del intake flexible.",
      "Los KPIs distinguen entre input formal, dossier y brief.",
      "El sistema puede detectar si la formalizacion fue pobre.",
      "Las metricas sirven para priorizar mejoras del arquitecto."
    ]
  },
  {
    "code": "AG-710",
    "phase": "Fase 7 - Hardening & Benchmark",
    "priority": "high",
    "title": "Benchmark chat-to-spec con casos reales",
    "depends_on": ["AG-114", "AG-115", "AG-116", "AG-606"],
    "summary": "Validar el flujo conversacional usando escenarios reales, incluyendo el caso de RRHH + contratos Ethereum + attendance desktop + payroll por hora.",
    "scope": [
      "Definir escenarios representativos de chat-to-spec.",
      "Ejecutar el flujo desde conversacion hasta artifacts aprobables.",
      "Medir calidad del output formal y del certified_input.",
      "Usar el caso RH + Ethereum + desktop attendance + payroll como benchmark oficial."
    ],
    "acceptance": [
      "Existe benchmark reproducible de chat-to-spec.",
      "El caso RH + Ethereum produce documentos formales razonables.",
      "El benchmark deja evidencia de preguntas, confianza y artifacts resultantes.",
      "Se puede evaluar readiness del intake conversacional con un caso de negocio real."
    ]
  },
  {
    "code": "AG-711",
    "phase": "Fase 7 - Hardening & Benchmark",
    "priority": "high",
    "title": "Validar cierre canonico de example_project_2 a input certificado",
    "depends_on": ["AG-118", "AG-707"],
    "summary": "Asegurar que docs/example_project_2 cierre al mismo input certificado esperado por contratos internos, sin adapters manuales.",
    "scope": [
      "Definir expected contract para example_project_2.",
      "Comparar output actual contra el contrato esperado.",
      "Detectar bypasses, adapters manuales o campos faltantes.",
      "Automatizar la validacion como parte del benchmark."
    ],
    "acceptance": [
      "example_project_2 produce el input certificado canonico esperado.",
      "La validacion es automatizada y repetible.",
      "No hay adapters manuales ocultos en el flujo.",
      "El resultado sirve como criterio de salida del intake semiestructurado."
    ]
  }
]
EOF
)

show_help() {
    echo "Uso: $0 [opciones]"
    echo ""
    echo "Opciones:"
    echo "  --url URL                URL de Plane (default: $DEFAULT_PLANE_URL)"
    echo "  --token TOKEN            API token de Plane"
    echo "  --workspace SLUG         Workspace slug"
    echo "  --project UUID           Project UUID"
    echo "  --only AG-109,AG-110     Migrar solo tickets especificos"
    echo "  --dry-run                Mostrar payloads sin crear issues"
    echo "  --force                  Crear aun si ya existe un issue con el mismo AG-*"
    echo "  --list                   Listar catalogo de tickets remanentes y salir"
    echo "  -h, --help               Mostrar ayuda"
}

PLANE_URL="${PLANE_URL:-$DEFAULT_PLANE_URL}"
PLANE_TOKEN="${PLANE_TOKEN:-}"
PLANE_WORKSPACE="${PLANE_WORKSPACE:-}"
PLANE_PROJECT="${PLANE_PROJECT:-}"
ONLY_CODES=""
DRY_RUN=false
FORCE=false
LIST_ONLY=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --url)
            PLANE_URL="$2"
            shift 2
            ;;
        --token)
            PLANE_TOKEN="$2"
            shift 2
            ;;
        --workspace)
            PLANE_WORKSPACE="$2"
            shift 2
            ;;
        --project)
            PLANE_PROJECT="$2"
            shift 2
            ;;
        --only)
            ONLY_CODES="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --list)
            LIST_ONLY=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}Error: opcion desconocida: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

if ! command -v jq >/dev/null 2>&1; then
    echo -e "${RED}Error: jq no esta instalado${NC}"
    exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
    echo -e "${RED}Error: curl no esta instalado${NC}"
    exit 1
fi

list_catalog() {
    echo -e "${BLUE}Catalogo de tickets remanentes de Mission Control${NC}"
    echo "$TICKETS_JSON" | jq -r '.[] | "\(.code)\t\(.phase)\t\(.priority)\t\(.title)"'
}

if [ "$LIST_ONLY" = true ]; then
    list_catalog
    exit 0
fi

if [ -z "$PLANE_TOKEN" ] || [ -z "$PLANE_WORKSPACE" ] || [ -z "$PLANE_PROJECT" ]; then
    echo -e "${RED}Error: faltan PLANE_TOKEN, PLANE_WORKSPACE o PLANE_PROJECT${NC}"
    echo "Carga .plane-config o pasa --token/--workspace/--project."
    exit 1
fi

PLANE_URL="${PLANE_URL%/}"
API_BASE="$PLANE_URL/api/v1/workspaces/$PLANE_WORKSPACE/projects/$PLANE_PROJECT"

plane_get() {
    local url="$1"
    curl -sS -H "X-Api-Key: $PLANE_TOKEN" "$url"
}

validate_plane() {
    local me
    me=$(plane_get "$PLANE_URL/api/v1/users/me/")
    if ! echo "$me" | jq -e '.id' >/dev/null 2>&1; then
        echo -e "${RED}Error: no se pudo validar el token o la URL de Plane${NC}"
        echo "$me" | head -c 200
        echo
        exit 1
    fi

    local project
    project=$(plane_get "$API_BASE/")
    if ! echo "$project" | jq -e '.id' >/dev/null 2>&1; then
        echo -e "${RED}Error: no se pudo leer el proyecto de Plane${NC}"
        echo "$project" | head -c 200
        echo
        exit 1
    fi

    echo -e "${GREEN}Plane autenticado${NC}: $(echo "$me" | jq -r '.display_name // .email')"
    echo -e "${GREEN}Proyecto${NC}: $(echo "$project" | jq -r '.name') ($(echo "$project" | jq -r '.identifier'))"
}

validate_plane

DEFAULT_STATE_ID=$(plane_get "$API_BASE/states/" | jq -r '.results[] | select(.default == true) | .id' | head -n1)

EXISTING_ISSUES_JSON=$(plane_get "$API_BASE/issues/?page=1&page_size=$DEFAULT_PAGE_SIZE")

issue_id_for_code() {
    local code="$1"
    echo "$EXISTING_ISSUES_JSON" | jq -r --arg code "$code" '
        (.results // [])
        | map(select(.name | startswith("[" + $code + "] ")))
        | .[0].id // empty
    '
}

build_description() {
    local ticket_json="$1"
    echo "$ticket_json" | jq -r '
        def html_list(items):
          if (items | length) == 0
          then "<p>Sin dependencias explicitas.</p>"
          else "<ul>" + (items | map("<li>" + . + "</li>") | join("")) + "</ul>"
          end;
        "<h2>" + .code + " · " + .title + "</h2>" +
        "<p><strong>Phase:</strong> " + .phase + "</p>" +
        "<p><strong>Source:</strong> docs/ROADMAP_AGENTIC.md</p>" +
        "<p>" + .summary + "</p>" +
        "<h3>Dependencies</h3>" + html_list(.depends_on) +
        "<h3>Scope</h3>" + html_list(.scope) +
        "<h3>Acceptance Criteria</h3>" + html_list(.acceptance)
    '
}

create_issue() {
    local ticket_json="$1"
    local code title priority description existing_id payload response http_code body created_id
    code=$(echo "$ticket_json" | jq -r '.code')
    title=$(echo "$ticket_json" | jq -r '.title')
    priority=$(echo "$ticket_json" | jq -r '.priority')
    description=$(build_description "$ticket_json")
    existing_id=$(issue_id_for_code "$code")

    if [ -n "$ONLY_CODES" ]; then
        case ",$ONLY_CODES," in
            *",$code,"*) ;;
            *) return 0 ;;
        esac
    fi

    if [ -n "$existing_id" ] && [ "$FORCE" = false ]; then
        echo -e "${YELLOW}Skip${NC} [$code] ya existe en Plane (${existing_id:0:8}...)"
        return 0
    fi

    payload=$(jq -n \
        --arg name "[$code] $title" \
        --arg desc "$description" \
        --arg prio "$priority" \
        --arg state "$DEFAULT_STATE_ID" \
        '{
            name: $name,
            description_html: $desc,
            priority: $prio,
            state: $state
        }')

    if [ "$DRY_RUN" = true ]; then
        echo -e "${BLUE}DRY-RUN${NC} [$code] $title"
        echo "$payload" | jq .
        return 0
    fi

    response=$(curl -sS -w "\n%{http_code}" -X POST \
        "$API_BASE/issues/" \
        -H "X-Api-Key: $PLANE_TOKEN" \
        -H "Content-Type: application/json" \
        -d "$payload")

    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    if [ "$http_code" = "200" ] || [ "$http_code" = "201" ]; then
        created_id=$(echo "$body" | jq -r '.id')
        echo -e "${GREEN}Creado${NC} [$code] ${created_id:0:8}... $title"
        return 0
    fi

    echo -e "${RED}Error creando [$code]${NC} HTTP $http_code"
    echo "$body" | jq . 2>/dev/null || echo "$body"
    return 1
}

echo
echo -e "${BLUE}Migrando tickets remanentes de Mission Control a Plane${NC}"
echo

FAILURES=0
while IFS= read -r ticket_json; do
    if ! create_issue "$ticket_json"; then
        FAILURES=$((FAILURES + 1))
    fi
done < <(echo "$TICKETS_JSON" | jq -c '.[]')

echo
if [ "$FAILURES" -gt 0 ]; then
    echo -e "${RED}Migracion terminada con $FAILURES fallos${NC}"
    exit 1
fi

if [ "$DRY_RUN" = true ]; then
    echo -e "${GREEN}Dry-run completado sin errores${NC}"
else
    echo -e "${GREEN}Migracion completada${NC}"
    echo "$PLANE_URL/$PLANE_WORKSPACE/projects/$PLANE_PROJECT/issues/"
fi
