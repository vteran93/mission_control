Sí. Te lo monto **sin frameworks**, a lo bestia pero útil.

La idea es esta:

* le pasas un requerimiento de alto nivel,
* Claude primero **planifica**,
* luego **implementa una tarea por iteración**,
* después **se auto-revisa**,
* luego **decide si sigue o corrige**,
* y todo eso usando la **misma conversación** con `--continue --print`, que es justo el patrón recomendado para scripts no interactivos. Claude Code soporta prompts de sistema por archivo y reanudar conversaciones en modo no interactivo; además, para integraciones conviene usar `--output-format text|json|stream-json` según necesites. ([Claude API Docs][1])

También te conviene **añadir** instrucciones al prompt por archivo en vez de reemplazar todo el prompt del sistema, porque Anthropic recomienda usar `--append-system-prompt-file` para conservar las capacidades nativas de Claude Code. ([Claude API Docs][1])

## Qué te recomiendo de verdad

No intentes hacer “autonomía total” desde el día 1.
Haz esto primero:

1. `plan`
2. `implement`
3. `review`
4. `fix if needed`
5. `repeat`

Con eso ya tienes un pseudo-sistema multiagente sin meter CrewAI, LangChain ni la secta del YAML ornamental.

---

# Estructura

```text
agent-workflow/
├── run.sh
├── prompts/
│   ├── global_system.md
│   ├── kickoff.txt
│   ├── implement.txt
│   ├── review.txt
│   ├── decide.txt
│   └── finalize.txt
└── .agent-workflow/
```

---

# 1) Prompt global del sistema

`prompts/global_system.md`

```md
Eres un sistema de ejecución por roles dentro de Claude Code.

Reglas globales:
- Trabaja de forma iterativa.
- No intentes resolver todo de una sola vez si la tarea es grande.
- Primero planifica, luego implementa por pasos.
- Después de cada implementación, revisa críticamente el resultado.
- Prefiere cambios pequeños, verificables y reversibles.
- No inventes requisitos faltantes; declara supuestos explícitos.
- Mantén compatibilidad con el código existente salvo que se indique lo contrario.
- Si existen tests o linters, úsalos para validar cuando sea razonable.
- Minimiza creación innecesaria de archivos.
- Devuelve salidas estructuradas y fáciles de parsear.

Formato general:
- Usa encabezados claros.
- Cuando se te pida JSON, devuelve JSON válido y nada más.
- Cuando se te pida una decisión, responde con una sola palabra de control si se indica.
```

Esto encaja con las recomendaciones de Anthropic: instrucciones claras, directas, estructuradas y con formato de salida explícito. ([Claude API Docs][2])

---

# 2) Prompt de arranque

`prompts/kickoff.txt`

```txt
Quiero que trabajes sobre este requerimiento de alto nivel:

<requirement>
__REQUIREMENT__
</requirement>

Tu proceso obligatorio es:

1. Analiza el requerimiento.
2. Crea un plan por fases.
3. Divide el trabajo en tareas pequeñas y verificables.
4. Identifica riesgos, supuestos y validaciones.
5. Empieza implementando SOLO la primera tarea útil.
6. Al terminar, resume:
   - qué hiciste,
   - qué falta,
   - qué validarías ahora.

Devuelve exactamente este formato:

## PLAN
- ...

## TAREA_ACTUAL
- ...

## IMPLEMENTACIÓN
- ...

## VALIDACIÓN
- ...

## SIGUIENTE_PASO
- ...
```

---

# 3) Prompt de implementación iterativa

`prompts/implement.txt`

```txt
Continúa desde el estado actual de la conversación.

Tu trabajo ahora es:
1. identificar la siguiente tarea pendiente más pequeña y valiosa,
2. implementarla,
3. validar razonablemente el cambio,
4. resumir qué cambió y qué queda pendiente.

Reglas:
- No replanifiques todo desde cero.
- No hagas refactors cosméticos.
- No abras frentes nuevos sin necesidad.
- Si algo está ambiguo, escoge la opción más conservadora y dilo.
- Si la tarea ya está terminada, pasa a la siguiente.
- Si todo ya quedó completo, dilo claramente.

Devuelve exactamente:

## TAREA_EJECUTADA
- ...

## CAMBIOS
- ...

## VALIDACIÓN
- ...

## RIESGOS
- ...

## ESTADO
- IN_PROGRESS | BLOCKED | DONE
```

---

# 4) Prompt de revisión adversarial

`prompts/review.txt`

```txt
Actúa como revisor crítico de lo ya hecho en esta conversación.

Tu trabajo:
- buscar errores funcionales,
- edge cases,
- deuda técnica innecesaria,
- omisiones contra el requerimiento original,
- validaciones faltantes.

Sé duro, concreto y útil.
No reescribas todo.
Señala solo lo importante.

Devuelve exactamente:

## HALLAZGOS_CRÍTICOS
- ...

## HALLAZGOS_MEDIOS
- ...

## PRUEBAS_FALTANTES
- ...

## VEREDICTO
REVISE | APPROVE
```

---

# 5) Prompt para decidir siguiente acción

`prompts/decide.txt`

```txt
Con base en todo el contexto de la conversación y la última revisión, decide cuál es la siguiente acción correcta.

Responde con UNA sola palabra exacta:

CONTINUE
FIX
FINALIZE
BLOCKED
```

---

# 6) Prompt de cierre

`prompts/finalize.txt`

```txt
Cierra el trabajo actual.

Devuelve exactamente:

## RESUMEN_FINAL
- ...

## ARCHIVOS_RELEVANTES
- ...

## VALIDACIÓN_REALIZADA
- ...

## PENDIENTES
- ...

## RIESGOS_REMANENTES
- ...
```

---

# 7) Script Bash

`run.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

# Uso:
# ./run.sh "crear un microservicio FastAPI con auth JWT, tests y docker"
#
# Requisitos:
# - claude instalado y autenticado
# - estar dentro del repo/proyecto objetivo
#
# Opcionales:
#   MAX_ITERS=8 ./run.sh "..."
#   CLAUDE_MODEL=sonnet ./run.sh "..."
#   AUTO_WORKTREE=1 ./run.sh "..."

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROMPTS_DIR="$ROOT_DIR/prompts"
STATE_DIR="$ROOT_DIR/.agent-workflow"
mkdir -p "$STATE_DIR"

REQUIREMENT="${1:-}"
if [[ -z "$REQUIREMENT" ]]; then
  echo "Uso: $0 \"requerimiento de alto nivel\""
  exit 1
fi

MAX_ITERS="${MAX_ITERS:-8}"
CLAUDE_MODEL="${CLAUDE_MODEL:-}"
AUTO_WORKTREE="${AUTO_WORKTREE:-0}"

timestamp="$(date +%Y%m%d-%H%M%S)"
RUN_DIR="$STATE_DIR/$timestamp"
mkdir -p "$RUN_DIR"

log() {
  printf "\n[%s] %s\n" "$(date +%H:%M:%S)" "$*"
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Falta dependencia: $1" >&2
    exit 1
  }
}

need_cmd claude
need_cmd sed
need_cmd awk
need_cmd grep
need_cmd tr

COMMON_ARGS=(
  --append-system-prompt-file "$PROMPTS_DIR/global_system.md"
  --output-format text
  --verbose
)

if [[ -n "$CLAUDE_MODEL" ]]; then
  COMMON_ARGS+=(--model "$CLAUDE_MODEL")
fi

if [[ "$AUTO_WORKTREE" == "1" ]]; then
  # Aíslalo en worktree si quieres evitar destrozos creativos.
  COMMON_ARGS+=(--worktree "auto-$timestamp")
fi

render_prompt() {
  local template_file="$1"
  local out_file="$2"
  sed "s|__REQUIREMENT__|$(printf '%s' "$REQUIREMENT" | sed 's/[&/\]/\\&/g')|g" \
    "$template_file" > "$out_file"
}

extract_verdict() {
  local file="$1"
  grep -E '^(REVISE|APPROVE)$' "$file" | tail -n1 || true
}

extract_decision() {
  local file="$1"
  grep -E '^(CONTINUE|FIX|FINALIZE|BLOCKED)$' "$file" | tail -n1 || true
}

run_first_turn() {
  local prompt_file="$RUN_DIR/00-kickoff.txt"
  local output_file="$RUN_DIR/00-kickoff.out"

  render_prompt "$PROMPTS_DIR/kickoff.txt" "$prompt_file"

  log "Iniciando sesión y ejecutando kickoff"
  claude -p "$(cat "$prompt_file")" "${COMMON_ARGS[@]}" | tee "$output_file"
}

run_continue_turn() {
  local name="$1"
  local prompt_path="$2"
  local output_file="$RUN_DIR/$name.out"

  log "Ejecutando paso: $name"
  claude --continue --print "$(cat "$prompt_path")" "${COMMON_ARGS[@]}" | tee "$output_file"
}

main() {
  cat <<EOF
========================================
Workflow autónomo con Claude CLI
Run dir: $RUN_DIR
Max iterations: $MAX_ITERS
========================================
EOF

  run_first_turn

  local i
  for (( i=1; i<=MAX_ITERS; i++ )); do
    printf -v iter "%02d" "$i"

    # Implementar siguiente tarea
    run_continue_turn "${iter}-implement" "$PROMPTS_DIR/implement.txt"

    # Revisar
    run_continue_turn "${iter}-review" "$PROMPTS_DIR/review.txt"

    verdict="$(extract_verdict "$RUN_DIR/${iter}-review.out")"
    verdict="${verdict:-REVISE}"

    log "Veredicto revisión: $verdict"

    if [[ "$verdict" == "REVISE" ]]; then
      cat > "$RUN_DIR/${iter}-fix.txt" <<'EOF'
Corrige los hallazgos de la última revisión.
Haz cambios mínimos y dirigidos.
Luego resume exactamente en este formato:

## CORRECCIONES
- ...

## VALIDACIÓN
- ...

## ESTADO
- IN_PROGRESS | DONE
EOF
      run_continue_turn "${iter}-fix" "$RUN_DIR/${iter}-fix.txt"
    fi

    # Decidir siguiente acción
    run_continue_turn "${iter}-decide" "$PROMPTS_DIR/decide.txt"
    decision="$(extract_decision "$RUN_DIR/${iter}-decide.out")"
    decision="${decision:-CONTINUE}"

    log "Decisión: $decision"

    case "$decision" in
      FINALIZE)
        run_continue_turn "${iter}-finalize" "$PROMPTS_DIR/finalize.txt"
        log "Trabajo finalizado"
        exit 0
        ;;
      BLOCKED)
        log "Claude reportó bloqueo. Revisa: $RUN_DIR/${iter}-decide.out"
        exit 2
        ;;
      FIX)
        cat > "$RUN_DIR/${iter}-force-fix.txt" <<'EOF'
Aún no cierres.
Realiza la corrección más importante pendiente y valida el resultado.
Devuelve:

## CORRECCIÓN
- ...

## VALIDACIÓN
- ...

## ESTADO
- IN_PROGRESS | DONE
EOF
        run_continue_turn "${iter}-force-fix" "$RUN_DIR/${iter}-force-fix.txt"
        ;;
      CONTINUE)
        ;;
      *)
        log "Decisión desconocida: $decision"
        exit 3
        ;;
    esac
  done

  log "Se alcanzó MAX_ITERS=$MAX_ITERS"
  log "Intentando cierre ordenado"
  run_continue_turn "99-finalize" "$PROMPTS_DIR/finalize.txt"
}

main "$@"
```

Dale permisos:

```bash
chmod +x run.sh
```

Y ejecútalo así:

```bash
./run.sh "crear un servicio FastAPI para gestión de tareas con auth JWT, SQLAlchemy, tests pytest y Dockerfile"
```

---

# Qué hace este script exactamente

* Arranca una conversación con Claude usando tu requerimiento.
* Usa `--append-system-prompt-file` para meter disciplina sin cargarse el prompt interno de Claude Code. ([Claude API Docs][1])
* Después reanuda la misma conversación con `--continue --print`, que es justamente el patrón documentado para scripts. ([Claude API Docs][3])
* Hace un loop:

  * implementa,
  * revisa,
  * corrige si hace falta,
  * decide si sigue o finaliza.
* Guarda todo en `.agent-workflow/<timestamp>/`.

O sea: no es magia. Es una tubería de prompts con memoria conversacional. Y eso, sorpresa, suele funcionar mejor que meter tres frameworks para terminar igual parseando texto con cara de sufrimiento.

---

# Cosas que debes saber antes de emocionarte demasiado

## 1) “Lo más automático posible” tiene límite

Sí, Claude Code puede editar archivos, ejecutar comandos y trabajar iterativamente sobre el repo. Esa es precisamente la propuesta del producto. ([Claude API Docs][4])

Pero:

* si el requerimiento es ambiguo, va a tomar decisiones;
* si el repo es caótico, va a heredar ese caos;
* si no hay tests, puede “funcionar” hasta que deje de funcionar con entusiasmo.

## 2) No le sueltes producción sin correa

Activa un `git worktree` o al menos corre esto en una rama aislada. Claude Code tiene soporte para worktrees desde CLI. ([Claude API Docs][1])

Ejemplo:

```bash
AUTO_WORKTREE=1 ./run.sh "..."
```

## 3) Mejor cambios pequeños que epopeyas

Un requerimiento tipo:

```text
rehaz toda la arquitectura, migra a microservicios, agrega observabilidad, CI/CD y multitenancy
```

es una invitación al crimen técnico.

Mejor:

```text
extrae autenticación JWT a un módulo reusable y agrega tests
```

---

# Mejora 1: hacerlo más estricto con JSON

Ahora mismo el script parsea palabras de control simples. Eso es intencional: **menos elegante, más robusto**.

Si quieres forzar JSON, puedes hacerlo, pero te aviso el problema: cuando el modelo decide ponerse creativo, romperá el parseo en el peor momento posible, porque los modelos adoran el caos con formato bonito.

---

# Mejora 2: usar subagents nativos, pero sin framework

Claude Code tiene subagents nativos con contexto separado, y puede delegar a agentes especializados como Plan o Explore; además puedes crear subagents personalizados. ([Claude API Docs][5])

Eso te serviría para tener:

* planner
* implementer
* reviewer

pero tú pediste Bash puro con prompts, así que este script ya cumple. Primero hazlo funcionar. Luego te pones exquisito.

---

# Mejora 3: meter hooks

Claude Code soporta hooks para ejecutar comandos o prompts automáticamente en puntos del ciclo. ([Claude API Docs][6])

Eso sería útil para:

* correr `pytest` al terminar cada iteración,
* ejecutar `ruff check`,
* filtrar logs antes de pasárselos a Claude,
* rechazar cambios si fallan validaciones.

Pero eso ya es fase 2. No mezcles todo hoy o acabarás debuggeando la automatización en vez del producto.

---

# Mi versión honesta

Este script te da un **workflow autónomo razonable**.
No te da autonomía infinita. Nadie serio te debería vender eso.

Lo bueno:

* simple,
* reusable,
* sin frameworks,
* fácil de tunear.

Lo malo:

* depende mucho de la calidad del requerimiento,
* no entiende “negocio” si no se lo explicas,
* puede atascarse en tareas demasiado abiertas.

La solución a eso no es CrewAI.
La solución es **prompts mejores, restricciones claras y validación real**. Qué escándalo.

Si quieres, en el siguiente mensaje te paso una **versión 2 del script** con:

* `jq`,
* control de sesión más fino,
* extracción de estado en JSON,
* ejecución automática de `pytest/ruff`,
* y modo “solo plan”, “plan+build” o “review-only”.

[1]: https://docs.anthropic.com/en/docs/claude-code/cli-reference "CLI reference - Claude Code Docs"
[2]: https://docs.anthropic.com/en/prompt-library/library "Prompting best practices - Claude API Docs"
[3]: https://docs.anthropic.com/en/docs/claude-code/common-workflows "Common workflows - Claude Code Docs"
[4]: https://docs.anthropic.com/en/docs/claude-code?utm_source=chatgpt.com "Claude Code overview - Claude Code Docs"
[5]: https://docs.anthropic.com/en/docs/claude-code/sub-agents "Create custom subagents - Claude Code Docs"
[6]: https://docs.anthropic.com/en/docs/claude-code/hooks?utm_source=chatgpt.com "Hooks reference - Claude Code Docs"
