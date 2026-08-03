# Ecuador Job Market Intelligence

> Un producto de datos de extremo a extremo, Python-primero, para entender las habilidades, los roles y la demanda tecnológica en el mercado laboral ecuatoriano de datos, IA y software.

## Ejecuta la mesa de evidencia (la demo interactiva)

La primera superficie visible es una **mesa de evidencia** local de Streamlit (`app/evidence_desk.py`): un panel de operar/leer sobre los artefactos existentes de la muestra de desarrollo — 20 registros de ofertas, extracción determinista de habilidades con citas de evidencia exactas y una revisión humana completa de los 740 pares anotados (7 decisiones aprobadas, `annotation_status: human_review_complete`). Lee solo los artefactos locales versionados bajo `data/` y no hace **ninguna llamada de API en vivo**; la evaluación es **final únicamente para esta muestra curada de 20 ofertas** (`evaluation-final-for-curated-20-offer-sample`) y nunca se generaliza más allá de esta muestra curada ni se presenta como cobertura de mercado. La superficie pública es español profesional; el matcher sigue siendo una línea base de palabras clave sin validación definitiva para el mercado completo, y las métricas finales describen solo esta muestra curada (20 ofertas, una página incompleta/fuente única, Himalayas, 37 habilidades, 740 pares). Estados de máquina derivados internamente: `evaluation-final`, `human-reviewed`.

```bash
uv sync --extra demo
uv run --extra demo streamlit run app/evidence_desk.py
```

(Un comando tras la primera instalación: `uv run --extra demo streamlit run app/evidence_desk.py`.) La configuración local `.streamlit/config.toml` usa el modo mínimo de Streamlit: oculta el toolbar, el menú y los controles de desarrollo, y desactiva las estadísticas de uso. La app es deliberadamente delgada: la carga y normalización de artefactos viven en el paquete probado por unidades `src/job_market_intelligence/demo/`, que no depende de Streamlit.

## Cómo funciona

1. **Recolectar** — una captura única, acotada y autorizada de la página de navegación de Himalayas (`limit=20&offset=0`), conservada byte por byte bajo `data/raw/` con un manifiesto bajo `data/manifests/` (verificada con SHA-256, `complete: false`).
2. **Normalizar y extraer** — la proyección canónica, la taxonomía versionada (`technical-skills-0.1.0`, 37 habilidades en 8 categorías) y la línea base determinista de palabras clave (`keyword-baseline-0.1.0`) añaden evidencia de habilidades transparente: citas exactas, campos y conteos de aparición. Sin LLMs, sin embeddings, sin búsqueda semántica, sin parseo de negación.
3. **Analizar y visualizar** — un artefacto de análisis descriptivo (frecuencia de habilidades, cobertura por categoría, coocurrencia, habilidades sin coincidencias) más gráficas SVG/Markdown de línea base, materializadas offline.
4. **Evaluar y auditar** — un conjunto de evaluación en borrador y después una pasada de anotación independiente de segunda pasada en borrador etiqueta los 20 × 37 = 740 pares completos; las siete decisiones en cola fueron aprobadas por la persona responsable del proyecto (2026-08-02), produciendo la revisión final adjudicada por humanos `skill-extraction-review-0.3.0` (`human_review_complete`, sin cola actual) con métricas finales solo para la muestra curada.
5. **Mostrar** — la mesa de evidencia local de Streamlit renderiza solo los cinco artefactos locales versionados; no hace llamadas de red y falla de forma cerrada con un mensaje de recuperación cuando faltan artefactos o son inconsistentes.

### Arquitectura simple

```text
data/raw + data/manifests            (una captura acotada de página 1, verificada con SHA-256)
            │  materialize (offline, solo stdlib)
            ▼
data/analytics/development-sample-0.1.0.json ──────────┐
            │  descriptive / visualize                    │
            ▼                                             ▼
data/analytics/descriptive-development-sample-0.1.0.json   app/evidence_desk.py
data/taxonomy/technical-skills-0.1.0.json ───────────────► (Streamlit local,
            │  evaluate / review (offline)                     sin red, lee
            ▼                                                  los cinco
data/evaluation/skill-extraction-review-0.3.0.json         artefactos locales
data/evaluation/skill-extraction-review-report-0.3.0.json  versionados)
(histórico, conservado: skill-extraction-review-0.2.0{,-report}.json)
```

### Estado de la mesa de evidencia

- Interfaz pública: superficie en español profesional que muestra `Revisión humana completa` / `Evaluación final · muestra curada` (puerta final superada para esta superficie local curada; no es una afirmación de mercado)
- Evaluación: `evaluation-final-for-curated-20-offer-sample` (revisión humana completa; las métricas finales describen solo esta muestra curada)
- Revisión humana: completa (7 decisiones aprobadas el 2026-08-02 por instrucción explícita de la persona responsable del proyecto; sin cola pendiente actual — la cola histórica v0.2.0 se conserva como historia)

La mesa deriva los estados de máquina de los artefactos (`annotation_status: human_review_complete`, `human_review_required: false`, `human_review_complete: true`) pero no los renderiza públicamente: la superficie muestra el aviso final de muestra `Muestra curada · métricas finales para 20 ofertas · no representa el mercado completo` y rechaza artefactos con metadatos de revisión inconsistentes. Los artefactos de borrador v0.2.0 siguen siendo cargables/legibles por rutas históricas explícitas y nunca se sobrescriben. Para trazabilidad, la copia de interfaz previa a la adjudicación se conserva como histórica: `Interfaz pública en validación` y `Prototipo local · evaluación provisional · 7 decisiones humanas pendientes`; ninguna describe la interfaz actual.

Captura real de la interfaz: `docs/assets/evidence-desk-public-es.png`, obtenida con Chromium/WebDriver y verificada después de los checks finales. Clasificación actual del proyecto: `evaluation-final-for-curated-20-offer-sample`, `demo-ready` y `portfolio-ready` para esta entrega local; sin afirmaciones de cobertura de mercado. La interfaz pública sigue siendo un prototipo local de soporte a la revisión, no una taxonomía de mercado final: el matcher (`keyword-baseline-0.1.0`) no está validado de forma definitiva, las métricas finales describen solo esta muestra curada de 20 ofertas y no hay «7 decisiones pendientes» actuales (la cola histórica está etiquetada como histórica). El paquete de revisión humana (`docs/human-review-package.md`) conserva el relato histórico v0.2.0 y documenta la resolución aprobada de los 7 ítems (HR-01…HR-07).

### Evaluación final para la muestra curada (metodología y métricas exactas)

La evaluación es una auditoría completa de 20 × 37 = 740 pares: una pasada de anotación de segunda pasada independiente en borrador etiquetó cada par oferta × habilidad leyendo directamente los campos del texto fuente — las predicciones del matcher nunca se leyeron al etiquetar. Las siete decisiones en cola (todas las etiquetas inciertas más los desacuerdos primera-vs-segunda pasada) fueron aprobadas por la persona responsable del proyecto el 2026-08-02 (instrucción explícita) y quedan registradas en un libro de decisiones auditable `human_review_decisions` con fecha de aprobación, fuente, criterio, evidencia conservada y etiquetas originales por ítem. Métricas finales sobre los 740 pares, exactamente: TP/FP/FN/TN = 40/16/0/684, precisión 40/56 = 0,7142857143 (0,7143), recall 1,0, F1 0,8333333333 (0,8333); macro precisión/recall/F1 = 0,9524 / 1,0 / 0,9662 sobre un alcance explícito de 37 habilidades (4 habilidades indefinidas y excluidas). Distribución final: 40 `supported`, 700 `not_supported`, 0 `uncertain`. Los 16 falsos positivos son coincidencias de palabras clave en menciones negativas o contextuales (13 de la limitación de negación 0.1.0 documentada más 3 confirmados por las decisiones humanas aprobadas). El recall perfecto es una propiedad de esta muestra curada (40 pares respaldados), no del mercado. Nada de aquí se generaliza más allá de esta muestra curada de 20 ofertas: las métricas son finales solo para esta muestra curada, y el matcher sigue siendo una línea base de palabras clave sin validación definitiva para el mercado completo. El relato histórico v0.2.0 (distribución de etiquetas, métricas, comparación primera-vs-segunda, cola de 7 ítems) se conserva verbatim en el bloque `historical` del informe; el `human_review_queue` actual es `count: 0, items: []`.

### Datos locales, licencia y atribución

La mesa lee solo los cinco artefactos locales versionados bajo `data/` — nunca las páginas crudas, los manifiestos, la API ni la red. Los datos de ofertas se muestran bajo el requisito de atribución de Himalayas: un enlace visible a [himalayas.app](https://himalayas.app) acompaña a los datos (barra lateral). `data/raw/` está en gitignore; `data/manifests/` no lo está por defecto. `data/manifests/` registra la única captura acotada de página 1. El código original se publica bajo MIT; los datos de fuente y sus términos se documentan por separado en la sección [Licencia](#licencia).

## Estado del proyecto

**Hito 6 completo: una pasada de anotación de segunda pasada independiente en borrador (no revisada por humanos, requiere revisión humana) etiqueta los 20 × 37 = 740 pares COMPLETOS de la muestra de desarrollo y compara ambas pasadas y el matcher.** `analysis/second_pass.py` (solo biblioteca estándar, cierre ante fallos) implementa una rutina separada de anotación de texto directo guiada por un manifiesto de adjudicación curado: cada etiqueta se decide leyendo los campos de texto fuente (`title_raw`, `excerpt_raw`, `categories_raw`, `description_html_raw`); los términos de la taxonomía se usan solo como vocabulario candidato; las predicciones del matcher (`skill_evidence.skills`) NUNCA se leen al etiquetar (probado por una prueba que elimina `skill_evidence` de una copia del conjunto de datos) y se comparan solo después mediante una `compare_with_predictions(...)` separada. El artefacto `data/evaluation/skill-extraction-review-0.2.0.json` declara `annotation_status: draft_second_pass` y `human_review_required: true` — NO es oro NI está revisado por humanos, y no se cambió ninguna regla del matcher ni de la taxonomía. La revisión etiqueta 740/740 pares (38 supported, 697 not_supported, 5 uncertain), re-verifica cada cita/offset de evidencia exactamente, compara con el primer borrador (57 acuerdos, 3 desacuerdos, 680 pares sin etiqueta del primer borrador, cola de revisión humana de 7 ítems = todas las etiquetas inciertas de la segunda pasada más los desacuerdos) y compara las etiquetas no inciertas con la línea base: TP/FP/FN/TN = 38/13/0/684, precisión 0,7451, recall 1,0, F1 0,8539 (micro), macro 0,9754/1,0/0,9793 sobre un alcance explícito de 37 habilidades con 4 excluidas por indefinidas, 20/20 registros, 0 registros sin evidencia, 0 pares predichos sin etiqueta. Los 13 falsos positivos son coincidencias `skill.ai` en roles cuyo texto dice explícitamente «No prior experience in AI is required» (limitación de negación documentada; sin cambio del matcher). La revisión se regenera con `uv run python -m job_market_intelligence.analysis.review`; el método, los casos de frontera/negativos, las métricas y la decisión de revisión humana requerida están documentados en `docs/evaluation-review.md`. La mesa de evidencia de Streamlit está implementada (interfaz `en validación pública`); ver la sección Ejecutar.

**Hito 7 completo: las siete decisiones de revisión humana fueron aprobadas y la evaluación es final para la muestra curada de 20 ofertas.** `analysis/finalize_review.py` (solo biblioteca estándar, cierre ante fallos) lee la revisión/informe v0.2.0 CONGELADOS y el conjunto de datos analítico local, aplica exactamente las siete decisiones aprobadas (HR-01…HR-07, fecha de aprobación 2026-08-02, fuente `explicit project-owner instruction`), conserva cada otra etiqueta y toda la evidencia/motivos/preguntas/notas originales sin cambios, y recalcula todo a partir de las 740 etiquetas resultantes: distribución final 40 `supported` / 700 `not_supported` / 0 `uncertain`; TP/FP/FN/TN = 40/16/0/684; precisión 0,7143, recall 1,0, F1 0,8333 (micro sobre 740 pares); macro 0,9524 / 1,0 / 0,9662 sobre un alcance explícito de 37 habilidades (4 excluidas por indefinidas). Los artefactos `data/evaluation/skill-extraction-review-0.3.0.json` / `skill-extraction-review-report-0.3.0.json` declaran `annotation_status: human_review_complete`, `human_review_required: false`, `human_review_complete: true`, llevan un libro de decisiones auditable `human_review_decisions` (fuente, habilidad, etiqueta de la primera pasada cuando existe, etiqueta original de la segunda pasada, etiqueta final, fecha/fuente de aprobación, criterio, evidencia conservada) y conservan el relato v0.2.0 (distribución de etiquetas, métricas, comparación primera-vs-segunda, cola de 7 ítems) en un bloque `historical` claramente histórico; el `human_review_queue` actual es `count: 0, items: []`. La evaluación es final solo para esta muestra curada — su alcance no se extiende al mercado completo — y el matcher sigue siendo una línea base de palabras clave sin validación definitiva para el mercado completo. Regenerar con `uv run python -m job_market_intelligence.analysis.finalize_review`; las decisiones están documentadas en `docs/evaluation-review.md` y `docs/human-review-package.md`. La mesa de evidencia ahora muestra `Revisión humana completa` / `Evaluación final · muestra curada` con métricas finales y sin decisiones pendientes actuales (los detalles históricos v0.2.0 viven en «Detalles técnicos»).

**Hito 5 completo: un conjunto de evaluación de borrador de extracción de habilidades y un informe de evaluación determinista están implementados y materializados totalmente offline.** `analysis/evaluation.py` (solo biblioteca estándar, cierre ante fallos) valida el artefacto de evaluación de borrador versionado (`data/evaluation/skill-extraction-development-0.1.0.json`) contra el conjunto de datos analítico y la taxonomía existentes — snapshot exacto (`cap_0370798f7af4b0e3`), versión de taxonomía (`technical-skills-0.1.0`), tipo `development_sample`, forma de la muestra, enumerado de etiquetas cerrado, sin etiquetas `(source_id, skill_id)` duplicadas, y la cita exacta y los offsets half-open de cada etiqueta supported re-verificados contra el valor del campo del conjunto de datos (`field[char_start:char_end] == exact_quote`) — y compara las 60 etiquetas de borrador escritas a mano (38 supported, 18 not_supported, 4 uncertain, 11 registros anotados) con las predicciones de la línea base de palabras clave embebidas en el conjunto de datos (`skill_evidence.skills`). El informe (`data/evaluation/skill-extraction-development-report-0.1.0.json`, regenerado con `uv run python -m job_market_intelligence.analysis.evaluate`) reporta TP/FP/FN/TN = 38/5/0/13, precisión 0,8837, recall 1,0, F1 0,9383 (micro sobre los 56 pares etiquetados no inciertos), macro precisión/recall/F1 = 0,9811/1,0/0,9862 sobre un alcance explícito de 35 habilidades, cobertura de etiquetas (60/740 pares; 11/20 registros), el conteo de inciertos, los 5 falsos positivos con la propia evidencia del matcher y salvaguardas. Las etiquetas son solo `draft_evaluation` — redactadas de forma independiente inspeccionando directamente el texto fuente, nunca copiadas de las predicciones, NI oro ni revisadas por humanos; las etiquetas inciertas se excluyen de todos los denominadores primarios; los pares predichos sin etiqueta se excluyen (nunca son negativos); recall = 1,0 refleja el borrador curado, no el mercado. La demo de Streamlit sigue pendiente.

**Hito 4 completo: la visualización descriptiva y el análisis de coocurrencia de habilidades están implementados y materializados offline desde el conjunto de datos de desarrollo existente.** Una nueva superficie de análisis solo-biblioteca-estándar (`analysis/descriptive.py`, `analysis/visualizations.py`, `analysis/visualize.py`) lee SOLO el conjunto de datos analítico versionado existente (`data/analytics/development-sample-0.1.0.json`) — nunca las páginas crudas, los manifiestos ni la API — y produce un artefacto de análisis determinista (`data/analytics/descriptive-development-sample-0.1.0.json`) más visualizaciones de línea base bajo `data/analytics/visualizations/development-sample-0.1.0/` (gráfica de barras de frecuencia de habilidades, gráfica de barras de cobertura por categoría, mapa de calor de coocurrencia, tabla Markdown de habilidades sin coincidencias). El analizador es de cierre: rechaza cualquier conjunto de datos que no sea el `development_sample` documentado (exactamente 20 registros, una página `limit=20`/`offset=0`, snapshot `cap_0370798f7af4b0e3`, `complete: false`) y cualquier artefacto de taxonomía cuya versión no coincida con el `taxonomy_version` del conjunto de datos (`technical-skills-0.1.0`). Todas las métricas son a nivel de registro (una habilidad cuenta como máximo una vez por registro), los pares de coocurrencia no tienen orden y son canónicos (`skill_a < skill_b`, sin auto-pares, sin duplicados invertidos), la matriz de 37×37 es simétrica con diagonal cero, y cada artefacto lleva metadatos de fuente/atribución y salvaguardas explícitas: evidencia descriptiva de palabras clave únicamente — no correlación, causalidad, cobertura de mercado ni representatividad. La demo de Streamlit sigue pendiente.

**Hito 3 completo: taxonomía versionada de habilidades técnicas, línea base determinista de palabras clave, conjunto de datos analítico de desarrollo e informe de calidad implementados y materializados desde la captura local existente de 20 registros.** Un paquete de análisis pequeño solo-biblioteca-estándar (`src/job_market_intelligence/analysis/`) define una taxonomía versionada (`data/taxonomy/technical-skills-0.1.0.json`, 37 habilidades en 8 categorías) con reglas de coincidencia explícitas, un matcher de palabras clave seguro en fronteras (sin embeddings, sin LLMs, sin búsqueda semántica) y un conjunto de datos de desarrollo determinista con un informe de calidad embebido (`data/analytics/development-sample-0.1.0.json`) generado totalmente offline a partir de la captura autorizada de una sola página (20 registros, `totalCount=94520`, SHA-256 crudo `0370798f7af4b0e39ab92fd0d486577f58cdd415812e612d6b86657ac07ab101`). El conjunto de datos conserva cada campo canónico y la identidad del snapshot (`cap_0370798f7af4b0e3`), se marca a sí mismo `development_sample` con `complete: false` e informa que 20 de 20 registros coincidieron con al menos una palabra clave — impulsado sobre todo por `skill.ai` (19 registros), lo que refleja los roles de entrenamiento de IA de la página fuente, no una afirmación de mercado completo.

El endpoint de feed completo `https://himalayas.app/jobs/api` está cableado de extremo a extremo a través de un adaptador tipado probado totalmente offline: paginación, conservación exacta de páginas crudas, clasificación de ubicación, detección de unidades de marcas de tiempo, deduplicación dentro de la fuente y manejo de errores de cierre. Un `LocalCaptureStore` opt-in solo-biblioteca-estándar persiste páginas crudas exactas bajo `data/raw/` con manifiestos de colección JSON bajo `data/manifests/` cuando se invoca explícitamente. Una ruta de captura de una sola página estrictamente acotada (`HimalayaAdapter.collect_and_persist_page`) realiza exactamente una solicitud (`limit=20`, `offset=0`) y persiste exactamente una página con `complete: false`; está implementada, probada offline y se ha ejecutado una vez contra la API en vivo. La captura autorizada devolvió 20 registros (`totalCount=94520`) y escribió 84 341 bytes crudos con SHA-256 `0370798f7af4b0e39ab92fd0d486577f58cdd415812e612d6b86657ac07ab101`. La persistencia es acotada y opt-in: no se ha descargado ningún feed completo, y Himalayas no representa todo el mercado laboral.

### Qué está completo en este hito

1. **Taxonomía versionada de habilidades técnicas (`data/taxonomy/technical-skills-0.1.0.json`).** Catálogo declarativo de 37 habilidades con identificadores estables (`skill.python`), nombres canónicos, categorías, **palabras clave** (términos canónicos de búsqueda) y **alias** (ortografías/abreviaturas alternativas) visibles en cada entrada, notas, una versión inicial de taxonomía explícita y el conjunto completo de reglas de coincidencia: la regla `term_types`, coincidencia sin distinguir mayúsculas (casefold), seguridad de límites de palabra (`java` nunca coincide con `javascript`; `ml` nunca coincide con `html`; `git` nunca coincide con `github`), términos multi-palabra flexibles a conectores (`machine learning` coincide con `machine-learning`), términos de puntuación literal (`c++`, `c#`, `n8n`) con comportamiento conservador de ortografía versionada, los cuatro campos buscados, manejo HTML-a-texto-visible, comportamiento de evidencia/deduplicación, manejo de campos faltantes, representación `no_evidence` y la declaración explícita de que 0.1.0 no interpreta negación. Los términos deliberadamente excluidos (por ejemplo `go`, que la coincidencia de límites no puede distinguir del verbo inglés) están documentados en el artefacto.
2. **Línea base determinista de palabras clave (`analysis/matcher.py`).** Coincidencia sin distinguir mayúsculas, segura en fronteras y flexible a conectores sobre `keywords` + `aliases` (primero las palabras clave) sin embeddings, LLM, búsqueda semántica ni inferencia difusa. Habilidades únicas por registro, una entrada de evidencia deduplicada por (campo, término coincidente) que registra el término y su tipo (`keyword`/`alias`) con extracto de primera aparición y conteo de apariciones, campos faltantes omitidos e informados, y registros sin coincidencias representados como `evidence_status: "no_evidence"` con `skills: []` — la ausencia de evidencia no es evidencia de ausencia.
3. **Conjunto de datos canónico de desarrollo (`data/analytics/development-sample-0.1.0.json`).** Generado totalmente offline desde la captura local existente de 20 registros con `uv run python -m job_market_intelligence.analysis.materialize`. Conserva cada campo canónico valor-por-valor (todos los campos `*_raw` y `snapshot_id` incluidos), añade solo evidencia de palabras clave transparente, registra `snapshot_id`/`capture_id` `cap_0370798f7af4b0e3` (del manifiesto persistido — nunca inventado), marca la muestra `development_sample` con página/límite/offset y `complete: false`, y es byte-reproducible (ordenamiento estable, serialización `sort_keys`, sin campos de reloj de pared).
4. **Informe de calidad determinista embebido.** Conteo de registros (20), conjunto de campos verificados explícito, conteos de campos faltantes (0 en los cuatro campos buscados para esta captura), conteos de duplicados (0 `source_id` duplicados), conteos de estado de observación (20 activos), cobertura de habilidades (20 registros con evidencia, 0 sin ella, conteos por habilidad para las 37 habilidades de la taxonomía) y frescura del snapshot (edad en la captura 45 815,6095 s = `captured_at` − `api_updated_at_utc`, ambos UTC del manifiesto, sin reloj de pared), más la nota de limitación explícita de que esto son 20 registros de una página y no cobertura de mercado.
5. **Endpoint de feed completo.** El adaptador recolecta `https://himalayas.app/jobs/api` con `limit=20` y `offset` creciente hasta cubrir el `totalCount` reportado por la fuente. Nunca usa búsqueda por palabras clave (`/jobs/api/search`); el feed de navegación documentado es la línea base.
6. **Conservación de páginas crudas con persistencia acotada en disco.** Cada respuesta exitosa se conserva como los bytes exactos de la respuesta más parámetros de solicitud, estado HTTP, tipo de contenido, SHA-256, `updatedAt` de la fuente y conteo total. Nada se re-codifica ni trunca. `LocalCaptureStore.persist_page` escribe estos bytes verbatim bajo `data/raw/` con un manifiesto JSON bajo `data/manifests/` cuando se invoca explícitamente (escrituras atómicas, rechazo de sobrescritura, redacción de secretos, validación de cierre).
7. **Clasificación de ubicación.** El alcance geográfico se clasifica solo desde `locationRestrictions`, en cuatro valores: `explicit_ec`, `worldwide`, `other_country` y `unknown`. Las restricciones de zona horaria se conservan como evidencia pero nunca se usan como prueba geográfica, y un valor faltante/nulo nunca se coerza a una lista vacía.
8. **Manejo de marcas de tiempo.** Los segundos Unix de 10 dígitos y los milisegundos Unix de 13 dígitos se detectan defensivamente; los valores inverosímiles elevan error en lugar de interpretarse en silencio. El `updatedAt` de nivel superior se trata como metadatos de refresco de API a nivel de snapshot, nunca como fecha de modificación de un empleo individual.
9. **Estado de pruebas offline.** La suite offline completa pasa contra fixtures guardados vía `httpx.MockTransport`; ninguna prueba invoca una API en vivo. Las pruebas cubren parseo, normalización, alcance de ubicación, marcas de tiempo, paginación, conservación de evidencia cruda, fallos, deduplicación, persistencia local acotada, la ruta opt-in de captura de una sola página y el paquete de análisis (carga de taxonomía, coincidencia segura en fronteras, proyección del conjunto de datos, informe de calidad y materialización offline).
10. **Pruebas de persistencia local acotada.** `tests/test_storage.py` cubre ida y vuelta byte-exacta de crudos, integridad SHA-256, manifiestos completos, rutas deterministas, rechazo de sobrescritura, capturas parciales/acotadas, redacción de secretos y limpieza de escrituras atómicas — todo offline contra el fixture de navegación existente.
11. **Captura opt-in acotada de una sola página.** `HimalayaAdapter.collect_and_persist_page(store=...)` emite exactamente un GET de `/jobs/api` con `limit=20&offset=0`, reutiliza el parser existente y la evidencia `RawPage` (bytes exactos conservados) y persiste exactamente una página cruda más un manifiesto a través de `LocalCaptureStore` con `complete: false` y un aviso `bounded_single_page_capture`. Nunca pagina, reintenta ni llama a `/jobs/api/search`, falla de forma cerrada antes de cualquier escritura y devuelve un `PageCaptureResult` tipado (página cruda + recibo de persistencia + sobre del manifiesto) para que la captura se pueda verificar sin otra solicitud. La cobertura offline está en `tests/test_bounded_capture.py` (exactamente-una-solicitud, consistencia de bytes/hash, contrato del manifiesto, rutas de cierre). La única solicitud en vivo autorizada escribió `data/raw/himalayas/jobs_api_6b8244a52a80/00000000.json` y `data/manifests/himalayas/jobs_api_6b8244a52a80/00000000.manifest.json`; no se hizo una segunda solicitud.
    12. **Visualización descriptiva y análisis de coocurrencia (`analysis/descriptive.py`, `analysis/visualizations.py`, `analysis/visualize.py`).** Un analizador solo-biblioteca-estándar, de cierre, consume SOLO el conjunto de datos analítico existente (el artefacto de taxonomía se usa únicamente como búsqueda ID → nombre/categoría canónicos, con guardia de coincidencia de versión) y calcula métricas a nivel de registro: frecuencia de habilidades por registros distintos (nunca conteos de apariciones textuales), cobertura por categoría por registros distintos (definición incluida en el artefacto), habilidades de taxonomía sin coincidencias (distinguidas explícitamente de los registros `no_evidence`), pares de coocurrencia canónicos sin orden y una matriz de coocurrencia simétrica de 37×37 con identificadores de habilidad ordenados y diagonal cero. Rechaza cualquier conjunto de datos que no sea el `development_sample` documentado (20 registros, una página, `complete: false`, snapshot `cap_0370798f7af4b0e3`). La CLI (`uv run python -m job_market_intelligence.analysis.visualize`) materializa `data/analytics/descriptive-development-sample-0.1.0.json` y los artefactos SVG/Markdown bajo `data/analytics/visualizations/development-sample-0.1.0/`; cada artefacto embebe metadatos de fuente/atribución, snapshot, versión de taxonomía y forma de muestra más las salvaguardas de no-representativo-de-mercado, no contiene texto crudo de descripciones de empleo y es byte-determinista (re-ejecutar es un no-op; el contenido diferente se rechaza). La mesa de evidencia de Streamlit está implementada (interfaz `en validación pública`); ver la sección Ejecutar.
    13. **Evaluación de borrador de extracción de habilidades (`analysis/evaluation.py`, `analysis/evaluate.py`).** Un evaluador solo-biblioteca-estándar, de cierre, valida el artefacto de evaluación de borrador versionado (`data/evaluation/skill-extraction-development-0.1.0.json` — estado `draft_evaluation`, nunca oro/revisado por humanos; fecha de anotación fija `2026-08-02`; snapshot `cap_0370798f7af4b0e3`; taxonomía `technical-skills-0.1.0`; 20 registros, una página, `complete: false`) contra el conjunto de datos analítico, re-verifica la cita exacta y los offsets half-open de cada etiqueta supported contra el valor exacto del campo, compara las 60 etiquetas de borrador escritas a mano con las predicciones `skill_evidence.skills` del conjunto de datos y materializa el informe determinista (`data/evaluation/skill-extraction-development-report-0.1.0.json`) vía `uv run python -m job_market_intelligence.analysis.evaluate`. Métricas principales (micro sobre los 56 pares etiquetados no inciertos): TP 38, FP 5, FN 0, TN 13; precisión 0,8837, recall 1,0, F1 0,9383; macro (alcance explícito de 35 habilidades, 33 habilidades con valores definidos): precisión 0,9811, recall 1,0, F1 0,9862; cobertura 60/740 pares (56 no inciertos), 11/20 registros; 4 etiquetas inciertas excluidas de todo denominador primario; 10 pares predichos sin etiqueta excluidos (nunca negativos). Los 5 falsos positivos son predicciones `skill.ai` en roles cuyo texto dice explícitamente «No prior experience in AI is required» (la limitación de negación 0.1.0 documentada de la línea base); el borrador no contiene ningún falso negativo claro (recall = 1,0 es una propiedad del conjunto curado, no del mercado). Cada artefacto embebe metadatos de fuente/atribución, snapshot, versión de taxonomía y forma de muestra más la salvaguarda de borrador/oro y la limitación de no-cobertura-de-mercado, y no contiene descripciones crudas completas. La generación es determinista y de cierre: rechazo de sobrescritura, verificación de serialización canónica del artefacto de evaluación y sin campos de reloj de pared.
    14. **Revisión independiente de etiquetas de segunda pasada (`analysis/second_pass.py`, `analysis/review.py`).** Un revisor solo-biblioteca-estándar, de cierre, etiqueta los 20 × 37 = 740 pares COMPLETOS de la muestra de desarrollo mediante una rutina separada de anotación de texto directo guiada por un manifiesto de adjudicación curado (`annotate_second_pass(...)`); las predicciones del matcher nunca se leen al etiquetar (probado por pruebas que eliminan `skill_evidence`) y solo las consume la `compare_with_predictions(...)` separada. El artefacto `data/evaluation/skill-extraction-review-0.2.0.json` es `draft_second_pass` con `human_review_required: true` — nunca oro/revisado por humanos; la revisión rechaza cualquier artefacto que declare un estado de oro/revisado por humanos. Valida metadatos, cobertura exacta de 740 pares, enumerado de etiquetas cerrado, sin duplicados y cada cita/offset de evidencia exactamente; compara con el primer borrador (57 acuerdos / 3 desacuerdos / 680 pares sin etiqueta del primer borrador; cola de revisión humana de 7 ítems = todas las etiquetas inciertas de la segunda pasada más los desacuerdos, cada uno con una `human_review_question`); y compara las etiquetas no inciertas con la línea base: TP/FP/FN/TN = 38/13/0/684, precisión 0,7451, recall 1,0, F1 0,8539 (micro sobre 735 pares no inciertos), macro precisión/recall/F1 0,9754/1,0/0,9793 sobre un alcance explícito de 37 habilidades (4 habilidades excluidas por indefinidas: `cpp`, `csharp`, `git`, `java`), cobertura 740/740 pares y 20/20 registros, 0 registros sin evidencia, 0 pares predichos sin etiqueta. Los 13 falsos positivos son todos predicciones `skill.ai` con limitación de negación (documentado; sin cambio de matcher/taxonomía). Los casos de frontera y requisito negativo están documentados por etiqueta: `java` vs `javascript`, `git` vs `github`, IA en contexto de empresa/categoría, «No prior experience in AI is required», `statistics` vs «Statistical Physics», «emotional intelligence» ≠ IA. La CLI (`uv run python -m job_market_intelligence.analysis.review`) materializa ambos artefactos de forma determinista (rechazo de sobrescritura, serialización canónica); el método y la decisión de revisión humana requerida están documentados en `docs/evaluation-review.md`. La demo de Streamlit sigue pendiente.

### Fixtures offline (`data/sample/`)

- `himalayas_browse_page_1.json` — página 1 del endpoint de navegación de feed completo `/jobs/api` (`limit=20&offset=0`), capturada el 2026-08-02. Es el fixture canónico offline para la validación del adaptador/parser. Su sidecar `himalayas_browse_page_1.metadata.json` registra la solicitud exacta, el momento de captura UTC, los metadatos HTTP/tipo de contenido, el `updatedAt` crudo de nivel superior y su interpretación de unidad, y el SHA-256 del fixture.
- `himalayas_ec_page_1.json` — una página **exploratoria** de `/jobs/api/search` filtrada a Ecuador. **No** es una línea base de feed completo; se conserva solo para ejercitar las formas de parseo de alcance Ecuador. Su archivo de metadatos registra esta distinción explícitamente.

### Persistencia local acotada (`data/raw/`, `data/manifests/`)

La persistencia cruda es opt-in y acotada: nada se ejecuta implícitamente durante la recolección, y `LocalCaptureStore.persist_page` almacena exactamente el `RawPage` que se le pasa. No es un snapshot completo.

- **Páginas crudas** se escriben byte por byte bajo `data/raw/<source>/<endpoint-component>_<endpoint-hash>/<offset>.json`. El componente de endpoint legible (por ejemplo `jobs_api`) más un SHA-256 estable de 12 hex del endpoint mantiene las rutas legibles y a prueba de colisiones entre endpoints; los offsets se rellenan a 8 dígitos con ceros.
- **Manifiestos** son sidecars JSON UTF-8 pequeños bajo `data/manifests/<source>/<endpoint-component>_<endpoint-hash>/<offset>.manifest.json`, que registran los parámetros de solicitud, el estado HTTP, el tipo de contenido exacto, las marcas de tiempo UTC de captura y de fuente, la unidad de marca de tiempo interpretada, los conteos total/devueltos, la ruta cruda relativa al repositorio, el SHA-256 crudo, la versión del adaptador, la URL de atribución, `complete`, avisos y errores.
- Las escrituras son atómicas por archivo (temp en el mismo directorio + fsync + rename); un archivo crudo o manifiesto existente nunca se sobrescribe, la salida parcial se limpia ante fallos, los parámetros de solicitud que contienen secretos se redactan y los manifiestos nunca contienen rutas absolutas, cabeceras, credenciales ni el directorio de trabajo.
- `data/raw/` está en gitignore; `data/manifests/` no se ignora por defecto. No se ha descargado ningún feed completo — la evidencia cruda guardada contiene el fixture existente de la página 1 de navegación y una captura en vivo autorizada de la página 1.

### Línea base de palabras clave de habilidades técnicas (`src/job_market_intelligence/analysis/`)

Un paquete de análisis pequeño, explícito y solo-biblioteca-estándar (sin LLMs, embeddings, búsqueda semántica, inferencia difusa, servicios cloud ni dependencias nuevas) que convierte la captura persistida en un conjunto de datos de desarrollo versionado y reproducible:

- **Taxonomía versionada — `data/taxonomy/technical-skills-0.1.0.json`.** 37 habilidades en 8 categorías (`programming_language`, `framework_library`, `ml_ai`, `cloud_platform`, `data_platform`, `developer_tool`, `mobile`, `security_identity`) con identificadores estables (`skill.python`, nunca nombres para mostrar), nombres canónicos, **palabras clave** (términos canónicos de búsqueda) y **alias** (ortografías y abreviaturas alternativas) declarados visiblemente en cada entrada, notas y el conjunto completo explícito de reglas de coincidencia (incluida la regla `term_types`). El cargador rechaza términos duplicados — palabras clave o alias — e identificadores de habilidad duplicados en tiempo de carga (cierre ante fallos). Los términos deliberadamente excluidos están documentados dentro del artefacto (por ejemplo `go`, porque la coincidencia de límites de palabra no puede distinguir el lenguaje del verbo inglés).
- **Matcher determinista — `analysis/matcher.py` (`keyword-baseline-0.1.0`).** Coincidencia sin distinguir mayúsculas (casefold); seguridad de límites de palabra (`java` nunca coincide con `javascript`, `ml` nunca coincide con `html`, `git` nunca coincide con `github`); espacios/`-`/`_`/`/` intercambiables entre las palabras de un término multi-palabra (`machine learning` coincide con `machine-learning`); términos de puntuación literal (`c++`, `c#`, `n8n`) con comportamiento conservador para ortografías versionadas (`C++17` no coincide en 0.1.0). Se buscan tanto `keywords` como `aliases` con las mismas reglas, primero las palabras clave y luego los alias. Campos buscados, en orden: `title_raw`, `excerpt_raw`, `categories_raw`, `description_html_raw` (convertido a texto visible solo para coincidir; el campo crudo nunca se modifica). Los campos faltantes/vacíos se omiten e informan; una entrada de evidencia deduplicada por (campo, término coincidente) que registra el término, su tipo (`keyword` o `alias`), el extracto de primera aparición y el conteo de apariciones; las habilidades son únicas por registro; un registro sin coincidencias es `evidence_status: "no_evidence"` con `skills: []` — la ausencia de evidencia no es evidencia de ausencia. La negación no se interpreta en 0.1.0; las coincidencias son solo evidencia de palabras clave.
- **Conjunto de datos de desarrollo — `data/analytics/development-sample-0.1.0.json`.** Generado totalmente offline desde la captura en vivo autorizada con `uv run python -m job_market_intelligence.analysis.materialize` (lee `data/raw/.../00000000.json` + el manifiesto, verifica SHA-256 y la consistencia manifiesto/payload, parsea la proyección canónica y escribe el artefacto; se niega a reemplazar una salida existente con contenido diferente). El conjunto de datos conserva cada campo canónico valor-por-valor (todos los campos `*_raw` y `snapshot_id`), añade solo evidencia de palabras clave transparente y registra la identidad de captura: `snapshot_id`/`capture_id` `cap_0370798f7af4b0e3` (del manifiesto persistido — nunca inventado), SHA-256 crudo `0370798f7af4b0e39ab92fd0d486577f58cdd415812e612d6b86657ac07ab101`, fuente, endpoint, versión del adaptador, atribución y marcas de tiempo. Los metadatos de la muestra están marcados `development_sample` con página 1, `limit=20`, `offset=0`, 20 registros, `total_count=94520`, `complete: false`, el aviso de captura acotada y limitaciones explícitas. `sample.complete` siempre es `false` en esta ruta: el constructor falla de forma cerrada con un error si un manifiesto llegara a declarar `complete: true`, de modo que nadie puede producir una muestra de desarrollo «completa». La serialización es determinista (`sort_keys`, sangría fija, salto de línea final) sin campos de reloj de pared.
- **Informe de calidad (embebido en el conjunto de datos).** Conjunto de campos verificado explícito (`title_raw`, `excerpt_raw`, `categories_raw`, `description_html_raw`), conteos de campos faltantes, conteos de `source_id` duplicados, conteos de estado de observación, cobertura de habilidades (registros con/sin evidencia más conteos por habilidad para las 37 habilidades de la taxonomía) y frescura del snapshot con la fórmula explícita segura para zonas horarias `age_at_capture_seconds = captured_at − api_updated_at_utc` (ambas marcas de tiempo UTC leídas del manifiesto; sin reloj de pared).
- **Métricas de línea base (captura local de 20 registros, `technical-skills-0.1.0`).** Los 20 registros tienen evidencia de palabras clave (0 registros `no_evidence`); la página está dominada por roles de contratista de entrenamiento de IA, lo que lleva `skill.ai` a 19 registros, `skill.machine_learning` a 3, `skill.data_science`/`skill.python`/`skill.aws` a 2 cada uno y 28 habilidades a 1 registro cada una; 4 entradas de taxonomía (`skill.java`, `skill.cpp`, `skill.csharp`, `skill.git`) tienen 0 coincidencias en esta muestra. Campos faltantes: 0 en todos los campos verificados. `source_id` duplicados: 0. Frescura: 45 815,6095 s entre el `updatedAt` de la fuente y el momento de captura. Estas cifras describen una página de una fuente, no un mercado.
- **Análisis descriptivo y visualizaciones de línea base (`analysis/descriptive.py`, `analysis/visualizations.py`, `analysis/visualize.py`).** Un analizador solo-biblioteca-estándar, de cierre, lee SOLO `data/analytics/development-sample-0.1.0.json` (el artefacto de taxonomía es una búsqueda de esquema local para nombres/categorías canónicos y debe coincidir con el `taxonomy_version` del conjunto de datos). Definiciones exactas de métricas (todas a nivel de registro, nunca conteos de apariciones textuales): **frecuencia de habilidades** = número de registros distintos cuyo conjunto de habilidades único por registro contiene la habilidad (contada como máximo una vez por registro); **cobertura por categoría** = número de registros distintos con al menos una habilidad coincidente en la categoría (contada como máximo una vez por registro por categoría); **habilidades sin coincidencias** = habilidades de la taxonomía con cero registros coincidentes (NO evidencia de ausencia, y distintas de los registros `no_evidence`); **pares de coocurrencia** = pares sin orden de habilidades distintas de los conjuntos de habilidades únicos por registro, canónicos `skill_a < skill_b`, nunca reflexivos, nunca invertidos, contados una vez por registro; **matriz de coocurrencia** = matriz simétrica sobre los 37 identificadores de habilidad de la taxonomía ordenados, celda `[i][j]` = registros distintos que contienen ambas habilidades, diagonal cero (sin auto-pares). La CLI `uv run python -m job_market_intelligence.analysis.visualize` materializa `data/analytics/descriptive-development-sample-0.1.0.json` (artefacto de análisis: fuente/atribución, metadatos de muestra, definiciones, métricas, el resumen de calidad/frescura copiado del conjunto de datos, salvaguardas, limitaciones y la nota `streamlit_status: pending`) y `data/analytics/visualizations/development-sample-0.1.0/` (`skill-frequency.svg`, `category-coverage.svg`, `cooccurrence-matrix.svg`, `zero-match-skills.md`). Cada artefacto embebe fuente (`himalayas`), atribución (`https://himalayas.app`), snapshot (`cap_0370798f7af4b0e3`), versión de taxonomía (`technical-skills-0.1.0`), el tipo `development_sample`, el aviso de 20 registros/una página/`complete: false` y la salvaguarda de que la salida es solo evidencia descriptiva de palabras clave — NO correlación, causalidad, cobertura de mercado ni representatividad. Los SVG contienen solo etiquetas, métricas y metadatos (nunca `description_html_raw` ni texto crudo de ofertas). La generación es byte-determinista y de cierre: entradas idénticas dan bytes idénticos, un artefacto existente con contenido diferente se rechaza y cualquier conjunto de datos que no sea la muestra documentada (tipo equivocado, forma de muestra equivocada, snapshot distinto, `complete: true`, versión de taxonomía no coincidente) se rechaza antes de escribir nada. La mesa de evidencia de Streamlit está implementada (interfaz `en validación pública`); ver la sección Ejecutar.
- **Evaluación de borrador de extracción de habilidades — `data/evaluation/`.** Artefacto de evaluación de borrador versionado (`skill-extraction-development-0.1.0.json`, estado `draft_evaluation`, fecha de anotación fija `2026-08-02`) con 60 etiquetas de borrador de inspección directa en 11 de los 20 registros: positivos con citas exactas y offsets half-open, etiquetas `not_supported` de cero coincidencias y confusión de fronteras (`java` vs `javascript`, `git` vs `github`, `statistics` vs «Statistical Physics») y 4 etiquetas `uncertain` excluidas de las métricas primarias. Las etiquetas se redactaron de forma independiente inspeccionando directamente el texto fuente de los campos del conjunto de datos analítico (nunca copiadas de las predicciones del matcher) y NO son oro ni están revisadas por humanos. El evaluador (`analysis/evaluation.py`) valida metadatos, etiquetas y cada cita/offset exactamente (`field[char_start:char_end] == exact_quote`), calcula TP/FP/FN/TN, precisión/recall/F1 con denominadores cero seguros, métricas micro y macro con un alcance explícito, cobertura, distribución de etiquetas y entradas de detalle FP/FN; la CLI (`analysis/evaluate.py`) escribe el informe determinista `skill-extraction-development-report-0.1.0.json`. Métricas: TP 38 / FP 5 / FN 0 / TN 13; precisión 0,8837, recall 1,0, F1 0,9383 (micro sobre 56 pares no inciertos); macro precisión/recall/F1 0,9811 / 1,0 / 0,9862; cobertura 60/740 pares, 11/20 registros; 4 inciertos; 10 pares predichos sin etiqueta excluidos. Los 5 falsos positivos son coincidencias `skill.ai` en roles que declaran explícitamente que no se requiere experiencia en IA (la negación no se interpreta en 0.1.0).

- **Pasada de anotación de segunda pasada separada en borrador (histórica) — `data/evaluation/` + `docs/evaluation-review.md`.** La segunda pasada (`skill-extraction-review-0.2.0.json`, `draft_second_pass`, `human_review_required: true`, fecha de anotación fija `2026-08-02`) etiqueta los 20 × 37 = 740 pares COMPLETOS de la muestra de desarrollo mediante una rutina separada de anotación de texto directo (`analysis/second_pass.py`) guiada por un manifiesto de adjudicación curado: las etiquetas se deciden de forma independiente leyendo los campos de texto fuente (los términos de la taxonomía son solo vocabulario candidato) y las predicciones del matcher nunca se leen al etiquetar — `annotate_second_pass(...)` y `compare_with_predictions(...)` son funciones separadas, y la suite de pruebas demuestra la independencia eliminando `skill_evidence` de una copia del conjunto de datos. El artefacto NO es oro y NO está revisado por humanos, cualquier artefacto que declare un estado de oro/revisado por humanos se rechaza y no se cambió ninguna regla del matcher ni de la taxonomía. El revisor valida metadatos, cobertura exacta de 740 pares, enumerado de etiquetas cerrado, sin duplicados y cada cita/offset de evidencia exactamente; compara con el primer borrador (57 acuerdos / 3 desacuerdos / 680 pares sin etiqueta del primer borrador; una cola de revisión humana de 7 ítems = todas las etiquetas inciertas de la segunda pasada más los desacuerdos, cada uno con una `human_review_question`); y compara las etiquetas no inciertas con la línea base (TP/FP/FN/TN = 38/13/0/684; precisión 0,7451, recall 1,0, F1 0,8539 micro; macro 0,9754 / 1,0 / 0,9793; cobertura 740/740 pares, 20/20 registros; 0 registros sin evidencia; 0 pares predichos sin etiqueta). Los 13 falsos positivos son todos predicciones `skill.ai` con limitación de negación (documentadas, no corregidas en el matcher). Los casos de frontera y requisito negativo están documentados por etiqueta: `java` vs `javascript`, `git` vs `github`, IA en contexto de empresa/categoría, «No prior experience in AI is required», `statistics` vs «Statistical Physics», «emotional intelligence» ≠ IA. La CLI (`analysis/review.py`) escribe `skill-extraction-review-0.2.0.json` y `skill-extraction-review-report-0.2.0.json` de forma determinista; `docs/evaluation-review.md` documenta el método, los campos, los offsets exactos, las comparaciones, las métricas y la decisión de revisión humana requerida. La mesa de evidencia de Streamlit está implementada (interfaz `en validación pública`); ver la sección Ejecutar. Este hito está completo; su sucesor es la revisión final adjudicada por humanos de abajo.

- **Revisión final adjudicada por humanos — `data/evaluation/` + `analysis/finalize_review.py`.** La revisión final (`skill-extraction-review-0.3.0.json` / `skill-extraction-review-report-0.3.0.json`, `human_review_complete`, `human_review_required: false`, fecha de aprobación 2026-08-02, fuente `explicit project-owner instruction`) aplica exactamente las siete decisiones aprobadas (HR-01…HR-07) a las etiquetas v0.2.0 congeladas, conserva cada otra etiqueta y toda la evidencia/motivos/preguntas/notas originales y recalcula a partir de las 740 etiquetas resultantes: 40 `supported` / 700 `not_supported` / 0 `uncertain`; TP/FP/FN/TN = 40/16/0/684; precisión 0,7143, recall 1,0, F1 0,8333 (micro); macro 0,9524 / 1,0 / 0,9662. El libro de decisiones auditable `human_review_decisions` registra por ítem la fuente, la habilidad, la etiqueta de la primera pasada cuando existe, la etiqueta original de la segunda pasada, la etiqueta final, la fecha/fuente de aprobación, el criterio y la evidencia conservada; el `human_review_queue` actual es `count: 0, items: []` y la cola/comparación primera-vs-segunda/métricas v0.2.0 se conservan bajo el bloque `historical` del informe. La evaluación es final solo para esta muestra curada de 20 ofertas — no oro, no benchmark universal, no representativa de mercado; el matcher sigue siendo una línea base de palabras clave sin validación definitiva para el mercado completo. CLI: `uv run python -m job_market_intelligence.analysis.finalize_review`.

### Limitaciones actuales

- **Una página por captura acotada.** El fixture offline de navegación cubre la página 1 (20 de los 94 542 empleos reportados por la fuente en el momento del fixture), y la captura en vivo autorizada también cubre solo la página 1 (20 de 94 520 en el momento de la captura en vivo). El comportamiento de paginación más allá de la página 1 está cubierto por páginas de prueba sintéticas, no por capturas reales guardadas.
- **Sin representación de mercado completo.** Una página de una fuente es una muestra, no un snapshot de mercado; el fixture offline guardado de la página 1 no contenía anuncios explícitos de Ecuador. Himalayas es una sola bolsa de trabajo y no representa todo el mercado laboral.
- **Sin segunda fuente.** Himalayas es la única fuente; no se afirma deduplicación ni comparación entre fuentes.
- **Solo persistencia acotada; no se descargó ningún feed completo.** `data/raw/` y `data/manifests/` se escriben solo cuando se invoca explícitamente `LocalCaptureStore.persist_page`. No se ha ejecutado ninguna corrida de feed completo contra la API en vivo; la evidencia cruda guardada contiene solo capturas de la página 1.
- **Captura de una sola página ejecutada una vez.** La única solicitud autorizada devolvió 20 registros de un `totalCount` reportado por la fuente de 94 520. El archivo crudo tiene 84 341 bytes, su SHA-256 está verificado contra el manifiesto y la captura está marcada `complete: false`; esto no es cobertura de mercado completo.
- **El análisis es solo evidencia de palabras clave.** Las coincidencias provienen de la taxonomía explícita `technical-skills-0.1.0` y de reglas de palabras clave seguras en fronteras; la línea base no interpreta la negación ni el contexto (por ejemplo «no prior experience in AI is required» igual coincide con `skill.ai`), y `no_evidence` no significa que una habilidad esté ausente. La taxonomía cubre 37 habilidades; cualquier cosa fuera de ella (por ejemplo SQL, Docker, Kubernetes) aún no se busca.
- **El análisis descriptivo está limitado a la muestra de desarrollo.** El artefacto de análisis y las visualizaciones describen exactamente 20 registros de una página (`limit=20`, `offset=0`) de una fuente, snapshot `cap_0370798f7af4b0e3`, `complete: false`; son solo descriptivos de evidencia de palabras clave y explícitamente NO son correlación, causalidad, cobertura de mercado ni representatividad. El analizador rechaza cualquier otro conjunto de datos y cualquier desajuste de versión de taxonomía.
- **Mesa de evidencia de Streamlit implementada (primera superficie visible, `Revisión humana completa` / `Evaluación final · muestra curada`).** `app/evidence_desk.py` (ejecutar: `uv run --extra demo streamlit run app/evidence_desk.py`) es un panel de operar/leer sobre los artefactos de la muestra de desarrollo: tesis + franja de evidencia (20 registros · 37 habilidades · 740 pares · 7 decisiones humanas resueltas · precisión final 0,7143 / recall 1,0 / F1 0,8333 para la muestra curada), panorama de habilidades, un explorador de ofertas con citas de evidencia exactas y veredictos finales por par, una sección de evaluación/auditoría (contingencia final, 16 falsos positivos, las 7 decisiones aprobadas) y proveniencia/limitaciones. Lee solo los artefactos locales versionados (sin llamadas de API en vivo), etiqueta la evaluación `human_review_complete` / `human_review_required: false` (`evaluation-final`, `human-reviewed`) y carga los datos a través del paquete probado por unidades y sin Streamlit `src/job_market_intelligence/demo/`. Existe una captura real de navegador congelada: `docs/assets/evidence-desk-public-es.png` (Chromium/WebDriver; nunca reemplazada ni regenerada). El paquete de revisión humana es `docs/human-review-package.md` (relato histórico v0.2.0 más la resolución aprobada de HR-01…HR-07).
- **Sin análisis semántico, LLM ni embeddings.** La coincidencia y búsqueda semánticas están explícitamente diferidas hasta que se mida y evalúe la línea base de palabras clave. El conjunto de evaluación de borrador ahora mide la línea base; los métodos semánticos siguen pendientes.
- **Las etiquetas de evaluación de borrador no son oro.**
- **La segunda pasada fue un borrador; la revisión final está completa-por-humanos para la muestra curada.** La pasada de anotación de segunda pasada en borrador (`skill-extraction-review-0.2.0`, histórica) etiquetó los 740 pares pero dejó 5 etiquetas inciertas excluidas de las métricas primarias y 7 ítems en cola para una decisión humana; nada de ese borrador era oro ni estaba revisado por humanos, y las métricas eran provisionales. Las 7 decisiones fueron aprobadas el 2026-08-02 (instrucción explícita de la persona responsable del proyecto) y la revisión final (`skill-extraction-review-0.3.0`, `human_review_complete`) es final solo para esta muestra curada de 20 ofertas — nunca oro, nunca benchmark universal, nunca representativa de mercado; el relato histórico v0.2.0 se conserva verbatim. El conjunto de evaluación (`skill-extraction-development-0.1.0`) es un `draft_evaluation`: las etiquetas se redactaron de forma independiente inspeccionando directamente el texto fuente del conjunto de datos analítico, no han sido revisadas por una segunda persona anotadora y NO son oro ni están revisadas por humanos; sus métricas siguen siendo provisionales. La cobertura del borrador fue parcial (60 de 740 pares, 11 de 20 registros), el borrador no contiene ningún falso negativo claro (recall = 1,0 refleja los positivos curados, no el mercado) y sus 5 falsos positivos provienen todos de la limitación de negación documentada de la línea base de palabras clave.
- **Sin cloud, LLM, embeddings ni agentes.** La extracción y evaluación de línea base van antes que cualquiera de estos.

## Problema

Estudiantes y profesionales de carrera temprana a menudo tienen que buscar entre ofertas de empleo dispersas para entender qué habilidades solicitan realmente los empleadores. La información es difícil de comparar porque los anuncios usan títulos de puesto inconsistentes, tecnologías duplicadas, etiquetas de senioridad diferentes y terminología mixta de ubicación o trabajo remoto.

Este proyecto convertirá datos públicos permitidos de ofertas de empleo en una vista explorable, reproducible y basada en evidencia del mercado laboral ecuatoriano y remoto relevante para Ecuador.

## Objetivo del producto

Construir una pequeña plataforma de datos de estilo producción que responda preguntas como:

- ¿Qué habilidades técnicas son las más solicitadas en roles de datos e IA?
- ¿Cómo difiere la demanda entre ciencia de datos, ingeniería de IA, ingeniería de datos y roles full-stack?
- ¿Qué herramientas aparecen juntas en los mismos anuncios de empleo?
- ¿Cómo afectan la senioridad, la ubicación y los requisitos de trabajo remoto a la demanda observada?
- ¿Cómo ha cambiado el mercado con el tiempo?

El producto debe mostrar la evidencia detrás de sus conclusiones. Cada registro debe conservar su fuente, su momento de recolección y su historial de transformación.

## Usuarios previstos

- Estudiantes que deciden qué aprender a continuación.
- Candidatos de carrera temprana que preparan un portafolio o CV.
- Asesores de carrera y comunidades universitarias.
- Reclutadores o gerentes de contratación que exploran la demanda tecnológica local.

## Qué hará el sistema

1. **Recolectar** datos de ofertas de empleo de fuentes públicas y permitidas. — *Implementado para Himalayas (adaptador de feed completo, paginación `limit=20` + `offset`).*
2. **Conservar** las respuestas crudas de la fuente con marcas de tiempo de recolección y metadatos de fuente. — *Conservación exacta de páginas crudas más persistencia acotada y opt-in a `data/raw/` con manifiestos en `data/manifests/` implementada; la orquestación de snapshot de feed completo está pendiente.*
3. **Normalizar** títulos, ubicaciones, senioridad, modo de trabajo y nombres de tecnología. — *Proyección canónica, alcance de ubicación y marcas de tiempo implementados para Himalayas; la taxonomía versionada de habilidades técnicas (`technical-skills-0.1.0`) está implementada; la normalización más amplia de títulos/senioridad está pendiente.*
4. **Extraer** habilidades de las descripciones con una taxonomía transparente y métodos NLP medibles. — *Línea base determinista de palabras clave (`keyword-baseline-0.1.0`) implementada con reglas de frontera explícitas y medida por un conjunto de evaluación de borrador; los embeddings y métodos semánticos siguen pendientes después de la línea base.*
5. **Modelar** un conjunto de datos analítico para roles, habilidades, empresas, ubicaciones y observaciones a lo largo del tiempo. — *Conjunto de datos de desarrollo versionado e informe de calidad embebido implementados para la captura de 20 registros; el modelado analítico completo está pendiente.*
6. **Analizar** demanda, coocurrencia, tendencias y diferencias entre familias de roles. — *Línea base descriptiva implementada para la muestra de desarrollo de 20 registros: frecuencia de habilidades, cobertura por categoría, pares de coocurrencia sin orden, matriz de coocurrencia y habilidades sin coincidencias; las tendencias y las comparaciones entre familias de roles siguen pendientes.*
7. **Exponer** los resultados mediante una API y una demo web interactiva. — *Pendiente.*
8. **Reportar** frescura de datos, salud de la fuente, checks de calidad, supuestos y limitaciones. — *Informe de calidad determinista básico para la muestra de desarrollo implementado (campos faltantes, duplicados, cobertura de habilidades, frescura); el reporte general de salud de la fuente está pendiente.*

## Visión de la demo

La demo final debe entenderse en menos de un minuto y debe mostrar más que una gráfica del camino feliz:

- Un panel de inicio con el volumen de roles actual, las habilidades principales, las familias de roles, las ubicaciones y la distribución de trabajo remoto.
- Un explorador de habilidades que muestre tendencias de demanda y tecnologías relacionadas.
- Una vista de comparación de roles para posiciones de Data Scientist, AI/ML Engineer, Data Engineer y Full-Stack AI Engineer.
- Una vista de empleos buscable con el enlace original de la fuente y la evidencia extraída.
- Una página de calidad de datos que muestre la última ingesta exitosa, el estado de la fuente, la tasa de duplicados y las limitaciones conocidas.
- Un estado de resultado vacío o caída de la fuente que explique qué ocurrió en lugar de fallar en silencio.

El proyecto tendrá un despliegue público cuando se entiendan las restricciones de la fuente de datos y el hosting. Hasta entonces, se requerirá una demo local reproducible y un recorrido grabado corto.

## Alcance

### Producto mínimo viable

- Una o más fuentes de datos públicas y permitidas. — *Himalayas implementada; una segunda fuente sigue pendiente.*
- Un comando de ingesta reproducible con fixtures guardados para el desarrollo offline. — *Adaptador verificado contra fixtures; un punto de entrada CLI sigue pendiente.*
- Capas de datos crudos y limpios. — *Capa cruda en disco acotada (`data/raw/` + `data/manifests/`) implementada; la capa limpia está pendiente.*
- Títulos de empleo, ubicaciones, senioridad y modo de trabajo normalizados. — *Proyección canónica implementada para Himalayas; la normalización más amplia está pendiente.*
- Una taxonomía versionada de habilidades tecnológicas. — *Implementada (`technical-skills-0.1.0`, 37 habilidades, reglas de coincidencia explícitas).*
- Análisis descriptivo y visualizaciones principales. — *Implementados para la muestra de desarrollo de 20 registros: artefacto de análisis descriptivo más visualizaciones de línea base SVG/Markdown; la mesa de evidencia interactiva de Streamlit está implementada (estado final `Revisión humana completa` / `Evaluación final · muestra curada`).*
- Una demo interactiva de Streamlit. — *Pendiente.*
- Pruebas automatizadas para parseo, normalización, deduplicación, validación de datos, persistencia local, taxonomía, la línea base de palabras clave y la evaluación de borrador. — *Implementadas (suite offline completa; ninguna prueba toca la red).*
- Un README que documente el linaje de datos, las métricas, las limitaciones y la configuración. — *Este documento; la documentación de linaje/ejecución crece con la persistencia.*

### Versión 2

- Servicio FastAPI para el conjunto de datos analítico.
- Almacenamiento PostgreSQL para los datos de la aplicación.
- Búsqueda semántica con embeddings de oraciones e índice vectorial, solo después de que exista una línea base de búsqueda por palabras clave.
- Ingesta programada y monitoreo de frescura.
- Un conjunto de evaluación etiquetado pequeño para extracción de habilidades y relevancia de búsqueda. — *Conjunto de evaluación de borrador implementado (`draft_evaluation`, no oro); las etiquetas oro/revisadas por humanos y la evaluación de relevancia de búsqueda siguen pendientes.*
- Despliegue local Dockerizado y checks de CI.

### Explícitamente fuera de alcance

- Extraer LinkedIn o cualquier sitio web en violación de sus términos, política de robots o controles de acceso.
- Recolectar información de contacto personal o perfiles de candidatos.
- Afirmar representar todo el mercado laboral ecuatoriano.
- Presentar correlación como causalidad.
- Construir un pipeline de extracción opaco solo-LLM sin línea base ni evaluación.
- Añadir infraestructura cloud antes de que el pipeline local sea reproducible.

## Pila técnica propuesta

| Capa | Elección inicial | Propósito |
| --- | --- | --- |
| Lenguaje | Python | Implementación principal y análisis |
| Entorno | `uv` | Gestión reproducible de dependencias y entorno |
| Calidad | Ruff, pytest, Pandera | Formateo/linting, pruebas y contratos de datos |
| Ingesta | Adaptadores de fuente Python, `httpx`, parsers permitidos | Recolectar datos sin acoplar el dominio a una fuente |
| Almacenamiento crudo | Fixtures JSON y Parquet | Conservar la evidencia de la fuente y permitir desarrollo offline |
| Analítica | pandas y DuckDB | Limpieza, análisis SQL y consultas analíticas locales |
| Línea base NLP | Reglas de normalización, coincidencia de taxonomía, scikit-learn | Extracción de habilidades transparente y medible |
| Extensión NLP | sentence-transformers | Coincidencia y búsqueda semánticas después de la línea base |
| API | FastAPI y Pydantic | Frontera de servicio tipada para la aplicación |
| Demo | Streamlit para el MVP | Demostración pública interactiva rápida y legible |
| Almacenamiento de aplicación | PostgreSQL, después | Registros duraderos y datos listos para búsqueda |
| Entrega | Docker y GitHub Actions, después | Ejecución reproducible y checks automatizados |

Las elecciones tecnológicas están escalonadas deliberadamente. El proyecto no empezará con una pila grande de frameworks ni con un LLM. Primero haremos confiables el pipeline de datos, la extracción de línea base y la evaluación.

## Habilidades demostradas

### Ciencia de datos

- Encuadre de problemas y definición de métricas.
- Análisis exploratorio de datos y visualización.
- Comparaciones agrupadas y análisis de tendencias por tiempo.
- Sesgo, missingness, limitaciones de muestreo e incertidumbre.
- Conclusiones basadas en evidencia en lugar de solo conteo de tecnologías.

### Ingeniería de datos

- Adaptadores de fuente e ingesta resiliente.
- Capas de datos crudos, limpios y analíticos.
- Diseño de esquemas y contratos de datos.
- Deduplicación, idempotencia, frescura y manejo de fallos.
- Analítica SQL con DuckDB y PostgreSQL.

### IA y NLP

- Diseño de taxonomías y normalización de entidades.
- Una línea base transparente de palabras clave/reglas.
- Embeddings y búsqueda semántica como extensión medida.
- Datos de evaluación etiquetados, análisis de errores y abstención cuando la evidencia es débil.

### Software y full stack

- Módulos Python tipados y fronteras de servicio.
- Endpoints FastAPI y validación con Pydantic.
- Experiencia de usuario interactiva con Streamlit.
- Pruebas, documentación, configuración, logging y ejecución reproducible.
- CI y preparación para despliegue.

### Comunicación profesional

- Declaración clara del problema y valor para las partes interesadas.
- Diagramas de arquitectura y linaje de datos.
- Métricas, compensaciones, limitaciones y análisis de fallos.
- Un video corto de demo y una publicación en LinkedIn enfocada en el resultado, no en la lista de herramientas.

## Plan de evaluación

El proyecto reportará evidencia medible, incluida:

- Tasa de éxito de ingesta y frescura de la fuente.
- Resultados de detección de duplicados en una muestra revisada.
- Completitud de campos para título, fuente, ubicación y momento de publicación.
- Precisión y recall de extracción de habilidades en un conjunto de evaluación etiquetado a mano pequeño. — *Implementado: `data/evaluation/skill-extraction-development-0.1.0.json` + informe determinista (`draft_evaluation`, no oro). La revisión de segunda pasada (`skill-extraction-review-0.2.0.json`, `draft_second_pass`) etiquetó los 740 pares y puso 7 decisiones humanas en cola; esas decisiones fueron aprobadas el 2026-08-02 y la revisión final adjudicada por humanos `skill-extraction-review-0.3.0.json` (`human_review_complete`) es final solo para esta muestra curada de 20 ofertas — nunca oro, benchmark universal ni cobertura de mercado.*
- Relevancia de búsqueda contra preguntas candidatas representativas.
- Tiempo de respuesta del panel o la API para la carga de trabajo de la demo.
- Reproducibilidad desde un entorno limpio usando fixtures.
- Al menos un fallo inducido intencionalmente y la respuesta del sistema.

Un buen resultado no es necesariamente un número grande de anuncios recolectados. Un buen resultado es un sistema confiable y explicable cuyas limitaciones son visibles.

## Principios de datos y ética

- Usar solo fuentes públicas o explícitamente permitidas.
- Respetar los términos de servicio, las políticas de robots, los límites de tasa y los requisitos de atribución.
- Almacenar URLs de la fuente y marcas de tiempo de recolección.
- Evitar datos personales e identificadores innecesarios.
- Mantener un conjunto de datos fixture para que el proyecto siga siendo ejecutable si una fuente cambia o desaparece.
- Documentar la cobertura de la fuente y el sesgo de muestreo conocido.
- Nunca presentar el panel como una estadística oficial del mercado laboral.

## Estructura del repositorio

```text
.
├── README.md
├── pyproject.toml
├── src/
│   └── job_market_intelligence/
│       ├── __init__.py
│       ├── ingestion/
│       │   ├── __init__.py
│       │   ├── adapter.py
│       │   ├── errors.py
│       │   ├── models.py
│       │   ├── parser.py
│       │   └── storage.py
│       └── analysis/
│           ├── __init__.py
│           ├── errors.py
│           ├── taxonomy.py      (cargador tipado de la taxonomía versionada)
│           ├── matcher.py       (línea base determinista de palabras clave)
│           ├── dataset.py       (conjunto de datos canónico de desarrollo)
│           ├── quality.py       (informe de calidad determinista)
│           ├── materialize.py   (CLI offline: regenerar el conjunto de datos)
│           ├── descriptive.py   (métricas descriptivas a nivel de registro)
│           ├── visualizations.py (artefactos SVG/Markdown de línea base stdlib)
│           ├── visualize.py     (CLI offline: análisis + visualizaciones)
│           ├── evaluation.py    (validación de evaluación de borrador + métricas)
│           ├── evaluate.py      (CLI offline: informe de evaluación)
│           ├── second_pass.py   (etiquetas de anotación de segunda pasada separadas + comparación)
│           ├── review.py        (CLI offline: artefactos de revisión de segunda pasada)
│           └── finalize_review.py (CLI offline: revisión final adjudicada por humanos v0.3.0)
├── tests/
│   ├── conftest.py
│   ├── test_adapter.py
│   ├── test_bounded_capture.py
│   ├── test_parser.py
│   ├── test_scope.py
│   ├── test_storage.py
│   ├── test_timestamps.py
│   ├── test_taxonomy.py
│   ├── test_matcher.py
│   ├── test_dataset.py
│   ├── test_quality.py
│   ├── test_materialize.py
│   ├── test_descriptive.py
│   ├── test_visualizations.py
│   ├── test_evaluation.py
│   └── test_finalize_review.py
├── data/
│   ├── raw/          (capturas locales acotadas; en gitignore)
│   ├── manifests/    (manifiestos de captura; no ignorados por defecto)
│   ├── taxonomy/
│   │   └── technical-skills-0.1.0.json
│   ├── analytics/
│   │   ├── development-sample-0.1.0.json   (conjunto de datos + informe de calidad embebido)
│   │   ├── descriptive-development-sample-0.1.0.json (artefacto de análisis descriptivo)
│   │   └── visualizations/development-sample-0.1.0/  (gráficas SVG + tabla de cero coincidencias)
│   ├── evaluation/
│   │   ├── skill-extraction-development-0.1.0.json   (etiquetas de evaluación de borrador)
│   │   ├── skill-extraction-development-report-0.1.0.json (informe de evaluación de borrador)
│   │   ├── skill-extraction-review-0.2.0.json   (etiquetas de revisión de segunda pasada, draft_second_pass — histórico)
│   │   ├── skill-extraction-review-report-0.2.0.json (informe de revisión de segunda pasada — histórico)
│   │   ├── skill-extraction-review-0.3.0.json   (etiquetas finales adjudicadas por humanos, human_review_complete)
│   │   └── skill-extraction-review-report-0.3.0.json (informe final para la muestra curada)
│   └── sample/
│       ├── himalayas_browse_page_1.json
│       ├── himalayas_browse_page_1.metadata.json
│       ├── himalayas_ec_page_1.json
│       └── himalayas_ec_page_1.metadata.json
├── docs/
│   └── ingestion/
│       └── himalayas-adapter-contract.md
└── planned: normalization/, notebooks/, app/, .github/
```

Los conjuntos de datos crudos grandes, las credenciales y el estado de ejecución local no deben confirmarse (commitearse).

## Hoja de ruta

- [x] Auditar la primera fuente de datos candidata (Himalayas) y sus restricciones de uso.
- [x] Definir el esquema de dominio canónico para la primera fuente (Himalayas).
- [x] Crear fixtures de fuente (página 1 de navegación + página EC exploratoria) y el primer adaptador de ingesta.
- [x] Normalizar la proyección canónica y deduplicar dentro de Himalayas (en memoria).
- [x] Añadir pruebas de rutas de fallo (no-2xx, payloads malformados, paginación, marcas de tiempo).
- [x] Persistir páginas crudas y manifiestos de recolección en disco (acotado, opt-in; la orquestación de snapshot de feed completo está pendiente).
- [x] Definir la taxonomía versionada de habilidades tecnológicas (`technical-skills-0.1.0`, reglas explícitas de palabras clave/fronteras, 37 habilidades).
- [x] Construir el primer conjunto de datos analítico de desarrollo y el informe de calidad desde la captura local existente de 20 registros (`data/analytics/development-sample-0.1.0.json`); las visualizaciones de línea base siguen pendientes.
- [x] Construir visualizaciones de línea base y análisis de coocurrencia sobre el conjunto de datos de desarrollo (artefacto de análisis descriptivo, gráficas de barras SVG de frecuencia de habilidades y cobertura por categoría, mapa de calor de coocurrencia, tabla de cero coincidencias; la demo de Streamlit sigue pendiente).
- [ ] Añadir reportes de calidad/frescura de datos más allá del informe de la muestra de desarrollo (salud de la fuente a lo largo del tiempo, tasa de duplicados entre páginas).
- [x] Construir el MVP de Streamlit (mesa de evidencia local, `Revisión humana completa` / `Evaluación final · muestra curada`; captura real de navegador congelada en `docs/assets/evidence-desk-public-es.png`; paquete de revisión humana `docs/human-review-package.md`).
- [x] Resolver las 7 decisiones de revisión humana pendientes (aprobadas el 2026-08-02; la evaluación es `evaluation-final-for-curated-20-offer-sample`).
- [x] Añadir un conjunto y un informe de evaluación de borrador de extracción de habilidades (`draft_evaluation`, no oro/revisado por humanos; la búsqueda semántica sigue pendiente).
- [x] Añadir una pasada de anotación de segunda pasada separada en borrador (`draft_second_pass`, `human_review_required: true`, no revisada por humanos; 740/740 pares, comparación primera-vs-segunda, comparación con el matcher; la revisión humana ahora está completa; sin cambios de matcher/taxonomía).
- [x] Aprobar las 7 decisiones de revisión humana y materializar la revisión final (`human_review_complete`, v0.3.0; métricas finales solo para la muestra curada de 20 ofertas; v0.2.0 histórico conservado).
- [ ] Añadir FastAPI y PostgreSQL solo cuando el MVP lo justifique.
- [ ] Añadir búsqueda semántica solo después de medir la línea base de palabras clave.
- [ ] Añadir una segunda fuente permitida cuando el pipeline lo justifique.
- [ ] Desplegar la demo o publicar un recorrido grabado.
- [ ] Escribir el caso de estudio técnico final y la publicación de LinkedIn.

## Definición de terminado

El proyecto está listo para publicación en portafolio cuando:

- Una persona nueva puede ejecutarlo desde instrucciones documentadas.
- La demo responde una pregunta clara del usuario con evidencia trazable.
- El pipeline de datos puede manejar duplicados, campos faltantes y una caída de la fuente.
- Las líneas base y los resultados de evaluación se reportan con honestidad.
- Las pruebas y el CI pasan en la revisión revisada.
- El README explica la arquitectura, las compensaciones, las limitaciones y los siguientes pasos.
- Una persona reclutadora puede entender el problema, el resultado y el enlace de la demo en menos de dos minutos.

## Licencia

**Código original.** El código original de este repositorio se publica bajo la licencia MIT (ver `LICENSE`).

**Datos y contenido de terceros.** Los datos de fuente, capturas raw, manifests, fixtures, citas de fuente y demás contenido externo no quedan cubiertos por la licencia MIT: conservan los términos independientes documentados (ver `docs/ingestion/himalayas-adapter-contract.md`) y no se otorga ningún derecho implícito sobre material de terceros.
