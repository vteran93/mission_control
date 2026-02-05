# Roadmap: Plataforma Agentic AI Standalone

Este roadmap convierte el prompt de `docs/AGENTIC_PROMPT.md` en un plan ejecutable con épicas, sprints y tickets específicos (user stories) para llegar al objetivo macro.

## Objetivo macro
Construir una plataforma **standalone** con agentes propios en LangChain, instancias LLM separadas por rol, interfaz de chat propia, panel de control configurable y observabilidad completa, permitiendo **crear agentes por copy/paste de role/alma/memory** sin tocar código.

## Épicas (alto nivel)
1. **E1 — Fundaciones & Arquitectura**
2. **E2 — Núcleo de Agentes (orquestación, roles, memoria)**
3. **E3 — Panel de Control (configuración y versiones)**
4. **E4 — Interfaz de Chat (multi‑agente)**
5. **E5 — Observabilidad & Operación**
6. **E6 — Seguridad, Entornos y Deploy**

---

## Plan de Sprints (propuesta)
> Duración sugerida: 2 semanas por sprint. Ajustar según capacidad del equipo.

### Sprint 0 — Discovery & Definición
**Objetivo:** Alinear visión, riesgos y arquitectura target.
- **E1-T1**: Inventario del sistema actual (openclaw/molbolt/clawde) y mapa de dependencias a reemplazar.
- **E1-T2**: Documento de arquitectura target (componentes, flujos, responsabilidades).
- **E1-T3**: Definición de roles base + prompts iniciales (system/developer).
- **E1-T4**: Backlog inicial + criterios de aceptación finales.

**Entregables:** Arquitectura target + backlog priorizado.

### Sprint 1 — Core de Agentes (MVP técnico)
**Objetivo:** Core operativo con agentes y memoria configurables.
- **E2-T1**: Servicio de orquestación LangChain (multi‑agente).
- **E2-T2**: Soporte de instancias LLM separadas por rol.
- **E2-T3**: Implementar almacenamiento de memoria por agente (sliding window + summary).
- **E2-T4**: Contrato de API para ejecución de agentes (REST/WS).

**Entregables:** Core de agentes funcional (sin UI).

### Sprint 2 — Panel de Control (MVP)
**Objetivo:** Configuración de agentes desde UI.
- **E3-T1**: CRUD de agentes con campos role/alma/memory.
- **E3-T2**: Gestión de prompts system/developer por agente.
- **E3-T3**: Selector de modelo LLM por agente (proveedor + modelo).
- **E3-T4**: Versionado básico de prompts (historial + rollback).

**Entregables:** Panel operativo con configuración de agentes sin código.

### Sprint 3 — Chat Multi‑agente (MVP)
**Objetivo:** UI de chat y conversaciones multi‑agente.
- **E4-T1**: UI de chat con selección de agentes.
- **E4-T2**: Conversaciones persistentes (threads).
- **E4-T3**: Integración API chat ↔ orquestador.

**Entregables:** Chat usable con agentes configurables.

### Sprint 4 — Observabilidad & Control
**Objetivo:** Logs, métricas, trazas y auditoría.
- **E5-T1**: Logging estructurado por agente y conversación.
- **E5-T2**: Métricas de uso por agente y costos LLM.
- **E5-T3**: Trazas de tool usage y decisiones.

**Entregables:** Dashboard operativo con observabilidad.

### Sprint 5 — Seguridad, Entornos y Deploy
**Objetivo:** Operación segura y escalable.
- **E6-T1**: Separación de entornos (dev/staging/prod) con configs.
- **E6-T2**: Autenticación y roles de usuario en panel.
- **E6-T3**: Pipeline de deploy (CI/CD) + backups.

**Entregables:** Plataforma lista para producción.

---

## Tickets detallados por épica

### E1 — Fundaciones & Arquitectura
- **E1-T1**: Mapear dependencias actuales y puntos de integración.
  - Criterio: Documento con módulos a reemplazar/reusar.
- **E1-T2**: Definir arquitectura target (diagramas y contratos de API).
  - Criterio: Diagrama en texto + flujos principales.
- **E1-T3**: Diseñar catálogo de roles iniciales y prompts base.
  - Criterio: Roles + prompts en formato versionable.
- **E1-T4**: Modelo de datos del panel (agentes, prompts, memoria, entornos).
  - Criterio: Esquema validado por backend.

### E2 — Núcleo de Agentes
- **E2-T1**: Orquestador multi‑agente con LangChain.
  - Criterio: Ejecutar N agentes con routing configurable.
- **E2-T2**: Instancias LLM separadas por rol.
  - Criterio: Cambiar proveedor/modelo por agente sin tocar código.
- **E2-T3**: Persistencia de memoria por agente.
  - Criterio: Sliding window + summary + vector store opcional.
- **E2-T4**: Templates de agente (duplicación por plantilla).
  - Criterio: Crear agente nuevo con copy/paste de role/alma/memory.

### E3 — Panel de Control
- **E3-T1**: CRUD de agentes y plantillas.
  - Criterio: Crear/editar/duplicar agentes desde UI.
- **E3-T2**: Editor de prompts con versionado.
  - Criterio: Historial + rollback por agente.
- **E3-T3**: Configuración de modelos por rol.
  - Criterio: Selector de modelo y parámetros (temp/top_p).
- **E3-T4**: Gestión de herramientas por agente.
  - Criterio: Habilitar/deshabilitar tools desde UI.

### E4 — Chat Multi‑agente
- **E4-T1**: UI de chat con contexto multi‑agente.
  - Criterio: Selección de agente y visualización de respuestas.
- **E4-T2**: Conversaciones persistentes.
  - Criterio: Threads con historial por usuario.
- **E4-T3**: Streaming de respuestas.
  - Criterio: Soporte SSE/WS.

### E5 — Observabilidad & Operación
- **E5-T1**: Logging estructurado.
  - Criterio: Logs por agente, request y tool.
- **E5-T2**: Métricas de costos LLM.
  - Criterio: Reporte por agente y por conversación.
- **E5-T3**: Auditoría de decisiones.
  - Criterio: Registro de prompts, tools y outputs.

### E6 — Seguridad, Entornos y Deploy
- **E6-T1**: Separación de entornos.
  - Criterio: Config por entorno con overrides.
- **E6-T2**: Autenticación y autorización.
  - Criterio: Roles (admin/editor/reader).
- **E6-T3**: CI/CD + backups.
  - Criterio: Pipeline y plan de recuperación.

---

## Dependencias críticas
- E2 depende de E1 (arquitectura + modelo de datos).
- E3 depende de E2 (configuración de agentes).
- E4 depende de E2 y E3 (orquestador + configuración).
- E5 depende de E2/E4 (eventos y logs).
- E6 puede ir en paralelo desde Sprint 2.

## Recomendaciones Scrum
- Refinamiento semanal del backlog.
- Definir *Definition of Done* por ticket (tests, doc, QA).
- Demo por sprint con feedback del equipo de producto.

