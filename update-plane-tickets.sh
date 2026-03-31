#!/bin/bash

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

show_help() {
    echo "Uso: $0 <action> <ticket-ref> [mensaje]"
    echo ""
    echo "Acciones:"
    echo "  list                          Listar issues del proyecto"
    echo "  show <ref>                    Mostrar issue"
    echo "  comment <ref> <text>          Agregar comentario"
    echo "  status <ref> <state>          Cambiar estado"
    echo "  start <ref> [detalle]         Marcar In Progress"
    echo "  complete <ref> [detalle]      Marcar Done"
    echo "  block <ref> [razon]           Marcar Blocked"
    echo "  update <ref> <description>    Actualizar descripcion"
    echo ""
    echo "Ticket ref puede ser:"
    echo "  - UUID de Plane"
    echo "  - clave del roadmap, ej: AG-110"
    echo "  - sequence id, ej: MISSIONCON-12"
    echo ""
    echo "Variables requeridas: PLANE_URL, PLANE_TOKEN, PLANE_WORKSPACE, PLANE_PROJECT"
}

ACTION="${1:-}"
if [ -z "$ACTION" ] || [ "$ACTION" = "-h" ] || [ "$ACTION" = "--help" ]; then
    show_help
    exit 0
fi

shift || true
TICKET_REF="${1:-}"
if [ -n "$TICKET_REF" ]; then
    shift || true
fi
MESSAGE="$*"

PLANE_URL="${PLANE_URL:-http://localhost}"
PLANE_URL="${PLANE_URL%/}"
PLANE_TOKEN="${PLANE_TOKEN:-}"
PLANE_WORKSPACE="${PLANE_WORKSPACE:-}"
PLANE_PROJECT="${PLANE_PROJECT:-}"
API_BASE="$PLANE_URL/api/v1/workspaces/$PLANE_WORKSPACE/projects/$PLANE_PROJECT"

if [ -z "$PLANE_TOKEN" ] || [ -z "$PLANE_WORKSPACE" ] || [ -z "$PLANE_PROJECT" ]; then
    echo -e "${RED}Error: faltan variables PLANE_*${NC}"
    echo "Carga .plane-config o exporta PLANE_URL/PLANE_TOKEN/PLANE_WORKSPACE/PLANE_PROJECT."
    exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
    echo -e "${RED}Error: jq no esta instalado${NC}"
    exit 1
fi

api_request() {
    local method="$1"
    local endpoint="$2"
    local data="${3:-}"

    if [ -z "$data" ]; then
        curl -sS -X "$method" \
            -H "X-Api-Key: $PLANE_TOKEN" \
            -H "Content-Type: application/json" \
            "$API_BASE/$endpoint"
    else
        curl -sS -X "$method" \
            -H "X-Api-Key: $PLANE_TOKEN" \
            -H "Content-Type: application/json" \
            -d "$data" \
            "$API_BASE/$endpoint"
    fi
}

PROJECT_INFO=$(curl -sS -H "X-Api-Key: $PLANE_TOKEN" "$API_BASE/")
PROJECT_IDENTIFIER=$(echo "$PROJECT_INFO" | jq -r '.identifier // "ISSUE"')
STATES_JSON=$(curl -sS -H "X-Api-Key: $PLANE_TOKEN" "$API_BASE/states/")

fetch_all_issues() {
    api_request "GET" "issues/?page=1&page_size=200"
}

resolve_issue_id() {
    local ref="$1"
    local issues resolved=""

    if [[ "$ref" =~ ^[0-9a-fA-F-]{36}$ ]]; then
        echo "$ref"
        return 0
    fi

    issues=$(fetch_all_issues)

    if [[ "$ref" =~ ^AG-[0-9]{3}$ ]]; then
        resolved=$(echo "$issues" | jq -r --arg ref "$ref" '
            (.results // [])
            | map(select(.name | startswith("[" + $ref + "] ")))
            | .[0].id // empty
        ')
    elif [[ "$ref" =~ ^[A-Z]+-[0-9]+$ ]]; then
        resolved=$(echo "$issues" | jq -r --arg ref "$ref" '
            (.results // [])
            | map(select((.project_detail.identifier + "-" + (.sequence_id|tostring)) == $ref))
            | .[0].id // empty
        ')
    else
        resolved=$(echo "$issues" | jq -r --arg ref "$ref" '
            (.results // [])
            | map(select(.name == $ref))
            | .[0].id // empty
        ')
    fi

    if [ -z "$resolved" ]; then
        echo -e "${RED}Error: no se encontro issue para '$ref'${NC}" >&2
        exit 1
    fi

    echo "$resolved"
}

get_states() {
    echo "$STATES_JSON" | jq -r '.results[] | "\(.id)|\(.name)|\(.group)"'
}

find_state_id() {
    local state_name="$1"
    get_states | grep -i "|$state_name|" | cut -d'|' -f1 | head -n1
}

state_name_from_id() {
    local state_id="$1"
    echo "$STATES_JSON" | jq -r --arg state_id "$state_id" '
        (.results // [])
        | map(select(.id == $state_id))
        | .[0].name // "N/A"
    '
}

if [ "$ACTION" = "list" ]; then
    echo -e "${BLUE}Issues de Plane para Mission Control${NC}"
    while IFS= read -r issue; do
        sequence_id=$(echo "$issue" | jq -r '.sequence_id')
        state_id=$(echo "$issue" | jq -r '.state // empty')
        if [ -n "$state_id" ]; then
            state_name=$(state_name_from_id "$state_id")
        else
            state_name="N/A"
        fi
        priority=$(echo "$issue" | jq -r '.priority // "none"')
        name=$(echo "$issue" | jq -r '.name')
        echo -e "${PROJECT_IDENTIFIER}-${sequence_id}\t${state_name}\t${priority}\t${name}"
    done < <(fetch_all_issues | jq -c '(.results // []) | sort_by(.sequence_id) | .[]')
    exit 0
fi

if [ -z "$TICKET_REF" ]; then
    echo -e "${RED}Error: se requiere un ticket-ref${NC}"
    show_help
    exit 1
fi

ISSUE_ID=$(resolve_issue_id "$TICKET_REF")

case "$ACTION" in
    show)
        info=$(api_request "GET" "issues/$ISSUE_ID/")
        if ! echo "$info" | jq -e '.id' >/dev/null 2>&1; then
            echo -e "${RED}Error: no se pudo leer el issue${NC}"
            echo "$info"
            exit 1
        fi
        state_id=$(echo "$info" | jq -r '.state // empty')
        if [ -n "$state_id" ]; then
            state_name=$(state_name_from_id "$state_id")
        else
            state_name="N/A"
        fi
        echo -e "${BLUE}Issue${NC}"
        echo -e "${CYAN}ID:${NC}           $(echo "$info" | jq -r '.id')"
        echo -e "${CYAN}Clave:${NC}        ${PROJECT_IDENTIFIER}-$(echo "$info" | jq -r '.sequence_id')"
        echo -e "${CYAN}Nombre:${NC}       $(echo "$info" | jq -r '.name')"
        echo -e "${CYAN}Estado:${NC}       ${state_name}"
        echo -e "${CYAN}Prioridad:${NC}    $(echo "$info" | jq -r '.priority // "none"')"
        echo -e "${CYAN}URL:${NC}          $PLANE_URL/$PLANE_WORKSPACE/projects/$PLANE_PROJECT/issues/$ISSUE_ID"
        ;;
    comment)
        if [ -z "$MESSAGE" ]; then
            echo -e "${RED}Error: se requiere texto para el comentario${NC}"
            exit 1
        fi
        payload=$(jq -n --arg comment "$MESSAGE" '{comment_html: $comment, comment: $comment}')
        response=$(api_request "POST" "issues/$ISSUE_ID/comments/" "$payload")
        if echo "$response" | jq -e '.id' >/dev/null 2>&1; then
            echo -e "${GREEN}Comentario agregado${NC}"
        else
            echo -e "${RED}Error al agregar comentario${NC}"
            echo "$response" | jq .
            exit 1
        fi
        ;;
    status)
        if [ -z "$MESSAGE" ]; then
            echo -e "${RED}Error: se requiere nombre de estado${NC}"
            exit 1
        fi
        state_id=$(find_state_id "$MESSAGE")
        if [ -z "$state_id" ]; then
            echo -e "${RED}Error: estado no encontrado: $MESSAGE${NC}"
            get_states | while IFS='|' read -r _id name group; do
                echo "  - $name ($group)"
            done
            exit 1
        fi
        payload=$(jq -n --arg state "$state_id" '{state: $state}')
        response=$(api_request "PATCH" "issues/$ISSUE_ID/" "$payload")
        if echo "$response" | jq -e '.id' >/dev/null 2>&1; then
            echo -e "${GREEN}Estado actualizado a $MESSAGE${NC}"
        else
            echo -e "${RED}Error actualizando estado${NC}"
            echo "$response" | jq .
            exit 1
        fi
        ;;
    start)
        state_id=$(find_state_id "In Progress")
        if [ -z "$state_id" ]; then
            echo -e "${RED}Error: no existe el estado In Progress${NC}"
            exit 1
        fi
        payload=$(jq -n --arg state "$state_id" '{state: $state}')
        response=$(api_request "PATCH" "issues/$ISSUE_ID/" "$payload")
        if ! echo "$response" | jq -e '.id' >/dev/null 2>&1; then
            echo -e "${RED}Error iniciando issue${NC}"
            exit 1
        fi
        comment_msg="🔄 Trabajo iniciado en Mission Control"
        if [ -n "$MESSAGE" ]; then
            comment_msg="$comment_msg: $MESSAGE"
        fi
        comment_payload=$(jq -n --arg comment "$comment_msg" '{comment_html: $comment, comment: $comment}')
        api_request "POST" "issues/$ISSUE_ID/comments/" "$comment_payload" >/dev/null
        echo -e "${GREEN}Issue marcado como In Progress${NC}"
        ;;
    complete)
        state_id=$(find_state_id "Done")
        if [ -z "$state_id" ]; then
            echo -e "${RED}Error: no existe el estado Done${NC}"
            exit 1
        fi
        payload=$(jq -n --arg state "$state_id" '{state: $state}')
        response=$(api_request "PATCH" "issues/$ISSUE_ID/" "$payload")
        if ! echo "$response" | jq -e '.id' >/dev/null 2>&1; then
            echo -e "${RED}Error completando issue${NC}"
            exit 1
        fi
        comment_msg="✅ Ticket completado en Mission Control"
        if [ -n "$MESSAGE" ]; then
            comment_msg="$comment_msg. $MESSAGE"
        fi
        comment_payload=$(jq -n --arg comment "$comment_msg" '{comment_html: $comment, comment: $comment}')
        api_request "POST" "issues/$ISSUE_ID/comments/" "$comment_payload" >/dev/null
        echo -e "${GREEN}Issue marcado como Done${NC}"
        ;;
    block)
        state_id=$(find_state_id "Blocked")
        if [ -z "$state_id" ]; then
            echo -e "${RED}Error: no existe el estado Blocked${NC}"
            exit 1
        fi
        payload=$(jq -n --arg state "$state_id" '{state: $state}')
        response=$(api_request "PATCH" "issues/$ISSUE_ID/" "$payload")
        if ! echo "$response" | jq -e '.id' >/dev/null 2>&1; then
            echo -e "${RED}Error bloqueando issue${NC}"
            exit 1
        fi
        comment_msg="🚫 Ticket bloqueado"
        if [ -n "$MESSAGE" ]; then
            comment_msg="$comment_msg. Razon: $MESSAGE"
        fi
        comment_payload=$(jq -n --arg comment "$comment_msg" '{comment_html: $comment, comment: $comment}')
        api_request "POST" "issues/$ISSUE_ID/comments/" "$comment_payload" >/dev/null
        echo -e "${GREEN}Issue marcado como Blocked${NC}"
        ;;
    update)
        if [ -z "$MESSAGE" ]; then
            echo -e "${RED}Error: se requiere descripcion nueva${NC}"
            exit 1
        fi
        payload=$(jq -n --arg desc "$MESSAGE" '{description_html: $desc}')
        response=$(api_request "PATCH" "issues/$ISSUE_ID/" "$payload")
        if echo "$response" | jq -e '.id' >/dev/null 2>&1; then
            echo -e "${GREEN}Descripcion actualizada${NC}"
        else
            echo -e "${RED}Error actualizando descripcion${NC}"
            echo "$response" | jq .
            exit 1
        fi
        ;;
    *)
        echo -e "${RED}Error: accion desconocida: $ACTION${NC}"
        show_help
        exit 1
        ;;
esac

echo
echo -e "${BLUE}Ver issue:${NC}"
echo "$PLANE_URL/$PLANE_WORKSPACE/projects/$PLANE_PROJECT/issues/$ISSUE_ID"
