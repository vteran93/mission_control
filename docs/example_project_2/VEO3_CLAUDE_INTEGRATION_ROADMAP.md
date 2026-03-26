# Roadmap: Plataforma enterprise de video agentic con Veo 3.1, Claude en Bedrock y adaptacion de libros de dominio publico

**Proyecto:** `legatus-video-factory`  
**Fecha de validacion externa:** 2026-03-26  
**Objetivo:** construir una plataforma comercial `video-first`, `multi-provider` y `agentic` donde Claude en Bedrock produzca instrucciones, parrafos, escenas y prompts cinematograficos, y el sistema pueda adaptar libros de dominio publico, producir peliculas completas, cuñas comerciales y piezas multimedia de clase mundial con calidad operativa enterprise.

## Resumen ejecutivo

El repositorio ya tiene piezas reutilizables, pero hoy el flujo principal sigue siendo `Wikipedia -> guion -> image prompts -> imagenes -> TTS -> FFmpeg`. Veo existe solo como stub local y no esta integrado al worker principal.

Este roadmap ya no debe leerse como un plan de prototipo. Debe leerse como el blueprint de una solucion comercial capaz de:

- producir peliculas narrativas completas
- producir cuñas comerciales de 6s, 15s, 30s y 60s
- producir multimedia premium para web, vertical social y branded storytelling
- operar con trazabilidad, metricas, manejo de errores y estandares de calidad profesional

La recomendacion correcta no es reemplazar todo de golpe. Hay que introducir un modo nuevo, por ejemplo `veo_cinematic_8s`, y mantener el pipeline actual como fallback. Claude en Bedrock debe convertirse en el unico LLM del pipeline para:

- plan narrativo
- descomposicion en escenas
- escritura de parrafos por escena
- generacion de prompt Veo por escena
- autocritica/QC textual antes de llamar al proveedor

El proveedor de video, sea Veo o Hunyuan, debe usarse solo como sintetizador de video. No debe decidir la narrativa.

Ademas, la abstraccion `VideoProvider` ya existe en el repo. La direccion correcta es endurecer esa interfaz y convertirla en una capa `multi-provider` real, no crear una integracion ad hoc solo para Veo.

Para adaptacion de libros hace falta, ademas, una capa editorial nueva. El repo no sabe ingerir EPUB/TXT/HTML de libros, no entiende capitulos, no mantiene una biblia de personajes/localizaciones y no tiene una planificacion jerarquica `libro -> capitulo -> beats -> escenas`. Sin eso, intentar generar "peliculas desde libros" terminaria siendo una sumarizacion plana y visualmente inconsistente.

Tambien hace falta separar dos conceptos que hoy estan mezclados: `escena narrativa` y `clip de video`. En el producto objetivo, una escena puede durar 16, 24 o 32 segundos y estar compuesta por varios `shots` de 8 segundos con cambios de angulo, cobertura o POV. Veo genera el `shot`; Claude debe dirigir la `escena` completa.

## Posicionamiento comercial

El MVP no debe entenderse como una demo reducida sin fiabilidad. El MVP debe ser el primer release comercial controlado de una plataforma enterprise.

Perfiles de producto que el roadmap debe soportar:

- `feature_film_longform`
  - peliculas narrativas y adaptaciones largas
- `premium_documentary`
  - documentales cinematicos narrados
- `commercial_spot`
  - cuñas de `6s | 15s | 30s | 60s`
- `brand_multimedia_campaign`
  - piezas web, social vertical, motion promos y derivados

Consecuencia de producto:

- el roadmap debe incluir desde el inicio operacion, observabilidad, costos, calidad y manejo formal de fallos
- no basta con "lograr generar un video"; hay que poder operarlo, medirlo, auditarlo y venderlo

## Hallazgos del codigo actual

### 1. La integracion Veo no es real todavia

- `src/blackforge/integrations/video/google_veo.py` es un skeleton que crea un `.mp4` vacio y marca el asset como `done`.
- No hay llamada real a Gemini API, no hay polling de operaciones, no hay descarga de archivos, y no hay idempotencia por `operation.name`.

### 2. El worker productivo es totalmente image-first

El flujo real en `backend/app/worker.py` hace esto:

- genera guion
- espera aprobacion de script
- genera image prompts
- genera imagenes
- espera aprobacion de imagenes
- genera TTS
- renderiza video con FFmpeg a partir de `image_path + audio_path`

Eso significa que Veo hoy no entra en el pipeline que usa la API.

### 3. Ya existe un experimento video-first, pero no esta listo para produccion

`src/blackforge/orchestration/langgraph_pipeline.py` ya prueba esta idea:

- genera `positive_prompt` y `negative_prompt`
- llama `GoogleVeoProvider.generate_clip()`
- hace un QC minimo

Pero es un proof of concept:

- no esta conectado al backend
- no persiste operaciones
- no usa Claude
- no tiene aprobaciones
- no renderiza el resultado final correctamente

### 4. La logica de escenas actual no sirve para clips fijos de 8 segundos

`src/blackforge/pipeline/utils/token_management.py` usa una heuristica de 1 escena por minuto, limitada entre 6 y 12 escenas. Eso es incompatible con un modo de clips fijos de 8 segundos.

Ejemplo:

- 120 segundos hoy produce ~6 escenas
- en Veo 8s deberian ser ~15 escenas

### 5. El prompt engine actual esta orientado a imagenes y OpenAI

`src/blackforge/pipeline/prompt_generation.py` todavia:

- usa `gpt-4o-mini` por defecto
- esta escrito para SD3.5 / imagen
- solo produce un `VideoPromptPack` compacto
- no modela continuidad visual, movimiento de camara, intencion sonora ni referencias por escena

### 6. El LLM por defecto no cumple tu requisito

`backend/app/config.py` y `src/blackforge/integrations/bedrock_llm.py` siguen defaulting a `DeepSeek` para narrativa. Eso contradice el requerimiento de usar Claude en Bedrock para instrucciones, parrafos y escenas.

### 7. La API todavia no expone modo/proveedor de video

`backend/app/models/requests.py` solo acepta:

- `wikipedia_url`
- `title`
- `target_duration`
- `webhook_url`

No hay campos para:

- modo de generacion
- proveedor de video
- resolucion
- aspect ratio
- duracion por escena
- uso de audio nativo o TTS

### 8. FFmpeg si tiene piezas reutilizables

`src/blackforge/integrations/ffmpeg.py` ya tiene dos bloques utiles para Veo:

- `normalize_video_clip()`
- `concatenate_videos()`

Eso permite coser clips Veo sin depender del render de imagen estatica.

### 9. No existe una capa de ingesta de libros

El sistema solo sabe traer contenido desde Wikipedia. No hay integraciones para:

- Project Gutenberg
- archivos `.txt`
- archivos `.epub`
- HTML de libros
- metadatos de dominio publico o procedencia editorial

Eso bloquea por completo el caso de uso `book-to-film`.

### 10. El dominio actual no modela capitulos, actos, personajes ni continuidad dramatica

`DocumentaryScript` y `Scene` sirven para mini documentales, pero no para una adaptacion larga de novela:

- `Metadata.source_url` asume una URL unica
- `scenes` tiene tope de 20
- no existen `chapter_id`, `sequence_id`, `beat_id`
- no existe una biblia persistida de personajes, vestuario, localizaciones o epoca
- no existe una capa de continuidad para que un personaje mantenga rostro, edad aparente y lenguaje de camara entre escenas



### 11. El sistema no es agentic todavia

Hoy el software no opera como un equipo de agentes persistentes:

- el flujo productivo esta implementado como pasos secuenciales dentro de un Celery worker
- no existe `CrewAI` en dependencias ni una capa equivalente de crews/flows multiagente
- el modulo `langgraph_pipeline.py` es solo un experimento local, no el runtime real del backend
- la capa Bedrock actual hace invocaciones puntuales, no coordinacion entre especialistas

Eso significa que hoy no existe una memoria operacional compartida entre roles como `chapter_summarizer`, `continuity_bible_builder`, `scene_planner` y `qc_agent`.

### 12. La persistencia actual no sirve como memoria durable de produccion

El estado del job hoy se apoya principalmente en Redis con TTL corto y en tablas de aprobacion puntuales:

- el metadata del job vive en Redis
- la expiracion actual es de 24 horas
- Postgres solo guarda aprobaciones de script e imagen
- no hay tablas para corridas de agentes, estado narrativo, memoria semantica ni checkpoints de flow

Para una fabrica de peliculas agentic, eso no alcanza.

## Restricciones externas verificadas

### Gemini / Veo 3.1

Verificado en la documentacion oficial de Google AI:

- `veo-3.1-generate-preview` y `veo-3.1-fast-generate-preview` aparecen en la pagina de versiones con actualizacion de enero de 2026.
- La generacion es asincrona: se crea una operacion y luego se hace polling hasta que `done=true`.
- Veo 3.1 acepta:
  - `prompt`
  - `image`
  - `lastFrame`
  - `referenceImages` de hasta 3 imagenes
  - `video` para extension
- Soporta `16:9` y `9:16`.
- Soporta `720p`, `1080p` y `4k`, pero `1080p` y `4k` solo con duracion de 8 segundos.
- Genera video con audio nativo.
- La extension agrega 7 segundos por llamada, hasta 20 veces, solo sobre videos Veo generados en los ultimos 2 dias.
- La pagina marca latencia de solicitud entre 11 segundos y 6 minutos en horas pico.

### Prompting para Gemini/Veo

La guia oficial de prompting de Google, actualizada el 2026-03-25, recomienda:

- prompts claros y especificos
- estructura con `role`, `context`, `constraints`, `task`, `output_format`
- few-shot cuando sea posible
- contexto largo primero y tarea al final
- pedir planificacion y autocritica en tareas complejas

La guia de Veo agrega que el prompt debe explicitar:

- sujeto
- accion
- estilo
- camara
- composicion
- lente / enfoque
- ambiente
- pistas de audio si se desean

### Bedrock / Claude

Verificado en la documentacion oficial de AWS:

- Bedrock soporta Anthropic Claude 3.5 Sonnet v2, Claude 3.7 Sonnet y Claude Sonnet 4 en la familia compatible con Messages/Converse.
- `CountTokens` existe y no genera cargos.
- Bedrock tambien tiene `OptimizePrompt`, util para trabajo de laboratorio sobre prompts, aunque no deberia entrar en el path critico de runtime.

### HunyuanVideo / HunyuanVideo-1.5

Verificado en los repositorios oficiales de Tencent Hunyuan:

- `HunyuanVideo` original fue open-sourced con codigo, pesos e inferencia publica.
- `HunyuanVideo-1.5` aparece como la variante mas practica para adopcion de producto: 8.3B parametros, soporte para consumer-grade GPUs, modelos T2V e I2V, soporte oficial en Diffusers y modelos de 480p/720p, con super-resolution a 1080p.
- El repo oficial de `HunyuanVideo-1.5` indica requisitos minimos de Linux, Python 3.10+, GPU NVIDIA con CUDA y 14 GB de VRAM minima usando offloading.
- `HunyuanVideo-I2V` existe como repositorio oficial separado para image-to-video y Tencent reporta mejoras de first-frame consistency en marzo de 2025.

Inferencia a partir de esas fuentes:

- Hunyuan no entra como API gestionada tipo Veo; entra como proveedor self-hosted.
- Por eso su integracion no se parece a `generateVideos + polling`, sino a una ejecucion local/GPU con colas, modelos, checkpoints y control de memoria.

### Project Gutenberg / fuentes editoriales

Verificado en la documentacion oficial de Project Gutenberg:

- existe un catalogo oficial de metadatos en `XML/RDF`, `CSV` y `OPDS`
- Gutenberg recomienda usar esos catalogos como input para software, en lugar de crawl/roboting del sitio
- hay disponibilidad de texto plano, HTML y EPUB segun el libro
- existe un tar zip semanal con los `.txt`

Inferencia a partir de esas fuentes:

- el camino mas pragmatico para MVP no es OCR ni PDF; es `Project Gutenberg -> metadata oficial -> HTML/TXT/EPUB limpio`
- conviene modelar `source_provenance` y `license_notes` por obra/edicion, no asumir que toda traduccion o toda edicion derivada es reusable en cualquier jurisdiccion

### Prompt caching para Bedrock

Verificado en la documentacion oficial de AWS:

- Bedrock soporta `prompt caching` para modelos compatibles
- reduce latencia y costo de input cuando se reutiliza contexto largo
- es especialmente util cuando varios prompts comparten el mismo prefijo largo

Inferencia a partir de esa fuente:

- para novelas largas, conviene cachear contexto de capitulo, biblia de personajes y reglas de adaptacion cuando se lancen varios prompts Claude sobre la misma unidad narrativa

### CrewAI / memoria y flows

Verificado en la documentacion oficial de CrewAI:

- `Agent(memory=True)` permite mantener memoria de interacciones previas
- CrewAI expone una clase unificada `Memory`
- la memoria usa analisis LLM para guardar contenido y `recall` con mezcla de similitud semantica, recencia e importancia
- la memoria puede usar embeddings de AWS Bedrock
- los `Crews` soportan `memory`, `embedder`, `step_callback` y `task_callback`
- los `Flows` soportan estado estructurado y `@persist`
- la persistencia por defecto de `Flows` usa SQLite
- los `Crews` usan por defecto embedder de OpenAI si no se configura uno

Inferencia a partir de esas fuentes:

- CrewAI memory ayuda al recuerdo, pero no debe ser la unica fuente de verdad del pipeline
- para este producto hace falta combinar `Flow state + artifact store + semantic memory`
- en este repo no conviene depender de defaults locales como SQLite o embeddings OpenAI
- si se usa CrewAI en produccion, hay que configurarlo explicitamente para Bedrock y persistencia durable

### Observabilidad

Google indica que `Logs and datasets` no soporta modelos Veo. Por eso no conviene depender de AI Studio para trazabilidad de produccion de Veo; hay que registrar prompts, operaciones y resultados dentro del propio software.

## Objetivo de arquitectura

Agregar una arquitectura de video productiva multi-provider:

- `classic_documentary`
  - flujo actual imagen + TTS + FFmpeg
- `book_to_film_8s`
  - ingesta de libro publico o cargado por usuario
  - Claude sintetiza por capitulo, luego por beats, luego por escena
  - proveedor de video genera clips de 8s
  - FFmpeg mezcla narracion, ambiente y concatena
- `veo_cinematic_8s`
  - Claude en Bedrock planifica escenas
  - proveedor gestionado como Veo genera clips de 8s
  - FFmpeg normaliza, mezcla audio y concatena
- `oss_cinematic_8s`
  - Claude en Bedrock planifica escenas
  - proveedor open source self-hosted como Hunyuan genera clips
  - FFmpeg normaliza, mezcla audio y concatena

## Decisiones de arquitectura multi-provider

### 1. Mantener un contrato comun y un registro de capacidades

No basta con `generate_clip(prompt)`. Hace falta modelar capacidades para no forzar a todos los proveedores al feature set de Veo.

Propongo un contrato tipo:

- `provider_id`
- `deployment_mode`: `managed_api | self_hosted`
- `supports_text_to_video`
- `supports_image_to_video`
- `supports_reference_images`
- `supports_native_audio`
- `supports_async_operations`
- `supported_resolutions`
- `supported_aspect_ratios`
- `duration_control_mode`: `fixed_choices | frames_fps | provider_default`
- `requires_gpu`
- `requires_linux`

Con eso el orquestador puede decidir:

- si una escena va por Veo o por Hunyuan
- si necesita imagen de referencia
- si puede pedir audio nativo
- si necesita worker GPU dedicado

### 2. Dos lanes de proveedor desde el inicio

Recomiendo que el roadmap soporte explicitamente:

- `google_veo`
  - lane managed, alta calidad base, duracion 8s nativa, audio nativo, latencia/costo externos
- `hunyuan_local`
  - lane self-hosted, open source, sin dependencia de API externa, pero con costo operativo de GPU e inferencia local

### 3. Hunyuan debe entrar como backend self-hosted, no como fallback transparente

No conviene esconder Hunyuan detras del mismo perfil operativo de Veo.

La diferencia real es fuerte:

- Veo: controlado por API y operaciones asincronas
- Hunyuan: controlado por GPU, checkpoints, steps, frames, kernels y memoria

La interfaz comun debe unificar resultado y trazabilidad, no fingir que ambos proveedores se operan igual.

### 4. Separar ingesta editorial, plan narrativo y sintesis de video

Para libros, el pipeline no debe ir directo de `source -> scene prompts`.

Hace falta una cadena jerarquica:

- `source ingestion`
  - bajar o cargar el libro
  - normalizar HTML/TXT/EPUB
  - extraer capitulos y metadatos
- `adaptation planning`
  - sintetizar cada capitulo
  - seleccionar beats dramaticos
  - construir outline global de la pelicula
- `scene planning`
  - convertir cada beat en escenas de 8 segundos
  - asignar prioridad dramatica, tono, POV y continuidad
- `production prompting`
  - escribir narracion de 8s
  - escribir prompt cinematografico por escena
  - autocriticar continuidad y filmabilidad

Si esta separacion no existe, el sistema mezclara extraccion de texto, adaptacion literaria y direccion cinematografica en un solo prompt, que es exactamente la forma mas fragil de resolverlo.

### 5. Introducir arquitectura agentic sin reemplazar la capa operativa

La recomendacion correcta no es reemplazar Celery/FastAPI por CrewAI. La recomendacion correcta es:

- Celery/FastAPI/Redis siguen siendo la capa operativa de jobs
- CrewAI entra como motor interno de razonamiento, planificacion y colaboracion
- Postgres y MinIO siguen siendo la fuente durable de artefactos

El patron recomendado es:

- `outer orchestration`
  - FastAPI crea el job
  - Celery corre el worker
- `inner agentic runtime`
  - un `CrewAI Flow` por job
  - uno o varios `Crew` especializados
  - memoria compartida por job
- `durable truth`
  - Postgres para estado estructurado
  - MinIO para assets y snapshots
  - Redis solo para progreso y señalizacion de corto plazo

### 6. La memoria debe tener tres capas

No conviene confiar en una sola memoria vectorial para "recordar la pelicula".

Recomiendo tres capas:

- `Flow state`
  - estado estructurado y versionado del job
  - outline, biblias, scene plans, shot plans, aprobaciones
- `Artifact store`
  - Postgres + MinIO
  - fuente de verdad durable y auditable
- `Semantic memory`
  - CrewAI Memory para recall contextual entre agentes
  - util para continuidad, decisiones previas y contexto recuperable

Regla clave:

- si algo afecta el resultado final o debe sobrevivir reintentos/reanudaciones, no basta con memoria semantica; debe persistirse como dato estructurado

## Decisiones de producto recomendadas

### 0. MVP comercial no significa MVP fragil

Este roadmap debe asumir desde el inicio:

- SLOs operativos por tipo de job
- trazabilidad completa por capitulo, escena, shot y provider
- manejo formal de errores y reanudacion
- telemetria de costo, calidad y throughput
- controles de calidad editorial y tecnica antes de publicar

Si estas piezas no entran en el MVP, el software podra generar videos, pero no sera una solucion enterprise comercializable.

### 1. Lanzar Veo como modo premium corto primero

Recomiendo que la primera version de produccion soporte:

- total de 48 a 96 segundos
- 6 a 12 clips
- `16:9`
- `1080p`
- 8 segundos por clip

Motivo:

- la UI y los workflows actuales ya estan pensados para 6-12 escenas
- 600 segundos equivalen a 75 clips de 8s, lo cual es costoso y operativamente pesado
- el sistema de aprobaciones y reintentos todavia no esta preparado para ese volumen

### 1.1. Lanzar Hunyuan como lane experimental controlado

Si se agrega open source, recomiendo que la primera version de Hunyuan sea:

- `experimental`
- solo para workers GPU dedicados
- enfocada en 480p/720p y upscale opcional
- sin prometer paridad total con Veo desde el primer release

Motivo:

- la calidad puede ser muy alta, pero el perfil operativo es distinto
- el repo actual nacio para Bedrock y servicios gestionados, no para checkpoints grandes de video
- el hardware target historico del proyecto era una RTX 3050, y HunyuanVideo-1.5 pide oficialmente 14 GB minimos con offloading

### 2. Claude genera la escena; Veo solo la materializa

Claude debe producir un `scene pack` estructurado por escena, por ejemplo:

- `scene_id`
- `scene_duration_total_s`
- `narration_es`
- `visual_goal`
- `subject`
- `action`
- `location`
- `time_of_day`
- `camera_position`
- `camera_motion`
- `composition`
- `lens_language`
- `ambience`
- `negative_prompt`
- `continuity_tokens`
- `reference_images`
- `veo_prompt_en`
- `audio_intent`
- `shots[]`

Cada `scene pack` debe contener uno o varios `shots` de 8 segundos. Ejemplo de `ShotPlan`:

- `shot_id`
- `scene_id`
- `duration_s=8`
- `shot_role`: `master | medium | close_up | over_shoulder | insert | reaction`
- `camera_position`
- `camera_angle`
- `camera_motion`
- `subject_focus`
- `transition_from_previous`: `scene_start | hard_cut | match_cut | extension`
- `continuity_source`: `none | previous_shot_last_frame | reference_images | previous_video`
- `veo_prompt_en`

La regla de producto debe ser:

- `escena narrativa`
  - unidad dramatica
  - puede durar mas de 8 segundos
- `shot`
  - unidad visual generada
  - dura 8 segundos por defecto en Veo/Hunyuan
- `clip`
  - archivo resultante de un shot individual

Esto permite casos como:

- aula vista desde el fondo, 8s
- profesor desde lateral izquierdo, 8s
- alumnos sobre el hombro del profesor, 8s

Todo eso sigue siendo una sola escena dramatica compuesta por tres shots.

### 2.1. Patrones de extension de escena

No todas las escenas largas deben resolverse igual. Recomiendo documentar tres patrones:

- `coverage_cut`
  - varios shots independientes de 8s
  - misma escena, distinta cobertura
  - es el modo por defecto para dialogo, clases, reuniones, interrogatorios
- `continuous_move`
  - un shot de 8s con bloqueo y movimiento de camara interno
  - util cuando el valor esta en el desplazamiento de camara, no en el montaje
- `scene_extension`
  - extender un video Veo ya generado para continuar la misma accion
  - util cuando la continuidad fisica importa mas que el cambio de angulo

Regla operativa:

- si cambia el angulo de camara de forma clara, crear un nuevo `shot`
- si continua la misma accion desde la misma puesta en escena, evaluar `video extension`
- si hace falta anclar continuidad entre shots, reutilizar `referenceImages` o `lastFrame`

### 3. Mantener TTS como canon narrativo al menos en v1

Veo 3.1 genera audio nativo. Eso choca con el flujo actual de narrador externo.

Para documentales narrados, recomiendo en v1:

- usar Claude para escribir narracion
- sintetizar voz con el proveedor TTS actual
- pedir a Veo escenas con ambiente o SFX ligeros, no dialogo principal
- mezclar con ducking fuerte o mutear el audio Veo si estorba al narrador

No recomiendo depender de dialogo nativo de Veo en el primer release de documental narrado.

### 4. No mover el orquestador a LangGraph en la primera fase

Ya existe un esqueleto en `src/blackforge/orchestration/langgraph_pipeline.py`, pero hoy el backend real usa Celery y aprobaciones persistidas. Meter LangGraph ahora agregaria una segunda capa de orquestacion sin resolver el problema principal.

Recomendacion:

- fase 1 y 2 sobre Celery/worker actual
- evaluar LangGraph solo cuando haya bucles sofisticados de regeneracion y QC automatico

## Requisitos no funcionales enterprise

### 1. Observabilidad y metricas

El sistema debe producir metricas de negocio y metricas tecnicas desde el primer release comercial.

Stack recomendado:

- instrumentacion en aplicacion con `OpenTelemetry`
- export por `OTLP`
- `OpenTelemetry Collector` como capa intermedia obligatoria
- Prometheus/Grafana para metricas y dashboards
- backend de traces compatible con OTLP

OpenTelemetry no debe entrar como adorno. Debe ser el lenguaje comun de telemetria del producto.

Modelo de telemetria recomendado:

- todos los procesos del runtime deben emitir trazas y metricas via `OpenTelemetry SDK`
- ningun servicio debe exportar directo a vendors finales; la salida debe pasar por `OTLP -> OpenTelemetry Collector`
- los IDs de alta cardinalidad como `job_id`, `scene_id`, `shot_id`, `flow_run_id` y `provider_operation_id` deben vivir en spans, eventos y logs correlacionados, no como labels de metricas
- las dimensiones de metricas deben limitarse a cardinalidad controlada como `provider`, `model`, `product_profile`, `environment`, `status`, `error_type` y `quality_gate_profile`
- las metricas de costo deben soportar correlacion con trazas mediante exemplars o atributos de span cuando el backend lo permita

Spans minimos requeridos:

- `job.create`
- `flow.run`
- `agent.task`
- `chapter.summarize`
- `scene.plan`
- `shot.generate`
- `provider.generate`
- `provider.extend`
- `render.normalize`
- `render.concat`
- `qc.evaluate`
- `approval.wait`

Metricas minimas:

- tiempo total por job
- tiempo por etapa
- tiempo por agente
- tiempo por provider
- costo por job
- costo por minuto util generado
- tasa de aprobacion por escena y por shot
- tasa de regeneracion
- tasa de fallos por categoria
- cola y espera por worker
- uso de VRAM/CPU/RAM
- storage consumido por job
- porcentaje de jobs reanudados con exito

Metricas de costo que deben salir por OpenTelemetry:

- `job.cost.usd`
- `job.cost.estimated_usd`
- `scene.cost.usd`
- `shot.cost.usd`
- `provider.cost.usd`
- `cost_per_approved_second.usd`
- `cost_per_delivery_package.usd`

Costos y metricas no deben reconstruirse desde logs crudos. Deben salir como instrumentos OTel de primer orden y quedar consultables desde dashboards y alertas operativas.

### 2. Manejo de errores

El sistema debe clasificar errores y responder de forma distinta segun su naturaleza:

- `retryable_transient`
- `retryable_provider`
- `non_retryable_validation`
- `non_retryable_content_policy`
- `human_action_required`
- `infrastructure_failure`

Requisitos minimos:

- retries con backoff y limites
- dead-letter queue o equivalente
- checkpoints reanudables
- compensacion para assets parciales
- cancelacion segura del job
- visibilidad completa del ultimo estado consistente

### 3. Calidad profesional

El output debe cumplir criterios tecnicos y editoriales de nivel comercial:

- continuidad narrativa y visual
- framing y coverage intencionales
- normalizacion de audio y mezcla limpia
- resolucion/fps/codec correctos
- titulos, captions y safe areas cuando aplique
- versiones finales y derivados consistentes
- aprobacion editorial antes de publicar

### 4. Operacion y gobierno

La plataforma debe poder:

- auditar decisiones de agentes
- rastrear prompts, assets y aprobaciones
- aplicar budgets y stop-loss por job
- ejecutar rollback o rerun controlado
- diferenciar entornos `dev | staging | prod`

## Roadmap por fases

## Fase 0. Contratos, configuracion e infraestructura

### Objetivo

Preparar el sistema para soportar varios modos de generacion sin romper el flujo actual.

### Cambios

- Agregar nuevos settings:
  - `PRODUCT_PROFILE`
  - `OUTPUT_PACKAGE_PROFILE`
  - `ENABLE_TRACING`
  - `ENABLE_METRICS`
  - `ENABLE_ERROR_TRACKING`
  - `ENABLE_COST_GUARDS`
  - `QUALITY_GATE_PROFILE`
  - `JOB_BUDGET_USD`
  - `JOB_MAX_RETRIES`
  - `AGENTIC_RUNTIME`
  - `AGENTIC_FLOW_PERSISTENCE`
  - `AGENTIC_MEMORY_ENABLED`
  - `AGENTIC_MEMORY_SCOPE_PREFIX`
  - `AGENTIC_MEMORY_STORAGE_DIR`
  - `AGENTIC_MEMORY_LLM_PROVIDER`
  - `AGENTIC_MEMORY_LLM_MODEL`
  - `AGENTIC_MEMORY_EMBEDDER_PROVIDER`
  - `AGENTIC_MEMORY_EMBEDDER_MODEL`
  - `AGENTIC_USE_BEDROCK_EMBEDDINGS`
  - `OTEL_EXPORTER_OTLP_ENDPOINT`
  - `OTEL_EXPORTER_OTLP_PROTOCOL`
  - `OTEL_SERVICE_NAME`
  - `OTEL_SERVICE_NAMESPACE`
  - `OTEL_SERVICE_VERSION`
  - `OTEL_RESOURCE_ATTRIBUTES`
  - `OTEL_TRACES_SAMPLER`
  - `OTEL_TRACES_SAMPLER_ARG`
  - `OTEL_METRIC_EXPORT_INTERVAL_MS`
  - `OTEL_ENABLE_PROVIDER_SPANS`
  - `OTEL_ENABLE_COST_METRICS`
  - `VIDEO_GENERATION_MODE`
  - `VIDEO_PROVIDER`
  - `GEMINI_API_KEY`
  - `GEMINI_VEO_MODEL_ID`
  - `SOURCE_TYPE`
  - `SOURCE_URI`
  - `SOURCE_FORMAT`
  - `SOURCE_LANGUAGE`
  - `BOOK_SOURCE_PROVIDER`
  - `BOOK_MAX_CHAPTERS`
  - `BOOK_CHAPTER_WINDOW`
  - `BOOK_SUMMARY_TARGET_TOKENS`
  - `BOOK_ENABLE_PROMPT_CACHE`
  - `BOOK_REQUIRE_PUBLIC_DOMAIN_METADATA`
  - `HUNYUAN_MODEL_FAMILY`
  - `HUNYUAN_MODEL_VARIANT`
  - `HUNYUAN_CHECKPOINT_PATH`
  - `HUNYUAN_DIFFUSERS_MODEL_ID`
  - `HUNYUAN_ENABLE_CPU_OFFLOAD`
  - `HUNYUAN_NUM_INFERENCE_STEPS`
  - `HUNYUAN_NUM_FRAMES`
  - `HUNYUAN_OUTPUT_FPS`
  - `VIDEO_SCENE_DURATION_S`
  - `VIDEO_ASPECT_RATIO`
  - `VIDEO_RESOLUTION`
  - `VIDEO_USE_NATIVE_AUDIO`
- Cambiar default del LLM de Bedrock a Claude:
  - recomendado: `anthropic.claude-sonnet-4-20250514-v1:0`
  - fallback: `anthropic.claude-3-5-sonnet-20241022-v2:0`
- Agregar `google-genai` a dependencias del backend.
- Agregar dependencias del runtime agentic:
  - `crewai`
  - opcionalmente `crewai-tools`
- Agregar dependencias de observabilidad:
  - `opentelemetry-api`
  - `opentelemetry-sdk`
  - `opentelemetry-exporter-otlp`
  - instrumentacion para `FastAPI`, `Celery`, `Redis`, `SQLAlchemy`, `requests/httpx` segun stack final
- Preparar extras o una imagen separada para proveedores open source de video:
  - `torch`
  - `diffusers`
  - `accelerate`
  - `transformers`
  - `safetensors`
  - kernels de atencion opcionales
- Extender `CreateJobRequest` con:
  - `product_profile`
  - `output_package_profile`
  - `quality_gate_profile`
  - `job_budget_usd`
  - `source_type`
  - `source_uri`
  - `source_format`
  - `source_language`
  - `adaptation_mode`
  - `max_chapters`
  - `chapter_selection`
  - `generation_mode`
  - `video_provider`
  - `scene_duration_s`
  - `aspect_ratio`
  - `resolution`
  - `native_audio_policy`
- Extender `JobDetailResponse` con metadatos de provider y pipeline mode.
- Extender `JobDetailResponse` con:
  - metricas de ejecucion
  - costo acumulado
  - estado de quality gates
  - error taxonomy
- Agregar storage layout para assets Veo:
  - `video_clips/raw/`
  - `video_clips/normalized/`
  - `video_prompts/`
  - `provider_ops/`
  - `qc/`
- Agregar storage layout para fuentes editoriales:
  - `sources/books/raw/`
  - `sources/books/normalized/`
  - `sources/books/chapters/`
  - `sources/books/metadata/`
  - `bibles/characters/`
  - `bibles/locations/`
- Agregar storage layout para modelos/checkpoints self-hosted:
  - `models/video/hunyuan/`
  - `cache/video/hunyuan/`
  - `runs/hunyuan/`
- Agregar storage layout para runtime agentic:
  - `runs/flows/`
  - `memory/crewai/`
  - `snapshots/state/`
- Agregar storage layout para operacion y calidad:
  - `metrics/`
  - `errors/`
  - `qc/reports/`
  - `deliverables/packages/`
- Agregar servicios de plataforma:
  - `otel-collector`
  - `prometheus`
  - `grafana`
  - backend de traces compatible con `OTLP`

### Archivos impactados

- `backend/app/config.py`
- `.env.example`
- `docker-compose.yml`
- `backend/requirements.txt`
- nuevo modulo recomendado: `backend/app/telemetry/otel.py`
- `backend/app/models/requests.py`
- `backend/app/models/responses.py`
- nuevo modulo recomendado: `src/blackforge/agentic/`
- nuevo modulo recomendado: `src/blackforge/integrations/books/`
- opcionalmente una nueva imagen Docker o servicio `worker-gpu-video`

### Criterio de salida

- la API puede crear jobs con `classic_documentary`, `veo_cinematic_8s` o `book_to_film_8s`
- el worker recibe config suficiente para elegir un provider de video real
- el sistema ya diferencia proveedores managed y self-hosted
- la plataforma ya puede exportar trazas y metricas base por `OTLP` hacia el collector

## Fase 0D. Foundation enterprise de observabilidad, errores y gobierno

### Objetivo

Hacer que el primer release sea operable como producto comercial, no como experimento.

### Cambios

- Definir una taxonomia de errores de plataforma:
  - `provider_timeout`
  - `provider_validation_error`
  - `policy_rejection`
  - `memory_resume_error`
  - `asset_integrity_error`
  - `human_approval_blocked`
  - `render_failure`
- Agregar instrumentacion distribuida del workflow:
  - spans por flow
  - spans por agente
  - spans por provider
  - spans por render
  - eventos por aprobacion y reanudacion
- Definir un contrato OTel interno para atributos de span:
  - `job.id`
  - `flow.run_id`
  - `agent.role`
  - `chapter.id`
  - `scene.id`
  - `shot.id`
  - `provider.name`
  - `provider.model`
  - `product.profile`
  - `quality_gate.profile`
  - `retry.count`
  - `error.type`
- Definir metricas de negocio:
  - jobs creados
  - jobs completados
  - jobs fallidos
  - minutos generados
  - aprobacion en primera pasada
  - regeneracion promedio
  - costo por entrega
- Definir metricas tecnicas:
  - latencia por etapa
  - retries por categoria
  - disponibilidad por provider
  - uso de recursos
  - tiempos de cola
- Definir instrumentos OTel explicitos:
  - contadores para volumen, retries, fallos y aprobaciones
  - histogramas para latencia, duracion util, costo y tiempo en cola
  - gauges o async instruments para backlog, uso de GPU, VRAM y almacenamiento
- Definir politica de cardinalidad:
  - IDs unicos solo en traces y logs correlacionados
  - labels de metricas limitados a dimensiones estables
- Agregar budgets y guardrails:
  - stop-loss por job
  - max retries por escena/shot
  - max gasto por provider
  - circuit breakers por proveedor
- Agregar manejo de errores enterprise:
  - retry policy tipada
  - dead-letter queue o cola de intervencion
  - snapshot del ultimo estado consistente
  - cancelacion segura y cleanup parcial
- Agregar package profiles:
  - `feature_film_master`
  - `commercial_master_16x9`
  - `social_vertical_master`
  - `multiformat_campaign_bundle`

### Archivos impactados

- `backend/app/config.py`
- `backend/app/models/requests.py`
- `backend/app/models/responses.py`
- `backend/app/services/orchestrator.py`
- `backend/app/worker.py`
- `backend/app/telemetry/otel.py`
- nuevo modulo recomendado: `src/blackforge/agentic/observability_hub.py`
- nuevo modulo recomendado: `src/blackforge/agentic/error_policy.py`

### Criterio de salida

- cada job expone metricas, costo, errores y quality gates
- la plataforma puede distinguir fallos recuperables de fallos terminales
- existe visibilidad operativa suficiente para vender y soportar el producto

## Fase 0C. Arquitectura agentic con CrewAI Memory

### Objetivo

Transformar el pipeline en un sistema multiagente sin perder trazabilidad, reanudacion ni control operativo.

### Cambios

- Introducir un `MovieProductionFlow` de CrewAI por job.
- Mantener Celery como contenedor externo del job y ejecutar el Flow dentro del worker.
- Definir `MovieState` estructurado con Pydantic, por ejemplo:
  - `job_id`
  - `documentary_id`
  - `book_source`
  - `chapter_summaries`
  - `character_bible`
  - `location_bible`
  - `scene_plans`
  - `shot_plans`
  - `provider_operations`
  - `approvals`
  - `final_timeline`
- Habilitar persistencia del Flow con `@persist`.
- No depender del backend default de SQLite para produccion distribuida sin una decision de despliegue explicita.
- Crear una `Memory` compartida por job y pasarla a los crews/agentes relevantes.
- Configurar memoria para AWS:
  - LLM de analisis de memoria sobre Claude en Bedrock
  - embeddings sobre AWS Bedrock
- No usar el embedder por defecto de OpenAI.
- Definir scopes de memoria por job:
  - `/job/{job_id}/global`
  - `/job/{job_id}/book`
  - `/job/{job_id}/characters`
  - `/job/{job_id}/locations`
  - `/job/{job_id}/chapter/{n}`
  - `/job/{job_id}/scene/{id}`
  - `/job/{job_id}/shot/{id}`
  - `/shared/cinematography`
- Usar `step_callback` y `task_callback` para:
  - sincronizar progreso a Redis
  - guardar trazas en Postgres
  - emitir eventos de observabilidad
- Definir equipos/agentes especializados, no delegacion libre total:
  - `source_ingestor`
  - `chapter_summarizer`
  - `continuity_bible_builder`
  - `scene_planner`
  - `scene_coverage_planner`
  - `veo_prompt_director`
  - `provider_router`
  - `qc_agent`
  - `editor_agent`

### Regla de memoria

CrewAI memory no debe ser la garantia unica de recuerdo.

Debe usarse asi:

- memoria semantica
  - para recuperar decisiones previas y contexto util
- estado estructurado
  - para representar la verdad del flujo
- artefactos persistidos
  - para todo lo que tenga impacto contractual o editorial

### Archivos impactados

- nuevo modulo: `src/blackforge/agentic/flow.py`
- nuevo modulo: `src/blackforge/agentic/crew_factory.py`
- nuevo modulo: `src/blackforge/agentic/memory_factory.py`
- nuevo modulo: `src/blackforge/agentic/state_models.py`
- `backend/app/worker.py`
- `backend/app/services/orchestrator.py`
- `backend/app/config.py`
- `backend/requirements.txt`

### Criterio de salida

- cada job corre un Flow agentic reanudable
- varios agentes colaboran con memoria compartida por job
- el sistema puede reanudar una corrida sin perder outline, biblias, escenas ni shots

## Fase 0B. Ingesta de libros y normalizacion editorial

### Objetivo

Hacer que el sistema pueda aceptar una novela o libro narrativo como fuente primaria sin depender de Wikipedia.

### Cambios

- Crear una capa `BookSourceProvider` con al menos:
  - `project_gutenberg`
  - `txt_upload`
  - `epub_upload`
- Para `Project Gutenberg`:
  - resolver metadata via catalogo oficial `RDF/OPDS/CSV`
  - descargar preferentemente `HTML` o `Plain Text UTF-8`
  - guardar `ebook_id`, `authors`, `language`, `release_date`, `source_urls`
- Crear un normalizador editorial que:
  - quite front matter y licencias repetitivas
  - detecte capitulos, partes, epilogos y notas
  - preserve titulos de capitulo y orden
  - convierta el contenido a texto limpio versionado
- Crear modelos nuevos:
  - `BookSource`
  - `BookMetadata`
  - `BookChapter`
  - `ChapterSummary`
  - `NarrativeBeat`
- Persistir procedencia:
  - fuente original
  - formato descargado
  - hash del contenido
  - notas de licencia/public domain
- Empezar por texto limpio y EPUB. PDF escaneado debe quedar fuera del MVP.

### Archivos impactados

- nuevo modulo: `src/blackforge/integrations/books/project_gutenberg.py`
- nuevo modulo: `src/blackforge/integrations/books/epub_loader.py`
- nuevo modulo: `src/blackforge/models/book_source.py`
- nuevo modulo: `src/blackforge/pipeline/book_ingestion.py`
- `backend/app/models/requests.py`
- `backend/app/worker.py`

### Criterio de salida

- la API acepta un libro como fuente
- el worker puede producir una representacion normalizada por capitulos
- el sistema conserva trazabilidad editorial suficiente para rehacer la adaptacion

## Fase 1. Claude como director narrativo y de escenas

### Objetivo

Reemplazar la generacion libre actual por un proceso estructurado, validable y orientado a clips cinematicos de 8 segundos.

### Cambios

- Dividir el trabajo de Claude en 3 prompts separados:
  - `chapter_summarizer`
  - `chapter_to_beats`
  - `story_planner`
  - `scene_writer`
  - `veo_prompt_director`
- Agregar un cuarto prompt opcional:
  - `prompt_critic`
- Agregar un quinto prompt muy recomendable:
  - `continuity_bible_builder`
- Cambiar la logica de conteo de escenas:
  - `scene_count = ceil(target_duration / 8)` para `veo_cinematic_8s`
- Agregar una segunda capa de descomposicion:
  - `shot_count = ceil(scene_duration_total_s / 8)` para escenas de cobertura multiple
- Para libros, agregar planificacion jerarquica:
  - `scene_count_per_chapter = budgeted by runtime share`
  - no todos los capitulos deben pesar igual
- Crear nuevos modelos Pydantic:
  - `ChapterAdaptationPlan`
  - `CharacterBible`
  - `LocationBible`
  - `ScenePlan`
  - `ShotPlan`
  - `SceneCoveragePlan`
  - `VeoScenePrompt`
  - `SceneContinuityBible`
  - `PromptCritique`
- Hacer que Claude devuelva JSON estricto y reintentar si la validacion falla.
- Aplicar prompting basado en la guia oficial:
  - rol claro
  - contexto primero
  - tarea al final
  - formato esperado
  - few-shot
  - autocritica antes de responder
- Usar `CountTokens` antes de invocar Claude en prompts largos para evitar desbordes.

### Ajuste clave de dominio

La restriccion real no es "cada escena dura 8 segundos". La restriccion real es "cada shot generado dura 8 segundos". Una escena puede durar mas y construirse mediante cobertura.

Definicion recomendada:

- `scene`
  - unidad dramatica y narrativa
  - puede durar 8s, 16s, 24s o mas
- `shot`
  - unidad de sintesis visual
  - 8 segundos por defecto
- `coverage`
  - conjunto ordenado de shots que construyen una misma escena

No basta con "un parrafo de narracion". Hace falta una unidad dramatica visual y, si la escena dura mas de 8 segundos, una estrategia explicita de cobertura o extension.

El prompt de Claude debe obligar a producir escenas con:

- una sola accion principal
- un solo beat emocional
- una cobertura de camara coherente, aunque haya varios shots
- un look visual coherente con el style bible global

Y por shot:

- un angulo dominante
- un encuadre dominante
- una transicion clara respecto al shot previo
- una razon dramatica para existir

Para adaptaciones de novela, ademas debe respetar:

- continuidad de personajes recurrentes
- continuidad de localizacion y epoca
- seleccion de eventos narrativamente esenciales, no resumen uniforme de todos los parrafos
- compresion dramatica por capitulo para que la pelicula no sea una sucesion mecanica de micro-resumenes

### Archivos impactados

- `src/blackforge/integrations/bedrock_llm.py`
- `src/blackforge/models/book_source.py`
- `src/blackforge/pipeline/book_ingestion.py`
- `src/blackforge/pipeline/book_adaptation.py`
- `src/blackforge/pipeline/story_generation.py`
- `src/blackforge/pipeline/prompt_generation.py`
- `Story-telling-prompt.md`
- nuevo archivo recomendado: `docs/prompt_veo_generation.md`

### Criterio de salida

- Claude entrega scene packs estructurados y validados
- el modo Veo ya no depende del generador de prompts orientado a SD3.5/OpenAI

## Fase 2. Capa de providers de video

### Objetivo

Convertir la abstraccion de provider en una capa de produccion que soporte varios backends reales.

### Cambios

- Extender `VideoProvider` para incluir:
  - `capabilities()`
  - `generate_clip()`
  - `extend_clip()` cuando aplique
  - `get_operation_status()` cuando aplique
  - `download_asset()` cuando aplique
- Agregar `VideoProviderRegistry` y selector por config.
- Estandarizar metadata de salida para todos los proveedores.

### Archivos impactados

- `src/blackforge/integrations/video/provider_base.py`
- `src/blackforge/integrations/video/models.py`
- `src/blackforge/integrations/video/client.py`
- nuevo modulo recomendado: `src/blackforge/integrations/video/registry.py`

### Criterio de salida

- la capa de video soporta mas de un backend sin ramas ad hoc en el dominio

## Fase 2A. Provider real de Veo 3.1

### Objetivo

Implementar `GoogleVeoProvider` real y confiable.

### Cambios

- Reemplazar el stub actual por integracion real con `google-genai`.
- Soportar:
  - `prompt`
  - `durationSeconds=8`
  - `aspectRatio`
  - `resolution`
  - `referenceImages`
  - `lastFrame`
  - `image` inicial para image-to-video
  - `video extension` para continuidad de accion cuando aplique
- Manejar flujo asincrono:
  - crear operacion
  - persistir `operation.name`
  - hacer polling
  - descargar archivo final
- Persistir metadata por clip:
  - provider model
  - request payload
  - timestamps
  - request id / operation id
  - path del clip descargado
- Hacer el provider idempotente:
  - si ya existe `operation_id` exitoso para esa escena, no regenerar
- Permitir dos modos de continuidad:
  - `new_shot`
    - genera un shot nuevo con continuidad via prompt + referencias
  - `extension`
    - continua un video Veo previo cuando el objetivo es extender la misma accion
- Implementar reintentos inteligentes:
  - no repetir sobre el mismo payload en errores permanentes
  - backoff sobre errores transitorios

### Modelo minimo de salida

`VideoAsset.metadata` deberia crecer para incluir:

- `operation_name`
- `model_id`
- `resolution`
- `aspect_ratio`
- `seed`
- `source_prompt_hash`
- `downloaded_at`
- `has_native_audio`
- `parent_asset_uri`
- `continuity_mode`
- `source_last_frame_uri`
- `shot_id`
- `scene_id`

### Criterio de salida

- una escena puede generar un clip Veo 3.1 real y descargable
- una escena larga puede construirse por coverage de varios shots o por extension controlada
- el provider deja de ser un placeholder

## Fase 2B. Provider self-hosted para HunyuanVideo

### Objetivo

Agregar un backend open source para no depender solo de proveedores cerrados.

### Recomendacion de alcance

Para la primera version, recomiendo integrar:

- `HunyuanVideo-1.5` como T2V principal
- `HunyuanVideo-I2V` como ruta de continuidad y escenas con referencia visual fuerte

No recomiendo arrancar con el `HunyuanVideo` original como primera opcion operativa del producto; es mas pesado y menos pragmatico para una primera integracion.

### Cambios

- Crear `HunyuanVideoProvider`.
- Ejecutarlo en un worker GPU separado o cola dedicada.
- Soportar al menos:
  - text-to-video
  - image-to-video
  - configuracion de steps
  - control de frames/fps
  - offloading y VAE tiling
- Empezar con la integracion oficial de Diffusers para `HunyuanVideo-1.5`, porque Tencent ya la documenta oficialmente.
- Persistir metadata de inferencia:
  - modelo exacto
  - variant `480p|720p`
  - steps
  - frames
  - fps
  - seed
  - offload enabled
  - tiempo de inferencia
  - memoria estimada
- Si el clip target del producto es 8 segundos, el contrato interno debe fijar esa duracion y el provider debe aproximarla via `num_frames + fps`, no via un `durationSeconds` de API como hace Veo.
- Agregar pipeline opcional de super-resolution a 1080p cuando se use Hunyuan y el modelo base corra en 480p/720p.

### Requisitos operativos reales

Segun el repo oficial de `HunyuanVideo-1.5`:

- Linux
- Python 3.10+
- GPU NVIDIA con CUDA
- 14 GB de VRAM minima usando offloading

Eso implica una decision de despliegue:

- o se provisiona una cola/worker GPU dedicada para Hunyuan
- o Hunyuan se deja fuera del path default del producto

### Archivos impactados

- nuevo modulo: `src/blackforge/integrations/video/hunyuan_video.py`
- `backend/app/worker.py`
- `docker-compose.yml`
- `backend/requirements.txt` o imagen GPU separada

### Criterio de salida

- una escena puede generarse con un backend open source real
- la API puede seleccionar `video_provider=hunyuan_local`
- el sistema documenta claramente los requisitos de hardware

## Fase 3. Integracion al worker productivo

### Objetivo

Conectar fuentes editoriales y providers de video al flujo que usa el backend real.

### Cambios

- En `backend/app/worker.py`, separar el pipeline en tres ramas:
  - el worker debe lanzar `MovieProductionFlow` como runtime interno
  - rama nueva de libros y adaptacion narrativa
  - rama actual de imagenes
  - rama nueva de clips managed
  - rama nueva de clips self-hosted
- Nuevos estados recomendados:
  - `ingesting_book_source`
  - `normalizing_book`
  - `summarizing_chapters`
  - `planning_adaptation`
  - `planning_scene_coverage`
  - `generating_scene_prompts`
  - `generating_shots`
  - `generating_video_clips`
  - `awaiting_clip_approval` (opcional)
  - `stitching_shots_into_scenes`
  - `mixing_audio`
  - `stitching_clips`
- Subir clips raw a MinIO apenas terminen.
- Si una escena tiene varios shots:
  - generar y aprobar shots individualmente
  - luego coserlos en una `scene timeline`
- Reutilizar `normalize_video_clip()` y `concatenate_videos()` para el ensamblado final.
- Si se usa TTS:
  - generar voz narrada por escena
  - mezclar audio del clip con ducking o muting selectivo
- Mantener upload final y estadisticas.
- Si se usa Hunyuan:
  - enrutar el job a una cola GPU adecuada
  - capturar telemetria de VRAM/tiempo para capacity planning

### Politica de audio recomendada

v1:

- `mute_native_audio`: elimina audio Veo si el narrador es protagonista
- `duck_native_audio`: baja la pista del clip por debajo del narrador

v2:

- `ambient_only`: mantener solo ventanas sin narrador o escenas de transicion

### Archivos impactados

- `backend/app/worker.py`
- `src/blackforge/integrations/ffmpeg.py`
- `src/blackforge/models/video_render.py`

### Criterio de salida

- un job del backend puede terminar en un MP4 final compuesto por clips Veo reales

## Fase 4. Aprobaciones, trazabilidad y QC

### Objetivo

Evitar caja negra y habilitar regeneracion controlada por escena.

### Cambios

- No reutilizar ciegamente `image_approvals` para Veo.
- Crear un workflow de `scene asset approval` o `clip approvals`.
- Guardar por escena:
  - prompt Claude
  - prompt Veo final
  - critic/QC output
  - clip raw
  - clip normalized
  - decision humana
- Guardar por shot:
  - `shot_id`
  - `scene_id`
  - orden dentro de la escena
  - tipo de cobertura
  - continuidad usada: `hard_cut | match_cut | extension | last_frame_anchor`
  - asset padre si hubo extension
- Como Google no soporta `Logs and datasets` para Veo, guardar observabilidad propia en Postgres/MinIO.
- Agregar endpoints para:
  - ver prompt por escena
  - ver coverage por escena
  - aprobar/rechazar shot individual
  - aprobar/rechazar clip
  - regenerar solo una escena
  - regenerar solo un shot
  - reemplazar referencia de imagen

### QC automatico recomendado

Deterministico:

- duracion exacta
- resolucion correcta
- codec reproducible
- audio track presente/ausente segun politica
- loudness dentro de objetivo del perfil de salida
- validacion de package profile y deliverables esperados

Semantico:

- opcional: usar Gemini video understanding para verificar prompt adherence, presencia del sujeto, estilo y artefactos graves
- score de continuidad por escena
- score de adherencia a brief o campaign brief

### Sistema de metricas recomendado

Negocio:

- `% de jobs completados`
- `% de jobs publicados`
- tiempo a primera version aprobable
- tiempo a master final
- costo por job
- costo por segundo util aprobado
- tasa de reaprovechamiento de shots

Operacion:

- latencia por flow
- latencia por agente
- latencia por provider
- retries por tipo de error
- jobs pausados por aprobacion
- jobs reanudados con exito
- saturacion de workers y colas

Todas estas metricas deben publicarse via `OpenTelemetry`, con cardinalidad limitada y con correlacion a traces para drill-down operativo.

Calidad:

- tasa de aprobacion en primera pasada
- promedio de regeneraciones por escena
- porcentaje de clips rechazados por continuidad
- porcentaje de entregas que pasan quality gates sin intervencion manual
- variacion de loudness y errores tecnicos de render

### Archivos impactados

- `backend/app/db/models.py`
- `backend/app/routes/images.py` o nuevo `routes/clips.py`
- `backend/app/services/image_service.py` o nuevo servicio especifico
- nuevo modulo recomendado: `backend/app/services/metrics_service.py`
- nuevo modulo recomendado: `backend/app/routes/metrics.py`

### Criterio de salida

- cada escena puede regenerarse de forma aislada sin repetir todo el documental
- cada shot puede regenerarse sin destruir la escena completa

## Fase 4B. Telemetria, SRE y soporte comercial

### Objetivo

Convertir la observabilidad del pipeline en una capacidad operativa real para soporte enterprise.

### Cambios

- Instrumentar traces, metricas y eventos a nivel:
  - flow
  - agente
  - provider
  - render
  - aprobacion
- Consolidar el pipeline de telemetria:
  - `app/worker/api -> OTLP -> OpenTelemetry Collector -> Prometheus/Grafana + backend de traces + Sentry`
- Habilitar correlacion `trace_id/span_id` en logs estructurados y eventos de soporte.
- Agregar dashboards operativos:
  - throughput
  - error rate
  - p95/p99 por provider
  - costo acumulado
  - colas y saturacion
- Agregar alertas:
  - provider degradation
  - retry storm
  - queue backlog
  - GPU starvation
  - cost anomaly
- Agregar runbooks de soporte para:
  - reanudacion de flows
  - reproceso de escena/shot
  - caida de proveedor
  - corrupcion de asset
- Definir SLOs observables con datos OTel:
  - tiempo a primer corte aprobable
  - tasa de jobs completados dentro de SLA
  - error budget por provider
  - desviacion de costo estimado vs costo real

### Criterio de salida

- soporte tecnico puede diagnosticar un job sin leer logs crudos
- operaciones puede detectar degradacion antes de afectar SLA

## Fase 4C. Sistema de calidad profesional y release gates

### Objetivo

Asegurar que el software entregue masters y derivados con calidad comercial consistente.

### Cambios

- Definir `quality gate profiles` por producto:
  - `feature_film`
  - `documentary_premium`
  - `commercial_spot`
  - `social_multimedia`
- Agregar quality gates tecnicos:
  - duracion
  - codec
  - fps
  - resolucion
  - loudness
  - black frames / silent frames
- Agregar quality gates editoriales:
  - continuidad
  - adherence a brief
  - legibilidad narrativa
  - consistencia visual
- Agregar paquetes de entrega:
  - master final
  - subtitulos/captions si aplican
  - thumbnails/keyframes
  - versiones por aspecto y canal
- Crear golden sets y regresion de calidad para:
  - peliculas
  - cuñas comerciales
  - piezas multimedia

### Criterio de salida

- el MVP puede producir entregables listos para cliente, no solo archivos generados
- cada release del sistema se valida contra quality gates y golden sets

## Fase 5. Continuidad visual avanzada y mejoras premium

### Objetivo

Pasar de clips buenos a clips consistentes entre si.

### Cambios

- Usar `referenceImages` hasta 3 por escena cuando aplique:
  - personaje
  - producto/objeto
  - look general
- Generar imagenes de referencia previas desde el pipeline actual o desde un modulo dedicado.
- Introducir `continuity bible` persistida por documental:
  - rostro / vestuario / paleta / lente / entorno
- Agregar soporte progresivo a:
  - `9:16`
  - `veo-3.1-fast-generate-preview`
  - `image-to-video`
  - `lastFrame`
  - `video extension`

### Criterio de salida

- continuidad visual consistente entre escenas y regeneracion selectiva mas estable

## Cambios tecnicos concretos por modulo

## `src/blackforge/integrations/bedrock_llm.py`

Hoy esta orientado a texto plano e image prompts cortos. Debe evolucionar a un adapter mas general, por ejemplo:

- `generate_structured_story_plan()`
- `generate_structured_scene_pack()`
- `generate_scene_coverage_plan()`
- `generate_veo_prompt()`
- `critique_scene_prompt()`
- `summarize_chapter()`
- `build_character_bible()`
- `build_location_bible()`

No recomiendo seguir mezclando narrativa e image prompt en una sola clase.

## `src/blackforge/integrations/books/project_gutenberg.py`

Debe resolver:

- busqueda de metadata oficial
- descarga de HTML/TXT/EPUB segun disponibilidad
- parsing de procedencia y enlaces utiles
- persistencia de `ebook_id`, `release_date`, `language`, `authors`

La integracion debe apoyarse en catalogos oficiales, no en scraping libre del buscador web.

## `src/blackforge/pipeline/book_ingestion.py`

Debe encargarse de:

- normalizar el libro
- retirar front matter repetitivo
- detectar capitulos/partes/anexos
- emitir una estructura limpia y versionada

## `src/blackforge/pipeline/book_adaptation.py`

Debe nacer como pipeline nuevo y separado de `story_generation.py`.

Responsabilidades:

- sintetizar por capitulo
- asignar presupuesto de runtime por capitulo
- convertir capitulos en beats
- convertir beats en escenas filmables de 8s
- convertir escenas largas en coverage de shots de 8s
- producir una biblia de continuidad reutilizable por todos los prompts posteriores

## `src/blackforge/pipeline/story_generation.py`

Debe separar dos perfiles:

- `documentary_longform`
- `veo_cinematic_8s`
- `book_to_film_8s`

Para Veo:

- no usar la heuristica fija de 6-12 escenas por minuto
- exigir escenas visualmente ejecutables en 8 segundos
- producir metadata para continuidad y referencia
- permitir escenas narrativas mas largas via `shots[]`

Para libros:

- no recibir `WikiArticle` como unico tipo posible
- aceptar una fuente editorial estructurada
- dejar de apoyarse en `h2_sections` como unidad narrativa
- trabajar por capitulos y beats, no por chunks arbitrarios

## `src/blackforge/pipeline/prompt_generation.py`

No debe seguir siendo el centro del modo Veo. Hoy el modelo y el prompt base estan pensados para SD3.5/OpenAI.

Recomendacion:

- extraer una clase nueva: `VeoPromptGenerator`
- dejar `ImagePromptGenerator` solo para el pipeline clasico

## `src/blackforge/integrations/video/google_veo.py`

Es el modulo de mayor brecha. Debe pasar de stub a provider real.

## `src/blackforge/integrations/video/hunyuan_video.py`

Debe nacer como proveedor self-hosted con concerns distintos:

- lifecycle de pipeline local
- carga de checkpoints
- configuracion de GPU y offloading
- exportacion a mp4
- opcionalmente super-resolution

## `backend/app/worker.py`

Es el punto de integracion principal. La mayor parte del trabajo productivo esta aqui.

Debe pasar de pipeline lineal a host del runtime agentic:

- recibe el job desde Celery
- inicializa `MovieProductionFlow`
- inyecta memoria/config/providers
- sincroniza progreso con Redis
- pausa/reanuda alrededor de aprobaciones humanas

## `backend/app/services/orchestrator.py`

Debe dejar de tratar el job como un estado efimero suficiente en Redis.

Responsabilidades futuras:

- crear el run del flow
- asociar `job_id`, `documentary_id` y `flow_state_id`
- exponer progreso resumido al frontend
- reanudar o reiniciar ejecuciones de forma controlada
- exponer metricas, costo y quality gates del job
- propagar contexto de tracing entre API, orchestrator, worker y flow runtime

## `backend/app/db/models.py`

Conviene agregar nuevas tablas o generalizar las aprobaciones:

- `provider_operations`
- `clip_approvals`
- `scene_generation_runs`
- `flow_runs`
- `agent_task_runs`
- `memory_checkpoints`
- `chapter_adaptation_runs`
- `shot_generation_runs`
- `job_metrics`
- `job_costs`
- `quality_gate_runs`
- `delivery_packages`

## `src/blackforge/agentic/`

Debe nacer como capa nueva con responsabilidades claras:

- `flow.py`
  - define `MovieProductionFlow`
- `state_models.py`
  - define `MovieState`
- `memory_factory.py`
  - centraliza configuracion de CrewAI Memory con Bedrock
- `crew_factory.py`
  - crea los crews/agentes por rol
- `observability_hub.py`
  - centraliza `OpenTelemetry` tracer/meter providers, emision de spans, metricas de costo y payloads de alerta
- `error_policy.py`
  - centraliza taxonomia, retry policy y decision de compensacion

No recomiendo dispersar la logica agentic en `worker.py` o en wrappers del LLM.

## `src/blackforge/integrations/ffmpeg.py`

Ya tiene piezas utiles. Solo falta orientarlo a:

- concatenar clips Veo
- mezclar audio de narrador y audio nativo
- normalizar loudness
- validar masters y derivados por package profile

## Tecnologias adicionales que si recomiendo

### Obligatorias

- `google-genai`
  - para llamar la API de Gemini/Veo de forma oficial
- `GEMINI_API_KEY` como secreto de entorno
- logging interno de prompts/operations/results
  - porque Google no soporta logs/datasets para Veo
- arquitectura multi-provider con registro de capacidades
  - para no acoplar el dominio a un solo backend
- `CrewAI`
  - para orquestacion multiagente real dentro del job
- `OpenTelemetry`
  - para traces, metricas y eventos del runtime
- `OpenTelemetry Collector`
  - para centralizar recepcion `OTLP`, control de routing y aislamiento de vendors
- `Prometheus`
  - para consulta de metricas operativas alimentadas desde el collector
- `Grafana`
  - para dashboards ejecutivos y operativos sobre metricas/costos/quality gates
- `Sentry`
  - para error tracking y diagnostico de fallos de aplicacion correlacionado con `trace_id`

### Muy recomendables

- Bedrock `CountTokens`
  - para controlar costo y tamaño de prompts Claude
- Bedrock `OptimizePrompt`
  - para laboratorio interno de prompt tuning, no en runtime critico
- QC semantico con Gemini video understanding
  - opcional pero muy util para regeneracion automatica por escena
- lane open source con `HunyuanVideo-1.5`
  - por ser open source, tener soporte oficial en Diffusers y reducir dependencia de APIs cerradas
- Project Gutenberg `OPDS/XML-RDF/CSV`
  - para catalogo, procedencia y descarga automatizable de libros
- Prompt caching en Bedrock
  - para reutilizar contexto largo de capitulos, personajes y reglas de adaptacion
- `EbookLib`
  - para parsear EPUB cuando el texto plano no preserve bien la estructura del libro
- CrewAI Memory con embedder de AWS Bedrock
  - para memoria semantica compartida sin salirnos del stack AWS
- golden datasets y regression harness
  - para medir calidad y regresiones entre releases

### Necesarias si se activa Hunyuan

- `torch`
- `diffusers`
- `accelerate`
- `transformers`
- `safetensors`
- worker GPU dedicado
- almacenamiento local o de red para checkpoints

### Opcionales para Hunyuan, pero de alto impacto

- kernels de atencion acelerados
- CPU offload
- VAE tiling
- super-resolution posterior

### No recomendaria en la primera fase

- mover el backend completo a LangGraph
- confiar en CrewAI memory como unica fuente de verdad
- depender de dialogo nativo de Veo para documental narrado
- soportar videos largos de varios minutos desde el dia 1
- meter OCR/PDF escaneado en el mismo MVP de Gutenberg/EPUB/TXT

## Riesgos principales

### 1. Explosion de costo y latencia

Cada clip es una llamada asincrona a Veo. Si permites 5-10 minutos desde el primer release, el costo operativo y el tiempo de espera se disparan.

### 1.1. Explosion de complejidad operativa en open source

Hunyuan reduce dependencia de APIs cerradas, pero traslada el costo a:

- VRAM
- tiempos de inferencia
- management de checkpoints
- compatibilidad CUDA/PyTorch/kernels
- capacidad de workers GPU

### 2. Conflicto de audio

Veo genera audio nativo y el pipeline ya tiene narrador. Si no defines una politica de mezcla clara, el resultado final puede ser inusable.

### 3. Falta de continuidad entre clips

Sin `referenceImages`, `continuity bible` y un director de prompts consistente, cada clip puede verse como otra produccion distinta.

### 4. Aprobaciones mal alineadas

La aprobacion actual esta pensada para imagenes estaticas. Si no se rediseña el flujo, el usuario aprobara assets equivocados para un pipeline video-first.

### 5. Doble stack de modelos

Si no se fuerza Claude como canon textual, el sistema quedara mezclando DeepSeek/OpenAI/Claude/Gemini sin una responsabilidad clara.

### 6. Asumir paridad falsa entre Veo y Hunyuan

Seria un error de producto prometer que ambos proveedores:

- tienen la misma calidad
- responden igual
- aceptan los mismos controles
- escalan igual en costo y latencia

La capa multi-provider debe exponer capacidades y degradaciones, no esconderlas.

### 7. Tratar el dominio publico como un booleano sin procedencia

Para libros, el sistema necesita guardar:

- obra
- edicion o archivo fuente
- traduccion
- jurisdiccion operativa

Sin esa trazabilidad, el producto puede mezclar una obra de dominio publico con una traduccion o edicion que no lo sea.

### 8. Confundir memoria semantica con persistencia durable

CrewAI memory mejora el recall, pero no reemplaza:

- estado estructurado del flow
- tablas de ejecucion
- assets persistidos
- checkpoints reanudables

Si no se separan estas capas, una corrida larga puede "recordar" algo en contexto semantico y aun asi perder la verdad operativa del proyecto.

### 9. Persistencia local incompatible con workers distribuidos

CrewAI Flows usan SQLite por defecto para persistencia y la memoria puede apoyarse en storage local. Eso no es una garantia suficiente si:

- hay varios workers
- hay reinicios
- el job puede reanudarse en otra maquina

Hay que tomar una decision explicita de despliegue antes de asumir que el runtime agentic es durable.

### 10. Tratar el MVP como demo y no como release comercial

Si el MVP sale sin:

- metricas
- trazabilidad
- error handling formal
- quality gates
- dashboards operativos

entonces no sera un MVP enterprise; sera solo una demo tecnica cara de operar.

## Secuencia recomendada de entrega

1. Cambiar defaults a Claude y agregar configuracion base de producto enterprise.
2. Crear la capa de fuentes editoriales para Gutenberg/EPUB/TXT.
3. Introducir la capa agentic con CrewAI Flow, estado estructurado y memoria compartida.
4. Implementar foundation enterprise de metricas, errores, costos y gobierno.
5. Crear contratos Pydantic de libro, capitulo, beats, scenes, shots y flow state.
6. Endurecer la capa `VideoProvider` como registro multi-provider.
7. Implementar `GoogleVeoProvider` real.
8. Implementar `HunyuanVideoProvider` en cola GPU dedicada.
9. Integrar runtime agentic + ramas de libros + providers de video en `backend/app/worker.py`.
10. Reusar FFmpeg para normalization/concat/audio mix y package outputs.
11. Agregar observabilidad propia, checkpoints, quality gates y regeneracion por escena/shot.
12. Recien despues, trabajar continuidad avanzada, extension de video y enrutamiento dinamico por proveedor.

## Resultado esperado al terminar la fase inicial

Un job nuevo con `generation_mode=veo_cinematic_8s` deberia poder:

- leer Wikipedia
- ejecutar un `MovieProductionFlow` agentic con varios especialistas
- usar Claude en Bedrock para planear escenas narrativas y descomponerlas en shots de 8 segundos
- generar prompts cinematograficos consistentes por escena
- pedir a Veo 3.1 un clip por escena
- o descomponer una escena larga en varios shots de 8 segundos
- almacenar y, si hace falta, aprobar o regenerar cada clip
- mezclar narracion/TTS y ensamblar el video final
- dejar trazabilidad completa de prompts, operaciones y resultados

Un job nuevo con `generation_mode=book_to_film_8s` deberia poder:

- ingerir un libro desde Project Gutenberg o archivo propio
- normalizarlo y segmentarlo por capitulos
- compartir memoria por job entre agentes de resumen, continuidad, scene planning y QC
- usar Claude en Bedrock para sintetizar cada capitulo
- convertir capitulos en beats dramaticos y luego en escenas narrativas compuestas por shots de 8 segundos
- permitir que una escena dramatica se cubra con varios shots de 8 segundos
- mantener biblia de personajes y localizaciones
- generar narracion breve y prompt cinematografico por escena
- pedir a Veo o Hunyuan un clip por escena
- ensamblar una pelicula narrada con trazabilidad por capitulo, beat y escena

En paralelo, un job con `video_provider=hunyuan_local` deberia poder:

- reutilizar el mismo `scene pack` generado por Claude
- reanudar el flow sin perder estado narrativo ni memoria esencial
- ejecutar la inferencia en un worker GPU self-hosted
- producir un clip compatible con el mismo ensamblador final
- dejar trazabilidad de pasos, frames, fps, seed, checkpoints y consumo operativo

## Fuentes oficiales usadas

- Google AI Developers, Veo 3.1 API docs: https://ai.google.dev/gemini-api/docs/video?hl=es-419&example=dialogue
- Google AI Developers, Prompt design strategies: https://ai.google.dev/gemini-api/docs/prompting-strategies?hl=es-419
- Google AI Developers, Logs and datasets: https://ai.google.dev/gemini-api/docs/logs-datasets
- Google AI Developers, Video understanding: https://ai.google.dev/gemini-api/docs/video-understanding
- AWS Bedrock, supported Claude models: https://docs.aws.amazon.com/bedrock/latest/userguide/claude-messages-supported-models.html
- AWS Bedrock, CountTokens: https://docs.aws.amazon.com/bedrock/latest/userguide/count-tokens.html
- AWS Bedrock, Prompt caching: https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html
- AWS Bedrock, OptimizePrompt: https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-management-optimize.html
- CrewAI, Memory: https://docs.crewai.com/en/concepts/memory
- CrewAI, Flows: https://docs.crewai.com/en/concepts/flows
- CrewAI, Agents: https://docs.crewai.com/en/concepts/agents
- CrewAI, Crews: https://docs.crewai.com/en/concepts/crews
- CrewAI, Collaboration: https://docs.crewai.com/en/concepts/collaboration
- OpenTelemetry documentation: https://opentelemetry.io/docs/
- Prometheus overview: https://prometheus.io/docs/introduction/overview/
- Grafana documentation: https://grafana.com/docs/grafana/latest/
- Sentry for Python: https://docs.sentry.io/platforms/python/
- Project Gutenberg, Offline Catalogs and Feeds: https://www.gutenberg.org/ebooks/offline_catalogs.html
- Project Gutenberg, download options and bibliographic record: https://www.gutenberg.org/help/bibliographic_record.html
- EbookLib on PyPI: https://pypi.org/project/ebooklib/
- Tencent HunyuanVideo official repo: https://github.com/Tencent-Hunyuan/HunyuanVideo
- Tencent HunyuanVideo-1.5 official repo: https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5
- Tencent HunyuanVideo-I2V official repo: https://github.com/Tencent-Hunyuan/HunyuanVideo-I2V
