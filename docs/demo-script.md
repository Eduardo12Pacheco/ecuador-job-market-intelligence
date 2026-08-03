# Mesa de evidencia — guion de demostración en 60 segundos

Un recorrido local por Streamlit de la mesa de evidencia
(`app/evidence_desk.py`), pensado para quien evalúa el proyecto sin leer
código. Lee estas líneas, señala la pantalla y deja que las cifras reales de
la mesa hagan la demostración. Todos los números salen en vivo de los
artefactos locales versionados bajo `data/`; nada está escrito a mano y nada
es una afirmación de mercado.

Estado que muestra esta demo: **`Revisión humana completa`** y **`Evaluación
final · muestra curada`** (`demo-ready` y `portfolio-ready` para esta entrega local;
sin una afirmación sobre el mercado completo). Las 7 decisiones humanas
fueron aprobadas el 2 de agosto de 2026 y no hay ninguna decisión pendiente
actual; la clasificación del proyecto es `evaluation-final-for-curated-20-offer-sample`
y el aviso `Muestra curada · métricas finales para 20 ofertas · no representa
el mercado completo` permanece visible en pantalla. Existe una captura real y
congelada de la interfaz en `docs/assets/evidence-desk-public-es.png`
(Chromium/WebDriver); captura real verificada después de los checks finales.

---

## 0:00–0:10 — El problema

> «Toda oferta de trabajo menciona tecnologías, pero casi nadie muestra su
> trabajo. Construí un proceso que extrae habilidades técnicas de las ofertas
> y — más importante — prueba cada extracción con la cita exacta del texto, y
> después audita su propia extracción con una revisión humana. Esta mesa
> muestra la evidencia, no un panel pulido.»

Señala la cabecera (título, etiqueta «Mesa de evidencia», chips «Revisión
humana completa» y «Evaluación final · muestra curada», propósito en una frase
y atribución a Himalayas), la barra de muestra curada (`Muestra curada ·
métricas finales para 20 ofertas · no representa el mercado completo`) y luego
la franja de evidencia: 20 ofertas analizadas, 37 habilidades de la taxonomía,
740 pares revisados, 7 decisiones humanas resueltas y las métricas finales.

## 0:10–0:25 — El mecanismo

> «¿Cómo funciona la extracción? Un buscador determinista por palabras clave
> examina cuatro campos de cada oferta — título, extracto, categorías y
> descripción — con una taxonomía fija de 37 habilidades: sin distinguir
> mayúsculas, respetando los límites de palabra, sin magia. `java` nunca
> coincide con `javascript`, `git` nunca coincide con `github`.»

Abre la pestaña **Panorama de habilidades** y señala «Cómo funciona el
buscador» y «Lo que el buscador no hace».

> «Lo que NO hace es igual de importante: no interpreta negaciones —
> “No se requiere experiencia previa en IA” igual coincide con la habilidad
> de IA — y no hay comprensión semántica, ni vectores, ni modelos de lenguaje
> en ninguna parte del proceso.»

## 0:25–0:40 — La evidencia

> «Elige cualquier oferta.» (Selecciona una en la pestaña **Explorar
> ofertas**.)

> «Aquí están sus datos: empresa, ubicación, salario, fechas. Aquí lo que
> detectó el buscador, con la cita exacta, el campo y el número de
> apariciones. Y aquí el veredicto final de la revisión humana sobre las 37
> habilidades posibles de esta oferta, incluyendo dónde no está de acuerdo
> con el buscador.»

Señala un veredicto «respaldado» con su cita verificada, un veredicto con el
chip «decisión humana aprobada» (las dos ofertas de audio de Micro1 cuyos
pares de IA fueron aprobados como respaldados) y el bloque «El buscador
predijo estas — la revisión final no está de acuerdo» con sus falsos
positivos.

> «Cada cita se vuelve a verificar al renderizar contra el artefacto: si los
> datos cambiaran algún día, el bloque pasaría a un estado de cita rota en
> lugar de mostrar en silencio evidencia vieja.»

## 0:40–0:50 — La evaluación

Abre la pestaña **Auditoría de evaluación**.

> «La evaluación es una auditoría completa de 20 × 37 = 740 pares, y las
> cifras de la mesa son exactas: 40 verdaderos positivos, 16 falsos
> positivos, 0 falsos negativos, 684 verdaderos negativos. Precisión final
> 0,7143; recall final 1,0; F1 final 0,8333 — para esta muestra curada. Los
> falsos positivos vienen de la limitación documentada: el buscador no
> entiende “No se requiere experiencia previa en IA”, y tres de ellos fueron
> confirmados por las decisiones humanas aprobadas. El recall perfecto es una
> propiedad de esta muestra curada, no del mercado.»

Señala la matriz de contingencia final, las tres métricas con su explicación
en lenguaje humano y los 7 expansores de «decisión humana aprobada» con su
criterio, su fecha y su fuente.

## 0:50–0:57 — Los límites

> «Lo que esta mesa NO es: la muestra son 20 ofertas de una sola página de
> una sola bolsa de trabajo, marcada como muestra incompleta — no representa
> al mercado ecuatoriano. Las métricas son finales solo para esta muestra
> curada: no describen el mercado completo, y el buscador sigue siendo
> una línea base de palabras clave sin validación definitiva para el mercado
> completo.»

Señala la frase de límite bajo la tesis («Esto no es un estudio del mercado
laboral ecuatoriano…») y la pestaña **Proveniencia y límites**.

## 0:57–1:00 — El siguiente paso

> «La revisión humana quedó completa: 7 decisiones aprobadas el 2 de agosto
> de 2026, cada una registrada con su criterio y su evidencia. El siguiente
> paso no es resolver decisiones, sino validar el buscador con más fuentes y
> más ofertas — y esta mesa mostrará honestamente el nuevo estado cuando eso
> ocurra.»

El relato completo de esas decisiones vive en `docs/human-review-package.md`:
el paquete histórico v0.2.0 (7 ítems HR-01…HR-07 con su evidencia y sus
offsets) más el apéndice de resolución con la etiqueta final aprobada de cada
ítem; ninguna decisión fue automática.

---

## Estado de la revisión humana

- El matcher (`keyword-baseline-0.1.0`) **no está validado de forma definitiva**;
  las métricas de la mesa son **finales solo para esta muestra curada de 20
  ofertas** y las **7 decisiones humanas fueron aprobadas** (2026-08-02,
  instrucción explícita de la persona responsable del proyecto).
- El sistema es un **prototipo local de soporte a la revisión**, no una taxonomía
  de mercado final; la clasificación actual es `evaluation-final-for-curated-20-offer-sample`
  y la superficie local está `demo-ready` y `portfolio-ready`; esto no extiende el alcance más allá de la muestra.
- El paquete de revisión humana (`docs/human-review-package.md`) conserva el
  relato histórico v0.2.0 (7 ítems HR-01…HR-07 con su evidencia del informe,
  sus offsets half-open y su motivo) y documenta la **resolución aprobada** de
  cada ítem; la cola histórica está etiquetada como histórica y no hay
  decisiones pendientes actuales.

## Notas para quien presenta

- No presentes estas métricas como evidencia de demanda
  de mercado ni como una validación del buscador fuera de la muestra curada.
- Presenta `demo-ready` y `portfolio-ready` únicamente en el sentido acotado de
  esta entrega local: **Revisión humana completa / Evaluación final · muestra curada**,
  con el aviso de muestra curada siempre visible.
- Los tokens técnicos (versiones, identificadores, siglas de la matriz,
  rutas de archivos, historial v0.2.0) viven solo dentro de «Detalles técnicos»,
  al final de la pestaña **Proveniencia y límites**; no los señales fuera de ahí.
- Atribución: los datos se muestran bajo el requisito de atribución de
  Himalayas (enlace visible a himalayas.app en la cabecera y en la barra
  lateral).
- Si falta un archivo, la mesa muestra un mensaje de recuperación con los
  comandos de regeneración en lugar de una página en blanco — eso también es
  parte de la demo si tienes diez segundos extra.
