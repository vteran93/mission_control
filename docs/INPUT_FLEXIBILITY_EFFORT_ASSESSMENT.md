# Evaluacion de Esfuerzo - Intake Flexible y Contratos Markdown

**Fecha:** 2026-03-26  
**Contexto:** evaluar dos cambios posibles sobre `mission_control`:

1. agregar un agente aguas arriba que convierta inputs abiertos o semiestructurados en un paquete formal reutilizable por el intake actual;
2. reemplazar o relajar contratos estructurados aguas abajo para que los agentes trabajen con prompts Markdown de alto nivel en vez de depender tanto de JSON, `dict` o modelos internos.

## Sintesis ejecutiva

La opcion con mejor relacion impacto/riesgo es:

- agregar un `upstream architect agent` que haga `close-the-gap`;
- mantener un modelo canonico estructurado dentro del sistema;
- permitir Markdown en la frontera entre agentes, pero normalizarlo antes de planning, persistence y QA.

Conclusiones cortas:

- `mission_control` hoy no esta rigido por Pydantic; esta rigido por el parser de intake, por contratos internos de planning y por persistencia/telemetria estructurada.
- poner un agente aguas arriba es un cambio de esfuerzo medio y riesgo controlable.
- convertir Markdown en el contrato canonico aguas abajo es un cambio caro y de alto riesgo, porque rompe planning, readiness, QA gate, artifacts, reportes, timeline y tests.
- si el objetivo es aceptar ideas abiertas y llegar a requerimientos formales, no hace falta desmontar el nucleo estructurado; hace falta un adaptador inteligente antes del nucleo.

## Estado real del sistema hoy

El sistema actual combina:

- `dataclasses` en intake y runtime contracts;
- `dict[str, Any]` y JSON para planner, delivery, artifacts y feedback;
- columnas JSON en base de datos para metadata, criterios, reportes y trazabilidad;
- prompts de texto para los agentes, pero con puntos de parseo estructurado obligatorios.

Puntos donde la estructura hoy es central:

- `spec_intake/`: parser regex y blueprint canonico.
- `autonomous_scrum/service.py`: planning review con salida JSON, `approval_status`, `confidence_score`, `definition_of_ready`, `definition_of_done`.
- `autonomous_delivery/service.py`: review, QA gate, release candidate y artifacts operativos serializados.
- `crew_runtime/toolkit.py`: tools que devuelven payloads JSON para consumo del agente.
- `database.py`: persistencia con multiples campos `*_json`.
- `app.py`: APIs y contratos de entrada/salida ya consumidos por tests y UI.

Superficie implicada observada en esta revision:

- `autonomous_scrum/service.py`: `1603` lineas.
- `autonomous_delivery/service.py`: `1721` lineas.
- `crew_runtime/toolkit.py`: `633` lineas.
- `database.py`: `906` lineas.
- `app.py`: `1167` lineas.
- tests directamente relacionados inspeccionados: `26`.

## Opciones evaluadas

### Opcion A - Agente aguas arriba y nucleo estructurado intacto

Descripcion:

- aceptar `input_artifacts[]` en vez de exigir solo `requirements_path + roadmap_path`;
- clasificar el tipo de input: `formal_pair`, `roadmap_dossier`, `multi_artifact_brief`, `use_case_only`;
- ejecutar un agente arquitecto/normalizador;
- generar:
  - `requirements.generated.md`
  - `roadmap.generated.md`
  - `assumptions.md`
  - `open_questions.md`
  - `traceability_map.json` o equivalente
- pasar esos artefactos al intake actual o a un intake ligeramente ampliado.

Ventajas:

- preserva planning, persistence, QA y operator UX.
- el cambio queda concentrado en intake y frontera API.
- permite evolucionar gradualmente.
- es compatible con el roadmap ya actualizado.

Desventajas:

- agrega una etapa mas al pipeline.
- obliga a definir bien `confidence_score`, `question_budget` y politicas de inferencia.

Esfuerzo estimado:

- MVP util: `8 a 12` dias-hombre.
- endurecido para operar con confianza: `15 a 20` dias-hombre.

Desglose probable:

- contrato nuevo `input_artifacts[]` + compatibilidad legacy: `1 a 2` dias.
- shape classifier + detection heuristics: `1 a 2` dias.
- agente arquitecto / requirements normalizer: `3 a 4` dias.
- persistencia de artefactos generados y trazabilidad: `1 a 2` dias.
- tests E2E y benchmarks con `example_project_2`: `2 a 3` dias.

Riesgo:

- `medio-bajo`.

### Opcion B - Markdown de alto nivel solo en la frontera entre agentes

Descripcion:

- los agentes pueden hablar en Markdown libre o semiestructurado;
- pero al cruzar puntos de control del sistema se normaliza a estructura canonica;
- ejemplos:
  - planning crew responde Markdown, luego un parser/adaptador lo convierte a `approval_status`, `risks`, `actions`;
  - toolkit puede devolver Markdown resumido, pero sigue existiendo un payload estructurado interno;
  - artifacts visibles para humanos pasan a `.md`, sin eliminar sus equivalentes operativos JSON donde hagan falta.

Ventajas:

- mejora legibilidad y ergonomia de prompts.
- reduce fragilidad de algunos prompts.
- no obliga a rediseñar DB ni gates.

Desventajas:

- sigue requiriendo adaptadores estructurales.
- si el Markdown no tiene formato minimo, el parser sera fragil.

Esfuerzo estimado:

- incremental sobre Opcion A: `4 a 7` dias-hombre.
- total combinado A + B: `12 a 18` dias-hombre.

Desglose probable:

- rediseño de prompts y templates: `1 a 2` dias.
- parsers/adapters Markdown -> payload canonico: `2 a 3` dias.
- ajuste de toolkit y reporting humano: `1 a 2` dias.
- pruebas de regresion: `1 a 2` dias.

Riesgo:

- `medio`.

### Opcion C - Reemplazar el contrato canonico aguas abajo por Markdown

Descripcion:

- usar Markdown de alto nivel como forma principal de intercambio y decision en planning, review, QA y delivery;
- minimizar o retirar estructura interna donde hoy existen `dict`, JSON y columnas derivadas;
- inferir estados desde texto libre.

Esto implica, como minimo:

- replantear planning review hoy basado en JSON.
- replantear `approval_status`, `confidence_score`, `risk_level`, `DoR`, `DoD`.
- replantear tooling que hoy devuelve payloads JSON.
- replantear feedback y artifacts que hoy son consumibles por timeline/report.
- decidir si la DB conserva estructura o pasa a blobs de texto.

Ventajas:

- maxima flexibilidad expresiva para agentes.
- reduce friccion si los modelos razonan mejor en texto que en esquema estricto.

Desventajas:

- rompe o debilita los puntos fuertes actuales: trazabilidad, reportes, gating y determinismo.
- eleva el costo de testing y debugging.
- complica operator UX y dashboards.
- obliga a reintroducir estructura mas adelante, porque el sistema necesita estados y decisiones discretas.

Esfuerzo estimado:

- MVP riesgoso: `20 a 30` dias-hombre.
- version operable con controles equivalentes a hoy: `30 a 45` dias-hombre.

Desglose probable:

- rediseño de contratos de planner y parsers de decision: `5 a 8` dias.
- rediseño de delivery/review/QA/release/retro: `6 a 10` dias.
- cambios en DB/API/serializacion/backward compatibility: `5 a 8` dias.
- toolkit y runtime contracts: `3 a 5` dias.
- migraciones, dashboards, timeline y reportes: `4 a 6` dias.
- regresion test suite y estabilizacion: `5 a 8` dias.

Riesgo:

- `alto`.

## Comparativo resumido

| Opcion | Valor | Esfuerzo | Riesgo | Recomendacion |
|---|---|---:|---|---|
| A. Agente aguas arriba + core estructurado | alto | `8-12d` MVP / `15-20d` endurecido | medio-bajo | si |
| B. Markdown solo en frontera | medio-alto | `+4-7d` sobre A | medio | si, despues de A |
| C. Markdown como contrato canonico | incierto | `20-30d` MVP / `30-45d` operable | alto | no por ahora |

## Por que la Opcion C cuesta tanto

Porque hoy la estructura no es solo una preferencia de serializacion. Es parte del comportamiento del producto:

- el planner decide `approved | review_required | draft`;
- el plan guarda `confidence_score` y `risk_score`;
- los tickets tienen dependencias, `DoR`, `DoD` y readiness;
- el delivery produce evidencia operativa consumible por QA y release;
- la UI y los reportes leen payloads discretos y comparables;
- los tests esperan contratos concretos.

Si eso pasa a Markdown libre, hay dos resultados posibles:

- o se pierde determinismo;
- o se vuelve a introducir un parser estructurado para recuperar esas decisiones.

Por eso, incluso en un diseño “Markdown-first”, el sistema termina necesitando una representacion canonica estructurada.

## Recomendacion tecnica

Orden recomendado:

1. implementar Opcion A;
2. agregar Opcion B donde mejore la UX de agentes;
3. mantener estructura canonica para persistence, planning, QA y observabilidad;
4. evitar Opcion C salvo que se quiera rehacer el producto alrededor de un modelo mas exploratorio y menos operativo.

Principio recomendado:

- `Markdown for reasoning, structured state for operations`.

Ese principio permite:

- que el agente arquitecto piense y sintetice en lenguaje natural;
- que el sistema siga teniendo estados discretos y trazables.

## Propuesta de implementacion por fases

### Fase F1 - Intake flexible sin romper el core

Objetivo:

- introducir `input_artifacts[]`;
- agregar `shape classifier`;
- soportar `example_project_2` y `roadmap-only`.

Esfuerzo:

- `4 a 6` dias-hombre.

### Fase F2 - Architect close-the-gap

Objetivo:

- generar artefactos formales derivados;
- explicitar supuestos, preguntas abiertas y score de confianza;
- persistir trazabilidad.

Esfuerzo:

- `4 a 6` dias-hombre.

### Fase F3 - Markdown envelopes sobre el core

Objetivo:

- permitir prompts/respuestas Markdown mas humanas;
- normalizar en puntos de control.

Esfuerzo:

- `4 a 7` dias-hombre.

### Fase F4 - Hardening

Objetivo:

- benchmarks con `docs/example_project_2/*`;
- benchmark `use-case-only`;
- metricas de precision del intake flexible.

Esfuerzo:

- `3 a 5` dias-hombre.

## Respuesta corta a la pregunta original

Si ponemos un agente aguas arriba, el esfuerzo es razonable y vale la pena.

Si ademas cambiamos los mensajes entre agentes a Markdown de alto nivel, el esfuerzo sube un poco pero sigue siendo manejable siempre que:

- el Markdown sea una interfaz;
- no reemplace el estado canonico interno.

Si intentamos reemplazar el estado estructurado aguas abajo por Markdown libre como contrato principal, el esfuerzo sube mucho y el riesgo sube mas todavia.

## Decision recomendada

Decidir esto:

- `si` a un `upstream architect agent`;
- `si` a Markdown en la frontera de razonamiento;
- `no` a eliminar el modelo canonico estructurado del sistema en esta etapa.
