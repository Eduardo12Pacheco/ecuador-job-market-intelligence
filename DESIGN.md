# Diseño — Mesa de evidencia (Streamlit local)

Documentado a partir del mundo construido (`app/evidence_desk.py`) en el
rediseño público en español, según el flujo de rediseño de Impeccable.
Dirección: **mesa de evidencia editorial y contenida, superficie pública en
español de publicación científica** (fijada por el brief superior; brief de
superficie en `.impeccable/surfaces/app-evidence-desk-py.md`).

## Mundo

La superficie se lee como el apéndice de publicación de un proyecto de
investigación — una mesa editorial donde la persona investigadora fijó las
cifras reales y sus fuentes: lienzo blanco roto, banda superior de pizarra
profunda, secciones con filetes separadas por líneas de 1 px y una sola señal
ámbar/terracota usada **solo** para estados contextuales o históricos
(candidatos a falso positivo, notas históricas). El estado actual es final
para la muestra curada: sin aviso de prototipo y sin bloques de decisiones
pendientes. Sin muros de tarjetas, sin teatro de indicadores, sin degradados,
sin emojis, sin sombras decorativas, sin fuentes remotas. Toda la copia
pública es español profesional; el contenido de los artefactos (notas de la
revisión, motivos, preguntas, limitaciones) se conserva verbatim como datos.

## Tokens

| Token | Valor | Uso |
| --- | --- | --- |
| `--canvas` | `#F4F2ED` | fondo de la página y de la barra lateral |
| `--paper` | `#FFFFFF` | bloques de tesis, límites, franja y veredictos |
| `--masthead` | `#1F2A37` | banda de pizarra profunda: cabecera, pestaña activa |
| `--masthead-ink` | `#F5F3EE` | texto sobre la banda |
| `--masthead-muted` | `#B9C2CD` | leyendas sobre la banda |
| `--signal-bright` | `#E8A33D` | ámbar sobre oscuro: etiqueta de la mesa, enlace de la cabecera |
| `--ink` | `#1C1E21` | texto corrido y encabezados |
| `--ink-accent` | `#243B53` | cifras destacadas, enlaces, barras de gráficas, chips respaldados, contorno de foco |
| `--signal` | `#9A3412` | terracota: barra de aviso, estados inciertos o pendientes sobre claro |
| `--signal-tint` / `--signal-line` | `#FBF1E6` / `#E9D5BE` | barra de aviso y superficies inciertas |
| `--muted` | `#5A6169` | leyendas, líneas de metadatos, chips no respaldados |
| `--hairline` | `#E0DDD4` | reglas y bordes de 1 px (secciones con filete) |
| `--block` | `#F8F7F3` | bloques de cita |

Contraste: texto corrido y atenuado ≥ 4,5:1 sobre papel y lienzo; la señal
terracota se usa como texto solo sobre su tinte; ámbar sobre pizarra ≥ 7:1.

## Tipografía

- Pila del sistema (`-apple-system`, Segoe UI, Roboto, Helvetica Neue, Arial) —
  superficie de operar/leer; sin cargas de fuentes remotas (demo totalmente
  sin conexión).
- Títulos: la misma familia a peso 700, tracking `-0.02em`, sin tipografía de
  exhibición, sin mayúsculas en encabezados, sin etiquetas tipo rótulo. La
  etiqueta de la mesa en la banda superior es una marca en ámbar, no un
  encabezado de sección.
- Monoespaciada (`ui-monospace`, SF Mono, Cascadia Code, JetBrains Mono,
  Consolas) reservada para citas de evidencia, desplazamientos de caracteres e
  identificadores técnicos dentro de «Detalles técnicos» — datos, no disfraz.
- Párrafos de cuerpo limitados a 74 caracteres; las cifras usan tabulares y
  coma decimal española (`0,7451`, `1,0`, `0,8539`).

## Diseño

- **Banda superior** (pizarra profunda, primer viewport): etiqueta de la mesa +
  chips `Revisión humana completa` y `Evaluación final · muestra curada`;
  título del proyecto; propósito en una frase en lenguaje llano; una línea de
  fuente (atribución a Himalayas + fecha de captura + nota sin conexión). Sin
  identificadores de snapshot, versiones ni rutas de artefactos.
- **Barra de muestra final**: regla de ancho completo con tinte de pizarra y el
  texto exacto `Muestra curada · métricas finales para 20 ofertas · no representa el mercado completo`.
- **Bloque de tesis**: cuatro párrafos con etiqueta — Qué resuelve / Qué datos
  usa / Qué encontró / Qué no puede afirmar.
- **Llamada al límite**: la frase exacta «Esto no es un estudio del mercado
  laboral ecuatoriano. Es una muestra de 20 ofertas de una sola página y una
  sola fuente.»
- **Franja de evidencia** (señal distintiva): una banda de papel con filetes y
  cinco celdas — Ofertas analizadas (20) · Habilidades de la taxonomía (37) ·
  Pares revisados (740) · Decisiones humanas resueltas (7) · Precisión / Recall
  / F1 finales apiladas, etiquetadas `· muestra curada`. Adaptable: 5 → 2
  columnas bajo 980 px, → 1 columna bajo 560 px, con los filetes re-trazados
  sin cruces.
- Pestañas (etiquetas exactas): Resumen · Panorama de habilidades · Explorar
  ofertas · Auditoría de evaluación · Proveniencia y límites. La pestaña activa
  es la banda de pizarra profunda con texto blanco roto (alto contraste); las
  inactivas están atenuadas sobre transparente. Pestañas nativas de Streamlit
  (operables con teclado).
- **Resumen**: filas de métricas explicadas (40/16/0/684/0 más las tres
  métricas finales, cada una con explicación en lenguaje humano) y una guía de
  lectura.
- **Explorar ofertas**: selectbox con etiquetas humanas (nunca identificadores
  de fuente) → lista de definición de metadatos → citas de la evidencia del
  buscador → veredictos finales (respaldado / no respaldado; las decisiones
  aprobadas llevan un chip `decisión humana aprobada`) → tabla expandible de
  las 37 habilidades.
- **Auditoría de evaluación**: matriz de contingencia final (40/16/0/684, 0
  inciertos), métricas finales de la muestra curada, 16 falsos positivos, las 7
  decisiones humanas aprobadas (criterio + fecha y fuente de aprobación, citas
  de evidencia re-verificadas) y las secciones de no generalización y
  no-mercado.
- **Barra lateral** (colapsada por defecto, colofón compacto): chip de estado
  (`Revisión humana completa`), fuente/atribución, conteos de la muestra, nota
  sin conexión. Sin estados de máquina, versiones ni rutas de artefactos.
- **Detalles técnicos**: un solo `st.expander` al final de la pestaña de
  proveniencia es el ÚNICO lugar donde aparecen los tokens de máquina (ver
  reglas de honestidad), incluidos el estado histórico v0.2.0, el registro de
  decisiones auditado y la comparación histórica primera-vs-segunda pasada.
- Gráficas: barras Altair en pizarra profunda (`#243B53`) con títulos de ejes
  en español; etiquetas del eje x rotadas; sin descripciones crudas en las
  gráficas.

## Componentes y estados

- Chips: píldora, mayúsculas a 0,74 rem: `evaluación final · muestra curada` /
  `decisión humana aprobada` / `candidato a falso positivo` (terracota),
  `respaldado` (pizarra), `no respaldado` (neutro), `Revisión humana completa`
  (neutro; variante translúcida sobre la banda).
- Palabras de veredicto en español (`respaldado`, `no respaldado`, `incierto`);
  los valores del enumerado cerrado viven solo en «Detalles técnicos».
  `incierto` ya no se usa en el estado final (la cola fue resuelta).
- Citas: bloque con la cita exacta en monoespaciada y línea de metadatos
  `Campo[inicio:fin] · cita verificada` con nombres de campo legibles (Título,
  Extracto, Categorías, Descripción), más una re-verificación defensiva al
  renderizar — una cita que ya no coincide con el artefacto pasa a un estado de
  cita rota (borde de señal + mensaje).
- Estados vacíos o faltantes: archivo de artefacto ausente → error amigable en
  español con comandos de recuperación; conjunto vacío → nota informativa;
  secciones descriptivas faltantes → nota informativa; campos opcionales
  faltantes de un registro → marcadores de posición en español (Rol sin
  título, Empresa no indicada, No indicado, No divulgado) mapeados al
  renderizar, mientras el cargador conserva sus propios valores de reserva en
  inglés.
- Foco de teclado: contorno visible `--ink-accent` en `:focus-visible` en toda
  la superficie.
- Las opciones del selectbox son etiquetas humanas; los identificadores de
  fuente nunca llegan al control.

## Reglas de honestidad incorporadas a la superficie

- La evaluación siempre se etiqueta como final-para-muestra-curada: la barra de
  muestra final, el sello de la franja, la pestaña de auditoría y las secciones
  de límites repiten que las métricas describen solo las 20 ofertas de la
  muestra curada y nunca se generalizan al mercado. El estado de máquina
  «demo-ready» nunca se renderiza; la superficie muestra `Revisión humana
  completa` / `Evaluación final · muestra curada`.
- La muestra siempre se etiqueta como incompleta: «muestra incompleta» en la
  franja, la tesis, la auditoría y la pestaña de proveniencia. La frase de
  límite exacta es prominente bajo la tesis.
- No se renderiza ninguna afirmación de mercado; el recall se explica como una
  propiedad de la muestra curada (40 respaldados). Ninguna afirmación se
  extiende más allá de la muestra curada ni presenta el resultado como una
  referencia general de mercado.
- Las siete decisiones humanas están resueltas (aprobación 2026-08-02,
  instrucción explícita de la persona responsable del proyecto); no existe
  copia actual de «7 decisiones pendientes». Los motivos históricos y las
  etiquetas antiguas (comparación primera-vs-segunda pasada, estado y cola
  v0.2.0) aparecen SOLO dentro del expansor «Detalles técnicos».
- Los tokens de máquina — `human_review_complete`, `draft_second_pass`,
  `human_review_required`, `annotation_status`, `complete: false`,
  identificadores de snapshot/fuente, rutas de artefactos, identificadores de
  versión, claves de campos crudos y las siglas de la matriz de contingencia —
  aparecen SOLO dentro del expansor «Detalles técnicos», cada uno con una
  explicación humana. Fuera de ahí se usa lenguaje humano.
- Atribución: enlace visible a himalayas.app (banda superior y barra lateral) —
  exigido por los términos de la fuente.
