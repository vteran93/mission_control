# Instrucciones de Plane para Mission Control

## Archivo canonico

Este es el archivo canonico para el workflow de Plane del repositorio.

## Configuracion inicial

1. Copia `.plane.config.example` a `.plane-config`.
2. Ajusta `PLANE_URL`, `PLANE_TOKEN`, `PLANE_WORKSPACE` y `PLANE_PROJECT`.
3. Carga la configuracion:

```bash
source .plane-config
```

## Regla de trabajo

Cuando trabajes en tickets del roadmap, usa `update-plane-tickets.sh` y referencia la clave del roadmap (`AG-110`, `AG-606`, etc.). No hace falta recordar el UUID de Plane.

## Workflow obligatorio

### 1. Antes de empezar

```bash
./update-plane-tickets.sh start AG-110 "Comenzando Architecture Synthesizer"
```

### 2. Durante el trabajo

Agrega comentarios cuando:

- cierres subtareas;
- tomes decisiones tecnicas;
- termines una parte relevante;
- corran tests;
- encuentres blockers.

```bash
./update-plane-tickets.sh comment AG-110 "💡 Decisión: usar contract-first output para requirements.generated.md"
./update-plane-tickets.sh comment AG-110 "🧪 Tests: pytest tests/test_phase1_spec_intake.py -q"
./update-plane-tickets.sh comment AG-110 "✅ Cerrado parser de supuestos y preguntas abiertas"
```

### 3. Si te bloqueas

```bash
./update-plane-tickets.sh block AG-110 "Falta definicion del threshold de confidence_score"
```

### 4. Al terminar

```bash
./update-plane-tickets.sh complete AG-110 "Architecture Synthesizer implementado. Tests verdes. Listo para review."
```

## Listar y validar tickets

```bash
./update-plane-tickets.sh list
./update-plane-tickets.sh show AG-110
```

## Migrar backlog remanente

```bash
source .plane-config
./migrate_to_plane.sh
```

Opciones utiles:

```bash
./migrate_to_plane.sh --list
./migrate_to_plane.sh --only AG-110,AG-112,AG-114 --dry-run
./migrate_to_plane.sh --only AG-606,AG-607
```

## Reglas estrictas

1. Siempre marca el ticket como `start` antes de modificar codigo.
2. Siempre deja al menos un comentario con decision tecnica o estado de tests.
3. Nunca cierres un ticket sin resumen de implementacion.
4. Usa la clave del roadmap (`AG-*`) como referencia principal.
5. Si un ticket no existe en Plane, primero corre `./migrate_to_plane.sh --only AG-XXX`.

## Notas del proyecto

- El proyecto de Plane para esta repo es `Mission Control`.
- `PLANE_URL` correcto en este entorno es `http://localhost`.
- `localhost:8000` corresponde a otro servicio y no debe usarse para Plane.
