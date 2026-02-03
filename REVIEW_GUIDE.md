# 🎯 Guía de Revisión - Mission Control Drag & Drop

## ✅ Cambios Listos para Review

**Rama:** `feature/kanban-drag-drop`  
**Base:** `main`  
**Commits:** 2 commits (794c2a2)

---

## 🚀 Cómo Probarlo

### 1. Cambiar a la rama

```bash
cd /home/victor/repositories/mission_control
git checkout feature/kanban-drag-drop
```

### 2. Aplicar migración de DB

```bash
sqlite3 instance/mission_control.db < migrations/add_sprints.sql
```

### 3. Reiniciar servidor

```bash
# Detener si está corriendo
pkill -f "python.*app.py"

# Iniciar con cambios
python app.py
```

### 4. Abrir en navegador

```
http://localhost:5001
```

**IMPORTANTE:** Hacer `Ctrl+F5` para forzar recarga de JS/CSS

---

## 🧪 Checklist de Testing

### ✅ Drag & Drop
- [ ] Arrastra una tarea de TODO → IN PROGRESS
- [ ] La tarea cambia de columna inmediatamente
- [ ] Recarga página → el cambio persiste
- [ ] Prueba arrastrar a REVIEW, DONE, BLOCKED
- [ ] Verifica feedback visual (zona azul, card semi-transparente)

### ✅ Task Modal
- [ ] Haz clic en cualquier tarjeta
- [ ] Modal se abre con toda la información
- [ ] Cambia Status con dropdown → se actualiza automáticamente
- [ ] Cambia Priority → se actualiza
- [ ] Cierra con X, botón "Cerrar", o click fuera
- [ ] Verifica que el Kanban refleja los cambios

### ✅ Sprint Filter
- [ ] Dropdown muestra Sprint 1, Sprint 2, "Todos los sprints"
- [ ] Sprint 2 (active) está seleccionado por default
- [ ] Selecciona Sprint 1 → solo muestra tasks #1-24
- [ ] Selecciona Sprint 2 → solo muestra tasks #25+
- [ ] Selecciona "Todos" → muestra todas las tareas
- [ ] Cada tarjeta muestra badge `📅 Sprint X`

---

## 📊 Archivos Modificados

```
app.py              - Endpoints para sprints + filtrado por sprint
database.py         - Modelo Sprint + relación con Task
templates/index.html - Modal HTML + dropdown de sprints
static/script.js    - Drag & drop logic + modal handlers
static/style.css    - Estilos para drag, modal, sprint filter
migrations/add_sprints.sql - Schema de sprints + data inicial
FEATURES.md         - Documentación completa
```

---

## 🔍 Puntos Clave a Revisar

1. **UX del Drag & Drop:**
   - ¿Es intuitivo?
   - ¿El feedback visual es claro?
   - ¿La animación es suave?

2. **Modal de Detalle:**
   - ¿Muestra toda la info necesaria?
   - ¿Es fácil editar status/priority?
   - ¿Falta algo importante?

3. **Sprint Filter:**
   - ¿Es útil para tu workflow?
   - ¿Deberían los sprints ser más flexibles?
   - ¿Necesitas crear sprints nuevos desde UI?

4. **Performance:**
   - ¿El drag & drop es responsive?
   - ¿El modal abre rápido?
   - ¿El filtrado de sprint es instantáneo?

---

## 🐛 Issues Conocidos / Limitaciones

1. **Drag & Drop solo con mouse** - No funciona con touch (mobile)
2. **Sprints hardcoded** - Solo Sprint 1 y 2, no hay UI para crear nuevos
3. **Descripción no editable** - Modal es read-only para description
4. **Sin búsqueda** - No hay barra de búsqueda de tareas aún

---

## ✅ Merge Checklist

Antes de mergear a `main`:

- [ ] Tests pasando
- [ ] UX aprobado por Victor
- [ ] Performance aceptable
- [ ] Documentación completa
- [ ] Migración aplicada en DB producción
- [ ] Sin breaking changes

---

## 🔀 Cómo Mergear

```bash
cd /home/victor/repositories/mission_control

# Verificar que estás en la rama correcta
git branch
# Debe mostrar: * feature/kanban-drag-drop

# Cambiar a main
git checkout main

# Mergear cambios
git merge feature/kanban-drag-drop

# Push a remote (si aplica)
git push origin main
```

---

## 💬 Feedback

Si algo no funciona o quieres cambios:

1. Coméntame qué ajustar
2. Puedo hacer cambios adicionales en la misma rama
3. Cuando esté todo OK, mergeamos a main

---

**Happy Testing! 🎉**
