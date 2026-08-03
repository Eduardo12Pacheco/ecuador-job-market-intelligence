# Producto

<!-- impeccable:product-schema 1 -->

## Plataforma

web

## Usuarios

- Reclutadores, revisores técnicos y gerentes de contratación que evalúan el proyecto — la audiencia principal de la primera superficie visible, que debe comunicar el mecanismo en un minuto.
- Estudiantes y profesionales de carrera temprana que deciden qué aprender a continuación; asesores de carrera y comunidades universitarias (objetivo del proyecto en README; aún no atendidos por una superficie dedicada).

## Propósito del producto

Convertir datos públicos permitidos de ofertas de empleo en una vista explorable, reproducible y basada en evidencia del mercado laboral ecuatoriano y remoto relevante para Ecuador y — de forma crítica — mostrar la evidencia detrás de cada conclusión: cada registro conserva su fuente, su momento de recolección y su historial de transformación, y cada habilidad extraída lleva una cita exacta al texto fuente. El éxito del primer hito visible es que una persona evaluadora externa entienda qué extrae la herramienta, cómo lo demuestra y qué no afirma, sin leer código.

## Posicionamiento

Transparente por construcción. El proceso es una línea base determinista de palabras clave (sin LLM, embeddings ni inferencia semántica) cuyas coincidencias se comparan con una pasada de anotación independiente en borrador (`draft_second_pass`, `human_review_required: true`) y con un resultado v0.3.0 adjudicado por humanos. Ambos permanecen limitados a la muestra curada y nunca se convierten en una afirmación sobre el mercado completo. El artefacto visible es la pista de auditoría, no una historia de mercado pulida.

## Contexto operativo

- Proceso offline con Python primero: adaptador de ingesta de Himalayas, taxonomía versionada de habilidades técnicas, matcher de palabras clave con límites seguros, conjunto de datos de desarrollo con informe de calidad integrado, análisis descriptivo, evaluación de borrador histórica y una revisión v0.3.0 adjudicada por humanos — todo materializado como artefactos JSON versionados bajo `data/`.
- La superficie interactiva es una app local de Streamlit (`app/evidence_desk.py`) que solo lee artefactos locales versionados y no hace llamadas de red.
- Fecha fija de anotación del repositorio `2026-08-02`; snapshot de captura `cap_0370798f7af4b0e3`; no se lee ningún reloj de pared en la generación de artefactos.
- Los artefactos están en inglés; la superficie de la app es español profesional (lengua de publicación de investigación). El estado público es `Revisión humana completa` / `Evaluación final · muestra curada`; el aviso de muestra final indica que las métricas cubren solo 20 ofertas y los tokens de máquina aparecen solo dentro del expansor «Detalles técnicos».

## Capacidades y restricciones

Capacidades confirmadas: muestra de desarrollo de 20 registros (una página, `complete: false`), taxonomía de 37 habilidades en 8 categorías, línea base determinista de palabras clave con extractos de evidencia exactos por coincidencia, revisión de 740 pares adjudicada por humanos con 7 decisiones aprobadas, métricas micro finales-para-muestra (precisión 0,7143, recall 1,0, F1 0,8333) más métricas macro, captura real con Chromium y pruebas offline de fixtures/adaptador.

Restricciones confirmadas: las coincidencias son solo evidencia de palabras clave (la negación no se interpreta en 0.1.0, p. ej. «No prior experience in AI is required» sigue coincidiendo con `skill.ai`); 20 registros de una página de una fuente no son cobertura de mercado; no hay análisis semántico/LLM/embeddings; no hay segunda fuente; las etiquetas históricas de borrador siguen siendo provisionales y se conservan por separado.

Sin decidir: captura del feed completo, matching semántico, comparación entre fuentes, tendencias en el tiempo y exposición por API (todo explícitamente pendiente en README).

## Compromisos de marca

- Nombre del proyecto: «Ecuador Job Market Intelligence» (título del README).
- Enlace visible de atribución a himalayas.app exigido al mostrar datos de ofertas (nota de términos en `data/sample/*.metadata.json`).
- Sin afirmaciones de generalización no respaldadas: el borrador v0.2.0 y los artefactos v0.3.0 adjudicados por humanos permanecen trazables por separado; la interfaz declara que las métricas finales cubren solo la muestra curada.
- [Supuesto] No existen otros activos de marca, logotipos ni compromisos de voz en el repositorio; la dirección visual fue delegada: mesa de evidencia contenida / cuaderno de investigación (ver el brief de superficie de la app).

## Evidencia disponible

- `data/analytics/development-sample-0.1.0.json` — 20 registros con evidencia de habilidades e informe de calidad integrado.
- `data/analytics/descriptive-development-sample-0.1.0.json` — frecuencia de habilidades, cobertura por categoría, coocurrencia, habilidades sin coincidencias.
- `data/evaluation/skill-extraction-review-0.3.0.json` y `-report-0.3.0.json` — etiquetas, métricas, falsos positivos y siete registros de aprobación finales-para-muestra.
- `data/evaluation/skill-extraction-review-0.2.0.json` y `-report-0.2.0.json` — etiquetas históricas congeladas, métricas provisionales y la cola de revisión original.
- `data/taxonomy/technical-skills-0.1.0.json` — 37 habilidades, 8 categorías, reglas de coincidencia, términos excluidos.
- `data/sample/` — fixtures de captura offline más sidecars de metadatos (términos de la fuente, SHA-256, momento de captura).

Ausente y que no debe fabricarse: afirmaciones de cobertura de mercado, una segunda fuente de ofertas o resultados de extracción semántica.

## Principios del producto

1. Toda afirmación lleva una cita exacta y verificable (campo, texto, desplazamientos de caracteres) — o no se muestra.
2. Los borradores históricos y los resultados finales-para-muestra se etiquetan por separado; el alcance es explícito en todas partes.
3. La muestra nunca es el mercado: el alcance de 20 registros y `complete: false` se declaran en cada superficie.
4. Determinista y reproducible antes que semántico o difuso.
5. Una persona evaluadora externa debe comprender el mecanismo — qué se extrae, cómo se evidencia, qué queda sin probar — en un minuto.

## Accesibilidad e inclusión

[Supuesto] No se ha registrado ningún requisito de accesibilidad específico del producto. La superficie web sigue como barra de calidad por defecto el contraste AA de WCAG 2.1, los controles operables con teclado y el foco visible.
