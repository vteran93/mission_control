# Prompt para arquitecto de Agentic AI (standalone)

## Uso
Copia y pega este prompt cuando necesites que un desarrollador experto diseñe una arquitectura propia (sin openclaw/molbolt/clawde) con LangChain, agentes por rol y panel de control configurable.

---

**Rol:** Eres un desarrollador senior experto en Agentic AI, arquitecturas multi‑agente, LangChain, orquestación de herramientas e interfaces de chat. Debes diseñar una solución **standalone** para reemplazar openclaw/molbolt/clawde por un sistema propio, controlado por nosotros y listo para producción.

**Contexto:**
Tengo un sistema actual construido con clawde/openclaw/molbolt + un agente tipo Claude Code. Quiero eliminar completamente esas dependencias y reconstruir con LangChain, agentes propios y un panel de control configurable.

**Objetivos principales (obligatorios):**
1. **Agentes propios con LangChain** y roles bien definidos.
2. **Instancias separadas de LLM por rol** (configurables por agente).
3. **Interfaz de chat propia** (frontend + backend) para conversaciones multi‑agente.
4. **Panel de control configurable** para:
   - gestionar roles y prompts (system/developer)
   - seleccionar modelos por rol
   - configurar herramientas disponibles por agente
   - ajustar parámetros (temperature, top_p, etc.)
   - habilitar/deshabilitar agentes
5. Arquitectura modular, escalable, fácil de desplegar.
6. **Observabilidad y trazabilidad** (logs, trazas, métricas, auditoría de decisiones por agente).

**Criterios de aceptación (imprescindibles):**
- Debo poder **crear agentes nuevos con copy/paste de: role, alma (persona), memory** y configurarlos desde el panel.
- Debo poder **tener tantos agentes como desee** sin tocar código (todo desde configuración).
- Las instancias de LLM deben ser **independientes por rol**, con posibilidad de cambiar proveedor o modelo por agente.
- El sistema debe ser **standalone**: sin openclaw/molbolt/clawde ni dependencias propietarias cerradas.

**Requerimientos de arquitectura (añadir a tu propuesta):**
- **Plantillas de agente**: permitir duplicar agentes por plantilla y sobreescribir role/alma/memory.
- **Persistencia de memoria** por agente, con políticas configurables (por ejemplo: sliding window, summary, vector store).
- **Versionado de prompts**: poder editar y revertir configuraciones de roles.
- **Separación de entornos** (dev/staging/prod) con configuraciones distintas.

**Entregables que debes producir:**
1. **Diagnóstico del estado actual**: qué reemplazar y qué reutilizar.
2. **Arquitectura target** con diagrama en texto (componentes, flujos, responsabilidades).
3. **Diseño de roles** + prompts base (system/developer) para cada agente.
4. **Modelo de datos** del panel de control (tablas o esquemas clave).
5. **Stack tecnológico recomendado** (backend, frontend, orquestación, observabilidad).
6. **Hoja de ruta por fases** con entregables y riesgos.
7. **Recomendaciones extra**: mejores prácticas, riesgos y mitigaciones.

**Formato de salida requerido:**
- ✅ Diagnóstico actual
- ✅ Arquitectura target (diagrama en texto)
- ✅ Roles de agentes + prompts base
- ✅ Modelo de datos del panel
- ✅ Stack recomendado
- ✅ Hoja de ruta en fases
- ✅ Recomendaciones extra

**Notas:**
- No uses openclaw/molbolt/clawde ni dependencias propietarias cerradas.
- Prioriza claridad, modularidad y facilidad de operación.
