# Learnings de Mi Barrio → Mission Control

**Fecha**: 2026-03-30  
**Contexto**: Durante el desarrollo del orchestrator.py de Mi Barrio (Saleor Commerce) se construyó un runtime CrewAI de bajo nivel que valida patrones aplicables al Delivery Loop de Mission Control. Este documento captura los hallazgos trazables para portarlos a Mission Control.

---

## Estado en Mission Control (esta rama)

### Implementado

- El runtime CrewAI ahora inyecta bloques de **guardrails**, **memoria operativa** y **feedback de retry** en el prompt cuando el `DispatchTask` viene asociado a un `blueprint`.
- Los guardrails del prompt se alimentan del `certified_input` del blueprint (`technology_guidance`, `issues`) y de la policy activa de `architecture_guardrails.json` del workspace si existe.
- La memoria del prompt se alimenta de `task_executions` y `stage_feedback` ya persistidos en Postgres.
- El planner acepta `NEEDS_WORK` como alias de `review_required` para reutilizar el patrón simple de veredicto de Mi Barrio sin romper el contrato actual.
- Las tools de contexto (`mission_control_blueprint_context`, `mission_control_delivery_task_context`) ahora exponen más estado útil (`certified_input`, ejecuciones recientes) para que el agente pueda auto-servirse contexto adicional.

### Pendiente

- Llevar este mismo patrón de prompt ordering al futuro arquitecto conversacional de intake (`chat -> requirements.generated.md -> roadmap.generated.md`).

### Cerrado para MVP

- `delivery_guardrails` ya se persiste por blueprint, se serializa en la API, se puede actualizar por `PUT /api/blueprints/<id>/delivery-guardrails` y se mergea de forma restrictiva en `delivery/guardrails/preview` y `delivery/execute`.
- `workspace_apply_markdown_bundle` ya soporta `# filepath`, `// filepath` y `<!-- filepath -->`, con validación de paths relativos, bloqueo de duplicados y enforcement de `architecture_guardrails`.

---

## 1. Guardrails inyectados como contexto de prompt

### Qué se construyó

Dos capas de guardrails que se inyectan al inicio del `task_description` antes de entregárselo al crew:

- **Capa global**: `guardrails.yaml` en la raíz del proyecto. Define tech stack aprobado, estructura de directorios obligatoria, librerías prohibidas, patrones prohibidos y reglas de formato de output. Se carga una vez y se cachea.
- **Capa por roadmap**: clave `guardrails:` en el YAML del roadmap (nivel raíz). Si existe, reemplaza completamente la capa global para ese roadmap particular. Backwards-compatible con la clave antigua `guardrails_override:`.

### Por qué importa

Sin guardrails inyectados, los agentes:
- Usan librerías prohibidas (e.g. `jest` en lugar de `vitest`, `redux` en lugar de `React Context`).
- Crean archivos fuera de la estructura esperada.
- Generan código parcial con placeholders (`// ... rest of code`).
- Instalan dependencias fuera del stack aprobado.

### Patrón de implementación

```python
# En execute_crew(), ANTES del contenido de la tarea
if state.roadmap_guardrails:
    guardrails = _format_roadmap_guardrails(state.roadmap_guardrails)
else:
    guardrails = load_guardrails()  # global guardrails.yaml (cached)

full_description = state.task_description + "\n" + guardrails
```

### Estructura del guardrails.yaml

```yaml
tech_stack:
  frontend:
    framework: "Next.js 14 (App Router ONLY — NO Pages Router)"
    testing_unit: "vitest 2.x"

directory_structure:
  storefront:
    root: "storefront/"
    components: "storefront/src/components/"

forbidden_libraries:
  - name: "jest"
    reason: "Usar vitest en su lugar"
  - name: "redux"
    reason: "Usar React Context + Apollo cache"

forbidden_patterns:
  - "NO crear archivos parciales — cada archivo DEBE estar COMPLETO"
  - "NO usar '// ... rest of code' o placeholders"

output_format:
  code_blocks: |
    ```<lenguaje>
    # filepath: <path/relativo/desde/raiz>
    ...contenido completo...
    ```

principles:
  - "KISS — No sobre-ingeniería"
  - "UNA librería por concern"
```

### Aplicación en Mission Control

La `guardrails:` clave ya existe conceptualmente como "architecture guardrails por workspace" en Fase 5. La propuesta es:

- Persistir guardrails en `crew_definitions` o en `project_blueprints` por workspace.
- Formatear e inyectarlos al inicio de *cada* `task_description` antes de enviarla al crew.
- Permitir un guardrails global del sistema + un override por proyecto (igual que la implementación de Mi Barrio).

---

## 2. Memoria de agentes entre tareas (flat YAML → Postgres)

### Qué se construyó

`agent_memory.yaml` — archivo YAML persistido entre corridas. Estructura:

```yaml
tasks:
  S0-T1:
    name: "docker-compose.saleor.yml + .env documentado"
    sprint: sprint-0
    status: approved          # approved | needs_work | failed
    last_attempt: 2
    attempts: 2
    files_created:
      - docker-compose.saleor.yml
      - .env.saleor.example
    supervisor_summary: "Todos los guardrails OK. Tests pasaron."
    updated: 2026-03-22T14:30:00Z
current_sprint: sprint-0
last_updated: 2026-03-22T14:30:00Z
```

### Qué se inyecta al crew

Antes de ejecutar una tarea, se construye un bloque de texto `build_memory_context()` que incluye:

1. **Tareas ya aprobadas**: lista de archivos creados en tareas anteriores + resumen del supervisor. Esto evita que los agentes recreen trabajo ya hecho o sobreescriban archivos existentes.
2. **Intentos previos de la tarea actual**: si es un retry, muestra al agente cuántos intentos lleva y el último feedback del supervisor.
3. **Tareas con problemas**: aviso de tareas en `needs_work` o `failed` como contexto de riesgo.

### Bugs encontrados y corregidos

**Bug 1 — `files_created` sobreescribía en retry**  
En cada reintento se sobreescribía la lista de archivos con sólo los del intento actual.  
**Fix**:
```python
existing = entry.get("files_created", [])
merged = existing + [f for f in files_written if f not in existing]
entry["files_created"] = merged  # deduplicated merge
```

**Bug 2 — `supervisor_summary` se borraba al alcanzar max retries**  
El handler de max-retries llamaba `update_task_memory()` con `supervisor_summary=""`, borrando el feedback real que había guardado `execute_crew()` en el intento anterior.  
**Fix**: en el handler de max-retries, no pasar `supervisor_summary` — sólo actualizar `status="failed"`.

### Aplicación en Mission Control

Esta memoria es equivalente a `task_executions` + `agent_runs` de Postgres (ya implementados en Fase 2 y 5). La diferencia es que Mission Control debe **inyectar ese contexto como texto** en el prompt del siguiente crew, igual que lo hace Mi Barrio. El dato ya está en Postgres; falta el paso de formateo e inyección.

Bloques de texto sugeridos para inyectar (en orden, al final del task_description):

```
## Tareas ya completadas (NO repetir este trabajo)
### S0-T1: docker-compose.saleor.yml
  Archivos creados (5): docker-compose.saleor.yml, .env.saleor.example ...
  Resumen: Todos los guardrails OK.

## Estado actual de S0-T2
  Intentos previos: 1
  Último status: needs_work
  Feedback: Faltaron los health checks en el servicio api.
```

---

## 3. Extractor de archivos multi-estilo (filepath directive)

### El problema

El formato que los agentes usan para marcar paths de archivo en sus respuestas varía por lenguaje:

| Estilo | Lenguajes |
|--------|----------|
| `# filepath: path/to/file` | Python, shell, YAML, TOML |
| `// filepath: path/to/file` | JavaScript, TypeScript, Go, Java, C++ |
| `<!-- filepath: path/to/file -->` | HTML, JSX templates |

La implementación original sólo extraía el estilo `#`. Los archivos JS/TS de los agentes frontend se escribían correctamente en el output del LLM pero **nunca llegaban al disco**. Este bug era silencioso — no producía error, simplemente los archivos no aparecían.

### Fix — regex multi-estilo

```python
pattern = re.compile(
    r"```[\w]*\s*\n"                                         # opening fence
    r"\s*(?:#|//|<!--)\s*filepath:\s*(.+?)\s*(?:-->)?\s*\n"  # filepath directive
    r"(.*?)"                                                  # content
    r"\n```",                                                 # closing fence
    re.DOTALL,
)
```

### Controles de seguridad del extractor

El extractor tiene una capa de seguridad antes de escribir cualquier archivo:

```python
PROTECTED_FILES = {
    ".env", ".env.local", ".gitignore", "orchestrator.py",
    "Pipfile", "docker-compose.yml", "agent_memory.yaml", ...
}
PROTECTED_PREFIXES = (".git/", "node_modules/", "__pycache__/", ".venv/")

# Rechaza paths absolutos y path traversal
if rel_path.startswith("/") or ".." in rel_path:
    print(f"⚠️ Skipping unsafe path: {rel_path}")
    continue

# Rechaza paths protegidos
if rel_path in PROTECTED_FILES or any(rel_path.startswith(p) for p in PROTECTED_PREFIXES):
    print(f"🔒 Skipping protected file: {rel_path}")
    continue
```

### Aplicación en Mission Control

El `Artifact Builder` de Fase 5 (`AG-504`) ya persiste artifacts en disco. La misma regex multi-estilo debe aplicarse en la herramienta de workspace que extrae archivos del output de los agentes. La lista de `PROTECTED_FILES` debe ser configurable por proyecto (para evitar sobreescribir por accidente archivos de configuración del workspace).

---

## 4. Loop de retry con feedback del supervisor

### Patrón implementado

```
mientras intentos <= max_retries:
    raw = execute_crew(state)
    si "APPROVED" en raw y "NEEDS_WORK" no en raw:
        commit + merge → main
        break
    si intentos == max_retries:
        marcar failed, salir
    state.previous_feedback = raw
    state.attempt += 1
    # En el siguiente execute_crew(), el feedback se inyecta así:
    full_description += f"""
⚠️ FEEDBACK DEL INTENTO ANTERIOR (intento {attempt - 1}):
El supervisor rechazó el trabajo anterior. Debes corregir TODOS
los issues listados abajo. NO repitas los mismos errores.
{state.previous_feedback}
"""
```

### Señal de veredicto

El supervisor emite texto con exactamente una de estas cadenas:
- `APPROVED` — tarea aceptada
- `NEEDS_WORK` — tarea rechazada con lista de issues

Detección:
```python
is_approved = "APPROVED" in raw.upper() and "NEEDS_WORK" not in raw.upper()
```

**Nota**: GPT-4o-mini a veces emite falsos positivos en el supervisor — rechaza librerías que están en el tech stack aprobado (e.g. marcó `@testing-library/react` como prohibida siendo parte del stack aprobado). Esto no es un bug del orquestador sino una limitación del modelo. Solución: usar un modelo más potente para el rol de supervisor/qa_lead (Bedrock Claude en Mission Control), o reforzar la lista de permitidas en los guardrails.

### Aplicación en Mission Control

El loop de retry existe en Fase 5 como `AG-505`. El patrón de inyección de feedback anterior en el prompt del siguiente intento es el mecanismo concreto que lo hace funcionar. La implementación de Mi Barrio es una referencia de producción validada.

---

## 5. Topología del crew (pipeline secuencial de 5 agentes)

### Estructura

```
roadmap.yaml task description
       ↓
1. architect     → diseño técnico, decisiones de arquitectura
2. developer     → implementación completa de todos los archivos
3. reviewer      → code review, correcciones inline
4. qa_engineer   → validación de tests, guardrails, criterios de aceptación
5. supervisor    → veredicto final: APPROVED o NEEDS_WORK + lista de issues
```

### Dónde vive el código generado

Los archivos de código se extraen de los outputs de los pasos `implement` (developer) y `review` (reviewer), **no** del output de supervision. El output de supervision es el veredicto de texto.

```python
if label in ("implement", "review"):
    all_code_text += f"\n{raw_text}\n"

written = extract_and_write_files(all_code_text, project_root)
```

### Configuración de LLMs

En Mi Barrio todos los agentes usan GPT-4o-mini (rápido y barato para prototipo):

```python
LLM(model="openai/gpt-4o-mini", temperature=0.1)
```

El routing multi-modelo deseable para Mission Control es:
- Workers (architect, developer, reviewer): Ollama `qwen2.5-coder:latest` (ya definido en Fase 3)
- QA + Supervisor: Bedrock Claude (más preciso para veredictos y review de seguridad)
- Blocker/Escalation: Bedrock Claude Sonnet/Opus

---

## 6. YAML-driven roadmap — formato validado

### Estructura canónica de una tarea

```yaml
- id: S0-T1
  name: "Nombre corto de la tarea"
  description: |
    Descripción detallada. Puede ser multilínea.
    Incluye criterios de aceptación, archivos a crear y comportamiento esperado.
  files_context:
    - archivo/existente/para/contexto.py   # se envía al crew truncado a 500 chars
  branch: feat/s0-t1-nombre-rama
  testing:
    unit:
      - tests/unit/test_algo.py
    integration:
      - tests/integration/test_algo.py
  estimated_hours: 6
```

### Guardrails por roadmap (override global)

```yaml
# top-level en el .yaml del roadmap
guardrails:
  tech_stack:
    frontend:
      framework: "React 18 + Vite"
      testing: "vitest 2.x"
  forbidden_libraries:
    - name: "jest"
      reason: "Usar vitest en su lugar"
  output_format:
    code_blocks: |
      ...
```

La clave `guardrails_override:` (legacy) sigue siendo soportada por backwards compatibility.

### Múltiples roadmaps por proyecto

El CLI acepta `--roadmap <archivo.yaml>`, lo que permite tener:
- `roadmap.yaml` — roadmap principal del proyecto
- `test_roadmap.yaml` — tareas de smoke test
- `test_roadmap_calc.yaml` — tareas con guardrails específicos de React/Vite

Esto es equivalente al concepto de "projects" de Mission Control con blueprints independientes.

---

## 7. Seguridad — litellm supply chain attack

### Hallazgo

Durante el trabajo con este proyecto se identificó un ataque a la cadena de suministro en litellm:

| Versión | Estado |
|---------|--------|
| ≤ 1.82.6 | ✅ Segura |
| 1.82.7 | ❌ **COMPROMETIDA** — malware embebido |
| 1.82.8 | ❌ **COMPROMETIDA** — malware embebido |

Confirmado por Snyk y Socket.dev Threat Research (marzo 2026).

### Mitigación aplicada

Archivo `constraints.txt` en la raíz del proyecto:

```
litellm==1.82.6
crewai==1.11.1
openai==2.29.0
instructor==1.14.5
mcp==1.26.0
pydantic==2.11.10
pydantic-settings==2.10.1
```

Uso: `pip install -c constraints.txt <paquete>`

### Aplicación en Mission Control

Mission Control debe:
1. Verificar que `litellm` en su `.venv` sea `== 1.82.6`.
2. Nunca actualizar a `1.82.7` o `1.82.8` hasta que exista una versión limpia post-1.82.8.
3. Agregar `constraints.txt` con el mismo pin.

---

## 8. Resultados de validación (tests end-to-end)

| Test | Stack | Resultado |
|------|-------|-----------|
| TEST-T1 — Python hola mundo | Python 3.12 + pytest | ✅ `holamundo.py` + `test_holamundo.py` generados y ejecutados |
| CALC-T1 — FastAPI backend | FastAPI 0.115 + pytest | ✅ 7/7 tests pasando (`main.py` + `test_main.py`) |
| CALC-T2 — React frontend | React 18 + Vite + vitest | ✅ 5/5 tests pasando tras fixes manuales |

### Issues encontrados en CALC-T2 (React/vitest)

El agente generó código usando la API de Jest en lugar de vitest. Fixes manuales necesarios:

1. `jest.mock` → `vi.mock` con factory function:
   ```js
   vi.mock('axios', () => ({ default: { post: vi.fn() } }))
   ```
2. `jest.clearAllMocks` → `vi.clearAllMocks`
3. Añadir `import '@testing-library/jest-dom'` para matchers como `toBeInTheDocument()`
4. Añadir bloque `test:` en `vite.config.js`:
   ```js
   test: { globals: true, environment: 'jsdom', setupFiles: [] }
   ```
5. String en español mal generado: `'Division by zero'` → `'División por cero'`

**Causa raíz**: el modelo (GPT-4o-mini) confunde Jest y vitest aunque se especifique vitest en los guardrails. Usar un modelo más potente (Claude 3.5 Sonnet o superior) para los agentes developer y reviewer reduce considerablemente este tipo de errores.

---

## 9. Orden de inyección de contexto en el prompt

El orden importa. En Mi Barrio el `task_description` se construye así:

```
1. Descripción original de la tarea (de roadmap.yaml)
2. Guardrails (global o por roadmap) — PRIMERO para que el modelo los vea siempre
3. Memoria de agentes (tareas completadas + feedback de intentos anteriores)
4. Contenido de archivos de contexto (truncado a 500 chars cada uno)
5. Requisitos de testing
6. Feedback del intento anterior (sólo en retries, con separador visual)
```

Este orden asegura que las restricciones (guardrails) siempre están presentes aunque el prompt sea largo y el modelo tenga pérdida de atención en el centro.

---

## Resumen: qué portar a Mission Control

| # | Feature | Estado en MC | Acción |
|---|---------|-------------|--------|
| 1 | Guardrails inyectados en prompt | Mencionado en Fase 5 | Implementar formateador + inyección al inicio del task_description |
| 2 | Guardrails por proyecto (override) | No existe | Añadir `guardrails` como campo en `project_blueprints` o `crew_definitions` |
| 3 | Memoria cross-task inyectada como texto | Datos en Postgres (Fase 2) | Añadir `build_memory_context()` que consulte `task_executions` y formatee para prompt |
| 4 | `files_created` dedup en retry | No aplica directo | Usar set/merge al actualizar `artifacts` con files de un retry |
| 5 | Extractor multi-estilo (`#`, `//`, `<!--`) | Workspace tool existe | Actualizar regex en la tool de escritura de código |
| 6 | Lista de archivos protegidos | Parcial | Configurar `PROTECTED_FILES` por workspace, persistir en `crew_definitions` |
| 7 | Señal APPROVED/NEEDS_WORK como texto | Fase 5 usa findings | Mantener señal simple (\`APPROVED\` / \`NEEDS_WORK\`) en el output del supervisor para el loop de control, además de los findings estructurados |
| 8 | Feedback anterior inyectado en retry | Loop existe en AG-505 | Añadir bloque de texto con feedback del intento anterior en task_description |
| 9 | Orden de inyección en prompt | No documentado | Documentar y fijar: guardrails → memoria → contexto → testing → feedback previo |
| 10 | Pin litellm==1.82.6 | No aplicado | Verificar versión en .venv y agregar constraints.txt |
