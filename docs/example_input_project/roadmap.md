# 🗺️ Roadmap — Sistema Multi-Agente de Prospección de Leads
**Proyecto**: Growth Guard · Lead Prospecting Agents  
**Framework**: CrewAI · Bedrock/OpenAI · Google Maps · Tavily/Brave · Excel Output  
**PM Owner**: TBD  
**Fecha base**: 2026-03-21  
**Estimación total**: ~13 días de desarrollo (1 desarrollador senior full-time)

---

## Índice de Epics

| Epic | Nombre | Tickets | Est. días |
|------|--------|---------|-----------|
| [EP-0](#ep-0--setup--fundamentos) | Setup & Fundamentos | 5 tickets | 1.5 d |
| [EP-1](#ep-1--capa-de-tools) | Capa de Tools | 7 tickets | 2.5 d |
| [EP-2](#ep-2--agentes-crewai) | Agentes CrewAI | 8 tickets | 4.0 d |
| [EP-3](#ep-3--prompts--structured-output) | Prompts & Structured Output | 3 tickets | 1.0 d |
| [EP-4](#ep-4--orquestación-crew) | Orquestación Crew | 2 tickets | 1.5 d |
| [EP-5](#ep-5--output--excel) | Output & Excel | 2 tickets | 1.0 d |
| [EP-6](#ep-6--testing--qa) | Testing & QA | 4 tickets | 1.5 d |
| **Total** | | **31 tickets** | **~13 días** |

---

## Convenciones de Tickets

```
[TICKET-ID] Título
Tipo:         feature | bugfix | chore | spike
Prioridad:    P0 (bloqueante) | P1 (crítico) | P2 (importante) | P3 (nice-to-have)
Estimación:   horas de desarrollo
Dependencias: ticket(s) que deben estar Done primero
Descripción:  contexto y motivación
Criterios de aceptación: lista verificable (checklist)
Notas técnicas: detalles de implementación relevantes
```

---

## EP-0 · Setup & Fundamentos

> Objetivo: tener el esqueleto del proyecto corriendo, con modelos tipados y config cargable antes de tocar ningún agente.

---

### TICKET-001 · Estructura de directorios y setup del proyecto

```
Tipo:       chore
Prioridad:  P0
Est.:       2 h
Deps.:      ninguna
```

**Descripción**  
Crear la estructura de archivos definida en `requirements.md §11` y el entorno virtual con todas las dependencias pinneadas.

**Criterios de aceptación**
- [ ] Carpetas creadas: `agents/`, `tools/`, `prompts/`, `output/`
- [ ] `requirements.txt` con versiones exactas de todas las librerías del stack (§10)
- [ ] `.env.example` con todas las variables de §12 documentadas
- [ ] `.gitignore` que excluye `.env`, `output/`, `__pycache__/`, `.venv/`
- [ ] `python -m venv .venv && pip install -r requirements.txt` ejecuta sin errores
- [ ] `playwright install chromium` ejecuta sin errores

**Notas técnicas**
```
crewai>=0.80
langchain-aws>=0.2
langchain-openai>=0.2
tavily-python>=0.5
duckduckgo-search>=6.0
httpx>=0.27
beautifulsoup4>=4.12
playwright>=1.44
rapidfuzz>=3.0
openpyxl>=3.1
pydantic-settings>=2.0
pyyaml>=6.0
rich>=13.0
```

---

### TICKET-002 · Modelos de datos (Pydantic)

```
Tipo:       feature
Prioridad:  P0
Est.:       3 h
Deps.:      TICKET-001
```

**Descripción**  
Implementar todos los modelos de datos en `models.py` usando Pydantic v2. Cada modelo hereda del anterior siguiendo la cadena de transformación del pipeline.

**Criterios de aceptación**
- [ ] `SearchConfig` — valida que `queries` sea `List[str]` no vacío, `max_leads > 0`
- [ ] `RawLead` — todos los campos de §6, `popular_times` acepta lista vacía por defecto
- [ ] `EnrichedLead(RawLead)` — herencia correcta, campos con defaults razonables
- [ ] `CommercialProfile` — scores con validación de rango (`0 <= hormozi_urgency <= 3`)
- [ ] `VisitTiming` — `timing_confidence` acepta solo `"high"` o `"inferred"` (Literal)
- [ ] `ProfiledLead(EnrichedLead)` — contiene `profile: CommercialProfile` y `visit_timing: VisitTiming`
- [ ] `QualifiedLead(ProfiledLead)` — `tier` acepta solo `"HOT"/"WARM"/"COLD"` (Literal)
- [ ] `RunReport` — campos: `campaign_name`, `total_raw`, `total_after_dedup`, `hot_count`, `warm_count`, `cold_count`, `sources_breakdown: dict`, `duration_seconds: float`, `iterations: int`
- [ ] `pytest models/` con tests básicos de validación pasa sin errores

**Notas técnicas**
- Usar `model_validator` de Pydantic v2 para validar `hormozi_score = sum([urgency, buying_power, accessibility, market_fit]) * (10/12)`
- `popular_times: List[dict] = Field(default_factory=list)`
- `social_links: dict = Field(default_factory=dict)`

---

### TICKET-003 · Config loader (SearchConfig + .env)

```
Tipo:       feature
Prioridad:  P0
Est.:       2 h
Deps.:      TICKET-002
```

**Descripción**  
Implementar `config.py`: carga `search_config.yaml`, valida con Pydantic, expone variables de entorno via `pydantic-settings`. El sistema nunca debe hardcodear queries ni API keys.

**Criterios de aceptación**
- [ ] `load_config(path: str) -> SearchConfig` lee y valida el YAML
- [ ] `AppSettings` (pydantic-settings) carga todas las vars de `.env` (§12)
- [ ] Si falta una API key requerida por los `sources` configurados → lanza `ConfigError` con mensaje claro (ej: "TAVILY_API_KEY requerida para source=tavily")
- [ ] Si `sources` incluye `duckduckgo` → no exige API key (modo local)
- [ ] `load_config` acepta override de campos via variables de entorno (LLM_PROVIDER, etc.)
- [ ] `search_config.yaml` de ejemplo funcional para campaña "Talleres Bogotá"

---

### TICKET-004 · LLM provider factory (Bedrock + OpenAI fallback)

```
Tipo:       feature
Prioridad:  P0
Est.:       2 h
Deps.:      TICKET-003
```

**Descripción**  
Crear `llm_factory.py` que instancia el LLM correcto según `llm.provider` y tiene retry automático con fallback a OpenAI si Bedrock falla.

**Criterios de aceptación**
- [ ] `get_llm(settings: AppSettings) -> BaseChatModel` retorna Bedrock o OpenAI
- [ ] Si Bedrock lanza `ClientError` (throttling/timeout) → reintenta 2x con backoff exponencial, luego hace fallback a OpenAI
- [ ] Log con `rich` indica qué LLM se está usando en cada momento
- [ ] `get_llm` acepta `temperature` como parámetro (default desde config)
- [ ] Test: mock de boto3 que simula throttling → verifica que se activa fallback

**Notas técnicas**
```python
# Bedrock
from langchain_aws import ChatBedrock
# OpenAI
from langchain_openai import ChatOpenAI
```

---

### TICKET-005 · CLI entry point (main.py)

```
Tipo:       feature
Prioridad:  P0
Est.:       1.5 h
Deps.:      TICKET-003, TICKET-004
```

**Descripción**  
Crear `main.py` como entry point con argumentos CLI usando `argparse`.

**Criterios de aceptación**
- [ ] `python main.py --config search_config.yaml` arranca el sistema
- [ ] `--config` requerido; si no se provee → error claro
- [ ] `--dry-run` flag: valida config y APIs sin ejecutar el crew
- [ ] `--max-leads N` override del valor en YAML
- [ ] `--llm bedrock|openai` override del provider
- [ ] Banner de inicio con `rich` que muestra: campaign name, queries, city, max_leads, sources activos, LLM provider
- [ ] Al finalizar: muestra `RunReport` con tabla `rich` (totales por tier, fuentes, duración)

---

## EP-1 · Capa de Tools

> Objetivo: todas las herramientas de integración con APIs y scraping, independientes de los agentes, testeables de forma aislada.

---

### TICKET-006 · TavilySearchTool

```
Tipo:       feature
Prioridad:  P1
Est.:       2 h
Deps.:      TICKET-001
```

**Descripción**  
Implementar `tools/tavily_tool.py` como `@tool` de CrewAI que busca resultados web con Tavily API.

**Criterios de aceptación**
- [ ] `TavilySearchTool(query: str, max_results: int = 10) -> List[dict]`
- [ ] Retorna: `[{url, title, snippet, domain, score}]`
- [ ] Filtra resultados con `score < 0.5` (baja relevancia)
- [ ] Timeout de 10s por request; en timeout → retorna lista vacía con log warning
- [ ] Rate limiting: máximo 5 req/seg (sleep entre calls)
- [ ] Test con mock HTTP: verifica parsing correcto de la respuesta Tavily

**Notas técnicas**
```python
from tavily import TavilyClient
client = TavilyClient(api_key=settings.TAVILY_API_KEY)
response = client.search(query, max_results=max_results, search_depth="advanced")
```

---

### TICKET-007 · BraveSearchTool

```
Tipo:       feature
Prioridad:  P1
Est.:       2 h
Deps.:      TICKET-001
```

**Descripción**  
Implementar `tools/brave_tool.py` que hace requests REST a `https://api.search.brave.com/res/v1/web/search`.

**Criterios de aceptación**
- [ ] `BraveSearchTool(query: str, country: str = "co", max_results: int = 20) -> List[dict]`
- [ ] Headers: `Accept: application/json`, `X-Subscription-Token: {BRAVE_API_KEY}`
- [ ] Paginación: soporta `offset` para obtener hasta 100 resultados
- [ ] Retorna: `[{url, title, description, domain}]`
- [ ] Maneja HTTP 429 (rate limit): exponential backoff 1s, 2s, 4s
- [ ] Test con `httpx` mock: verifica parsing de `web.results[]`

---

### TICKET-008 · DuckDuckGoTool (modo local/dev)

```
Tipo:       feature
Prioridad:  P2
Est.:       1 h
Deps.:      TICKET-001
```

**Descripción**  
Implementar `tools/duckduckgo_tool.py` para uso en desarrollo sin API key.

**Criterios de aceptación**
- [ ] `DuckDuckGoTool(query: str, max_results: int = 20) -> List[dict]`
- [ ] Usa `duckduckgo_search.DDGS().text()`
- [ ] Maneja `DuckDuckGoSearchException` → retorna lista vacía con log warning
- [ ] Mismo formato de output que Tavily/Brave: `[{url, title, snippet, domain}]`
- [ ] Habilitado automáticamente si `duckduckgo` está en `sources` del config

---

### TICKET-009 · GooglePlacesTool + GooglePlaceDetailsTool

```
Tipo:       feature
Prioridad:  P0
Est.:       3 h
Deps.:      TICKET-001
```

**Descripción**  
Implementar `tools/maps_tool.py` con dos herramientas: búsqueda por texto y detalle de un lugar específico (incluyendo `popular_times`).

**Criterios de aceptación**

**GooglePlacesTool:**
- [ ] `search_places(query: str, city: str, language: str) -> List[dict]`
- [ ] Endpoint: `POST https://places.googleapis.com/v1/places:searchText`
- [ ] Fields mask incluye: `places.id,places.displayName,places.formattedAddress,places.nationalPhoneNumber,places.websiteUri,places.rating,places.userRatingCount,places.businessStatus,places.currentOpeningHours`
- [ ] Paginación via `pageToken` (hasta 3 páginas, sleep 2s entre páginas)
- [ ] Filtra `businessStatus != "OPERATIONAL"`

**GooglePlaceDetailsTool:**
- [ ] `get_place_details(place_id: str) -> dict`
- [ ] Fields mask adiciona: `regularOpeningHours,currentOpeningHours`
- [ ] Si la respuesta incluye datos de ocupación → guarda en `popular_times`
- [ ] Si no hay `popular_times` en la API → setea `popular_times = []` (será llenado por PopularTimesTool)
- [ ] Retorna `RawLead`-compatible dict completo
- [ ] Test: mock API response con y sin `popular_times`

**Notas técnicas**
```
API Key header: X-Goog-Api-Key: {GOOGLE_MAPS_API_KEY}
Field mask header: X-Goog-FieldMask: places.id,places.displayName,...
```

---

### TICKET-010 · PopularTimesTool (scraping HTML fallback)

```
Tipo:       feature
Prioridad:  P1
Est.:       3 h
Deps.:      TICKET-001
```

**Descripción**  
Implementar `tools/popular_times_tool.py` para extraer datos de "Popular times" directamente del HTML de Google Maps via Playwright cuando la API no los entrega.

**Criterios de aceptación**
- [ ] `get_popular_times(place_id: str) -> List[dict]`
- [ ] URL: `https://www.google.com/maps/place/?q=place_id:{place_id}`
- [ ] Playwright en modo headless, User-Agent rotativo (3 opciones)
- [ ] Extrae la info del script JS `window.APP_INITIALIZATION_STATE` o del atributo `data-value` de los nodos de barra de ocupación
- [ ] Output: `[{day: "lunes", hours: [{hour: 8, busyness: 35}, {hour: 9, busyness: 52}, ...]}]`
- [ ] Si el elemento "Popular times" no existe en la página → retorna `[]` sin error
- [ ] Timeout de página 15s; si supera → retorna `[]` con log warning
- [ ] Rate limit: sleep 3s entre scrapes para evitar bloqueo

**Notas técnicas**
- Google Maps renderiza las barras de popular times como elementos con `aria-label="X% de ocupación"` o en el JSON de inicialización de la app. Priorizar el JSON pues es más estable.
- Verificar con `place_id` de un taller real como smoke test manual.

---

### TICKET-011 · StaticScraperTool + PlaywrightScraperTool

```
Tipo:       feature
Prioridad:  P1
Est.:       3 h
Deps.:      TICKET-001
```

**Descripción**  
Implementar `tools/scraper_tool.py` con dos estrategias de scraping y heurística de selección automática.

**Criterios de aceptación**

**Heurística de selección:**
- [ ] `detect_needs_js(url: str) -> bool`: hace GET con httpx, si body text < 500 chars O contiene `react-root|__NEXT_DATA__|ng-version|nuxt` → retorna `True`

**StaticScraperTool:**
- [ ] `scrape_static(url: str) -> ScrapedProfile`
- [ ] httpx GET con timeout 10s, headers User-Agent realista
- [ ] BS4: extrae `og:description`, `schema.org LocalBusiness`, meta generator
- [ ] Regex emails, teléfonos Colombia, WhatsApp links
- [ ] Detecta redes sociales en atributos `href`: instagram.com, facebook.com, tiktok.com, linkedin.com
- [ ] Detecta tecnología: WordPress (wp-content), Shopify (cdn.shopify), Wix (wix.com/static), custom (ninguno anterior)

**PlaywrightScraperTool:**
- [ ] `scrape_dynamic(url: str) -> ScrapedProfile`
- [ ] Playwright async, modo headless
- [ ] `page.wait_for_load_state("networkidle")` antes de extraer
- [ ] Mismo parsing que estático pero sobre DOM renderizado
- [ ] Timeout total: 20s por página

**ScrapedProfile output:**
```python
{emails: List[str], phones: List[str], has_whatsapp: bool,
 whatsapp_number: str, social_links: dict, description: str,
 technology_stack: List[str]}
```

---

### TICKET-012 · ExcelExportTool

```
Tipo:       feature
Prioridad:  P1
Est.:       3 h
Deps.:      TICKET-002
```

**Descripción**  
Implementar `tools/excel_tool.py` que genera el Excel final con todas las hojas, columnas y formato visual especificado en `requirements.md §9`.

**Criterios de aceptación**
- [ ] Genera archivo `output/leads_{campaign}_{YYYYMMDD}.xlsx`
- [ ] Hojas: `HOT`, `WARM`, `COLD`, `TODOS`, `RESUMEN`
- [ ] Columnas en el orden exacto definido en §9 (7 grupos: CONTACTO, DATOS OPERATIVOS, PERFIL HORMOZI, PERFIL CHALLENGER, PERFIL CARDONE, TIMING DE CONTACTO, PITCH)
- [ ] Colores por fila: HOT `#C6EFCE`, WARM `#FFEB9C`, COLD `#D9D9D9`
- [ ] Header: `PatternFill` fondo oscuro `#243F60`, texto blanco, negrita
- [ ] `pitch_hook`: wrap text, column width 60
- [ ] `timing_summary`: fill `#DEEAF1`, wrap text, width 50
- [ ] `avoid_times`: fill `#FCE4D6`
- [ ] Filas con `timing_confidence == "inferred"`: font italic, color gris `#808080`
- [ ] Hoja `RESUMEN`: tabla con totales por tier, fuentes, timestamp run, duración
- [ ] Auto-filter en header de cada hoja
- [ ] Columnas congeladas (freeze panes) en fila 1 + columna 4 (hasta `name`)
- [ ] Test: genera Excel con 3 leads de prueba, verifica que el archivo es legible con openpyxl

---

## EP-2 · Agentes CrewAI

> Objetivo: implementar los 8 agentes con sus roles, goals, backstories y tools correctamente conectados. Cada agente es una clase con método `create() -> Agent`.

---

### TICKET-013 · SearchAgent (Tavily + Brave + DDG)

```
Tipo:       feature
Prioridad:  P0
Est.:       3 h
Deps.:      TICKET-006, TICKET-007, TICKET-008, TICKET-003
```

**Descripción**  
Implementar `agents/search_agent.py` con el `SearchAgent` y su `Task` de búsqueda.

**Criterios de aceptación**
- [ ] `SearchAgent.create(config: SearchConfig, settings: AppSettings) -> Agent`
- [ ] `role`, `goal`, `backstory` exactos según §3.1
- [ ] `tools` instanciados según `sources` en config (solo incluye los habilitados)
- [ ] `SearchTask.create(queries: List[str], config: SearchConfig) -> Task`
- [ ] La task incluye instrucción explícita de generar 3-5 variaciones de cada query
- [ ] La task incluye instrucción de detectar y expandir directorios (Páginas Amarillas, etc.)
- [ ] Output esperado: `List[RawLead]` serializado como JSON string
- [ ] `expected_output` del Task describe el schema JSON de forma clara para el LLM

---

### TICKET-014 · MapsAgent (Google Places)

```
Tipo:       feature
Prioridad:  P0
Est.:       2 h
Deps.:      TICKET-009, TICKET-003
```

**Descripción**  
Implementar `agents/maps_agent.py`.

**Criterios de aceptación**
- [ ] `MapsAgent.create(config: SearchConfig, settings: AppSettings) -> Agent`
- [ ] `role`, `goal`, `backstory` exactos según §3.2
- [ ] `tools = [GooglePlacesTool, GooglePlaceDetailsTool]`
- [ ] `MapsTask.create(config: SearchConfig) -> Task`
- [ ] Task especifica: para cada resultado de `searchText`, llamar `PlaceDetails` con todos los fields
- [ ] Task especifica: manejar `next_page_token` hasta agotarlo o llegar a `max_leads`
- [ ] Output: `List[RawLead]` JSON con `source="google_maps"`

---

### TICKET-015 · ScraperAgent

```
Tipo:       feature
Prioridad:  P1
Est.:       2 h
Deps.:      TICKET-011, TICKET-003
```

**Descripción**  
Implementar `agents/scraper_agent.py`.

**Criterios de aceptación**
- [ ] `ScraperAgent.create(settings: AppSettings) -> Agent`
- [ ] `role`, `goal`, `backstory` exactos según §3.3
- [ ] `tools = [StaticScraperTool, PlaywrightScraperTool]`
- [ ] `ScraperTask.create(leads: List[RawLead], concurrency: int) -> Task`
- [ ] Task instruye al agente a aplicar heurística de detección JS antes de elegir herramienta
- [ ] Task especifica que las URLs se procesen en lotes de `concurrency`
- [ ] Output: `List[RawLead]` enriquecidos con campos de `ScrapedProfile`
- [ ] Si `scrape_websites = false` en config → task retorna leads sin modificar

---

### TICKET-016 · EnrichmentAgent

```
Tipo:       feature
Prioridad:  P0
Est.:       3 h
Deps.:      TICKET-002, TICKET-003, TICKET-004
```

**Descripción**  
Implementar `agents/enrichment_agent.py` con lógica de deduplicación fuzzy y enriquecimiento LLM.

**Criterios de aceptación**
- [ ] `EnrichmentAgent.create(settings: AppSettings) -> Agent`
- [ ] `role`, `goal`, `backstory` exactos según §3.4
- [ ] `tools = [DeduplicationTool]`
- [ ] `EnrichmentTask.create(raw_leads: List[RawLead]) -> Task`
- [ ] Task incluye: instrucción de deduplicación con clave `(nombre_normalizado, primeros_7_digitos_telefono)`
- [ ] Task incluye: en merge, prioridad Maps > Brave > Scraper
- [ ] Task llama LLM para generar `lead_summary`, `estimated_size`, `main_sector`, `digital_maturity`, `sales_opportunity` por cada lead dedup
- [ ] Output: `List[EnrichedLead]` JSON
- [ ] Log: `"{N_raw} leads crudos → {N_dedup} leads únicos ({N_merged} mergeados)"`

---

### TICKET-017 · VisitTimingAgent

```
Tipo:       feature
Prioridad:  P1
Est.:       3 h
Deps.:      TICKET-010, TICKET-003, TICKET-004
```

**Descripción**  
Implementar `agents/visit_timing_agent.py`.

**Criterios de aceptación**
- [ ] `VisitTimingAgent.create(settings: AppSettings) -> Agent`
- [ ] `role`, `goal`, `backstory` exactos según §3.5
- [ ] `tools = [PopularTimesTool]`
- [ ] `VisitTimingTask.create(enriched_leads: List[EnrichedLead]) -> Task`
- [ ] Task especifica: si `popular_times` vacío → invocar `PopularTimesTool` con `place_id`
- [ ] Task especifica el algoritmo LLM completo (§3.5): umbrales de ocupación, franjas preferidas, exclusiones de primera/última hora
- [ ] Task especifica output JSON con schema exacto de `VisitTiming`
- [ ] `timing_confidence = "inferred"` cuando `popular_times` original era vacío
- [ ] Output: `List[EnrichedLead]` con campo `visit_timing: VisitTiming` poblado

---

### TICKET-018 · ProfilerAgent (Hormozi + Challenger + Cardone)

```
Tipo:       feature
Prioridad:  P0
Est.:       4 h
Deps.:      TICKET-002, TICKET-004, TICKET-021
```

**Descripción**  
Implementar `agents/profiler_agent.py`. Es el agente más complejo en términos de prompt y output estructurado.

**Criterios de aceptación**
- [ ] `ProfilerAgent.create(settings: AppSettings) -> Agent`
- [ ] `role`, `goal`, `backstory` exactos según §3.6
- [ ] `tools = []` (solo LLM)
- [ ] `ProfilerTask.create(enriched_leads: List[EnrichedLead]) -> Task`
- [ ] Task aplica los 3 frameworks de §5 para cada lead
- [ ] Output JSON incluye todos los campos de `CommercialProfile` (§5.4)
- [ ] Scores Hormozi validados en rango 0-3 por dimensión
- [ ] `hormozi_score` calculado como suma normalizada a 0-10
- [ ] `challenger_insight` y `cardone_action_line` son textos generados (no enums fijos)
- [ ] `composite_profile_score` = media ponderada (Hormozi 40%, Challenger 30%, Cardone 30%)
- [ ] Output: `List[ProfiledLead]` JSON

---

### TICKET-019 · QualifierAgent

```
Tipo:       feature
Prioridad:  P0
Est.:       2 h
Deps.:      TICKET-002, TICKET-004, TICKET-022
```

**Descripción**  
Implementar `agents/qualifier_agent.py` con la fórmula de score de §8.

**Criterios de aceptación**
- [ ] `QualifierAgent.create(config: SearchConfig, settings: AppSettings) -> Agent`
- [ ] `role`, `goal`, `backstory` exactos según §3.7
- [ ] `tools = []`
- [ ] `QualifierTask.create(profiled_leads: List[ProfiledLead], config: SearchConfig) -> Task`
- [ ] Task aplica la fórmula: `hormozi*0.35 + digital*0.25 + contact*0.25 + market*0.15`
- [ ] `digital_score`: inverso de `digital_maturity` ("ninguna"=10, "básica"=7, "intermedia"=4, "avanzada"=1)
- [ ] `contact_score`: phone(4) + email(3) + whatsapp(3) = máx 10
- [ ] Tiers según umbrales de config (`min_score_hot`, `min_score_warm`)
- [ ] `pitch_hook` generado por LLM: personalizado con nombre del negocio, sector, insight Challenger
- [ ] `contact_priority`: HOT ordenados por score DESC, luego WARM, luego COLD
- [ ] `discard_reason` solo si `tier = "COLD"` (1 línea explicando por qué)
- [ ] Output: `List[QualifiedLead]` JSON ordenado por `contact_priority`

---

### TICKET-020 · OutputAgent

```
Tipo:       feature
Prioridad:  P1
Est.:       1.5 h
Deps.:      TICKET-012, TICKET-002
```

**Descripción**  
Implementar `agents/output_agent.py`.

**Criterios de aceptación**
- [ ] `OutputAgent.create(settings: AppSettings) -> Agent`
- [ ] `role`, `goal`, `backstory` exactos según §3.8
- [ ] `tools = [ExcelExportTool]`
- [ ] `OutputTask.create(qualified_leads: List[QualifiedLead], report: RunReport, config: SearchConfig) -> Task`
- [ ] Task genera Excel con nombre `output/{output_filename}_{YYYYMMDD}.xlsx`
- [ ] Task genera `output/run_log_{YYYYMMDD_HHMMSS}.json` con `RunReport` completo
- [ ] Task imprime resumen en consola vía `rich.table.Table`

---

## EP-3 · Prompts & Structured Output

> Objetivo: prompts centralizados, versionables y probados de forma aislada. Todo output LLM usa `with_structured_output`.

---

### TICKET-021 · Prompts del ProfilerAgent

```
Tipo:       feature
Prioridad:  P0
Est.:       3 h
Deps.:      TICKET-002
```

**Descripción**  
Implementar `prompts/profiler_prompt.py` con el prompt completo de perfilización y schema de output.

**Criterios de aceptación**
- [ ] `PROFILER_SYSTEM_PROMPT`: define los 3 frameworks con ejemplos de aplicación
- [ ] `build_profiler_prompt(lead: EnrichedLead) -> str`: formatea el contexto del lead
- [ ] `ProfilerOutput` (Pydantic): schema completo de `CommercialProfile` para `with_structured_output`
- [ ] Prompt incluye contexto de Growth Guard (qué vende, a quién va dirigido)
- [ ] Sección Hormozi del prompt: incluye los 4 criterios con ejemplos de score 0/1/2/3
- [ ] Sección Challenger del prompt: describe los 5 perfiles de comprador del SEC
- [ ] Sección Cardone del prompt: criterios de commitment, objeciones típicas de PYMES Colombia
- [ ] Test: ejecutar prompt contra un lead de prueba con LLM mockeado → output parseable

---

### TICKET-022 · Prompts del QualifierAgent y EnrichmentAgent

```
Tipo:       feature
Prioridad:  P0
Est.:       2 h
Deps.:      TICKET-002
```

**Descripción**  
Implementar `prompts/qualifier_prompt.py` y `prompts/enrichment_prompt.py`.

**Criterios de aceptación**

**enrichment_prompt.py:**
- [ ] `EnrichmentOutput` (Pydantic): `lead_summary, estimated_size, main_sector, digital_maturity, sales_opportunity`
- [ ] Prompt incluye contexto del tipo de negocio esperado (PYMES de servicios, Colombia)
- [ ] `estimated_size` guiado por ejemplo: "micro = 1-5 empleados, pequeño = 5-20, mediano = 20-100"

**qualifier_prompt.py:**
- [ ] `QualifierOutput` (Pydantic): `final_score, tier, discard_reason, pitch_hook`
- [ ] `pitch_hook`: instrucción de máximo 2 oraciones, primera con el nombre del negocio, segunda con el insight de valor
- [ ] Prompt incluye ejemplos de pitch_hook bien y mal formateados

---

### TICKET-023 · Prompts del VisitTimingAgent

```
Tipo:       feature
Prioridad:  P1
Est.:       2 h
Deps.:      TICKET-002
```

**Descripción**  
Implementar `prompts/visit_timing_prompt.py`.

**Criterios de aceptación**
- [ ] `VisitTimingOutput` (Pydantic): schema completo de `VisitTiming` para `with_structured_output`
- [ ] `build_timing_prompt(lead: EnrichedLead) -> str`: serializa `opening_hours` y `popular_times` de forma legible
- [ ] Prompt incluye el algoritmo completo de §3.5 como instrucciones explícitas
- [ ] Prompt incluye ejemplo de output esperado (el JSON de §3.5 con talleres)
- [ ] Si `popular_times` vacío: prompt activa el modo "inferred" con instrucciones basadas en tipo de negocio
- [ ] Test: 2 casos — con datos reales de popular_times y sin ellos → outputs válidos y distintos

---

## EP-4 · Orquestación Crew

> Objetivo: ensamblar todos los agentes en un Crew con `Process.hierarchical`, flujo con re-iteración y RunReport.

---

### TICKET-024 · Crew assembly y flujo principal

```
Tipo:       feature
Prioridad:  P0
Est.:       4 h
Deps.:      TICKET-013 al TICKET-020, TICKET-004
```

**Descripción**  
Implementar el Crew principal en `crew.py` con `Process.hierarchical` y el flujo completo de 9 pasos.

**Criterios de aceptación**
- [ ] `ProspectingCrew(config: SearchConfig, settings: AppSettings)`
- [ ] Manager LLM: instanciado via `llm_factory.get_llm(settings)`
- [ ] `Crew(agents=[...], tasks=[...], process=Process.hierarchical, manager_llm=llm)`
- [ ] Tasks definidas en orden: Search → Maps → Scraper → Enrichment → VisitTiming || Profiler → Qualifier → Output
- [ ] VisitTiming y Profiler configurados para correr en paralelo (`async_execution=True`)
- [ ] `crew.kickoff()` retorna `RunReport`
- [ ] Log de `rich` en cada paso con conteo de leads y timing

**Lógica de re-iteración (PASO 8):**
- [ ] Después de Qualifier: si `HOT + WARM < config.target_hot_warm` Y `iterations < 3`
- [ ] → Crew Manager genera 3 queries nuevas (variaciones más específicas)
- [ ] → Re-ejecuta Search + Maps + Scraper + Enrichment (no sobreescribe leads existentes, hace merge)
- [ ] → `iterations += 1`, re-evalúa
- [ ] Log warning: `"Iteración {n}: solo {N} leads calificados, generando nuevas queries..."`

---

### TICKET-025 · DeduplicationTool (rapidfuzz)

```
Tipo:       feature
Prioridad:  P0
Est.:       2 h
Deps.:      TICKET-002
```

**Descripción**  
Implementar `tools/dedup_tool.py` con lógica de deduplicación fuzzy entre iteraciones.

**Criterios de aceptación**
- [ ] `DeduplicationTool.deduplicate(leads: List[RawLead]) -> List[RawLead]`
- [ ] Normalización de nombre: lowercase, `unidecode`, quitar sufijos legales (S.A.S, LTDA, S.A., SAS, CIA)
- [ ] Clave secundaria: primeros 7 dígitos del teléfono limpio (solo dígitos)
- [ ] Match fuzzy: `rapidfuzz.fuzz.token_sort_ratio(name_a, name_b) > 85` Y misma `city` → merge
- [ ] En merge: campos de Maps tienen prioridad sobre Brave > Scraper > DDG
- [ ] `merge_sources: List[str]` en el lead merged (ej: `["google_maps", "tavily"]`)
- [ ] Test: lista de 10 leads con 3 duplicados → retorna 7 leads únicos correctamente

---

## EP-5 · Output & Excel

> Los tests de esta epic confirman el artefacto final que verá el equipo de ventas.

---

### TICKET-026 · Integración end-to-end del Excel

```
Tipo:       feature
Prioridad:  P0
Est.:       2 h
Deps.:      TICKET-012, TICKET-019, TICKET-020
```

**Descripción**  
Validar que el Excel generado es correcto, completo y abre sin errores en Microsoft Excel y LibreOffice.

**Criterios de aceptación**
- [ ] Generar Excel con dataset de prueba de 20 leads (5 HOT, 10 WARM, 5 COLD)
- [ ] Verificar que las 5 hojas existen y tienen datos correctos
- [ ] Verificar colores de fila por tier con openpyxl
- [ ] Verificar que `contact_priority` es continuo (1, 2, 3... sin gaps) en hoja TODOS
- [ ] Verificar que hoja RESUMEN tiene: total leads, % por tier, fuentes, timestamp
- [ ] Verificar que columnas de timing tienen el formato correcto
- [ ] Archivo no supera 5MB para 200 leads (razonable para email/Drive)
- [ ] Nombre de archivo incluye fecha: `prospectos_talleres_bogota_20260321.xlsx`

---

### TICKET-027 · JSON Run Log

```
Tipo:       feature
Prioridad:  P2
Est.:       1 h
Deps.:      TICKET-024
```

**Descripción**  
Generar `run_log_{timestamp}.json` con metadata completa del run para auditoría y reproducibilidad.

**Criterios de aceptación**
- [ ] Archivo JSON válido con: `campaign_name`, `timestamp`, `duration_seconds`, `config_snapshot`, `RunReport` completo
- [ ] `config_snapshot`: copia del YAML usado (sin API keys, solo parámetros funcionales)
- [ ] `sources_breakdown`: `{tavily: N, brave: N, google_maps: N, duckduckgo: N}`
- [ ] `iterations_used: int`
- [ ] `leads_per_iteration: List[int]`
- [ ] `error_log: List[{agent, error, timestamp}]` (errores no fatales capturados)

---

## EP-6 · Testing & QA

> Objetivo: cobertura de los caminos críticos del pipeline. No coverage exhaustiva — foco en los contratos entre agentes y las herramientas de integración externa.

---

### TICKET-028 · Tests unitarios de Tools

```
Tipo:       chore
Prioridad:  P1
Est.:       3 h
Deps.:      TICKET-006 al TICKET-012, TICKET-025
```

**Descripción**  
Tests unitarios para cada herramienta con mocks de las APIs externas.

**Criterios de aceptación**
- [ ] `test_tavily_tool.py`: mock de `TavilyClient.search`, verifica parsing y filtrado por score
- [ ] `test_brave_tool.py`: mock httpx, verifica paginación y manejo de 429
- [ ] `test_maps_tool.py`: mock API Places, verifica extracción de fields y paginación
- [ ] `test_scraper_tool.py`: HTML estático de prueba con emails/phones/WhatsApp → verifica extracción
- [ ] `test_scraper_tool.py`: HTML con markers SPA → verifica que `detect_needs_js = True`
- [ ] `test_dedup_tool.py`: 10 leads con 3 duplicados → 7 únicos, merge correcto
- [ ] `test_excel_tool.py`: genera Excel con 3 leads → verifica hojas, colores y columnas
- [ ] Todos los tests pasan con `pytest tests/` sin acceso a internet

---

### TICKET-029 · Tests de integración de Agentes

```
Tipo:       chore
Prioridad:  P1
Est.:       3 h
Deps.:      TICKET-013 al TICKET-020
```

**Descripción**  
Tests de integración que verifican la cadena de transformación de datos entre agentes con LLM mockeado.

**Criterios de aceptación**
- [ ] `test_search_agent.py`: task con query mock → output parseable como `List[RawLead]`
- [ ] `test_enrichment_agent.py`: 5 RawLeads → 4 EnrichedLeads (1 dedup), campos LLM presentes
- [ ] `test_profiler_agent.py`: 3 EnrichedLeads → 3 ProfiledLeads con todos los scores en rango
- [ ] `test_visit_timing_agent.py`: lead con `popular_times` real → `timing_confidence = "high"` + ventanas correctas; lead sin `popular_times` → `timing_confidence = "inferred"`
- [ ] `test_qualifier_agent.py`: lead con todos los datos perfectos → `tier = "HOT"`; lead sin contacto → `tier = "COLD"` con `discard_reason`
- [ ] LLM mockeado con respuestas JSON predefinidas (no consume tokens en CI)

---

### TICKET-030 · Smoke test end-to-end (modo dev)

```
Tipo:       chore
Prioridad:  P1
Est.:       2 h
Deps.:      TICKET-024, todos los agentes
```

**Descripción**  
Test de humo que corre el pipeline completo en modo dev (DuckDuckGo sin API key, LLM real o mock) con `max_leads=5` para verificar que el flujo completo produce un Excel válido.

**Criterios de aceptación**
- [ ] `python main.py --config tests/fixtures/smoke_config.yaml --max-leads 5` → ejecuta sin crash
- [ ] `smoke_config.yaml`: `sources: [duckduckgo]`, query simple, `max_leads: 5`
- [ ] Al finalizar existe el archivo Excel en `output/`
- [ ] Excel tiene al menos 1 fila en alguna hoja (HOT, WARM o COLD)
- [ ] `run_log_*.json` generado correctamente
- [ ] Duración total < 120 segundos (no incluye popular_times scraping)
- [ ] Documentado en README: `# Quick smoke test` con el comando

---

### TICKET-031 · README y documentación mínima

```
Tipo:       chore
Prioridad:  P2
Est.:       1.5 h
Deps.:      TICKET-030 (smoke test OK)
```

**Descripción**  
README de uso del sistema para el equipo de Growth Guard.

**Criterios de aceptación**
- [ ] Sección: **Setup** (python version, pip install, playwright install, .env config)
- [ ] Sección: **Configurar una campaña** (editar `search_config.yaml` con ejemplo anotado)
- [ ] Sección: **Ejecutar** (`python main.py --config search_config.yaml`)
- [ ] Sección: **Entender el Excel** (descripción de cada grupo de columnas, tiers, scores)
- [ ] Sección: **Modo local sin API keys** (solo DuckDuckGo + OpenAI)
- [ ] Sección: **Quick smoke test**
- [ ] Sección: **Variables de entorno** (tabla con nombre, fuente de obtención, si es obligatoria)

---

## Dependencias Visuales

```
TICKET-001 (Setup)
    │
    ├── TICKET-002 (Modelos)
    │       └── TICKET-003 (Config)
    │               └── TICKET-004 (LLM Factory)
    │                       └── TICKET-005 (CLI main.py)
    │
    ├── TICKET-006 (Tavily) ──────────┐
    ├── TICKET-007 (Brave) ───────────┤
    ├── TICKET-008 (DDG) ─────────────┤── TICKET-013 (SearchAgent)
    ├── TICKET-009 (Maps) ────────────┼── TICKET-014 (MapsAgent)
    ├── TICKET-010 (PopularTimes) ────┼── TICKET-017 (VisitTimingAgent)
    ├── TICKET-011 (Scraper) ─────────┤── TICKET-015 (ScraperAgent)
    └── TICKET-012 (Excel) ───────────┘── TICKET-020 (OutputAgent)
                                      │
    TICKET-002 + TICKET-004 ──────────┼── TICKET-016 (EnrichmentAgent)
    TICKET-021 (Profiler Prompts) ────┼── TICKET-018 (ProfilerAgent)
    TICKET-022 (Qualifier Prompts) ───┼── TICKET-019 (QualifierAgent)
    TICKET-023 (Timing Prompts) ──────┘── TICKET-017 (VisitTimingAgent)

    TICKET-013 → 020 ─── TICKET-024 (Crew Assembly)
    TICKET-025 (Dedup) ──┘
         │
    TICKET-026 (Excel E2E)
    TICKET-027 (JSON Log)
         │
    TICKET-028 (Unit Tests Tools)
    TICKET-029 (Integration Tests)
    TICKET-030 (Smoke Test)
         │
    TICKET-031 (README)
```

---

## Cronograma Sugerido (1 dev senior)

```
SEMANA 1                          SEMANA 2               SEMANA 3
│                                 │                       │
├─ Día 1 ── EP-0 completo         ├─ Día 6 ── EP-2b:     ├─ Día 11 ── EP-4:
│           (T001-T005)           │          Enrichment,  │            Crew Assembly
│                                 │          VisitTiming  │            (T024, T025)
├─ Día 2 ── EP-1a:                │          (T016, T017) │
│           Tavily, Brave, DDG,   │                       ├─ Día 12 ── EP-5:
│           Dedup (T006-008, T025)├─ Día 7 ── EP-2c:     │            Excel E2E,
│                                 │          Profiler     │            JSON Log
├─ Día 3 ── EP-1b:                │          (T018)       │            (T026, T027)
│           Maps, PopularTimes    │                       │
│           (T009, T010)          ├─ Día 8 ── EP-2d:     ├─ Día 13 ── EP-6:
│                                 │          Qualifier,   │            Tests, Smoke,
├─ Día 4 ── EP-1c:                │          Output       │            README
│           Scraper, Excel        │          (T019, T020) │            (T028-T031)
│           (T011, T012)          │
│                                 ├─ Día 9 ── EP-3:
├─ Día 5 ── EP-2a:                │          Todos los
│           Search, Maps,         │          Prompts
│           Scraper agents        │          (T021-T023)
│           (T013-T015)           │
│                                 ├─ Día 10 ── Buffer/
                                  │           review
```

---

## Registro de Riesgos

| # | Riesgo | Probabilidad | Impacto | Mitigación |
|---|--------|-------------|---------|------------|
| R1 | `popular_times` no disponible en Places API (New) | Alta | Medio | PopularTimesTool scraping HTML (T010) ya es el fallback |
| R2 | Google Maps bloquea Playwright scraping | Media | Medio | User-Agent rotation; rate limiting 3s entre scrapes |
| R3 | Bedrock throttling en batches grandes | Media | Bajo | Fallback OpenAI automático (T004) |
| R4 | CrewAI `Process.hierarchical` inestable con 8+ agentes | Baja | Alto | Spike: probar con 3 agentes primero antes de T024 |
| R5 | LLM genera JSON no parseable en ProfilerAgent | Media | Medio | `with_structured_output` + Pydantic validation + retry 1x |
| R6 | DuckDuckGo bloquea requests frecuentes | Alta | Bajo | Es solo modo dev; en prod se usa Tavily+Brave |
| R7 | Sites con Cloudflare bloquean Playwright | Media | Bajo | Skip y marcar como `scrape_failed = True` en el lead |
