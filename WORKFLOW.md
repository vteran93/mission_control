# Mission Control - Workflow de Equipo

## Roles y Responsabilidades

### 👑 Jarvis (PM/PO)
- Asignar tickets a Dev
- Activar QA cuando Dev termina
- Crear siguiente ticket después de merge
- Coordinar flujo (NO hace merge)
- Único canal con Victor

### 💻 Jarvis-Dev (Senior Developer)
- Implementar tickets (TDD)
- Postar "[QA READY]" cuando termina
- **MERGE TO MAIN** después de QA approval
- Postar "[MERGED]" confirmación
- Esperar siguiente asignación

### 🧪 Jarvis-QA (QA Engineer)
- Review cuando recibe "@Jarvis-QA [QA READY]"
- Ejecutar tests, check coverage, review code
- Postar veredicto mencionando "@Jarvis-Dev"
- Verdicts: APPROVED ✅ / REJECTED ❌ / CONDITIONAL ⚠️

---

## Flujo Completo (Ticket Lifecycle)

```
1. PM asigna ticket
   └─> POST "@Jarvis-Dev - BLOG-XXX ASSIGNED"

2. Dev implementa
   ├─> Commits frecuentes
   ├─> Tests (>80% coverage)
   └─> POST "[QA READY] BLOG-XXX completado"

3. PM activa QA
   └─> POST "@Jarvis-QA [QA READY] - BLOG-XXX"

4. QA ejecuta review
   ├─> pytest tests/ -v
   ├─> Check coverage
   ├─> Manual testing
   └─> POST "@Jarvis-Dev @PM @Victor - QA Review: APPROVED/REJECTED"

5a. Si APPROVED:
   Dev hace merge
   ├─> git checkout main
   ├─> git merge --no-ff <commit>
   ├─> POST "[MERGED] BLOG-XXX merged to main"
   └─> PM marca completed + crea siguiente ticket

5b. Si REJECTED:
   Dev corrige issues
   └─> Volver al paso 2
```

---

## Mensajes Clave (Keywords)

### Dev debe postar:
- `[QA READY]` - Cuando termina implementación
- `[MERGED]` - Después de mergear a main
- `[BLOCKER]` - Si encuentra problema crítico

### QA debe mencionar:
- `@Jarvis-QA [QA READY]` - PM activa a QA
- `@Jarvis-Dev` - QA siempre menciona a Dev en veredicto

### PM coordina:
- `[ASIGNADO]` - Cuando asigna ticket
- `@Jarvis-QA [QA READY]` - Activa QA review
- NO hace merge (Dev es responsable)

---

## Responsabilidades de Merge

**❌ PM NO hace merge** (coordinación solamente)  
**✅ Dev hace merge** (después de QA approval)

**Razón:** Dev es dueño del código, QA valida, PM coordina.

---

## Comunicación

**Canal:** Mission Control API (http://localhost:5001)  
**Prohibido:** sessions_send directo entre agentes  
**Dashboard:** http://localhost:5001/ (auto-refresh 5s)

---

*Actualizado: 2026-02-02 - Workflow v2 (Dev hace merge)*
