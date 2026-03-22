# Arquitectura de Requerimientos v2 — Sistema Multi-Agente de Prospección de Leads
**Framework**: CrewAI · Agnóstico a la Query · Perfil Hormozi + Challenger + Cardone · Output Excel

---

## Visión General

Sistema **multi-agente con CrewAI** que busca, enriquece, perfiliza y califica leads de forma autónoma para **cualquier nicho de mercado configurable**. La query es 100% externa (YAML/CLI), nunca hardcodeada. Cada lead recibe un **perfil comercial profundo** basado en tres frameworks de ventas (Hormozi, El Vendedor Desafiante, Vendes o Vendes / Cardone) junto a sus datos de contacto. La salida es un **archivo Excel** listo para usar como base de prospectos.

---

## 1. Diagrama de Arquitectura CrewAI

```
┌─────────────────────────────────────────────────────────────────────┐
│                    search_config.yaml / CLI args                    │
│          query, city, category, max_leads, sources, llm            │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │   CREW      │  Process.hierarchical
                    │  MANAGER    │  LLM: Bedrock / OpenAI
                    │  (Manager)  │  Delega tareas al crew
                    └──────┬──────┘
        ┌──────────────────┼─────────────────────────────┐
        ▼                  ▼                             ▼
 ┌────────────┐    ┌──────────────┐            ┌────────────────┐
 │  SEARCH    │    │   MAPS       │            │   SCRAPER      │
 │  AGENT     │    │   AGENT      │            │   AGENT        │
 │            │    │              │            │                │
 │ Tavily     │    │ Google Places│            │ httpx + BS4    │
 │ Brave API  │    │ API (New)    │            │ + Playwright   │
 │ DDG (local)│    │ textsearch + │            │ JS detection   │
 │            │    │ place details│            │                │
 └────┬───────┘    └──────┬───────┘            └───────┬────────┘
      │                   │                            │
      └───────────────────┴────────────────────────────┘
                          │ RawLeads
                   ┌──────▼──────┐
                   │ ENRICHMENT  │
                   │   AGENT     │
                   │ Deduplica + │
                   │ normaliza + │
                   │ LLM summary │
                   └──────┬──────┘
                          │ EnrichedLeads
                   ┌──────▼──────┐
                   │  PROFILER   │  ← NUEVO
                   │   AGENT     │
                   │             │
                   │ Hormozi     │
                   │ Challenger  │
                   │ Cardone     │
                   └──────┬──────┘
                          │ ProfiledLeads
                   ┌──────▼──────┐
                   │  QUALIFIER  │
                   │   AGENT     │
                   │ Score 1-10  │
                   │ HOT/WARM/   │
                   │ COLD + pitch│
                   └──────┬──────┘
                          │ QualifiedLeads
                   ┌──────▼──────┐
                   │   OUTPUT    │
                   │   AGENT     │
                   │  Excel .xlsx│
                   │  + JSON log │
                   └─────────────┘
```

---

## 2. Diseño Agnóstico a la Query

La query **nunca está en el código**. Se carga desde `search_config.yaml`:

```yaml
# search_config.yaml — editar sin tocar código
campaign:
  name: "Talleres Bogotá Q1-2026"
  queries:
    - "taller mecánico"
    - "mecánico automotriz"
    - "servicio técnico de autos"
  city: "Bogotá"
  country: "Colombia"
  language: "es"
  max_leads: 150
  sources:
    - tavily        # AI-search, requiere API key
    - brave         # Web search, requiere API key
    - google_maps   # Places API, requiere API key
    - duckduckgo    # Gratuito, sin API key (modo local/dev)
  scrape_websites: true
  scraper_concurrency: 10
  output_filename: "prospectos_talleres_bogota"

llm:
  provider: bedrock          # bedrock | openai
  primary_model: "anthropic.claude-3-5-sonnet-20241022-v2:0"
  fallback_model: "gpt-4o"
  temperature: 0.2

qualification:
  min_score_hot: 8.0
  min_score_warm: 5.0
  target_hot_warm: 80        # reintentar si se consiguen menos
```

---

## 3. Agentes CrewAI

### 3.1 Search Agent
```
role:         "Prospector Web de Negocios"
goal:         Encontrar URLs y datos crudos de negocios que coincidan
              con la query y ciudad configuradas
backstory:    Experto en búsqueda avanzada con múltiples motores.
              Genera variaciones de la query para maximizar cobertura.
tools:        [TavilySearchTool, BraveSearchTool, DuckDuckGoTool]
llm:          manager LLM
```

**Comportamiento**:
- Genera 3-5 variaciones de la query con sinónimos y variantes locales
- Detecta URLs de directorios (Páginas Amarillas, Clutch, FindLaw, etc.) y extrae sub-URLs
- Marca cada resultado con la fuente: `tavily | brave | duckduckgo`
- Itera hasta cubrir `max_leads` candidatos o agotar páginas

### 3.2 Maps Agent
```
role:         "Investigador Google Maps"
goal:         Extraer negocios de Google Places con datos oficiales
              (teléfono, dirección, rating, website, horario)
backstory:    Especialista en APIs de localización. Maneja paginación
              y enriquecimiento de Place Details.
tools:        [GooglePlacesTool, GooglePlaceDetailsTool]
llm:          (sin LLM, solo herramientas)
```

**Comportamiento**:
- `textsearch` con la query + ciudad
- Por cada resultado: llama `Place Details` con fields:
  `name, formatted_address, formatted_phone_number, website, rating,`
  `user_ratings_total, opening_hours, current_opening_hours, business_status,`
  **`popular_times`** ← datos de ocupación por hora y día
- Maneja `next_page_token` (sleep 2s entre páginas)
- Filtra `business_status != OPERATIONAL`

> **Nota sobre `popular_times`**: La Places API (New) devuelve `regularOpeningHours` y,
> cuando está disponible, los datos de ocupación relativa (`currentBusyness` y la serie
> horaria de cada día de la semana). Si el campo no llega vía API REST, el Maps Agent
> usa como fallback scraping del HTML de la página de Google Maps del `place_id`
> (la sección "Popular times" es accesible en el DOM via Playwright).

### 3.3 Scraper Agent
```
role:         "Analista de Presencia Digital"
goal:         Extraer emails, teléfonos, redes sociales, tecnologías
              y descripción del negocio desde su sitio web
backstory:    Web scraper avanzado que detecta automáticamente si un
              sitio necesita rendering JS y elige la estrategia correcta.
tools:        [StaticScraperTool, PlaywrightScraperTool]
llm:          (sin LLM, solo herramientas)
```

**Heurística de detección JS**:
```
Si el HTML estático tiene < 500 chars de body text
O contiene markers SPA (react-root, __NEXT_DATA__, ng-version)
→ usar Playwright
Sino → usar httpx + BeautifulSoup4
```

**Patrones de extracción**:
- Emails: `[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+`
- Teléfonos Colombia: `(\+?57)?[\s\-]?(60[0-9]|3[0-2][0-9])\d{7}`
- WhatsApp links: `wa\.me/|api\.whatsapp\.com/send`
- Schema.org `LocalBusiness` → nombre, dirección, teléfono structured
- Open Graph `og:description` → descripción del negocio
- Meta generator → tecnología (WordPress, Shopify, Wix, custom)

### 3.4 Enrichment Agent
```
role:         "Analista de Datos Comerciales"
goal:         Fusionar, deduplicar y normalizar todos los datos crudos
              en perfiles de lead coherentes y enriquecidos
backstory:    Experto en normalización de datos B2B y deduplicación
              fuzzy. Genera resúmenes concisos para equipos de ventas.
tools:        [DeduplicationTool, LLMEnrichTool]
llm:          manager LLM
```

**Lógica de deduplicación**:
- Clave primaria: normalizar nombre (lowercase, sin tildes, sin S.A.S/LTDA)  
  + primeros 7 dígitos del teléfono
- Si similitud nombre > 85% (fuzzy) Y misma ciudad → merge
- En merge: datos de Maps tienen prioridad sobre Brave > Scraper

**LLM Task** (structured output):
```
Input: perfil crudo del negocio
Output JSON:
  - lead_summary: str (2 líneas, qué hace el negocio)
  - estimated_size: "micro|pequeño|mediano"
  - main_sector: str
  - digital_maturity: "ninguna|básica|intermedia|avanzada"
  - sales_opportunity: str (1 línea, por qué Growth Guard les sirve)
```

### 3.5 Visit Timing Agent ← NUEVO
```
role:         "Analista de Ventanas de Contacto"
goal:         Determinar los mejores horarios de visita y llamada para
              cada lead usando sus métricas de ocupación de Google Maps
backstory:    Combina los datos de horarios de apertura y la curva de
              ocupación semanal (popular_times) para encontrar ventanas
              donde el negocio está abierto pero con baja afluencia.
              Un vendedor que llega en el momento correcto tiene 3x más
              posibilidades de recibir atención del decisor.
tools:        []
llm:          manager LLM (structured output obligatorio)
```

**Lógica LLM para timing**:

```
Input:
  opening_hours: dict          # horarios de apertura por día
  popular_times: List[dict]    # ocupación relativa 0-100 por hora, por día
  timezone: str                # "America/Bogota"

Algoritmo LLM:
  1. Para cada día con popular_times disponible:
     → Identificar franjas donde ocupación < 40% Y negocio está abierto
     → Excluir primera hora de apertura (setup del negocio)
     → Excluir última hora antes de cierre (cierre anticipado)
     → Dar preferencia a franjas entre 10:00-12:00 y 14:00-17:00 (decisores disponibles)
  2. Rankear las 3 mejores ventanas por día con justificación
  3. Identificar el mejor día de la semana para visita presencial
  4. Identificar el mejor horario para llamada (menor ocupación = menor estrés del dueño)
  5. Si popular_times no disponible → inferir desde tipo de negocio + horarios generales

Output JSON:
  best_visit_windows: List[{day, time_start, time_end, busyness_pct, reason}]
  best_call_time: {day, time, reason}
  worst_times: List[{day, time_range, reason}]   # picos de ocupación a evitar
  timing_confidence: str    # "high" (datos reales) | "inferred" (sin popular_times)
  timing_summary: str       # texto accionable de 1 línea para el vendedor
```

**Ejemplo de output**:
```json
{
  "best_visit_windows": [
    {"day": "martes",   "time_start": "10:00", "time_end": "11:30",
     "busyness_pct": 18, "reason": "punto más bajo antes del mediodía"},
    {"day": "jueves",   "time_start": "15:00", "time_end": "16:30",
     "busyness_pct": 22, "reason": "valle post-almuerzo, decisor más tranquilo"},
    {"day": "miércoles","time_start": "10:30", "time_end": "12:00",
     "busyness_pct": 25, "reason": "día de menor tráfico semanal"}
  ],
  "best_call_time": {"day": "martes", "time": "10:15",
                     "reason": "mínimo histórico de ocupación semanal"},
  "worst_times": [
    {"day": "sábado",    "time_range": "09:00-13:00", "reason": "pico máximo 87%"},
    {"day": "viernes",  "time_range": "11:00-13:00", "reason": "cierre de semana 74%"}
  ],
  "timing_confidence": "high",
  "timing_summary": "Visitar martes 10-11:30 o jueves 15-16:30. Evitar sábados."
}
```

---

### 3.6 Profiler Agent ← NUEVO
```
role:         "Estratega Comercial de Perfilización"
goal:         Evaluar cada lead contra tres frameworks de ventas para
              identificar el perfil de compra, urgencia y ángulo de entrada
backstory:    Conoce a fondo los frameworks de Hormozi ($100M Leads),
              el Vendedor Desafiante (SEC) y Grant Cardone (Vendes o Vendes).
              Traduce datos operativos en insight comercial accionable.
tools:        []
llm:          manager LLM (structured output obligatorio)
```

**Ver Sección 5 — Framework de Perfilización para el detalle completo.**

### 3.7 Qualifier Agent
```
role:         "Clasificador de Oportunidades de Venta"
goal:         Asignar score final, tier y primer mensaje de contacto
              personalizado para cada lead perfilizado
backstory:    Combina datos operativos + perfil comercial para priorizar
              la base de prospectos con criterios objetivos y reproducibles.
tools:        []
llm:          manager LLM (structured output obligatorio)
```

### 3.8 Output Agent
```
role:         "Generador de Base de Prospectos"
goal:         Exportar la base calificada como Excel profesional con
              múltiples hojas, colores por tier y columnas ordenadas
backstory:    Especialista en reportes comerciales para equipos de ventas.
tools:        [ExcelExportTool]
llm:          (sin LLM)
```

---

## 4. Herramientas de Búsqueda (Search Tools)

### Comparativa y Selección

| Tool | API Key | Costo | Calidad | Uso recomendado |
|---|---|---|---|---|
| **Tavily** | Sí | Freemium (1k/mes) | ★★★★★ AI-optimized | Primario en producción |
| **Brave Search** | Sí | Freemium (2k/mes) | ★★★★☆ Web indexing | Secundario, alta cobertura |
| **DuckDuckGo** | No | Gratuito | ★★★☆☆ Limitado | Desarrollo local / fallback |
| **SearXNG** | No (self-host) | Gratuito | ★★★★☆ Configurable | On-premise / privado |
| **Serper** | Sí | Freemium (2.5k/mes) | ★★★★☆ Google results | Alternativa a Brave |

### Implementación Recomendada

```
Modo PRODUCTION:  Tavily (primario) + Brave (secundario)
Modo DEV/LOCAL:   DuckDuckGo (sin API key, gratis, package: duckduckgo-search)
Modo ON-PREMISE:  SearXNG self-hosted (Docker: searxng/searxng)
```

**DuckDuckGo como herramienta local** (sin API key):
```python
# pip install duckduckgo-search
from duckduckgo_search import DDGS
with DDGS() as ddgs:
    results = ddgs.text("taller mecánico Bogotá", max_results=20)
```

**SearXNG self-hosted** (máxima privacidad):
```bash
docker run -d -p 8080:8080 searxng/searxng
# Endpoint: GET http://localhost:8080/search?q=query&format=json
```

---

## 5. Framework de Perfilización (Profiler Agent)

El **Profiler Agent** aplica tres lentes sobre cada lead enriquecido y genera un perfil estructurado. Este perfil va incluido como columnas en el Excel final.

### 5.1 Perfil Hormozi ($100M Leads / $100M Offers)

Hormozi define al cliente ideal como una **"multitud hambrienta"** con 4 características:
problema urgente + poder adquisitivo + accesibilidad + mercado creciente.

**Dimensiones evaluadas**:

| Dimensión | Descripción | Score 0-3 |
|---|---|---|
| **Urgency** | ¿El negocio tiene un dolor activo hoy? (bajo volumen, sin sistema, caótico) | 0-3 |
| **Buying Power** | ¿Puede pagar? (tamaño estimado, facturación implícita, tipo de negocio) | 0-3 |
| **Accessibility** | ¿Es contactable? (teléfono + email + WhatsApp verificados) | 0-3 |
| **Market Fit** | ¿Su sector está creciendo o tiene dolor específico que Growth Guard resuelve? | 0-3 |

**Hormozi Score** = suma (0-12) → normalizado a 0-10

**Etiqueta Hormozi**:
- 8-10 → `STARVING_CROWD` (máxima prioridad)
- 5-7 → `WARM_MARKET`
- 0-4 → `COLD_MARKET`

### 5.2 Perfil Challenger (El Vendedor Desafiante — SEC Research)

El Challenger define **5 perfiles de comprador**. Para prospectar, el objetivo es identificar si hay un **Movilizador** o **Buscador de Información** al que llegar primero. También evalúa la **sofisticación de compra** del cliente.

**Dimensiones evaluadas**:

| Dimensión | Descripción | Valor |
|---|---|---|
| **Buyer Type** | Inferido del perfil digital: activo/pasivo/resistente | `mobilizer|talker|blocker|unknown` |
| **Solution Awareness** | ¿Ya saben que necesitan una herramienta de ventas? | `aware|unaware|searching` |
| **Complexity** | ¿La venta necesitará múltiples interacciones/decisores? | `simple|complex` |
| **Insight Angle** | Qué insight del Challenger aplica (costo de no cambiar, eficiencia, diferenciación) | texto libre |

**Challenger Approach** (generado por LLM):
> "Antes de presentar Growth Guard, enseñarles que [insight específico al negocio]"

### 5.3 Perfil Cardone (Vendes o Vendes / Grant Cardone)

Cardone establece que **siempre se vende algo**: o el vendedor vende el producto, o el cliente vende su excusa. Para prospectar, se evalúa la **resistencia esperada** y el **potencial de seguimiento**.

**Dimensiones evaluadas**:

| Dimensión | Descripción | Valor |
|---|---|---|
| **Commitment Level** | ¿Cuánto esfuerzo requerirá este lead? (señales de disponibilidad) | `high|medium|low` |
| **Objection Type** | Objeción principal anticipada | `precio|tiempo|no_necesita|ya_tiene_algo|desconfianza` |
| **Followup Potential** | ¿Cuántos toques se estiman para cerrar? | `1-2|3-5|5+` |
| **Entry Channel** | Canal de contacto más efectivo para este lead | `whatsapp|llamada|email|visita` |

**Cardone Action Line** (generado por LLM):
> "Primer contacto por [canal], abordar objeción [tipo], preparar 3 seguimientos"

### 5.4 Perfil Combinado (Output del Profiler Agent)

```python
CommercialProfile:
  # Hormozi
  hormozi_urgency: int           # 0-3
  hormozi_buying_power: int      # 0-3
  hormozi_accessibility: int     # 0-3
  hormozi_market_fit: int        # 0-3
  hormozi_score: float           # 0-10
  hormozi_label: str             # STARVING_CROWD | WARM_MARKET | COLD_MARKET

  # Challenger
  challenger_buyer_type: str     # mobilizer | talker | blocker | unknown
  challenger_awareness: str      # aware | unaware | searching
  challenger_complexity: str     # simple | complex
  challenger_insight: str        # insight recomendado (LLM generated)

  # Cardone
  cardone_commitment: str        # high | medium | low
  cardone_objection: str         # tipo de objeción anticipada
  cardone_followup_est: str      # "1-2" | "3-5" | "5+"
  cardone_entry_channel: str     # whatsapp | llamada | email | visita
  cardone_action_line: str       # primera acción recomendada (LLM generated)

  # Síntesis
  composite_profile_score: float # promedio ponderado de los 3 frameworks
  pitch_hook: str                # primer mensaje personalizado (LLM generated)
```

---

## 6. Modelos de Datos

```python
# ── Entrada ──────────────────────────────────────────
SearchConfig:
  campaign_name: str
  queries: List[str]           # lista de queries, nunca una sola
  city: str
  country: str
  language: str                # "es" | "en"
  max_leads: int
  sources: List[str]           # ["tavily","brave","google_maps","duckduckgo"]
  scrape_websites: bool
  scraper_concurrency: int
  output_filename: str
  llm_provider: str            # "bedrock" | "openai"

# ── Crudo (después de Search + Maps) ─────────────────
RawLead:
  source: str                  # "google_maps" | "tavily" | "brave" | "duckduckgo"
  name: str
  address: str
  phone: str
  email: str
  website: str
  rating: float
  reviews_count: int
  lat: float
  lng: float
  social_links: dict           # {instagram, facebook, tiktok, linkedin}
  raw_snippet: str
  place_id: str                # de Google Maps, "" si no aplica
  opening_hours: dict          # {lunes: ["08:00-18:00"], ...} de Places API
  popular_times: List[dict]    # [{day: "lunes", hours: [{hour: 8, busyness: 35}, ...]}, ...]
  timezone: str                # "America/Bogota"

# ── Enriquecido (después de Scraper + EnrichmentAgent) ──
EnrichedLead(RawLead):
  emails_scraped: List[str]    # emails encontrados en el sitio
  phones_scraped: List[str]
  has_whatsapp: bool
  whatsapp_number: str
  technology_stack: List[str]  # ["WordPress", "Wix", "custom"]
  lead_summary: str            # LLM: qué hace el negocio
  estimated_size: str          # "micro" | "pequeño" | "mediano"
  main_sector: str
  digital_maturity: str        # "ninguna|básica|intermedia|avanzada"
  sales_opportunity: str       # LLM: por qué Growth Guard les sirve

# ── Perfilizado (después de ProfilerAgent) ────────────
ProfiledLead(EnrichedLead):
  profile: CommercialProfile   # ver Sección 5.4

# ── Timing de contacto (después de VisitTimingAgent) ────
VisitTiming:
  best_visit_windows: List[dict]  # [{day, time_start, time_end, busyness_pct, reason}]
  best_call_time: dict            # {day, time, reason}
  worst_times: List[dict]         # [{day, time_range, reason}]
  timing_confidence: str          # "high" | "inferred"
  timing_summary: str             # 1 línea accionable para el vendedor

# ── Enriquecido con timing ────────────────────────────
ProfiledLead(EnrichedLead):
  profile: CommercialProfile      # ver Sección 5.4
  visit_timing: VisitTiming       # ← NUEVO

# ── Calificado / Output final ─────────────────────────
QualifiedLead(ProfiledLead):
  final_score: float           # 1.0 - 10.0
  tier: str                    # "HOT" | "WARM" | "COLD"
  discard_reason: str | None   # si tier == COLD
  contact_priority: int        # orden de contacto (1 = primero)
```

---

## 7. Flujo de Ejecución CrewAI

```
python main.py --config search_config.yaml

PASO 1 — Crew Manager lee SearchConfig
         → expande queries (3-5 variantes por query configurada)
         → distribuye al Search Agent y Maps Agent en PARALELO

PASO 2 — Search Agent (Tavily + Brave + DDG)
         → entrega List[RawLead] con source="web"

PASO 3 — Maps Agent (Google Places)
         → entrega List[RawLead] con source="google_maps"

PASO 4 — Scraper Agent
         → recibe URLs de websites de RawLeads
         → scraping en lotes de `scraper_concurrency`
         → enriquece cada RawLead con ScrapedProfile

PASO 5 — Enrichment Agent
         → deduplica el pool combinado
         → llama LLM para lead_summary, estimated_size, sales_opportunity
         → entrega List[EnrichedLead]

PASO 5b — Visit Timing Agent (en PARALELO con Profiler Agent)
         → recibe opening_hours + popular_times de cada EnrichedLead
         → si popular_times vacío: intenta scraping HTML de Google Maps (Playwright)
         → llama LLM para calcular best_visit_windows, best_call_time, worst_times
         → entrega VisitTiming por lead

PASO 6 — Profiler Agent
         → por cada EnrichedLead: LLM structured output con 3 frameworks
         → entrega List[ProfiledLead]

PASO 7 — Qualifier Agent
         → calcula final_score (ver Sección 8)
         → clasifica HOT / WARM / COLD
         → genera pitch_hook personalizado
         → ordena por contact_priority

PASO 8 — Crew Manager evalúa:
         ¿HOT + WARM >= target_hot_warm?
         SI  → continúa al Output Agent
         NO → genera nuevas query variations y repite desde PASO 2
              (máximo 3 iteraciones)

PASO 9 — Output Agent
         → genera Excel con múltiples hojas + JSON log
         → imprime resumen en consola con rich
```

---

## 8. Criterios de Calificación Final

### Fórmula de Score

```
final_score = (
  hormozi_score       * 0.35 +   # urgencia + poder de compra
  digital_score       * 0.25 +   # presencia digital inversa (sin sistema = oportunidad)
  contact_score       * 0.25 +   # qué tan contactable es
  market_score        * 0.15     # potencial del sector
) → escala 1-10
```

### Tiers

```yaml
HOT (8.0 - 10.0):
  criterios:
    - hormozi_label: STARVING_CROWD
    - Teléfono Y email/WhatsApp verificados
    - Rating ≥ 4.0 con ≥ 20 reseñas (negocio activo)
    - digital_maturity: básica o ninguna (sin sistema de ventas visible)
    - NO cadenas ni franquicias

WARM (5.0 - 7.9):
  criterios:
    - Al menos un contacto disponible (phone OR email)
    - Reviews ≥ 5
    - digital_maturity: cualquiera
    - Puede ser pequeño con potencial

COLD (< 5.0):
  criterios:
    - Sin datos de contacto accesibles
    - Franquicia o cadena grande
    - business_status: CLOSED_PERMANENTLY
    - Sin reseñas ni actividad reciente
    → descartado con discard_reason en Excel
```

---

## 9. Output: Excel Enriquecido

### Estructura de Hojas

```
leads_prospectos_[fecha].xlsx
│
├── 📋 HOT — Leads prioritarios (tier=HOT, ordenados por score)
├── 📋 WARM — Leads secundarios (tier=WARM)
├── 📋 COLD — Descartados (tier=COLD, con razón)
├── 📋 TODOS — Base completa sin filtro
└── 📊 RESUMEN — Stats del run: totales, fuentes, timing
```

### Columnas Excel (en este orden)

```
CONTACTO
  contact_priority | tier | final_score | name | phone | email
  whatsapp_number  | website | address | city

DATOS OPERATIVOS
  source | rating | reviews_count | business_status
  has_whatsapp | technology_stack | digital_maturity | estimated_size

PERFIL HORMOZI
  hormozi_score | hormozi_label | hormozi_urgency | hormozi_buying_power
  hormozi_accessibility | hormozi_market_fit

PERFIL CHALLENGER
  challenger_buyer_type | challenger_awareness | challenger_complexity
  challenger_insight

PERFIL CARDONE
  cardone_commitment | cardone_objection | cardone_followup_est
  cardone_entry_channel | cardone_action_line

TIMING DE CONTACTO
  timing_summary | timing_confidence
  best_call_day | best_call_time
  best_visit_day | best_visit_window
  avoid_times

PITCH
  lead_summary | sales_opportunity | pitch_hook
```

### Formato Visual
- Filas HOT: fondo verde claro `#C6EFCE`
- Filas WARM: fondo amarillo `#FFEB9C`
- Filas COLD: fondo gris `#D9D9D9`
- Header: negrita con fondo oscuro, texto blanco
- Columna `pitch_hook`: wrap text, ancho 60
- Columna `timing_summary`: fondo azul claro `#DEEAF1`, wrap text, ancho 50
- Columna `avoid_times`: fondo rojo claro `#FCE4D6`
- Columna `timing_confidence` = `"inferred"`: cursiva gris (sin datos reales de Maps)

---

## 10. Stack Tecnológico

| Capa | Tecnología | Versión |
|---|---|---|
| Orquestación | `crewai` | ≥ 0.80 |
| Process | `crewai.Process.hierarchical` | — |
| LLM Primario | AWS Bedrock `claude-3-5-sonnet-20241022-v2:0` | via `langchain-aws` |
| LLM Fallback | OpenAI `gpt-4o` | via `langchain-openai` |
| Búsqueda AI | `tavily-python` + CrewAI `TavilySearchResults` | ≥ 0.5 |
| Búsqueda web | Brave Search API REST | v1 |
| Búsqueda local | `duckduckgo-search` (sin API key) | ≥ 6.0 |
| Mapas | Google Places API (New) | REST |
| Scraping estático | `httpx` + `beautifulsoup4` | — |
| Scraping dinámico | `playwright` (async) | ≥ 1.44 |
| Popular Times | Playwright scraping de HTML Google Maps | — |
| Deduplicación fuzzy | `rapidfuzz` | ≥ 3.0 |
| Output Excel | `openpyxl` | ≥ 3.1 |
| Config | `pydantic-settings` + `PyYAML` | — |
| Consola | `rich` | ≥ 13 |

---

## 11. Estructura de Archivos

```
client_prospective_agents/
├── main.py                       ← entry point: carga config, lanza Crew
├── search_config.yaml            ← ÚNICA fuente de verdad de la query
├── config.py                     ← SearchConfig pydantic model + env loader
├── models.py                     ← RawLead, EnrichedLead, ProfiledLead, QualifiedLead
│
├── agents/
│   ├── search_agent.py           ← BraveSearchAgent + TavilyAgent + DDGAgent
│   ├── maps_agent.py             ← GoogleMapsAgent (Places API)
│   ├── scraper_agent.py          ← WebScraperAgent (httpx/BS4 + Playwright)
│   ├── enrichment_agent.py       ← EnrichmentAgent (dedup + LLM summary)
│   ├── profiler_agent.py         ← ProfilerAgent (Hormozi + Challenger + Cardone)
│   ├── visit_timing_agent.py     ← VisitTimingAgent (popular_times + LLM analysis)
│   ├── qualifier_agent.py        ← QualifierAgent (score + tier + pitch)
│   └── output_agent.py           ← ExcelOutputAgent (openpyxl)
│
├── tools/
│   ├── tavily_tool.py            ← CrewAI Tool wrapper para Tavily
│   ├── brave_tool.py             ← CrewAI Tool wrapper para Brave
│   ├── duckduckgo_tool.py        ← CrewAI Tool wrapper para DDG (local/free)
│   ├── maps_tool.py              ← CrewAI Tool wrapper para Google Places
│   ├── scraper_tool.py           ← StaticScraperTool + PlaywrightScraperTool
│   ├── popular_times_tool.py     ← PopularTimesTool (scraping HTML Google Maps via Playwright)
│   ├── dedup_tool.py             ← FuzzyDeduplicationTool (rapidfuzz)
│   └── excel_tool.py             ← ExcelExportTool (openpyxl)
│
├── prompts/
│   ├── enrichment_prompt.py      ← Prompt estructurado para EnrichmentAgent LLM
│   ├── profiler_prompt.py        ← Prompt estructurado para ProfilerAgent LLM
│   ├── visit_timing_prompt.py    ← Prompt estructurado para VisitTimingAgent LLM
│   └── qualifier_prompt.py       ← Prompt estructurado para QualifierAgent LLM
│
├── output/                       ← generado en runtime
│   ├── leads_[campaign]_[date].xlsx
│   └── run_log_[date].json
│
├── requirements.txt
├── requirements.md               ← este archivo
└── .env.example
```

---

## 12. Variables de Entorno

```bash
# LLM — Bedrock (primario)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_DEFAULT_REGION=us-east-1
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0

# LLM — OpenAI (fallback)
OPENAI_API_KEY=

# Search APIs
TAVILY_API_KEY=              # https://app.tavily.com (1k búsquedas/mes gratis)
BRAVE_API_KEY=               # https://api.search.brave.com
# DUCKDUCKGO: no requiere API key (usa duckduckgo-search package)
# SEARXNG: si self-hosted → SEARXNG_BASE_URL=http://localhost:8080

# Maps
GOOGLE_MAPS_API_KEY=         # habilitar: Places API (New)

# Runtime (override del YAML si se prefiere)
LLM_PROVIDER=bedrock         # bedrock | openai
```

---

## 1. Diagrama de Componentes

```
┌─────────────────────────────────────────────────────────────────┐
│                     ORQUESTADOR (LLM Agent)                     │
│              Decide flujo, maneja errores, itera                │
│              LLM: Bedrock (Claude 3.5) | OpenAI (GPT-4o)        │
└────┬──────────┬──────────┬──────────┬──────────────────────────┘
     │          │          │          │
     ▼          ▼          ▼          ▼
┌─────────┐ ┌──────────┐ ┌────────┐ ┌──────────────┐
│ SEARCH  │ │  MAPS    │ │SCRAPER │ │ QUALIFIER    │
│  AGENT  │ │  AGENT   │ │ AGENT  │ │   AGENT      │
│         │ │          │ │        │ │              │
│ Brave   │ │ Google   │ │BeautSp │ │ LLM Score    │
│ Search  │ │ Maps API │ │Requests│ │ + Criteria   │
│   API   │ │ Places   │ │Playwright│ │              │
└─────────┘ └──────────┘ └────────┘ └──────────────┘
     │          │          │          │
     └──────────┴──────────┴──────────┘
                           │
                    ┌──────▼──────┐
                    │  ENRICHMENT │
                    │    AGENT    │
                    │  Fusiona y  │
                    │ deduplica   │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   OUTPUT    │
                    │  CSV / JSON │
                    │  + Report   │
                    └─────────────┘
```

---

## 2. Agentes y Responsabilidades

### 2.1 Orquestador (`OrchestratorAgent`)
- **LLMs**: AWS Bedrock (`anthropic.claude-3-5-sonnet`) + OpenAI (`gpt-4o`) como fallback
- **Función**: Recibe la query objetivo (ej. `"talleres mecánicos Bogotá"`), planifica subtareas, distribuye trabajo a agentes, reintenta fallos, decide cuándo hay suficientes leads, genera reporte final
- **Framework**: `langchain` con `AgentExecutor` y herramientas custom
- **Entrada**: `SearchConfig` (query, ciudad, categoría, max_leads)
- **Salida**: `List[Lead]` calificados + `RunReport`

### 2.2 Search Agent (`BraveSearchAgent`)
- **API**: Brave Search API (`/res/v1/web/search`)
- **Función**: Genera variaciones de queries (LLM-assisted), busca en web abierta, extrae URLs de negocios relevantes, detecta directorios de empresas (Páginas Amarillas, Clutch, etc.)
- **Herramientas**: `brave_web_search`, `brave_local_search` (si disponible)
- **Output**: `List[SearchResult]` → `{url, title, snippet, domain}`

### 2.3 Maps Agent (`GoogleMapsAgent`)
- **API**: Google Places API (`nearbysearch`, `textsearch`, `Place Details`)
- **Función**: Busca negocios por coordenadas + tipo, extrae nombre, dirección, teléfono, rating, horario, website, place_id
- **Paginación**: Maneja `next_page_token` automáticamente
- **Output**: `List[PlaceLead]` → `{place_id, name, address, phone, rating, website, lat, lng}`

### 2.4 Scraper Agent (`WebScraperAgent`)
- **Librerías**: `httpx` + `BeautifulSoup4` (HTML estático), `playwright` (sitios con JS)
- **Función**: Recibe URLs de SearchAgent o MapAgent, extrae emails, teléfonos, redes sociales, descripción del negocio, tecnologías usadas, formularios de contacto
- **Lógica inteligente**: Detecta si el sitio necesita JS rendering; extrae metadatos Open Graph y schema.org
- **Patrones regex**: emails, teléfonos colombianos (`+57`, `60X`, `31X`), WhatsApp links
- **Output**: `ScrapedProfile` → `{emails, phones, social_links, description, technologies}`

### 2.5 Enrichment Agent (`EnrichmentAgent`)
- **Función**: Fusiona datos de los 3 agentes anteriores para el mismo negocio (deduplicación por nombre + teléfono), normaliza campos, enriquece con LLM (infiere sector, tamaño estimado, potencial de venta)
- **LLM Task**: Dado el perfil crudo → generar `lead_summary` de 2 líneas y `sales_angle` para Growth Guard
- **Output**: `EnrichedLead`

### 2.6 Qualifier Agent (`QualifierAgent`)
- **LLM**: Bedrock o OpenAI
- **Función**: Evalúa cada lead contra criterios de Growth Guard (tamaño, digitalización, potencial), asigna score 1-10, clasifica en `HOT / WARM / COLD`, genera `pitch_hook` personalizado
- **Criterios configurables**: `QualificationCriteria` via YAML/env
- **Output**: `QualifiedLead` con `score`, `tier`, `pitch_hook`, `discard_reason`

---

## 3. Modelos de Datos

```python
# Entrada
SearchConfig:
  query: str               # "taller mecánico"
  city: str                # "Bogotá"
  max_leads: int           # 150
  sources: List[str]       # ["brave", "maps", "scraper"]
  qualification_criteria: dict

# Intermedio
RawLead:
  source: str              # "google_maps" | "brave" | "scraped"
  name: str
  address: str
  phone: str
  email: str
  website: str
  rating: float
  reviews_count: int
  lat: float
  lng: float
  social_links: dict
  raw_snippet: str

# Enriquecido
EnrichedLead(RawLead):
  lead_summary: str        # generado por LLM
  sales_angle: str         # ángulo de venta para Growth Guard
  estimated_size: str      # "micro" | "pequeño" | "mediano"
  has_website: bool
  has_whatsapp: bool
  digital_presence_score: int  # 0-10

# Calificado (output final)
QualifiedLead(EnrichedLead):
  score: float             # 1.0 - 10.0
  tier: str                # "HOT" | "WARM" | "COLD"
  pitch_hook: str          # primer mensaje sugerido
  discard_reason: str | None
```

---

## 4. Flujo de Ejecución

```
1. Usuario define SearchConfig (query, ciudad, max_leads)
2. Orquestador lanza MapsAgent + BraveSearchAgent en PARALELO
3. BraveSearchAgent detecta URLs → lanza ScraperAgent en lotes de 10
4. MapsAgent agota paginación → entrega PlaceLeads
5. EnrichmentAgent fusiona resultados, deduplica
6. QualifierAgent procesa en batch (LLM con structured output)
7. Orquestador evalúa: ¿suficientes HOT+WARM? → si no, genera nuevas queries y repite
8. Output: CSV enriquecido + JSON + reporte de ejecución
```

---

## 5. Stack Tecnológico

| Capa | Tecnología |
|---|---|
| Orquestación | `langchain` + `langgraph` (StateGraph) |
| LLM Primario | AWS Bedrock `anthropic.claude-3-5-sonnet-20241022` |
| LLM Fallback | OpenAI `gpt-4o` via `langchain-openai` |
| Búsqueda web | Brave Search API REST |
| Mapas | Google Places API (New) |
| Scraping estático | `httpx` + `BeautifulSoup4` |
| Scraping dinámico | `playwright` (async) |
| Paralelismo | `asyncio` + `asyncio.gather` |
| Configuración | `pydantic-settings` + `.env` |
| Output | `csv`, `json`, `rich` (consola) |

---

## 6. Estructura de Archivos

```
search_talleres/
├── search_talleres.py        ← entry point (reemplaza el actual)
├── config.py                 ← SearchConfig, env vars, criteria YAML
├── models.py                 ← RawLead, EnrichedLead, QualifiedLead
├── agents/
│   ├── orchestrator.py       ← OrchestratorAgent (LangGraph)
│   ├── search_agent.py       ← BraveSearchAgent
│   ├── maps_agent.py         ← GoogleMapsAgent
│   ├── scraper_agent.py      ← WebScraperAgent
│   ├── enrichment_agent.py   ← EnrichmentAgent
│   └── qualifier_agent.py    ← QualifierAgent
├── tools/
│   ├── brave_tool.py         ← LangChain Tool wrapper
│   ├── maps_tool.py          ← LangChain Tool wrapper
│   └── scraper_tool.py       ← LangChain Tool wrapper
├── output/
│   └── talleres_bogota.csv
├── requirements.txt
└── .env.example
```

---

## 7. Variables de Entorno Requeridas

```bash
# LLM
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_DEFAULT_REGION=us-east-1
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
OPENAI_API_KEY=

# APIs
BRAVE_API_KEY=
GOOGLE_MAPS_API_KEY=

# Configuración
MAX_LEADS=150
TARGET_QUERY="taller mecanico"
TARGET_CITY="Bogotá"
SCRAPER_CONCURRENCY=10
LLM_PROVIDER=bedrock   # bedrock | openai
```

---

## 8. Criterios de Calificación (Growth Guard)

```yaml
HOT (score 8-10):
  - Tiene website pero sin presencia digital fuerte
  - Teléfono y/o WhatsApp verificado
  - Rating ≥ 4.0 con ≥ 20 reseñas (activo)
  - Sin evidencia de software de gestión de ventas

WARM (score 5-7):
  - Solo redes sociales, sin website
  - Teléfono disponible
  - Negocios con ≥ 10 reseñas

COLD (score 1-4):
  - Sin contacto accesible
  - Sin presencia digital
  - Cadenas o franquicias grandes
```
