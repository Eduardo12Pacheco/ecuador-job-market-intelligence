# Evaluación de extracción de habilidades: histórico y revisión final

> **Estado actual: revisión humana completa.** La evaluación final está en
> `data/evaluation/skill-extraction-review-0.3.0.json` y
> `data/evaluation/skill-extraction-review-report-0.3.0.json`, con estado
> `human_review_complete` y métricas finales únicamente para la muestra curada
> de 20 ofertas. La revisión v0.2.0 que se documenta más abajo es histórica y se
> conserva sin modificaciones; sus siete decisiones fueron resueltas en la
> revisión v0.3.0. No se afirma cobertura ni generalización al mercado completo.

## Resumen de la revisión final (v0.3.0)

- **Alcance:** 20 ofertas de una sola página de Himalayas, 37 habilidades y 740 pares.
- **Estado:** `evaluation-final-for-curated-20-offer-sample`; revisión humana completa el 2 de agosto de 2026.
- **Distribución final:** 40 `supported`, 700 `not_supported`, 0 `uncertain`.
- **Matriz final:** TP/FP/FN/TN = 40/16/0/684.
- **Métricas:** precisión 0,7143; recall 1,0; F1 0,8333. Describen únicamente esta muestra curada.
- **Trazabilidad:** las siete decisiones están en `human_review_decisions`, con criterio, fecha, fuente, etiquetas originales, evidencia y offsets preservados.
- **Baseline:** matcher determinista de palabras clave; no interpreta negación ni contexto y no está validado de forma definitiva para el mercado completo.

La interfaz muestra `Revisión humana completa` y
`Evaluación final · muestra curada`. La advertencia de alcance es:
`Muestra curada · métricas finales para 20 ofertas · no representa el mercado completo`.

## Histórico v0.2.0: segunda pasada pendiente en ese momento

El resto de este documento conserva la explicación original de
`skill-extraction-review-0.2.0` y de su cola humana. Las frases sobre siete
pendientes, estado provisional y decisiones por resolver describen exclusivamente
ese artefacto histórico; no son el estado actual del proyecto.

## Alcance fijo

| Campo | Valor |
| --- | --- |
| Versión de la evaluación | `skill-extraction-review-0.2.0` |
| Estado de anotación | `draft_second_pass` |
| Revisión humana requerida | `true` |
| Tipo de conjunto de datos | `development_sample` |
| Snapshot | `cap_0370798f7af4b0e3` |
| Taxonomía | `technical-skills-0.1.0` (37 habilidades) |
| Matcher | `keyword-baseline-0.1.0` (sin cambios) |
| Fuente / atribución | Himalayas (`https://himalayas.app`) |
| Endpoint | `https://himalayas.app/jobs/api` |
| Fecha de anotación | `2026-08-02` (fecha fija del repositorio; sin reloj de pared) |
| Muestra | exactamente 20 registros, una página (`limit=20`, `offset=0`), `complete: false` |
| Cobertura | 740 / 740 pares `(source_id, skill_id)`; 20 / 20 registros |

**No se afirma cobertura de mercado**: una página de una sola bolsa de trabajo es
una captura acotada (`complete: false`), no un snapshot de mercado, y todo
artefacto lleva el aviso explícito de no-cobertura-de-mercado.

## Método

La segunda pasada es una **re-anotación independiente**: los 740 pares (20
registros × 37 habilidades de la taxonomía) fueron etiquetados por una rutina
separada de anotación de texto directo
(`src/job_market_intelligence/analysis/second_pass.py`) guiada por un **manifiesto
de adjudicación curado** (`_ADJUDICATION` en ese módulo). La rutina:

1. lee solo los campos de texto fuente conservados en el conjunto de datos
   analítico — `title_raw`, `excerpt_raw`, `categories_raw`,
   `description_html_raw`;
2. usa los términos de la taxonomía solo como vocabulario candidato — nunca
   como veredicto;
3. decide cada etiqueta a partir del texto real y de reglas de contexto
   explícitas;
4. **nunca lee `skill_evidence`** mientras etiqueta. La separación se garantiza
   por construcción y se prueba: `annotate_second_pass(...)` (etiquetado) y
   `compare_with_predictions(...)` (comparación con el matcher) son funciones
   separadas, y la suite de pruebas demuestra que quitar `skill_evidence` de una
   copia del conjunto de datos produce etiquetas idénticas. Las etiquetas de la
   segunda pasada nunca son `labels = predictions`.

### Semántica de las etiquetas

- **`supported`** — al menos una entrada de evidencia exacta: `field`,
  `exact_quote`, `char_start`, `char_end` con `field[char_start:char_end] ==
  exact_quote` (offsets half-open, estilo Python, sobre el valor exacto del
  campo del conjunto de datos). Solo los campos de texto pueden llevar offsets:
  `title_raw`, `excerpt_raw`, `description_html_raw`. `categories_raw` es una
  lista JSON y se revisa, pero nunca se usa para evidencia con offsets.
- **`not_supported`** — **sin evidencia positiva explícita** en los campos
  revisados (que se listan en `reviewed_fields`). Nunca significa que la persona
  o el puesto carezca de la habilidad. La evidencia está vacía; el motivo
  documenta el requisito negativo o el caso de frontera cuando existe.
- **`uncertain`** — una mención genuinamente ambigua. Cuando el texto ambiguo
  existe en un campo de texto se cita con offsets exactos; en caso contrario
  (por ejemplo menciones en contexto de categoría) el motivo documenta la
  ambigüedad. Cada etiqueta `uncertain` lleva una `human_review_question` que
  indica qué debe decidir una persona, y se excluye de todo denominador de
  métricas primario.

Cada etiqueta lleva un `reason` preciso; las `notes` capturan observaciones de
frontera y de contexto de categoría o empresa.

### Campos revisados y contrato de evidencia

Para cada etiqueta, `reviewed_fields` es la superficie revisada completa:

```text
title_raw, excerpt_raw, categories_raw, description_html_raw
```

La evidencia se valida de forma cerrada: una cita de evidencia debe reproducir
el corte exacto del campo (`field[char_start:char_end] == exact_quote`) con
offsets no negativos y dentro de los límites. Las etiquetas `supported` deben
llevar al menos una entrada de evidencia; las `not_supported` no deben llevar
ninguna.

## Casos de frontera, confusión y requisito negativo

La segunda pasada documenta (por etiqueta) los siguientes casos; no se añadió
ninguna regla de negación ni de contexto al matcher, solo se documentaron:

| Caso | Ejemplo de evidencia | Decisión de la segunda pasada |
| --- | --- | --- |
| `java` vs `javascript` | "server-side JavaScript (Node.js)" | `java`: `not_supported` (frontera); `javascript`: `supported` |
| `git` vs `github` | "GitHub, Azure, Metabase, and JIRA" | `git`: `not_supported` (frontera); `github`: `supported` |
| Requisito negativo | "No prior experience in AI is required" (14 registros) | `skill.ai`: `not_supported` (13 registros) o `uncertain` (mandarín — ver abajo), con la frase negativa documentada en el motivo |
| IA en contexto de empresa | "applications … that are not AI-native" (rol de estrategia y operaciones) | `skill.ai`: `uncertain` — contexto de empresa/producto, no requisito del rol |
| IA en contexto de categoría | `categories_raw` = "Brazilian-Portuguese-AI-Specialist" | `skill.ai`: `uncertain` — las menciones de categoría no pueden llevar offsets y entran en conflicto con el requisito negativo |
| Vocabulario `ai` vs `machine_learning` | "developing advanced AI models" / "AI training" | `skill.machine_learning`: `not_supported` — «AI models» es vocabulario de IA; no aparece ningún término de ML |
| `statistics` vs "Statistical Physics" | título "Physics Expert (Statistical Physics …)" | `skill.statistics`: `not_supported` — subcampo de la física, no el término independiente statistics |
| "emotional intelligence" ≠ IA | "at the intersection of biometrics, emotional intelligence, and mobile software" | `skill.ai`: `not_supported` — no aparece el token «AI» |
| "data models" ≠ ciencia de datos | "Design data models and backend services" | `skill.data_science`: `not_supported` |
| Mención de campo de titulación | "Bachelor's degree in computer science, engineering, data science, or equivalent" | `skill.data_science`: `uncertain` — mención de cualificación, no habilidad desempeñada |

## Primera pasada frente a segunda pasada

La comparación es a nivel de par sobre los 60 pares que etiquetó el primer
borrador (`skill-extraction-development-0.1.0.json`, `draft_evaluation`):

- **Acuerdos: 57** — incluidos los 38 `supported` (las dos pasadas alcanzaron
  de forma independiente los mismos positivos) y 17 `not_supported`.
- **Desacuerdos: 3**, cada uno puesto en cola de revisión humana:
  1. `engineering-data-tools-specialist` / `skill.ai`: primer borrador
     `uncertain` → segunda pasada `not_supported` (el requisito negativo
     explícito es decisivo; la IA aparece solo como contexto del proyecto).
  2. `mandarin-audio-recording-expert` / `skill.ai`: primer borrador
     `not_supported` → segunda pasada `uncertain` (el deseable «AI data
     collection … is a plus» entra en conflicto con el requisito negativo).
  3. `mandarin-audio-recording-expert` / `skill.machine_learning`: primer
     borrador `uncertain` → segunda pasada `not_supported` (no aparece ningún
     término de ML; «AI models» es vocabulario de IA).
- **Pares sin etiqueta del primer borrador: 680** (el primer borrador etiquetó
  60 de 740). Se cuentan por separado y nunca se tratan como desacuerdos.
- **Conteos de etiquetas explícitos** — primer borrador: 38 `supported` / 18
  `not_supported` / 4 `uncertain` (60 en total); segunda pasada: 38 `supported`
  / 697 `not_supported` / 5 `uncertain` (740 en total). Las distribuciones no
  son directamente comparables porque la cobertura difiere (60 frente a 740).

## Comparación con el matcher y métricas

Las etiquetas de la segunda pasada se compararon con las predicciones existentes
de `skill_evidence.skills` del conjunto de datos **después** de crear las 740
etiquetas; una habilidad predicha cuenta como máximo una vez por registro. Las
etiquetas inciertas (5) se excluyen de las métricas primarias y se reportan por
separado.

| Métrica | Valor |
| --- | --- |
| TP / FP / FN / TN | 38 / 13 / 0 / 684 |
| Precisión (micro) | 38/51 ≈ 0,7451 |
| Recall (micro) | 38/38 = 1,0 |
| F1 (micro) | 76/89 ≈ 0,8539 |
| Precisión / recall / F1 macro | 0,9754 / 1,0 / 0,9793 (33 habilidades definidas) |
| Alcance macro | las 37 habilidades de la taxonomía; 4 excluidas por indefinidas: `skill.cpp`, `skill.csharp`, `skill.git`, `skill.java` (todas `not_supported`) |
| Cobertura de etiquetas | 740/740 pares (100%); 735/740 no inciertos |
| Registros revisados | 20/20 |
| Registros sin evidencia del matcher | 0 |
| Etiquetas inciertas | 5 (`skill.ai` × 3, `skill.data_science` × 1, `skill.machine_learning` × 1) |
| Pares predichos sin etiqueta | 0 (el primer borrador excluyó 10) |

**Semántica macro**: media no ponderada de la precisión/recall/F1 por habilidad
sobre las 37 habilidades con al menos un par etiquetado no incierto; una
habilidad cuyo valor por habilidad es indefinido (todas las etiquetas
`not_supported`, sin oro ni predicción positivos) se excluye de la media y se
lista explícitamente. Precisión/recall son `None` cuando su denominador es cero;
F1 es `0.0` cuando al menos uno de ellos está definido como 0.

**Falsos positivos principales (13, todos `skill.ai`)**: cada uno es una
coincidencia `ai` de la línea base de palabras clave en un rol cuyo texto dice
explícitamente «No prior experience in AI is required» o menciona la IA solo
como contexto del proyecto (`german`, `italian`, `portugal`, `dutch`,
`biophysics`, `highenergy`, `kiembu`, `condensed`, `biglaw`, `amo`,
`statistical`, `gravitation` — registros de audio/física/derecho — más
`engineering-data-tools`). La limitación documentada de negación 0.1.0 de la
línea base es la única causa; el informe lista cada uno con la propia evidencia
del matcher (campo, término coincidente, extracto).

**Falsos negativos: 0** — toda etiqueta `supported` de la segunda pasada está
predicha. Recall = 1,0 es una propiedad del conjunto curado (los positivos se
eligieron donde la línea base es fuerte), no una afirmación de mercado.

## Histórico v0.2.0: decisiones que quedaron pendientes entonces

`human_review_required: true` significa que una persona debía decidir los
siguientes 7 ítems antes de cualquier afirmación de oro (todos están en el
`human_review_queue` del informe):

1. `engineering-data-tools-specialist` / `skill.ai` — desacuerdo: ¿el «No prior
   experience in AI is required» explícito es decisivo (`not_supported`) o el
   contexto del proyecto lo mantiene ambiguo (`uncertain`)?
2. `engineering-data-tools-specialist` / `skill.data_science` — ¿la mención de
   campo de titulación cuenta como evidencia?
3. `german-audio-recording-expert` / `skill.machine_learning` — ¿la frase
   posterior «datasets for advanced machine learning applications» cuenta como
   evidencia?
4. `mandarin-audio-recording-expert` / `skill.ai` — ¿el deseable «AI data
   collection … is a plus» pesa más que el requisito negativo?
5. `mandarin-audio-recording-expert` / `skill.machine_learning` — ¿«AI models»
   es vocabulario de ML o de IA?
6. `portuguese-audio-recording-expert-brazil` / `skill.ai` — ¿las menciones de
   contexto de categoría y «audio samples for AI training» cuentan como
   evidencia pese al requisito negativo?
7. `strategy-operations-associate` / `skill.ai` — ¿el contexto de
   empresa/producto («not AI-native») cuenta como evidencia para un rol no
   técnico?

Cada ítem de la cola lleva la etiqueta de la segunda pasada, la etiqueta del
primer borrador (cuando existe), el motivo, la evidencia (o la ubicación de la
ambigüedad) y la `human_review_question` exacta. Una pasada futura revisada por
humanos (`gold`) debe ser un artefacto nuevo con otra versión y otro estado;
este borrador nunca debe re-etiquetarse en su lugar.

## Reproducibilidad

```bash
uv run python -m job_market_intelligence.analysis.review
```

regenera ambos artefactos de forma determinista a partir del conjunto de datos
local versionado, la taxonomía y la evaluación del primer borrador. La
regeneración es de cierre: un artefacto existente con contenido diferente se
rechaza (nunca se sobrescribe) y ambos archivos se serializan canónicamente
(claves ordenadas, sangría de 2 espacios, salto de línea final). Pruebas:
`uv run pytest tests/test_second_pass.py`.

## Limitaciones y salvaguardas del histórico v0.2.0

- Muestra de desarrollo: 20 registros, una página (`limit=20`, `offset=0`), una
  fuente, `complete: false` — **no es cobertura de mercado**.
- Etiquetas de borrador: 5 etiquetas inciertas excluidas de las métricas
  primarias; 7 ítems en cola de revisión humana; nada es oro ni está revisado
  por humanos.
- 680 de 740 pares no estaban etiquetados en el primer borrador y no pueden
  compararse entre pasadas.
- Sin análisis semántico, LLM ni embeddings; la línea base de palabras clave no
  interpreta la negación y no se añadió ninguna regla de negación/contexto al
  matcher — los casos solo se documentaron.
- `not_supported` nunca significa que la persona o el puesto carezca de la
  habilidad.
- No aparecen descripciones crudas completas en ningún artefacto ni informe;
  solo citas exactas y extractos acotados.
