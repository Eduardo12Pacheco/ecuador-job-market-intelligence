# Paquete de revisión humana — histórico v0.2.0

Este documento conserva el paquete de trabajo que preparó las siete decisiones
humanas sobre la evaluación provisional. **Es un registro histórico:** las siete
decisiones fueron aprobadas y materializadas en
`data/evaluation/skill-extraction-review-0.3.0.json` y su informe. La interfaz
pública actual muestra revisión humana completa; esta página conserva la evidencia,
alternativas y estado previo sin reescribirlo.

| Estado del paquete histórico | Valor |
|---|---|
| Estado actual del proyecto | `evaluation-final-for-curated-20-offer-sample` — revisión humana completa |
| Captura real de la interfaz pública | `docs/assets/evidence-desk-public-es.png` (obtenida con Chromium/WebDriver) |
| Etiquetas de la cola histórica | Las 7 (HR-01…HR-07) quedaron `PENDIENTE` en este paquete y fueron resueltas en v0.3.0 |
| Decisión automática | No hubo: la resolución fue aprobada explícitamente por la persona responsable |
| Artefactos fuente | Congelados y sin modificar (ver §1) |

---

## 1. Estado congelado y métricas

Este paquete se preparó solo con lectura de los artefactos congelados; no se
modificó ningún JSON de evaluación ni ningún otro artefacto fuente.

| Concepto | Valor congelado |
|---|---|
| Evaluación / informe | `skill-extraction-review-0.2.0` (`report_version: 0.2.0`) |
| Estado de anotación | `draft_second_pass`; `human_review_required: true` |
| Conjunto de datos | `development_sample` v0.1.0 — 20 registros, una página (`limit=20`, `offset=0`), `complete: false`, snapshot `cap_0370798f7af4b0e3` |
| Taxonomía | `technical-skills-0.1.0` (37 habilidades) |
| Matcher | `keyword-baseline-0.1.0` (sin análisis de negación, sin semántica) |
| Pares anotados | 740 (20 registros × 37 habilidades); segunda pasada: 38 `supported`, 697 `not_supported`, 5 `uncertain` |
| Fecha de anotación | 2026-08-02 |
| Fuente / atribución | himalayas.app (`https://himalayas.app/jobs/api`) |

**Métricas congeladas** (micro primarias, 735 pares no inciertos):
TP=38, FP=13, FN=0, TN=684; `precision=0.7450980392`, `recall=1.0`,
`F1=0.8539325843` — mostradas a cuatro decimales: precisión 0,7451,
recall 1,0000, F1 0,8539. Las 5 etiquetas `uncertain` quedan excluidas de todos
los denominadores primarios. En ese momento ninguna etiqueta tenía resolución humana; la resolución actual está registrada en v0.3.0.

> Formato de números: en este documento las métricas se muestran con coma
> decimal (cuatro decimales), salvo los valores citados textualmente de los
> artefactos congelados, que conservan el punto decimal del JSON.

**Reglas de contingencia aplicadas** (definición `primary_micro` del informe):

- predicha + `supported` → TP
- predicha + `not_supported` → FP
- predicha + `uncertain` → excluida
- no predicha + `supported` → FN
- no predicha + `not_supported` → TN
- no predicha + `uncertain` → excluida

**Cola de revisión**: 7 ítems en el orden exacto del informe
(`human_review_queue.items`): cinco `uncertain`, uno `not_supported` sobre
`skill.ai` y uno `not_supported` sobre `skill.machine_learning`.

**Predicciones del matcher** (leídas de `data/analytics/development-sample-0.1.0.json`
sin modificar, campo `records[].skill_evidence.skills`): HR-01 predicha, HR-02
predicha, HR-03 predicha, HR-04 predicha, HR-05 predicha, HR-06 **no predicha**,
HR-07 predicha. En el estado actual de la contingencia, HR-02 aporta un FP,
HR-06 aporta un TN y los cinco ítems `uncertain` están excluidos.

---

## 2. Protocolo de decisión

1. **Quién decide.** La persona responsable (humana) revisa cada ítem; el
   sistema no toma ninguna decisión.
2. **Una etiqueta por ítem.** Para cada ítem HR-01…HR-07 se elige exactamente
   una de las tres etiquetas permitidas del enumerado cerrado:
   - `supported` — **respaldado**: hay evidencia explícita positiva de la
     habilidad en los campos revisados de la oferta (título, extracto,
     categorías, descripción).
   - `not_supported` — **no respaldado**: no hay evidencia explícita positiva en
     los campos revisados. Nunca significa que la persona o el puesto carezca de
     la habilidad.
   - `uncertain` — **incierto**: la mención es ambigua o los indicios se
     contradicen; la etiqueta se reporta por separado y se excluye de los
     denominadores primarios.
3. **Evidencia.** Cada ítem cita la evidencia del informe con su cita exacta y
   sus offsets half-open verificables (`campo[char_start:char_end] == quote`).
   Si el informe no aporta evidencia, se indica `evidence=[]` y **no** se
   inventa cita ni offset. Si se recupera una frase de contexto del registro
   local sin modificar, se etiqueta únicamente como **texto fuente contextual**
   (no es evidencia del informe) y se indica campo y offsets exactos.
4. **Proyecciones.** Para cada alternativa se muestra la proyección de
   sensibilidad de **un solo ítem**: se cambia solo ese ítem y los otros seis
   permanecen en su estado congelado actual. Las proyecciones **no son métricas
   finales combinadas**: las métricas finales solo existen cuando la persona
   responsable resuelve los siete ítems y los artefactos se regeneran.
5. **Bloque de aprobación.** Cada sección termina con un bloque en blanco
   (decisión aprobada por la persona responsable, fecha, justificación y
   etiqueta seleccionada). En este registro histórico **ningún bloque del formulario
   quedó completado**; la aprobación vigente está documentada en §7 y en v0.3.0.

---

## 3. Resumen de la cola

| Ítem | Empresa | Oferta | Habilidad | Matcher | 1.ª pasada | Actual (2.ª) | Estado |
|---|---|---|---|---|---|---|---|
| HR-01 | Bjak | Strategy & Operations Associate | `skill.ai` | predicha | `uncertain` | `uncertain` | `PENDIENTE` |
| HR-02 | Micro1 | Engineering & Data tools Specialist | `skill.ai` | predicha | `uncertain` | `not_supported` | `PENDIENTE` |
| HR-03 | Micro1 | Engineering & Data tools Specialist | `skill.data_science` | predicha | sin etiqueta | `uncertain` | `PENDIENTE` |
| HR-04 | Micro1 | German Audio Recording Expert | `skill.machine_learning` | predicha | `uncertain` | `uncertain` | `PENDIENTE` |
| HR-05 | Micro1 | Mandarin Audio Recording Expert | `skill.ai` | predicha | `not_supported` | `uncertain` | `PENDIENTE` |
| HR-06 | Micro1 | Mandarin Audio Recording Expert | `skill.machine_learning` | no predicha | `uncertain` | `not_supported` | `PENDIENTE` |
| HR-07 | Micro1 | Portuguese Audio Recording Expert (Brazil) | `skill.ai` | predicha | sin etiqueta | `uncertain` | `PENDIENTE` |

---

## 4. Ítems de revisión

### HR-01 — `skill.ai` — Strategy & Operations Associate (Bjak)

**Oferta** (registro congelado; identificador estable del par: `source_id` + `skill_id`):

| Campo | Valor |
|---|---|
| `source_id` (URL) | `https://himalayas.app/companies/bjak/jobs/strategy-operations-associate-7652220692` |
| Título | Strategy & Operations Associate |
| Empresa | Bjak (slug `bjak`; `company_raw` es el marcador `name`) |
| Ubicación | `other_country`; restricción: United States |
| Empleo | Full Time; seniority: Entry-level, Mid-level |

**Habilidad**: `skill.ai` — Artificial Intelligence (AI) — categoría `ml_ai` (ML & AI).

**Clasificaciones**: primera pasada `uncertain`; actual (segunda pasada)
`uncertain` → **PENDIENTE**. **Predicción del matcher**: predicha — `skill.ai`
está en `skill_evidence.skills`; término `ai` (keyword) en `excerpt_raw` y en
`description_html_raw`.

**Evidencia del informe** (`skill-extraction-review-report-0.2.0.json`, cola,
ítem 1):

- `description_html_raw`, cita exacta «that are not AI-native», offsets half-open
  `[107, 129)` — verificada: `description_html_raw[107:129] == "that are not AI-native"`.

**Texto fuente contextual** (recuperado del registro local sin modificar; no es
evidencia del informe):

- `description_html_raw`, «proactive smart assistant», `[157, 182)`
- `description_html_raw`, «multi-step reasoning», `[460, 480)`

**Motivo por el que queda pendiente**: la IA aparece solo en contexto de
empresa/producto: el empleador construye un «proactive smart assistant» para
«basic applications … that are not AI-native»; el rol de estrategia y
operaciones, no técnico, no tiene requisito de IA. Pregunta para la persona
responsable (del informe): decidir si el contexto de IA a nivel de
empresa/producto («not AI-native», «proactive smart assistant»,
«multi-step reasoning») cuenta como evidencia de la habilidad de IA para un rol
no técnico de estrategia y operaciones.

**Alternativas permitidas y proyección de sensibilidad de un solo ítem**
(los otros seis ítems permanecen en su estado congelado; las proyecciones no
son métricas finales combinadas):

| Alternativa | Efecto sobre la contingencia | TP | FP | FN | TN | Precisión | Recall | F1 |
|---|---|---|---|---|---|---|---|---|
| `supported` | el par pasa de excluido a TP | 39 | 13 | 0 | 684 | 0,7500 | 1,0000 | 0,8571 |
| `not_supported` | el par pasa de excluido a FP | 38 | 14 | 0 | 684 | 0,7308 | 1,0000 | 0,8444 |
| `uncertain` | el par permanece excluido | 38 | 13 | 0 | 684 | 0,7451 | 1,0000 | 0,8539 |

**Decisión aprobada por la persona responsable: __________________**

- Fecha: __________________
- Justificación: __________________
- Etiqueta seleccionada: __________________ (una de: `supported`, `not_supported`, `uncertain`)

---

### HR-02 — `skill.ai` — Engineering & Data tools Specialist (Micro1)

**Oferta** (registro congelado; identificador estable del par: `source_id` + `skill_id`):

| Campo | Valor |
|---|---|
| `source_id` (URL) | `https://himalayas.app/companies/micro1/jobs/engineering-data-tools-specialist` |
| Título | Engineering & Data tools Specialist |
| Empresa | Micro1 (slug `micro1`; `company_raw` es el marcador `name`) |
| Ubicación | `worldwide`; sin restricciones (remoto) |
| Empleo | Contractor; seniority: Mid-level |

**Habilidad**: `skill.ai` — Artificial Intelligence (AI) — categoría `ml_ai` (ML & AI).

**Clasificaciones**: primera pasada `uncertain`; actual (segunda pasada)
`not_supported` → **PENDIENTE**. **Predicción del matcher**: predicha —
`skill.ai` está en `skill_evidence.skills`; término `ai` (keyword) en
`description_html_raw` (2 apariciones). En la contingencia actual este par es
un FP.

**Evidencia del informe**: `evidence=[]` — el informe no cita ninguna frase con
offsets para este par; no se inventa cita ni offset.

**Texto fuente contextual** (recuperado del registro local sin modificar; no es
evidencia del informe):

- `description_html_raw`, «No prior experience in AI is required», `[471, 508)`
- `description_html_raw`, «help train next-generation AI systems», `[333, 370)`

**Motivo por el que queda pendiente**: caso de requisito negativo. La oferta
dice explícitamente «No prior experience in AI is required»; la IA aparece solo
como contexto de proyecto («help train next-generation AI systems») y el
alcance del rol (evaluación de herramientas) no contiene trabajo de IA. La
segunda pasada, de forma independiente, decidió `not_supported` (el requisito
negativo explícito es decisivo); el primer borrador etiquetó el par `uncertain`,
por lo que queda en la cola de revisión humana. El informe no plantea una
pregunta específica adicional para este ítem.

**Alternativas permitidas y proyección de sensibilidad de un solo ítem**
(los otros seis ítems permanecen en su estado congelado; las proyecciones no
son métricas finales combinadas):

| Alternativa | Efecto sobre la contingencia | TP | FP | FN | TN | Precisión | Recall | F1 |
|---|---|---|---|---|---|---|---|---|
| `supported` | el par pasa de FP a TP | 39 | 12 | 0 | 684 | 0,7647 | 1,0000 | 0,8667 |
| `not_supported` | el par permanece FP (sin cambio) | 38 | 13 | 0 | 684 | 0,7451 | 1,0000 | 0,8539 |
| `uncertain` | el par pasa de FP a excluido | 38 | 12 | 0 | 684 | 0,7600 | 1,0000 | 0,8636 |

**Decisión aprobada por la persona responsable: __________________**

- Fecha: __________________
- Justificación: __________________
- Etiqueta seleccionada: __________________ (una de: `supported`, `not_supported`, `uncertain`)

---

### HR-03 — `skill.data_science` — Engineering & Data tools Specialist (Micro1)

**Oferta** (registro congelado; identificador estable del par: `source_id` + `skill_id`):

| Campo | Valor |
|---|---|
| `source_id` (URL) | `https://himalayas.app/companies/micro1/jobs/engineering-data-tools-specialist` |
| Título | Engineering & Data tools Specialist |
| Empresa | Micro1 (slug `micro1`; `company_raw` es el marcador `name`) |
| Ubicación | `worldwide`; sin restricciones (remoto) |
| Empleo | Contractor; seniority: Mid-level |

**Habilidad**: `skill.data_science` — Data Science — categoría `ml_ai` (ML & AI).

**Clasificaciones**: primera pasada sin etiqueta (el par no fue etiquetado en el
primer borrador); actual (segunda pasada) `uncertain` → **PENDIENTE**.
**Predicción del matcher**: predicha — `skill.data_science` está en
`skill_evidence.skills`; término `data science` (keyword) en
`description_html_raw` (1 aparición).

**Evidencia del informe** (cola, ítem 3):

- `description_html_raw`, cita exacta «engineering, data science, or equivalent
  practical experience», offsets half-open `[2696, 2757)` — verificada:
  `description_html_raw[2696:2757] == "engineering, data science, or equivalent practical experience"`.

**Texto fuente contextual**: no se añade ninguno; la evidencia del informe cubre
la única mención de la habilidad.

**Motivo por el que queda pendiente**: «data science» aparece solo como campo de
titulación aceptable bajo cualificaciones preferidas («Bachelor's degree in
computer science, engineering, data science, or equivalent practical
experience»), no como una habilidad que el rol desempeña. Pregunta para la
persona responsable (del informe): decidir si la mención de un campo de
titulación bajo cualificaciones preferidas cuenta como evidencia explícita de la
habilidad de ciencia de datos (`supported`) o no (`not_supported`).

**Alternativas permitidas y proyección de sensibilidad de un solo ítem**
(los otros seis ítems permanecen en su estado congelado; las proyecciones no
son métricas finales combinadas):

| Alternativa | Efecto sobre la contingencia | TP | FP | FN | TN | Precisión | Recall | F1 |
|---|---|---|---|---|---|---|---|---|
| `supported` | el par pasa de excluido a TP | 39 | 13 | 0 | 684 | 0,7500 | 1,0000 | 0,8571 |
| `not_supported` | el par pasa de excluido a FP | 38 | 14 | 0 | 684 | 0,7308 | 1,0000 | 0,8444 |
| `uncertain` | el par permanece excluido | 38 | 13 | 0 | 684 | 0,7451 | 1,0000 | 0,8539 |

**Decisión aprobada por la persona responsable: __________________**

- Fecha: __________________
- Justificación: __________________
- Etiqueta seleccionada: __________________ (una de: `supported`, `not_supported`, `uncertain`)

---

### HR-04 — `skill.machine_learning` — German Audio Recording Expert (Micro1)

**Oferta** (registro congelado; identificador estable del par: `source_id` + `skill_id`):

| Campo | Valor |
|---|---|
| `source_id` (URL) | `https://himalayas.app/companies/micro1/jobs/german-audio-recording-expert` |
| Título | German Audio Recording Expert |
| Empresa | Micro1 (slug `micro1`; `company_raw` es el marcador `name`) |
| Ubicación | `worldwide`; sin restricciones (remoto) |
| Empleo | Contractor; seniority: Mid-level |

**Habilidad**: `skill.machine_learning` — Machine Learning — categoría `ml_ai`
(ML & AI).

**Clasificaciones**: primera pasada `uncertain`; actual (segunda pasada)
`uncertain` → **PENDIENTE**. **Predicción del matcher**: predicha —
`skill.machine_learning` está en `skill_evidence.skills`; término
`machine learning` (keyword) en `description_html_raw` (1 aparición).

**Evidencia del informe** (cola, ítem 4):

- `description_html_raw`, cita exacta «datasets for advanced machine learning
  applications», offsets half-open `[837, 888)` — verificada:
  `description_html_raw[837:888] == "datasets for advanced machine learning applications"`.

**Texto fuente contextual**: no se añade ninguno; la evidencia del informe cubre
la única mención de la habilidad.

**Motivo por el que queda pendiente**: el aprendizaje automático aparece solo
como uso posterior de las grabaciones («helping to build diverse and reliable
datasets for advanced machine learning applications»), no como una habilidad
que el rol deba realizar. Pregunta para la persona responsable (del informe):
decidir si la mención de contexto de proyecto («datasets for advanced machine
learning applications») cuenta como evidencia explícita de la habilidad de
machine learning (`supported`) o no (`not_supported`).

**Alternativas permitidas y proyección de sensibilidad de un solo ítem**
(los otros seis ítems permanecen en su estado congelado; las proyecciones no
son métricas finales combinadas):

| Alternativa | Efecto sobre la contingencia | TP | FP | FN | TN | Precisión | Recall | F1 |
|---|---|---|---|---|---|---|---|---|
| `supported` | el par pasa de excluido a TP | 39 | 13 | 0 | 684 | 0,7500 | 1,0000 | 0,8571 |
| `not_supported` | el par pasa de excluido a FP | 38 | 14 | 0 | 684 | 0,7308 | 1,0000 | 0,8444 |
| `uncertain` | el par permanece excluido | 38 | 13 | 0 | 684 | 0,7451 | 1,0000 | 0,8539 |

**Decisión aprobada por la persona responsable: __________________**

- Fecha: __________________
- Justificación: __________________
- Etiqueta seleccionada: __________________ (una de: `supported`, `not_supported`, `uncertain`)

---

### HR-05 — `skill.ai` — Mandarin Audio Recording Expert (Micro1)

**Oferta** (registro congelado; identificador estable del par: `source_id` + `skill_id`):

| Campo | Valor |
|---|---|
| `source_id` (URL) | `https://himalayas.app/companies/micro1/jobs/mandarin-audio-recording-expert` |
| Título | Mandarin Audio Recording Expert |
| Empresa | Micro1 (slug `micro1`; `company_raw` es el marcador `name`) |
| Ubicación | `worldwide`; sin restricciones (remoto) |
| Empleo | Contractor; seniority: Mid-level |

**Habilidad**: `skill.ai` — Artificial Intelligence (AI) — categoría `ml_ai` (ML & AI).

**Clasificaciones**: primera pasada `not_supported`; actual (segunda pasada)
`uncertain` → **PENDIENTE** (desacuerdo primera-vs-segunda pasada).
**Predicción del matcher**: predicha — `skill.ai` está en `skill_evidence.skills`;
término `ai` (keyword) en `excerpt_raw` y en `description_html_raw` (5
apariciones en la descripción).

**Evidencia del informe** (cola, ítem 5):

- `description_html_raw`, cita exacta «AI data collection or linguistic resource
  creation is a plus», offsets half-open `[2722, 2782)` — verificada:
  `description_html_raw[2722:2782] == "AI data collection or linguistic resource creation is a plus"`.

**Texto fuente contextual** (recuperado del registro local sin modificar; no es
evidencia del informe):

- `description_html_raw`, «No prior experience in AI is required», `[445, 482)`

**Motivo por el que queda pendiente**: señales contradictorias. La oferta dice
explícitamente «No prior experience in AI is required», pero lista un plus
(«Experience participating in projects involving AI data collection or
linguistic resource creation is a plus») y el rol «help[s] train next-generation
AI systems». Pregunta para la persona responsable (del informe): decidir si el
plus relacionado con IA («AI data collection … is a plus») pesa más que el
requisito negativo explícito.

**Alternativas permitidas y proyección de sensibilidad de un solo ítem**
(los otros seis ítems permanecen en su estado congelado; las proyecciones no
son métricas finales combinadas):

| Alternativa | Efecto sobre la contingencia | TP | FP | FN | TN | Precisión | Recall | F1 |
|---|---|---|---|---|---|---|---|---|
| `supported` | el par pasa de excluido a TP | 39 | 13 | 0 | 684 | 0,7500 | 1,0000 | 0,8571 |
| `not_supported` | el par pasa de excluido a FP | 38 | 14 | 0 | 684 | 0,7308 | 1,0000 | 0,8444 |
| `uncertain` | el par permanece excluido | 38 | 13 | 0 | 684 | 0,7451 | 1,0000 | 0,8539 |

**Decisión aprobada por la persona responsable: __________________**

- Fecha: __________________
- Justificación: __________________
- Etiqueta seleccionada: __________________ (una de: `supported`, `not_supported`, `uncertain`)

---

### HR-06 — `skill.machine_learning` — Mandarin Audio Recording Expert (Micro1)

**Oferta** (registro congelado; identificador estable del par: `source_id` + `skill_id`):

| Campo | Valor |
|---|---|
| `source_id` (URL) | `https://himalayas.app/companies/micro1/jobs/mandarin-audio-recording-expert` |
| Título | Mandarin Audio Recording Expert |
| Empresa | Micro1 (slug `micro1`; `company_raw` es el marcador `name`) |
| Ubicación | `worldwide`; sin restricciones (remoto) |
| Empleo | Contractor; seniority: Mid-level |

**Habilidad**: `skill.machine_learning` — Machine Learning — categoría `ml_ai`
(ML & AI).

**Clasificaciones**: primera pasada `uncertain`; actual (segunda pasada)
`not_supported` → **PENDIENTE** (desacuerdo primera-vs-segunda pasada).
**Predicción del matcher**: **no predicha** — `skill.machine_learning` no está
en `skill_evidence.skills` del registro (solo `skill.ai`). En la contingencia
actual este par es un TN.

**Evidencia del informe**: `evidence=[]` — el informe no cita ninguna frase con
offsets para este par; no se inventa cita ni offset.

**Texto fuente contextual** (recuperado del registro local sin modificar; no es
evidencia del informe):

- `description_html_raw`, «developing advanced AI models», `[231, 260)`
- `description_html_raw`, «AI training», `[1249, 1260)`
- `description_html_raw`, «No prior experience in AI is required», `[445, 482)`

**Motivo por el que queda pendiente**: caso de confusión de vocabulario. Los
campos revisados mencionan «developing advanced AI models» y «AI training», pero
nunca «machine learning» ni «ml»; «AI models» es vocabulario de IA, no evidencia
explícita de la habilidad de machine learning. El primer borrador etiquetó el
par `uncertain`; la segunda pasada, de forma independiente, lo marcó
`not_supported`, por lo que queda en la cola de revisión humana. El informe no
plantea una pregunta específica adicional para este ítem.

**Alternativas permitidas y proyección de sensibilidad de un solo ítem**
(los otros seis ítems permanecen en su estado congelado; las proyecciones no
son métricas finales combinadas):

| Alternativa | Efecto sobre la contingencia | TP | FP | FN | TN | Precisión | Recall | F1 |
|---|---|---|---|---|---|---|---|---|
| `supported` | el par pasa de TN a FN | 38 | 13 | 1 | 683 | 0,7451 | 0,9744 | 0,8444 |
| `not_supported` | el par permanece TN (sin cambio) | 38 | 13 | 0 | 684 | 0,7451 | 1,0000 | 0,8539 |
| `uncertain` | el par pasa de TN a excluido | 38 | 13 | 0 | 683 | 0,7451 | 1,0000 | 0,8539 |

Nota: en la alternativa `uncertain` el TN baja de 684 a 683, pero precisión,
recall y F1 no cambian porque el TN no participa en esas razones.

**Decisión aprobada por la persona responsable: __________________**

- Fecha: __________________
- Justificación: __________________
- Etiqueta seleccionada: __________________ (una de: `supported`, `not_supported`, `uncertain`)

---

### HR-07 — `skill.ai` — Portuguese Audio Recording Expert (Brazil) (Micro1)

**Oferta** (registro congelado; identificador estable del par: `source_id` + `skill_id`):

| Campo | Valor |
|---|---|
| `source_id` (URL) | `https://himalayas.app/companies/micro1/jobs/portuguese-audio-recording-expert-brazil` |
| Título | Portuguese Audio Recording Expert (Brazil) |
| Empresa | Micro1 (slug `micro1`; `company_raw` es el marcador `name`) |
| Ubicación | `other_country`; restricción: Brazil |
| Empleo | Contractor; seniority: Mid-level |

**Habilidad**: `skill.ai` — Artificial Intelligence (AI) — categoría `ml_ai` (ML & AI).

**Clasificaciones**: primera pasada sin etiqueta (el par no fue etiquetado en el
primer borrador); actual (segunda pasada) `uncertain` → **PENDIENTE**.
**Predicción del matcher**: predicha — `skill.ai` está en `skill_evidence.skills`;
término `ai` (keyword) en `categories_raw` y en `description_html_raw` (3
apariciones en la descripción).

**Evidencia del informe** (cola, ítem 7):

- `description_html_raw`, cita exacta «audio samples for AI training», offsets
  half-open `[881, 910)` — verificada:
  `description_html_raw[881:910] == "audio samples for AI training"`.

**Texto fuente contextual** (recuperado del registro local sin modificar; no es
evidencia del informe):

- `description_html_raw`, «No prior experience in AI is required», `[448, 485)`
- `categories_raw` (arreglo de 4 valores): elemento «Brazilian-Portuguese-AI-Specialist»
  (índice 3). Por ser un valor de arreglo no se definen offsets de caracteres;
  el valor es verificable contra el artefacto congelado sin modificar.

**Motivo por el que queda pendiente**: señales mixtas. El valor de
`categories_raw` «Brazilian-Portuguese-AI-Specialist» y la frase «contextually
relevant audio samples for AI training» sugieren participación en IA, mientras
la oferta dice explícitamente «No prior experience in AI is required». Pregunta
para la persona responsable (del informe): decidir si la mención de contexto de
categoría («Brazilian-Portuguese-AI-Specialist» en `categories_raw`) y la frase
«audio samples for AI training» cuentan como evidencia de la habilidad de IA
pese al requisito negativo explícito.

**Alternativas permitidas y proyección de sensibilidad de un solo ítem**
(los otros seis ítems permanecen en su estado congelado; las proyecciones no
son métricas finales combinadas):

| Alternativa | Efecto sobre la contingencia | TP | FP | FN | TN | Precisión | Recall | F1 |
|---|---|---|---|---|---|---|---|---|
| `supported` | el par pasa de excluido a TP | 39 | 13 | 0 | 684 | 0,7500 | 1,0000 | 0,8571 |
| `not_supported` | el par pasa de excluido a FP | 38 | 14 | 0 | 684 | 0,7308 | 1,0000 | 0,8444 |
| `uncertain` | el par permanece excluido | 38 | 13 | 0 | 684 | 0,7451 | 1,0000 | 0,8539 |

**Decisión aprobada por la persona responsable: __________________**

- Fecha: __________________
- Justificación: __________________
- Etiqueta seleccionada: __________________ (una de: `supported`, `not_supported`, `uncertain`)

---

## 5. Firma final

La persona responsable declara haber revisado y decidido los siete ítems de la
cola, completando el bloque de aprobación de cada sección (§4). La firma final
solo es válida cuando los siete ítems están aprobados:

- [ ] HR-01 — `https://himalayas.app/companies/bjak/jobs/strategy-operations-associate-7652220692` — `skill.ai`
- [ ] HR-02 — `https://himalayas.app/companies/micro1/jobs/engineering-data-tools-specialist` — `skill.ai`
- [ ] HR-03 — `https://himalayas.app/companies/micro1/jobs/engineering-data-tools-specialist` — `skill.data_science`
- [ ] HR-04 — `https://himalayas.app/companies/micro1/jobs/german-audio-recording-expert` — `skill.machine_learning`
- [ ] HR-05 — `https://himalayas.app/companies/micro1/jobs/mandarin-audio-recording-expert` — `skill.ai`
- [ ] HR-06 — `https://himalayas.app/companies/micro1/jobs/mandarin-audio-recording-expert` — `skill.machine_learning`
- [ ] HR-07 — `https://himalayas.app/companies/micro1/jobs/portuguese-audio-recording-expert-brazil` — `skill.ai`

Nombre y firma de la persona responsable: __________________

Fecha: __________________

---

## 6. Plantilla de respuesta (máquina-legible, en blanco)

Plantilla JSON en blanco para registrar las decisiones; la etiqueta `label` solo
acepta `supported`, `not_supported` o `uncertain`. Esta plantilla no constituye
una decisión ni modifica ningún artefacto.

```json
{
  "evaluation_version": "skill-extraction-review-0.2.0",
  "dataset_version": "0.1.0",
  "snapshot_id": "cap_0370798f7af4b0e3",
  "reviewed_by": "",
  "review_date": "",
  "decisions": [
    { "item_id": "HR-01", "source_id": "https://himalayas.app/companies/bjak/jobs/strategy-operations-associate-7652220692", "skill_id": "skill.ai", "label": "" },
    { "item_id": "HR-02", "source_id": "https://himalayas.app/companies/micro1/jobs/engineering-data-tools-specialist", "skill_id": "skill.ai", "label": "" },
    { "item_id": "HR-03", "source_id": "https://himalayas.app/companies/micro1/jobs/engineering-data-tools-specialist", "skill_id": "skill.data_science", "label": "" },
    { "item_id": "HR-04", "source_id": "https://himalayas.app/companies/micro1/jobs/german-audio-recording-expert", "skill_id": "skill.machine_learning", "label": "" },
    { "item_id": "HR-05", "source_id": "https://himalayas.app/companies/micro1/jobs/mandarin-audio-recording-expert", "skill_id": "skill.ai", "label": "" },
    { "item_id": "HR-06", "source_id": "https://himalayas.app/companies/micro1/jobs/mandarin-audio-recording-expert", "skill_id": "skill.machine_learning", "label": "" },
    { "item_id": "HR-07", "source_id": "https://himalayas.app/companies/micro1/jobs/portuguese-audio-recording-expert-brazil", "skill_id": "skill.ai", "label": "" }
  ]
}
```

## 7. Resolución aplicada en v0.3.0

Esta sección y los artefactos v0.3.0 son la referencia actual. Los bloques en
blanco de las secciones anteriores pertenecen al formulario histórico v0.2.0;
no representan una solicitud abierta ni una aprobación faltante.

| Ítem | Etiqueta final | Criterio aprobado |
|---|---|---|
| HR-01 | `not_supported` | La IA aparece únicamente como contexto del producto; el cargo no exige ni ejecuta trabajo de IA. |
| HR-02 | `not_supported` | La oferta no requiere experiencia previa en IA y la mención pertenece al contexto del proyecto. |
| HR-03 | `not_supported` | `data science` aparece como campo posible de título, no como tarea ejecutada por el cargo. |
| HR-04 | `not_supported` | El uso posterior por aplicaciones de ML no demuestra que el cargo desarrolle o aplique ML. |
| HR-05 | `supported` | La experiencia en recolección de datos para IA es una ventaja relacionada directamente con el rol. |
| HR-06 | `not_supported` | Se mencionan AI models/training, pero no trabajo explícito de machine learning. |
| HR-07 | `supported` | La producción de muestras para entrenamiento de IA se relaciona directamente con el rol. |

**Aprobación común:** persona responsable del proyecto; fecha `2026-08-02`;
fuente `explicit project-owner instruction`. Las siete decisiones se aplicaron
exactamente una vez a sus pares congelados. El artefacto actual conserva la
etiqueta de segunda pasada, la decisión final, la evidencia y los offsets
half-open; la cola actual es `count: 0`.
