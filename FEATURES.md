# Mission Control - Nuevas Funcionalidades

## 🎯 Características Implementadas

### 1. Drag & Drop de Tickets 🔄

**Funcionalidad:**
- Arrastra cualquier ticket entre las columnas del Kanban (TODO, IN PROGRESS, REVIEW, DONE, BLOCKED)
- El estado se actualiza automáticamente en la base de datos
- Feedback visual durante el arrastre (tarjeta semi-transparente, zona de drop resaltada)

**Cómo usarlo:**
1. Haz clic y mantén presionado sobre cualquier tarjeta de tarea
2. Arrastra la tarjeta a la columna deseada
3. Suelta para actualizar el estado
4. El Kanban se recarga automáticamente mostrando la nueva posición

**Indicadores visuales:**
- 🟦 Zona de drop resaltada en azul con borde punteado
- 👻 Tarjeta arrastrada se vuelve semi-transparente (50% opacity)
- ✨ Animación suave al soltar

---

### 2. Modal de Detalle de Tarea 📋

**Funcionalidad:**
- Haz clic en cualquier tarjeta para ver el detalle completo
- Edita estado y prioridad directamente desde el modal
- Ver descripción completa, fechas, assignee, y sprint

**Información mostrada:**
- **ID** - Identificador único (#25, #26, etc.)
- **Sprint** - Sprint al que pertenece la tarea
- **Status** - Estado actual (editable con dropdown)
- **Priority** - Prioridad (editable: Low, Medium, High, Critical)
- **Assignee** - Agente asignado
- **Created** - Fecha de creación
- **Updated** - Última actualización
- **Description** - Descripción completa formateada

**Cómo usarlo:**
1. Haz clic en cualquier tarjeta del Kanban
2. El modal se abre automáticamente
3. Cambia Status o Priority usando los dropdowns
4. Los cambios se guardan automáticamente
5. Cierra con el botón X, botón "Cerrar", o haciendo clic fuera del modal

**Atajos:**
- `ESC` - Cerrar modal
- Click fuera del modal - Cerrar

---

### 3. Filtro de Sprints 📅

**Funcionalidad:**
- Dropdown en la esquina superior derecha del Kanban
- Filtra tickets por sprint seleccionado
- Muestra "Todos los sprints" o un sprint específico
- El sprint activo se selecciona por defecto al cargar

**Sprints disponibles:**
- **Sprint 1** (completed) - Tasks #1-24
- **Sprint 2** (active) - Tasks #25+ ← Seleccionado por default

**Cómo usarlo:**
1. Selecciona un sprint del dropdown
2. El Kanban se actualiza mostrando solo las tareas de ese sprint
3. Cada tarjeta muestra su sprint con badge `📅 Sprint 2`

---

## 🔧 Cambios Técnicos

### Base de Datos

**Nueva tabla: `sprints`**
```sql
CREATE TABLE sprints (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100),
    goal TEXT,
    start_date DATETIME,
    end_date DATETIME,
    status VARCHAR(50),  -- active, completed, archived
    created_at DATETIME
);
```

**Columna añadida a `tasks`:**
```sql
ALTER TABLE tasks ADD COLUMN sprint_id INTEGER REFERENCES sprints(id);
```

### API Endpoints Nuevos

**Sprints:**
- `GET /api/sprints` - Listar todos los sprints
- `POST /api/sprints` - Crear nuevo sprint
- `GET /api/sprints/:id` - Detalle de sprint (incluye tareas)
- `PUT /api/sprints/:id` - Actualizar sprint

**Tasks (actualizado):**
- `GET /api/tasks?sprint_id=2` - Filtrar tareas por sprint
- `PUT /api/tasks/:id` - Ahora acepta `sprint_id` en el body

### Frontend

**JavaScript:**
- `handleDragStart()` - Inicia drag con efecto visual
- `handleDrop()` - Actualiza status en DB vía API
- `openTaskModal(taskId)` - Abre modal con detalle
- `updateTaskFromModal()` - Guarda cambios desde modal
- `filterBySprint()` - Filtra Kanban por sprint

**CSS:**
- `.dragging` - Estilo durante drag (opacity 0.5)
- `.drag-over` - Highlight de zona de drop (border azul)
- `.modal` - Modal responsivo con backdrop blur
- `.task-sprint` - Badge de sprint en tarjetas

---

## 📦 Instalación / Migración

### 1. Aplicar migración de base de datos

```bash
cd /home/victor/repositories/mission_control
sqlite3 instance/mission_control.db < migrations/add_sprints.sql
```

Esto crea:
- Tabla `sprints`
- Columna `sprint_id` en `tasks`
- Sprint 1 y Sprint 2 iniciales
- Asigna tasks existentes a sprints

### 2. Reiniciar servidor Flask

```bash
# Si está corriendo, detenerlo
pkill -f "python.*app.py"

# Iniciar con cambios
python app.py
```

### 3. Refrescar navegador

- Ctrl+F5 para forzar recarga de JS/CSS
- O limpiar cache del navegador

---

## 🎨 UX / Diseño

### Drag & Drop
- **Cursor:** `grab` en hover, `grabbing` durante drag
- **Animación:** Transición suave de 0.2s
- **Feedback:** Borde azul punteado en zona válida

### Modal
- **Backdrop:** Blur + overlay oscuro (rgba)
- **Animación:** Slide up + fade in (0.3s)
- **Responsive:** 90% width en mobile, 700px max en desktop

### Sprint Filter
- **Posición:** Top-right del Kanban
- **Auto-select:** Sprint activo seleccionado por default
- **Estado:** Muestra "(active)" o "(completed)" junto al nombre

---

## 🧪 Testing

### Test Drag & Drop
1. Abre Mission Control: http://localhost:5001
2. Arrastra BLOG-010 de TODO a IN PROGRESS
3. Verifica que la tarjeta cambia de columna
4. Recarga la página → el cambio persiste

### Test Modal
1. Haz clic en cualquier tarjeta
2. Verifica que el modal muestra toda la info
3. Cambia Status de "todo" a "review"
4. Cierra modal → verifica que la tarjeta está en columna REVIEW

### Test Sprint Filter
1. Selecciona "Sprint 1" en el dropdown
2. Verifica que solo se muestran tasks #1-24
3. Selecciona "Sprint 2"
4. Verifica que solo se muestran tasks #25+
5. Selecciona "Todos los sprints"
6. Verifica que se muestran todas las tareas

---

## 📝 Notas

- **Drag & Drop:** Solo funciona con mouse (no touch en mobile por ahora)
- **Modal:** Auto-actualiza al cambiar status/priority (no requiere "Guardar")
- **Sprints:** Actualmente hardcoded Sprint 1 y 2, expandible en futuro
- **Performance:** Cache de tareas en frontend para filtrado rápido

---

## 🚀 Próximos Pasos (Opcional)

- [ ] Touch support para drag & drop en mobile
- [ ] Editar descripción desde modal
- [ ] Crear nuevo sprint desde UI
- [ ] Arrastrar tareas entre sprints
- [ ] Búsqueda/filtro de tareas por texto
- [ ] Keyboard shortcuts (j/k para navegar)

---

**Rama:** `feature/kanban-drag-drop`  
**Commit:** `38042e0`  
**Fecha:** 2026-02-03  
**Autor:** Jarvis (via Victor)
