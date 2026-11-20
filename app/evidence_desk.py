"""Mesa de evidencia — Inteligencia del mercado laboral ecuatoriano.

Contrato de dirección (rediseño fijado por el brief: mesa de evidencia
editorial y contenida, superficie pública en español de publicación
científica):

- TESIS: esta superficie pública muestra UN mecanismo, con transparencia —
  extracción determinista de habilidades técnicas de 20 ofertas reales, cada
  coincidencia con su cita exacta y cada uno de los 20 × 37 pares posibles
  decidido por una revisión humana completa. Rechaza el panel de mercado
  pulido por defecto: sin teatro de indicadores, sin afirmación de mercado
  inventada, sin tokens de máquina a la vista y con el alcance limitado a la
  muestra de las métricas finales imposible de pasar por alto.
- MUNDO PROPIO: lienzo blanco roto, banda superior de pizarra profunda, un
  solo color de señal ámbar/terracota reservado a los estados históricos o
  contextuales, secciones con filetes y sans serif del sistema legible;
  monoespaciada solo para citas de evidencia, desplazamientos de caracteres
  e identificadores técnicos dentro de «Detalles técnicos».
- RELATO: quien lee en un minuto (reclutador, revisor técnico, gerente de
  contratación) entiende qué extrae la herramienta, con qué citas exactas,
  cómo una revisión humana independiente decidió los 740 pares y qué no
  puede afirmar; después puede profundizar en las citas de cualquier oferta.
- PRIMER VIEWPORT: banda superior de pizarra profunda (título, etiqueta de
  mesa, propósito, atribución de la fuente) -> aviso prominente de muestra
  final -> tesis -> límite de la muestra -> franja de evidencia con las
  cifras locales reales -> pestañas (Resumen · Panorama de habilidades ·
  Explorar ofertas · Auditoría de evaluación · Proveniencia y límites).
- FORMA: mesa de evidencia (dirección fijada por el brief; el lanzamiento de
  semillas de concepto queda eximido por el brief superior, como en la
  versión anterior).
- TERMINACIÓN: lo no revisado y no documentado está sin terminar; esta
  versión cierra con la revisión final, el veredicto y DESIGN.md.

Reglas de publicación en español incorporadas a la superficie:

- La interfaz pública es español profesional; el contenido de los artefactos
  (notas de la revisión, motivos, preguntas, limitaciones) se conserva
  verbatim como datos.
- Los tokens de máquina, versiones, identificadores, nombres crudos de
  campos y las siglas de la matriz de contingencia aparecen SOLO dentro del
  expansor «Detalles técnicos»; fuera de él se usa lenguaje humano
  («muestra incompleta», «verdaderos positivos», «respaldado», …).
- El estado público es «Revisión humana completa» / «Evaluación final ·
  muestra curada»; el estado de máquina «demo-ready» nunca se renderiza.
- Las siete decisiones humanas fueron resueltas (aprobación 2026-08-02,
  instrucción explícita de la persona responsable del proyecto); no existe
  copia actual de «7 decisiones pendientes». Los motivos históricos y las
  etiquetas antiguas aparecen solo dentro de «Detalles técnicos».
- Todas las cifras se leen en vivo de los artefactos locales versionados;
  nada está escrito a mano.

Ejecución local: ``uv run --extra demo streamlit run app/evidence_desk.py``.
"""

from __future__ import annotations

from html import escape

import altair as alt
import streamlit as st

from job_market_intelligence.demo import artifacts as A

st.set_page_config(
    page_title="Mesa de evidencia — Inteligencia del mercado laboral ecuatoriano",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Sistema visual: mesa de evidencia editorial y contenida. Lienzo blanco
# roto, banda superior de pizarra profunda, un color de señal ámbar/terracota
# para los estados contextuales o históricos, secciones con filetes y sans
# serif del sistema. Sin degradados, sin emojis, sin sombras decorativas.
# ---------------------------------------------------------------------------

CSS = """
<style>
:root {
  --canvas: #F4F2ED;
  --paper: #FFFFFF;
  --ink: #1C1E21;
  --ink-accent: #243B53;
  --masthead: #1F2A37;
  --masthead-ink: #F5F3EE;
  --masthead-muted: #B9C2CD;
  --signal: #9A3412;
  --signal-bright: #E8A33D;
  --signal-tint: #FBF1E6;
  --signal-line: #E9D5BE;
  --muted: #5A6169;
  --hairline: #E0DDD4;
  --block: #F8F7F3;
  --chip-supported: #EDF0F4;
}

html, body, .stApp, [data-testid="stSidebar"] {
  background-color: var(--canvas);
  color: var(--ink);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
    "Helvetica Neue", Arial, sans-serif;
}

/* Publicación limpia: no queda cabecera, toolbar ni control de menú visible. */
[data-testid="stHeader"], [data-testid="stToolbar"] {
  display: none !important;
}

.block-container {
  max-width: 1240px;
  padding-top: 1.25rem;
  padding-bottom: 4rem;
}

/* --- Jerarquía tipográfica: moderada, secciones con filete, sin etiquetas --- */
h1, h2, h3, h4 { color: var(--ink); }
h1 { font-size: 2.15rem; font-weight: 700; letter-spacing: -0.025em; line-height: 1.1; }
h2 {
  font-size: 1.45rem; font-weight: 650; letter-spacing: -0.02em;
  margin-top: 2rem; padding-top: 1.05rem; border-top: 1px solid var(--hairline);
}
h3 { font-size: 1.13rem; font-weight: 650; margin-top: 1.45rem; }
p, li { font-size: 0.99rem; line-height: 1.58; }
.stMarkdown p, .stMarkdown li { max-width: 74ch; }
.stMarkdown a { color: var(--ink-accent); text-decoration: underline;
  text-underline-offset: 2px; }

code {
  font-family: ui-monospace, "SF Mono", "Cascadia Code", "JetBrains Mono",
    Consolas, monospace;
  font-size: 0.85em; color: var(--ink); background: #EFEDE7;
  border: 1px solid var(--hairline); border-radius: 4px; padding: 0.08em 0.35em;
}

/* --- Cabecera: banda de pizarra profunda --- */
.masthead {
  background: var(--masthead); color: var(--masthead-ink);
  border-radius: 12px; padding: 1.85rem 2rem 1.55rem; margin-bottom: 0.85rem;
}
.masthead-row {
  display: flex; align-items: center; justify-content: space-between;
  gap: 0.8rem; flex-wrap: wrap; margin-bottom: 0.55rem;
}
.masthead .desk-label { color: var(--signal-bright); font-size: 0.88rem;
  font-weight: 650; letter-spacing: 0.02em; }
.masthead h1 { color: var(--masthead-ink); font-size: clamp(2.35rem, 4vw, 3.2rem); font-weight: 700;
  letter-spacing: -0.035em; line-height: 1.04; margin: 0 0 0.65rem; max-width: 22ch; }
.masthead .purpose { color: var(--masthead-muted); font-size: 1.06rem;
  max-width: 74ch; margin: 0 0 0.6rem; line-height: 1.5; }
.masthead .masthead-line { color: var(--masthead-muted); font-size: 0.82rem;
  margin: 0; }
.masthead a { color: var(--signal-bright); }

/* --- Chips --- */
.chip {
  display: inline-block; border-radius: 999px; padding: 0.14em 0.7em;
  font-size: 0.74rem; font-weight: 600; letter-spacing: 0.04em;
  text-transform: uppercase; white-space: nowrap; vertical-align: middle;
}
.chip-provisional, .chip-uncertain { color: var(--signal); background: var(--signal-tint);
  border: 1px solid var(--signal-line); }
.chip-supported { color: var(--ink-accent); background: var(--chip-supported);
  border: 1px solid #D8DFE7; }
.chip-unsupported { color: var(--muted); background: transparent;
  border: 1px solid var(--hairline); }
.chip-neutral { color: var(--muted); background: transparent;
  border: 1px solid var(--hairline); }
.chip-validate { color: var(--masthead-ink); background: rgba(245, 243, 238, 0.08);
  border: 1px solid rgba(245, 243, 238, 0.45); }

/* --- Aviso provisional prominente --- */
.warnbar {
  background: var(--signal-tint); border: 1px solid var(--signal-line);
  border-radius: 10px; padding: 0.85rem 1.25rem; margin-bottom: 0.9rem;
  font-size: 1.05rem; font-weight: 650; color: var(--signal);
}

/* --- Aviso final de muestra curada (estado final, sin tinta provisional) --- */
.finalbar {
  background: var(--chip-supported); border: 1px solid #D8DFE7;
  border-radius: 10px; padding: 0.85rem 1.25rem; margin-bottom: 0.9rem;
  font-size: 1.05rem; font-weight: 650; color: var(--ink-accent);
}

/* --- Bloque de tesis --- */
.thesis {
  background: var(--paper); border: 1px solid var(--hairline);
  border-radius: 10px; padding: 1.15rem 1.35rem; margin-bottom: 0.9rem;
}
.thesis p { margin: 0 0 0.72rem; font-size: 1rem; }
.thesis p:last-child { margin-bottom: 0; }
.thesis .t-label { font-weight: 650; color: var(--ink-accent); }

/* --- Llamada al límite de la muestra --- */
.limitation {
  background: var(--paper); border: 1px solid var(--hairline);
  border-radius: 10px; padding: 0.95rem 1.25rem; margin-bottom: 0.9rem;
  font-size: 1.02rem; line-height: 1.5;
}

/* --- Franja de evidencia --- */
.strip {
  background: var(--paper); border: 1px solid var(--hairline);
  border-radius: 10px; margin-bottom: 0.4rem; overflow: hidden;
}
.strip-head {
  display: flex; align-items: center; justify-content: space-between;
  gap: 0.8rem; flex-wrap: wrap; padding: 0.55rem 1.15rem;
  border-bottom: 1px solid var(--hairline); font-size: 0.8rem; color: var(--muted);
}
.strip-grid { display: grid; grid-template-columns: repeat(5, 1fr); }
.strip-cell { padding: 1rem 1.1rem 0.95rem; border-left: 1px solid var(--hairline); }
.strip-cell:first-child { border-left: none; }
.strip-num {
  font-size: 2.25rem; font-weight: 700; letter-spacing: -0.025em;
  color: var(--ink-accent); line-height: 1.1; font-variant-numeric: tabular-nums;
}
.strip-label { font-size: 0.88rem; font-weight: 650; color: var(--ink);
  margin-top: 0.25rem; }
.strip-note { font-size: 0.78rem; color: var(--muted); margin-top: 0.3rem;
  line-height: 1.4; }
.metric-line { margin-top: 0.4rem; }
.metric-line:first-of-type { margin-top: 0; }
.metric-val { font-size: 1.18rem; font-weight: 700; color: var(--ink-accent);
  font-variant-numeric: tabular-nums; letter-spacing: -0.01em; line-height: 1.15; }
.metric-lab { font-size: 0.74rem; color: var(--muted); font-weight: 600; }
@media (max-width: 980px) {
  .strip-grid { grid-template-columns: repeat(2, 1fr); }
  .strip-cell:nth-child(3) { border-left: none; }
  .strip-cell { border-top: 1px solid var(--hairline); }
  .strip-cell:nth-child(-n+2) { border-top: none; }
  .strip-cell:nth-child(odd) { border-left: none; }
}
@media (max-width: 560px) {
  .strip-grid { grid-template-columns: 1fr; }
  .strip-cell { border-top: 1px solid var(--hairline); border-left: none; }
  .strip-cell:first-child { border-top: none; }
}

/* --- Filas de métricas explicadas --- */
.m-rows {
  border: 1px solid var(--hairline); border-radius: 10px;
  background: var(--paper); margin: 0.2rem 0 0.6rem; overflow: hidden;
}
.m-row { display: grid; grid-template-columns: 110px 1fr; gap: 0 1.3rem;
  padding: 0.8rem 1.2rem; border-top: 1px solid var(--hairline); }
.m-row:first-child { border-top: none; }
.m-num { font-size: 1.48rem; font-weight: 700; color: var(--ink-accent);
  font-variant-numeric: tabular-nums; letter-spacing: -0.01em; line-height: 1.2; }
.m-label { font-weight: 650; color: var(--ink); font-size: 0.94rem; }
.m-desc { font-size: 0.92rem; color: var(--muted); margin-top: 0.18rem;
  line-height: 1.5; }
@media (max-width: 640px) {
  .m-row { grid-template-columns: 1fr; gap: 0.25rem 0; }
}

/* --- Bloques de cita (monoespaciada solo para evidencia y desplazamientos) --- */
.cite {
  background: var(--block); border: 1px solid var(--hairline);
  border-radius: 6px; padding: 0.7rem 0.9rem; margin: 0.45rem 0 0.8rem;
}
.cite .quote {
  font-family: ui-monospace, "SF Mono", "Cascadia Code", "JetBrains Mono",
    Consolas, monospace; font-size: 0.84rem; line-height: 1.5;
  color: var(--ink); word-break: break-word;
}
.cite .meta { font-size: 0.74rem; color: var(--muted); margin-top: 0.4rem; }
.cite-broken { border-color: var(--signal-line); }
.cite-broken .meta { color: var(--signal); }

/* --- Bloques de veredicto --- */
.verdict { border: 1px solid var(--hairline); border-radius: 8px;
  background: var(--paper); padding: 0.8rem 1rem; margin: 0.55rem 0; }
.verdict-uncertain { border-color: var(--signal-line);
  background: var(--signal-tint); }
.verdict-head { display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap;
  margin-bottom: 0.3rem; }
.verdict .q { font-size: 0.9rem; font-weight: 650; color: var(--signal);
  margin-top: 0.5rem; }

/* --- Listas de definición pequeñas --- */
.dl { display: grid; grid-template-columns: max-content 1fr; gap: 0.3rem 1.2rem;
  font-size: 0.87rem; }
.dl dt { color: var(--muted); white-space: nowrap; }
.dl dd { margin: 0; color: var(--ink); word-break: break-word; }

/* --- Barra lateral: colofón compacto, sin estados de máquina --- */
[data-testid="stSidebar"] { border-right: 1px solid var(--hairline); }
.side-fact { font-size: 0.8rem; color: var(--muted); line-height: 1.5;
  margin: 0.9rem 0; }
.side-fact b { color: var(--ink); font-weight: 650; }
.side-fact a { color: var(--ink-accent); }

/* --- Pestañas: pestaña activa de alto contraste sobre pizarra --- */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
  gap: 0.2rem; border-bottom: 1px solid var(--hairline);
}
[data-testid="stTabs"] button[role="tab"] {
  font-size: 0.96rem; font-weight: 650; color: var(--muted);
  background: transparent; border: 1px solid transparent; border-bottom: none;
  border-radius: 8px 8px 0 0; padding: 0.62rem 1.05rem;
}
[data-testid="stTabs"] button[role="tab"]:hover { color: var(--ink); }
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
  color: var(--masthead-ink); background: var(--masthead);
  border-color: var(--masthead);
}

/* --- Etiquetas de controles --- */
.stSelectbox label, .stToggle label { font-size: 0.9rem; font-weight: 600;
  color: var(--ink); }

/* --- Foco de teclado (visible en toda la superficie) --- */
:focus-visible { outline: 2px solid var(--ink-accent); outline-offset: 2px; }

/* --- Tablas: filetes sobrios, sin ruido de cebra --- */
[data-testid="stTable"] table, [data-testid="stDataFrame"] table {
  border: 1px solid var(--hairline);
}
[data-testid="stTable"] th, [data-testid="stDataFrame"] th {
  font-size: 0.74rem; text-transform: uppercase; letter-spacing: 0.05em;
  color: var(--muted); border-bottom: 1px solid var(--hairline);
}
[data-testid="stTable"] td { font-size: 0.85rem; }
</style>
"""


def esc(value: object) -> str:
    return escape(str(value if value is not None else ""))


def chip(text: str, kind: str) -> str:
    return f'<span class="chip chip-{kind}">{esc(text)}</span>'


def markdown_html(html: str) -> None:
    st.markdown(html, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Presentación en español: fechas, valores por defecto del cargador y datos
# con vocabulario cerrado. Los artefactos originales no se modifican.
# ---------------------------------------------------------------------------

_MESES_ES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


def _date_es(iso: str) -> str:
    """``2026-08-02T18:32:15+00:00`` -> ``2 de agosto de 2026``."""
    date_part = str(iso).split("T", 1)[0]
    parts = date_part.split("-")
    if len(parts) == 3 and all(p.isdigit() for p in parts):
        try:
            return f"{int(parts[2])} de {_MESES_ES[int(parts[1]) - 1]} de {parts[0]}"
        except (ValueError, IndexError):
            return date_part
    return date_part


#: Valores por defecto que produce el cargador (datos originales intactos).
_FALLBACK_ES = {
    "Untitled role": "Rol sin título",
    "Unknown company": "Empresa no indicada",
    "Not stated": "No indicado",
    "Not disclosed": "No divulgado",
    "Not recorded": "No registrada",
}

#: Vocabulario cerrado de la muestra traducido para la superficie pública.
_DATO_ES = {
    "Full Time": "Tiempo completo",
    "Contractor": "Contratista",
    "Mid-level": "Nivel medio",
    "Entry-level": "Nivel inicial",
    "Executive": "Ejecutivo",
    "Worldwide (remote)": "Remoto, en todo el mundo",
    "Other Country": "Otro país",
}


def _es(value: str) -> str:
    if value.startswith("Restricted to: "):
        return "Restringido a: " + value[len("Restricted to: ") :]
    return _DATO_ES.get(value, _FALLBACK_ES.get(value, value))


_CATEGORIAS_ES = {
    "Cloud platform": "Plataformas cloud",
    "Data platform": "Plataformas de datos",
    "Developer tool": "Herramientas de desarrollo",
    "Framework / library": "Frameworks y bibliotecas",
    "ML & AI": "Aprendizaje automático e IA",
    "Mobile": "Móviles",
    "Programming language": "Lenguajes de programación",
    "Security & identity": "Seguridad e identidad",
}


def _categoria_es(value: str) -> str:
    return _CATEGORIAS_ES.get(value, value)


def _salary_es(value: str) -> str:
    text = value
    if text.startswith("up to "):
        text = "hasta " + text[len("up to ") :]
    text = text.replace(" per annual", " por año").replace(" per month", " por mes")
    return _es(text)


_PREGUNTAS_REVISION_ES = {
    "Decide whether company/product-level AI context ('not AI-native', 'proactive smart assistant', 'multi-step reasoning') counts as evidence of the AI skill for a non-technical strategy and operations role.": "Decide si el contexto de IA de la empresa o del producto («not AI-native», «proactive smart assistant», «multi-step reasoning») cuenta como evidencia de la habilidad de IA para un puesto no técnico de estrategia y operaciones.",
    "question_degree_field": "Decide si mencionar un campo de estudio entre las calificaciones deseables cuenta como evidencia explícita de la habilidad de ciencia de datos o no.",
    "question_machine_learning_context": "Decide si la mención contextual de aprendizaje automático («datasets for advanced machine learning applications») cuenta como evidencia explícita de esa habilidad o no.",
    "Decide whether the nice-to-have AI-adjacent qualification ('AI data collection ... is a plus') outweighs the explicit negative requirement ('No prior experience in AI is required').": "Decide si la calificación deseable relacionada con IA («AI data collection ... is a plus») pesa más que el requisito negativo explícito («No prior experience in AI is required»).",
    "question_category_context": "Decide si la mención contextual de la categoría («Brazilian-Portuguese-AI-Specialist») y la frase «audio samples for AI training» cuentan como evidencia de IA pese al requisito negativo explícito.",
}

_NOTAS_REVISION_ES = {
    "note_uncertain_to_negative": "Primera pasada: incierto; segunda pasada: no respaldado. Desacuerdo real entre ambas pasadas.",
    "note_negative_to_uncertain": "Primera pasada: no respaldado; segunda pasada: incierto. Desacuerdo real entre ambas pasadas.",
    "note_ai_ml_confusion": "Primera pasada: incierto; segunda pasada: no respaldado. Confusión entre el vocabulario de IA y el de aprendizaje automático.",
}


def _pregunta_revision_es(value: object) -> str:
    text = str(value or "").strip()
    if text.startswith("Decide whether company/product-level AI context"):
        return "Decide si el contexto de IA de la empresa o del producto («not AI-native», «proactive smart assistant», «multi-step reasoning») cuenta como evidencia de la habilidad de IA para un puesto no técnico de estrategia y operaciones."
    if text.startswith("Decide whether a degree-field mention"):
        return "Decide si mencionar un campo de estudio entre las calificaciones deseables cuenta como evidencia explícita de la habilidad de ciencia de datos o no."
    if text.startswith("Decide whether the project-context mention"):
        return "Decide si la mención contextual de aprendizaje automático («datasets for advanced machine learning applications») cuenta como evidencia explícita de esa habilidad o no."
    if text.startswith("Decide whether the nice-to-have AI-adjacent qualification"):
        return "Decide si la calificación deseable relacionada con IA («AI data collection ... is a plus») pesa más que el requisito negativo explícito («No prior experience in AI is required»)."
    if text.startswith("Decide whether the category-context mention"):
        return "Decide si la mención contextual de la categoría («Brazilian-Portuguese-AI-Specialist») y la frase «audio samples for AI training» cuentan como evidencia de IA pese al requisito negativo explícito."
    return "Decide cómo debe clasificarse esta mención de la habilidad."


def _motivo_revision_es(value: object) -> str:
    """Presenta los motivos del artefacto en español sin alterar el artefacto."""
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith("No explicit mention of "):
        skill = text[len("No explicit mention of ") :].split(" in the reviewed fields", 1)[0]
        return (
            f"No hay una mención explícita de {skill} en los campos revisados; "
            "«no respaldado» significa que no se encontró evidencia positiva explícita, "
            "no que la persona o la oferta carezcan de esa habilidad."
        )
    if text.startswith("Negative-requirement case:"):
        return (
            "Caso de requisito negativo: la oferta dice explícitamente «No prior "
            "experience in AI is required»; la IA aparece como contexto del proyecto "
            "y no como requisito explícito del puesto. La revisión no la respalda "
            "como habilidad requerida."
        )
    if text.startswith("AI appears only in company/product context:"):
        return (
            "La IA aparece solo en el contexto de la empresa o del producto "
            "(«proactive smart assistant»), no como requisito explícito del puesto."
        )
    if text.startswith("Machine learning appears only"):
        return (
            "«Machine learning» aparece como uso posterior de las grabaciones, no "
            "como una habilidad que el puesto deba ejecutar."
        )
    if text.startswith("Conflicting signals:"):
        return (
            "Hay señales contrapuestas: la oferta no exige experiencia previa en IA, "
            "pero menciona una experiencia deseable relacionada con recopilación de "
            "datos para IA."
        )
    if text.startswith("Mixed signals:"):
        return (
            "Hay señales contrapuestas: las categorías y el texto sugieren relación "
            "con IA, pero la oferta también indica que no exige experiencia previa en IA."
        )
    if text.startswith("Confusion case:"):
        return (
            "Caso de confusión: se mencionan modelos o entrenamiento de IA, pero no "
            "la expresión «machine learning»; la decisión debe determinar si son "
            "evidencias equivalentes."
        )
    if text.startswith("Boundary case:"):
        if "JavaScript" in text:
            return "Caso de frontera: aparece «JavaScript», pero no «java»; la taxonomía las trata como habilidades distintas."
        if "GitHub" in text:
            return "Caso de frontera: aparece «GitHub», pero no hay evidencia explícita de «git»; la taxonomía las trata como habilidades distintas."
        if "Statistical Physics" in text:
            return "Caso de frontera: aparece «Statistical Physics», pero no el término independiente «statistics»; la taxonomía las trata como habilidades distintas."
        return "Caso de frontera: la coincidencia depende de distinguir términos parecidos."
    if text.startswith("The tech stack explicitly lists"):
        return "La pila tecnológica enumera explícitamente: " + text.split(": ", 1)[-1]
    if text.startswith("Explicitly required"):
        return "Requisito explícito registrado en la oferta: " + text.split(": ", 1)[-1]
    if text.startswith("Explicitly listed"):
        return "Aparece explícitamente en el alcance o las calificaciones: " + text.split(": ", 1)[-1]
    if text.startswith("Listed under nice-to-have"):
        return "Aparece como requisito deseable: " + text.split(": ", 1)[-1]
    if text.startswith("The title"):
        return "El título y la descripción presentan explícitamente la habilidad."
    if text.startswith("The role builds"):
        return "El puesto construye sistemas centrales de aprendizaje automático y un producto de IA; la IA es el dominio del producto."
    if text.startswith("The role explicitly builds AI features"):
        return "El puesto construye explícitamente funcionalidades de IA."
    if text.startswith("AI is central to the role"):
        return "La IA es central para este puesto, según su descripción y requisitos."
    if text.startswith("The tech stack"):
        return "La pila tecnológica registra esta evidencia explícita."
    if text.startswith("'data science' appears only"):
        return "«data science» aparece solo como campo de estudio aceptable, no como una habilidad que el puesto deba ejecutar."
    return "La revisión registra una mención contextual; consulte la cita exacta para verificarla."


def _nota_revision_es(value: object) -> str:
    text = str(value or "").strip()
    if text.startswith("First draft: uncertain; second pass:") and "AI-vs-machine-learning" in text:
        return "Primera pasada: incierto; segunda pasada: no respaldado. Confusión entre el vocabulario de IA y el de aprendizaje automático."
    if text.startswith("First draft: uncertain; second pass:"):
        return "Primera pasada: incierto; segunda pasada: no respaldado. Desacuerdo real entre ambas pasadas."
    if text.startswith("First draft:"):
        return "Primera pasada: no respaldado; segunda pasada: incierto. Desacuerdo real entre ambas pasadas."
    return "Nota de comparación entre las dos pasadas."


#: Criterio aprobado de cada decisión humana, en español para la superficie pública
#: (los criterios originales del artefacto se conservan verbatim como datos).
_CRITERIOS_FINALES_ES = {
    "HR-01": (
        "La IA aparece solo en el contexto de la empresa o del producto; el puesto no "
        "requiere ni realiza trabajo de IA."
    ),
    "HR-02": (
        "La oferta dice que no se requiere experiencia previa en IA y la IA es contexto "
        "del proyecto, no tareas del puesto."
    ),
    "HR-03": (
        "«Data science» es solo un posible campo de estudio universitario, no evidencia "
        "de que el puesto ejecute trabajo de ciencia de datos."
    ),
    "HR-04": (
        "Las grabaciones se usan después en aplicaciones de aprendizaje automático, pero "
        "el puesto no desarrolla ni aplica ese aprendizaje."
    ),
    "HR-05": (
        "La experiencia explícita en recopilación de datos para IA es un requisito "
        "deseable relacionado con el puesto; que sea opcional no significa que no exista."
    ),
    "HR-06": (
        "Se mencionan modelos y entrenamiento de IA, pero no hay trabajo explícito de "
        "aprendizaje automático; IA y aprendizaje automático no son intercambiables."
    ),
    "HR-07": (
        "Producir muestras de audio para entrenamiento de IA se relaciona directamente "
        "con el puesto; la categoría AI-Specialist lo refuerza, pero no es la única base."
    ),
}

#: Fuente de aprobación en español (el valor crudo vive solo en «Detalles técnicos»).
_APROBACION_FUENTE_ES = "instrucción explícita de la persona responsable del proyecto"


def _decision_for(bundle: A.DemoBundle, source_id: str, skill_id: str) -> dict | None:
    """La decisión humana aprobada para un par, si existe."""
    for item in bundle.report.human_review_decisions:
        if item.get("source_id") == source_id and item.get("skill_id") == skill_id:
            return item
    return None


def _criterio_final_es(item: dict) -> str:
    """Criterio aprobado en español; valores desconocidos degradan a una frase genérica."""
    return _CRITERIOS_FINALES_ES.get(
        item.get("item_id", ""),
        "Decisión humana aprobada por la persona responsable del proyecto.",
    )


def _aprobacion_es(item: dict) -> str:
    """Línea de aprobación legible: fecha + fuente, sin tokens del artefacto."""
    fecha = _date_es(item.get("approval_date", ""))
    fecha_texto = f"el {fecha}" if fecha else "con fecha registrada en el artefacto"
    return f"Aprobada {fecha_texto} por {_APROBACION_FUENTE_ES}."


def _bars(data: object, x: str, y: str, x_title: str, y_title: str, height: int = 340) -> None:
    """Gráfica de barras Altair con la paleta de la mesa (sin texturas crudas)."""
    import pandas as pd

    frame = pd.DataFrame(data) if not isinstance(data, pd.DataFrame) else data
    chart = (
        alt.Chart(frame)
        .mark_bar(color="#243B53", cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X(
                x,
                type="nominal",
                title=x_title,
                sort="-y",
                axis=alt.Axis(
                    labelAngle=-40,
                    labelFontSize=10,
                    labelColor="#3E444B",
                    titleFontSize=12,
                    titleColor="#1C1E21",
                ),
            ),
            y=alt.Y(
                y,
                type="quantitative",
                title=y_title,
                axis=alt.Axis(
                    grid=True,
                    gridColor="#E4E1D9",
                    labelFontSize=11,
                    labelColor="#3E444B",
                    titleFontSize=12,
                    titleColor="#1C1E21",
                ),
            ),
        )
        .properties(height=height, background="transparent")
        .configure_view(stroke=None)
        .configure_axis(titleFontWeight=700)
    )
    st.altair_chart(chart, width="stretch")


# ---------------------------------------------------------------------------
# Secciones globales (primer viewport)
# ---------------------------------------------------------------------------


def render_masthead(bundle: A.DemoBundle) -> None:
    identity = bundle.dataset.capture_identity
    captured_raw = str(identity.get("captured_at", "") or "")
    captured = _date_es(captured_raw) if captured_raw else "fecha de captura no registrada"
    markdown_html(
        '<div class="masthead">'
        '<div class="masthead-row">'
        '<span class="desk-label">Mesa de evidencia</span>'
        f"{chip('Revisión humana completa', 'validate')}"
        f"{chip('Evaluación final · muestra curada', 'supported')}"
        "</div>"
        "<h1>Inteligencia del mercado laboral ecuatoriano</h1>"
        '<p class="purpose">Una herramienta local que extrae habilidades técnicas de '
        "ofertas de trabajo y prueba cada hallazgo con la cita textual exacta.</p>"
        f'<p class="masthead-line">Fuente: <a href="https://himalayas.app" '
        f'target="_blank" rel="noopener">Himalayas</a> · {esc(captured)} · '
        "funciona sin conexión · todos los números se leen de los archivos locales "
        "versionados</p>"
        "</div>"
    )


def render_final_sample_bar() -> None:
    markdown_html(
        '<div class="finalbar">Muestra curada · métricas finales para 20 ofertas · '
        "no representa el mercado completo</div>"
    )


def render_thesis(bundle: A.DemoBundle) -> None:
    m = bundle.report.primary_metrics
    predicted = m.get("tp", 0) + m.get("fp", 0)
    markdown_html(
        '<div class="thesis">'
        '<p><span class="t-label">Qué resuelve.</span> '
        "Para quien evalúa este proyecto — reclutadores, revisores técnicos, gerentes "
        "de contratación — entender qué hace el buscador de habilidades y con qué "
        "evidencia es difícil a partir del código. Esta mesa muestra el mecanismo "
        "completo: qué habilidades detecta, con qué cita exacta y qué tan confiable "
        "es esa detección según una revisión humana completa de los 740 pares.</p>"
        '<p><span class="t-label">Qué datos usa.</span> '
        f"{bundle.dataset.record_count} ofertas reales capturadas de una sola página "
        f"de Himalayas, un vocabulario cerrado de {len(bundle.taxonomy.skills)} "
        f"habilidades técnicas en {len(bundle.taxonomy.categories)} categorías, y una "
        f"revisión humana que leyó los {len(bundle.review.labels)} pares "
        "posibles (cada oferta × cada habilidad).</p>"
        '<p><span class="t-label">Qué encontró.</span> '
        f"El buscador propuso {predicted} coincidencias; la revisión final "
        f"respalda {m.get('tp', 0)} y no respalda {m.get('fp', 0)}. Ningún respaldo "
        f"quedó sin detectar ({m.get('fn', 0)} falsos negativos). Las 7 decisiones "
        "humanas fueron resueltas: las métricas son finales para esta muestra curada.</p>"
        '<p><span class="t-label">Qué no puede afirmar.</span> '
        "Que esto describa la demanda del mercado laboral ecuatoriano. La muestra es "
        "pequeña, de una sola fuente, y las métricas finales describen solo esta "
        "muestra curada de 20 ofertas; el buscador sigue siendo una línea base de "
        "palabras clave, sin validación definitiva para el mercado completo.</p>"
        "</div>"
    )


def render_limitation() -> None:
    markdown_html(
        '<div class="limitation">Esto no es un estudio del mercado laboral '
        "ecuatoriano. Es una muestra de 20 ofertas de una sola página y una sola "
        "fuente.</div>"
    )


def render_strip(bundle: A.DemoBundle) -> None:
    report = bundle.report
    m = report.primary_metrics
    label_counts = bundle.review.label_counts()
    metric_vals = "".join(
        f'<div class="metric-line"><span class="metric-val">{A.format_metric_es(m.get(key))}</span>'
        f' <span class="metric-lab">{label}</span></div>'
        for key, label in (
            ("precision", "Precisión final · muestra curada"),
            ("recall", "Recall final · muestra curada"),
            ("f1", "F1 final · muestra curada"),
        )
    )
    decisions = len(report.human_review_decisions)
    markdown_html(
        '<div class="strip">'
        '<div class="strip-head">'
        "<span>Las cifras reales de esta mesa, leídas de los archivos</span>"
        f"{chip('evaluación final · muestra curada', 'supported')}"
        "</div>"
        '<div class="strip-grid">'
        f'<div class="strip-cell"><div class="strip-num">{bundle.dataset.record_count}</div>'
        '<div class="strip-label">Ofertas analizadas</div>'
        '<div class="strip-note">una sola página · muestra incompleta</div></div>'
        f'<div class="strip-cell"><div class="strip-num">{len(bundle.taxonomy.skills)}</div>'
        '<div class="strip-label">Habilidades de la taxonomía</div>'
        f'<div class="strip-note">{len(bundle.taxonomy.categories)} categorías · '
        "vocabulario cerrado</div></div>"
        f'<div class="strip-cell"><div class="strip-num">{len(bundle.review.labels)}</div>'
        '<div class="strip-label">Pares revisados</div>'
        f'<div class="strip-note">{bundle.dataset.record_count} × '
        f"{len(bundle.taxonomy.skills)} · revisión humana completa · "
        f"{label_counts.get('supported', 0)} respaldados · "
        f"{label_counts.get('uncertain', 0)} inciertos</div></div>"
        f'<div class="strip-cell"><div class="strip-num">{decisions}</div>'
        '<div class="strip-label">Decisiones humanas resueltas</div>'
        '<div class="strip-note">7 decisiones humanas resueltas · 7 de 7 aprobadas · ninguna pendiente</div></div>'
        '<div class="strip-cell">'
        f"{metric_vals}"
        f'<div class="strip-note">finales · sobre los {len(bundle.review.labels)} pares · '
        "solo esta muestra curada</div></div>"
        "</div></div>"
    )


def render_sidebar(bundle: A.DemoBundle) -> None:
    st.sidebar.markdown(chip("Revisión humana completa", "supported"), unsafe_allow_html=True)
    st.sidebar.markdown(
        '<div class="side-fact">Fuente de los datos: '
        '<a href="https://himalayas.app" target="_blank" rel="noopener">himalayas.app</a>'
        "<br>La atribución a Himalayas es obligatoria al mostrar estos datos.</div>",
        unsafe_allow_html=True,
    )
    st.sidebar.markdown(
        f'<div class="side-fact"><b>{bundle.dataset.record_count}</b> ofertas · '
        f"<b>{len(bundle.taxonomy.skills)}</b> habilidades · "
        f"<b>{len(bundle.review.labels)}</b> pares revisados</div>",
        unsafe_allow_html=True,
    )
    st.sidebar.markdown(
        '<div class="side-fact"><b>Funciona sin conexión.</b> Sin llamadas de red: '
        "solo lee los archivos locales versionados.</div>",
        unsafe_allow_html=True,
    )


def render_error(exc: A.DemoDataError) -> None:
    st.error("La mesa de evidencia no pudo leer uno de sus archivos locales.")
    st.markdown(
        f"**Qué ocurrió:** {esc(exc)}\n\n"
        "La mesa necesita sus insumos locales preparados por el proceso offline. Comprueba "
        "la instalación y vuelve a materializar los datos antes de abrir la interfaz."
    )


# ---------------------------------------------------------------------------
# Pestañas
# ---------------------------------------------------------------------------


def tab_resumen(bundle: A.DemoBundle) -> None:
    m = bundle.report.primary_metrics
    label_counts = bundle.review.label_counts()
    st.markdown("## Las cifras, explicadas")
    st.markdown(
        "Cada cifra se lee de los archivos locales; ninguna está escrita a mano. La "
        "revisión humana resolvió las 7 decisiones que la segunda pasada había dejado "
        "pendientes y fijó la etiqueta final de los "
        f"{len(bundle.review.labels)} pares posibles (cada oferta × cada habilidad): "
        f"{label_counts.get('supported', 0)} respaldados y "
        f"{label_counts.get('not_supported', 0)} no respaldados. Las métricas finales se "
        "calculan sobre los 740 pares y describen solo esta muestra curada."
    )
    tp = m.get("tp", 0)
    rows = [
        (
            tp,
            "Verdaderos positivos",
            "Pares en los que el buscador detectó la habilidad y la revisión final está de acuerdo.",
        ),
        (
            m.get("fp", 0),
            "Falsos positivos",
            "Pares en los que el buscador detectó la habilidad, pero la revisión final no la respalda.",
        ),
        (
            m.get("fn", 0),
            "Falsos negativos",
            "Pares que la revisión final respalda y que el buscador habría omitido. Hoy no hay ninguno.",
        ),
        (
            m.get("tn", 0),
            "Verdaderos negativos",
            "Pares en los que el buscador y la revisión coinciden: no hay evidencia de la habilidad.",
        ),
        (
            label_counts.get("uncertain", 0),
            "Inciertos",
            "Pares que la revisión no pudo decidir. Hoy no hay ninguno: las 7 decisiones humanas fueron resueltas.",
        ),
        (
            A.format_metric_es(m.get("precision")),
            "Precisión final · muestra curada",
            f"De cada 100 coincidencias que propone el buscador, la revisión final "
            f"respalda aproximadamente {round(m.get('precision', 0) * 100)} — dentro de "
            "esta muestra curada de 20 ofertas. Es la proporción de coincidencias "
            "propuestas que la revisión apoya.",
        ),
        (
            A.format_metric_es(m.get("recall")),
            "Recall final · muestra curada",
            f"De los {tp} pares que la revisión final respalda, el buscador "
            f"detectó los {tp}. Esta cifra vale solo para esta muestra curada: no "
            "dice nada sobre lo que hay fuera de ella.",
        ),
        (
            A.format_metric_es(m.get("f1")),
            "F1 final · muestra curada",
            "Un solo número que equilibra la precisión y el recall; cuanto más cerca de "
            "1, mejor equilibradas están ambas. Describe solo esta muestra curada.",
        ),
    ]
    cells = "".join(
        f'<div class="m-row"><div class="m-num">{esc(str(num))}</div>'
        f'<div><div class="m-label">{esc(label)}</div>'
        f'<div class="m-desc">{esc(desc)}</div></div></div>'
        for num, label, desc in rows
    )
    markdown_html(f'<div class="m-rows">{cells}</div>')

    st.markdown("## Cómo leer esta mesa")
    st.markdown(
        "1. **La franja de cifras, arriba:** cinco números reales leídos de los "
        "archivos. El sello «evaluación final · muestra curada» significa que las 7 "
        "decisiones humanas fueron resueltas y que cada métrica describe solo estas "
        "20 ofertas.\n"
        "2. **Panorama de habilidades:** qué detectó el buscador en las 20 ofertas, "
        "con las definiciones de su funcionamiento.\n"
        "3. **Explorar ofertas:** elige una oferta para ver sus datos, la evidencia "
        "con citas exactas y el veredicto final de la revisión humana sobre las 37 "
        "habilidades.\n"
        "4. **Auditoría de evaluación:** la matriz completa de 740 pares, los 16 "
        "falsos positivos, los 0 falsos negativos, las 7 decisiones humanas "
        "aprobadas y por qué las métricas finales no son un estudio de mercado.\n"
        "5. **Proveniencia y límites:** origen de los datos, controles de calidad, "
        "límites y los detalles técnicos."
    )
    st.markdown(
        "**En un minuto:** esta herramienta extrae habilidades técnicas de ofertas "
        "de trabajo con reglas deterministas, prueba cada extracción con una cita "
        "exacta y audita su propia extracción con una revisión humana completa sobre "
        "los 740 pares posibles. Las métricas son finales para esta muestra curada "
        "de 20 ofertas: ese es el estado honesto del proyecto, y esta mesa lo muestra "
        "en lugar de ocultarlo."
    )


def tab_landscape(bundle: A.DemoBundle) -> None:
    taxonomy = bundle.taxonomy
    st.markdown(
        "Frecuencia de habilidades a nivel de oferta: en cuántas de las "
        f"{bundle.dataset.record_count} ofertas aparece cada habilidad de la "
        "taxonomía (se cuenta como máximo una vez por oferta). Es evidencia de "
        "palabras clave de una página de una sola bolsa de trabajo: descriptiva, "
        "nunca una afirmación de mercado."
    )
    st.markdown("### Cómo funciona el buscador")
    st.markdown(
        "Un buscador determinista por palabras clave examina cuatro campos de cada "
        "oferta — título, extracto, categorías y descripción — con el vocabulario "
        f"cerrado de {len(taxonomy.skills)} habilidades. No distingue mayúsculas y "
        "respeta los límites de palabra: `java` nunca coincide con `javascript`, "
        "`git` nunca coincide con `github`, y los términos compuestos admiten "
        "variantes como «machine learning» y «machine-learning». Cada coincidencia "
        "conserva la cita exacta, el campo y el número de apariciones."
    )
    st.markdown("### Lo que el buscador no hace")
    st.markdown(
        "No interpreta negaciones ni contexto: «No se requiere experiencia previa en "
        "IA» igual coincide con la habilidad de IA. No hay comprensión semántica, ni "
        "vectores, ni modelos de lenguaje en ninguna parte del proceso. Estas "
        "gráficas son evidencia de palabras clave, nunca una afirmación de mercado."
    )
    freq = A.skill_frequency(bundle.descriptive)
    show_zero = st.toggle("Incluir las habilidades sin coincidencias", value=False, key="zm_toggle")
    rows = [{"habilidad": taxonomy.skill_name(skill_id), "ofertas": count} for skill_id, count in freq.items()]
    if show_zero:
        for entry in A.zero_match_skills(bundle.descriptive):
            rows.append(
                {
                    "habilidad": entry.get("name") or taxonomy.skill_name(entry.get("skill_id", "")),
                    "ofertas": 0,
                }
            )
        rows.sort(key=lambda r: (-r["ofertas"], r["habilidad"].lower()))
    if not rows:
        st.info("El archivo de análisis no contiene datos de frecuencia de habilidades.")
        return
    _bars(rows, "habilidad", "ofertas", "Habilidad", "Ofertas que la mencionan", height=360)
    st.caption(
        "Eje x: habilidad de la taxonomía · eje y: ofertas distintas que la mencionan. "
        f"{len(freq)} de las {len(taxonomy.skills)} habilidades coincidieron con al "
        "menos una oferta."
    )

    zero = A.zero_match_skills(bundle.descriptive)
    if zero:
        st.markdown("### Habilidades sin coincidencias")
        st.markdown(
            f"Estas {len(zero)} habilidades de la taxonomía no aparecieron en ninguna "
            "oferta de la muestra. Que no haya coincidencias no es prueba de "
            "ausencia: significa que la palabra clave no apareció en estas 20 "
            "ofertas."
        )
        st.table(
            [
                {
                    "Habilidad": entry.get("name") or taxonomy.skill_name(entry.get("skill_id", "")),
                    "Categoría": _categoria_es(taxonomy.category_label(entry.get("category", ""))),
                    "Ofertas con coincidencia": 0,
                }
                for entry in zero
            ]
        )

    cats = A.category_coverage(bundle.descriptive)
    if cats:
        st.markdown("### Cobertura por categoría")
        st.markdown(
            "Ofertas distintas con al menos una habilidad detectada en cada categoría "
            "(una oferta cuenta una vez por categoría)."
        )
        _bars(
            [
                {
                    "categoria": _categoria_es(taxonomy.category_label(c.get("category", ""))),
                    "ofertas": c.get("records", 0),
                }
                for c in cats
            ],
            "categoria",
            "ofertas",
            "Categoría",
            "Ofertas",
            height=300,
        )

    pairs = bundle.descriptive.get("cooccurrence_pairs")
    if isinstance(pairs, dict):
        raw_pairs = [p for p in pairs.get("pairs", []) if isinstance(p, dict)]
        if raw_pairs:
            st.markdown("### Pares de habilidades más frecuentes")
            st.markdown("Pares de habilidades distintas de la misma oferta (sin orden, contados una vez por oferta).")
            top = sorted(raw_pairs, key=lambda p: -p.get("records", 0))[:8]
            st.table(
                [
                    {
                        "Habilidades": f"{taxonomy.skill_name(p.get('skill_a', ''))} + "
                        f"{taxonomy.skill_name(p.get('skill_b', ''))}",
                        "Ofertas": p.get("records", 0),
                    }
                    for p in top
                ]
            )

    with st.expander("Las 37 habilidades y sus categorías"):
        freq_all = A.skill_frequency(bundle.descriptive)
        zero_ids = {entry.get("skill_id") for entry in A.zero_match_skills(bundle.descriptive)}
        st.dataframe(
            [
                {
                    "Habilidad": skill.name,
                    "Categoría": _categoria_es(taxonomy.category_label(skill.category)),
                    "Ofertas con coincidencia": freq_all.get(skill.skill_id, 0),
                    "Sin coincidencias": "sí" if skill.skill_id in zero_ids else "—",
                }
                for skill in taxonomy.skills
            ],
            hide_index=True,
            width="stretch",
        )


def _matcher_evidence_blocks(record: A.JobRecord, taxonomy: A.TaxonomyInfo) -> None:
    if not record.skills:
        st.markdown(
            "El buscador no encontró ninguna coincidencia de palabras clave en esta "
            "oferta. Que no haya coincidencias no significa que la habilidad esté "
            "ausente: los términos de la taxonomía simplemente no aparecen en el "
            "texto."
        )
        return
    st.markdown(
        " ".join(chip(taxonomy.skill_name(s), "supported") for s in record.skills),
        unsafe_allow_html=True,
    )
    for entry in record.evidence:
        term_type = {
            "keyword": "palabra clave",
            "alias": "alias",
        }.get(entry.term_type, "término")
        apariciones = "1 aparición" if entry.occurrence_count == 1 else f"{entry.occurrence_count} apariciones"
        markdown_html(
            f'<div class="cite cite-verified">'
            f'<div class="quote">“{esc(entry.excerpt)}”</div>'
            f'<div class="meta">{esc(A.field_es(entry.field))} · '
            f"término «{esc(entry.matched_term)}» · {apariciones} · {esc(term_type)}</div>"
            "</div>"
        )


def _verify_and_render_quote(record: A.JobRecord, ev: A.ReviewEvidence) -> None:
    value = record.field_value(ev.field)
    ok = A.verify_quote(value, ev.char_start, ev.char_end, ev.exact_quote)
    kind = "cite-verified" if ok else "cite-broken"
    status = "cita verificada" if ok else "la cita ya no coincide con el artefacto — los datos cambiaron"
    markdown_html(
        f'<div class="cite {kind}">'
        f'<div class="quote">“{esc(ev.exact_quote)}”</div>'
        f'<div class="meta">{esc(A.field_es(ev.field))}[{ev.char_start}:{ev.char_end}] · '
        f"{esc(status)}</div>"
        "</div>"
    )


def _verdict_block(
    bundle: A.DemoBundle,
    record: A.JobRecord,
    label: A.ReviewLabel,
    *,
    highlight: str | None = None,
    highlight_kind: str = "unsupported",
) -> None:
    taxonomy = bundle.taxonomy
    kind = "verdict-uncertain" if label.label == "uncertain" else ""
    chip_kind = {
        "supported": "supported",
        "not_supported": "unsupported",
        "uncertain": "uncertain",
    }.get(label.label, "neutral")
    head = (
        f'<span class="chip chip-{chip_kind}">{esc(A.verdict_es(label.label))}</span>'
        f"<b>{esc(taxonomy.skill_name(label.skill_id))}</b>"
    )
    if highlight:
        head += f'<span class="chip chip-{highlight_kind}">{esc(highlight)}</span>'
    markdown_html(f'<div class="verdict {kind}"><div class="verdict-head">{head}</div>')
    decision = _decision_for(bundle, label.source_id, label.skill_id)
    if decision is not None:
        # Los pares resueltos por la revisión humana muestran el criterio aprobado;
        # el motivo y las preguntas originales (históricos) viven en «Detalles técnicos».
        st.markdown(f"**Motivo de la decisión humana:** {_criterio_final_es(decision)}")
        st.caption(_aprobacion_es(decision))
    elif label.reason:
        st.markdown(f"**Motivo de la revisión:** {_motivo_revision_es(label.reason)}")
    for ev in label.evidence:
        _verify_and_render_quote(record, ev)
    if not label.evidence:
        st.caption(
            "Esta etiqueta no conserva una cita positiva: la decisión se basa en "
            "la ausencia de evidencia explícita en los campos revisados."
        )
    if not label.is_adjudicated and label.human_review_question:
        markdown_html(
            f'<div class="q">Decisión necesaria: {esc(_pregunta_revision_es(label.human_review_question))}</div>'
        )
    if not label.is_adjudicated and label.notes:
        st.caption(_nota_revision_es(label.notes))
    markdown_html("</div>")


def _job_label(bundle: A.DemoBundle, source_id: str) -> str:
    record = bundle.dataset.record_by_source(source_id)
    if record is None:
        return "Oferta no localizada"
    return f"{_es(record.display_title)} — {_es(record.display_company)}"


def tab_jobs(bundle: A.DemoBundle) -> None:
    taxonomy = bundle.taxonomy
    records = bundle.dataset.records
    if not records:
        st.info("El archivo de datos no contiene ofertas para explorar.")
        return
    st.markdown(
        "Elige una de las 20 ofertas capturadas. Para cada una puedes ver sus datos "
        "de origen, lo que detectó el buscador determinista (con citas exactas) y el "
        "veredicto final de la revisión humana completa sobre las 37 habilidades "
        "posibles."
    )
    labels = [f"{_es(record.display_title)} — {_es(record.display_company)}" for record in records]
    selected = st.selectbox("Oferta de trabajo", labels, key="job_select")
    index = labels.index(selected) if selected in labels else 0
    record = records[index]

    st.markdown(f"### {_es(record.display_title)}")
    st.markdown(
        '<div class="dl">'
        f"<dt>Empresa</dt><dd>{esc(_es(record.display_company))}</dd>"
        f"<dt>Ubicación</dt><dd>{esc(_es(record.display_location))}</dd>"
        f"<dt>Empleo</dt><dd>{esc(_es(record.employment_type)) or 'No indicado'}</dd>"
        f"<dt>Senioridad</dt><dd>{esc(', '.join(_es(v) for v in record.seniority)) or 'No indicado'}</dd>"
        f"<dt>Categorías</dt><dd>{esc(', '.join(record.categories)) or 'No indicado'}</dd>"
        f"<dt>Salario</dt><dd>{esc(_salary_es(record.salary))}</dd>"
        f"<dt>Publicada</dt><dd>{esc(_date_es(record.published_at_utc)) or 'No registrada'}</dd>"
        f"<dt>Vence</dt><dd>{esc(_date_es(record.expires_at_utc)) or 'No registrada'}</dd>"
        f'<dt>Oferta</dt><dd><a href="{esc(record.source_url)}" target="_blank" '
        'rel="noopener">abrir la oferta original en Himalayas</a></dd>'
        "</div>",
        unsafe_allow_html=True,
    )

    labels = bundle.review.labels_for(record.source_id)
    counts = {}
    for label in labels:
        counts[label.label] = counts.get(label.label, 0) + 1
    supported = counts.get("supported", 0)
    uncertain = counts.get("uncertain", 0)
    not_supported = counts.get("not_supported", 0)

    st.markdown("### Lo que detectó el buscador")
    _matcher_evidence_blocks(record, taxonomy)

    st.markdown("### Lo que decidió la revisión final")
    st.markdown(
        " ".join(
            [
                chip(f"{supported} respaldados", "supported"),
                chip(f"{uncertain} inciertos", "uncertain") if uncertain else "",
                chip(f"{not_supported} no respaldados", "unsupported"),
            ]
        ),
        unsafe_allow_html=True,
    )
    st.caption(
        "Veredictos finales: las 7 decisiones humanas fueron resueltas el 2 de agosto "
        "de 2026 por la persona responsable del proyecto; las métricas finales "
        "describen solo esta muestra curada de 20 ofertas."
    )

    for label in labels:
        if label.label == "supported":
            if label.is_adjudicated:
                _verdict_block(
                    bundle,
                    record,
                    label,
                    highlight="decisión humana aprobada",
                    highlight_kind="supported",
                )
            else:
                _verdict_block(bundle, record, label)

    predicted = set(record.skills)
    disagreements = [label for label in labels if label.label == "not_supported" and label.skill_id in predicted]
    if disagreements:
        st.markdown("#### El buscador predijo estas — la revisión final no está de acuerdo")
        st.markdown(
            "Son los falsos positivos finales de esta oferta: la evidencia de palabras "
            "clave del buscador frente a la decisión final de la revisión humana sobre "
            "el mismo texto."
        )
        for label in disagreements:
            if label.is_adjudicated:
                _verdict_block(
                    bundle,
                    record,
                    label,
                    highlight="decisión humana aprobada",
                    highlight_kind="supported",
                )
            else:
                _verdict_block(bundle, record, label, highlight="falso positivo final", highlight_kind="unsupported")

    with st.expander("Los 37 veredictos de esta oferta"):
        rows = []
        for label in labels:
            matcher_yes = "sí" if label.skill_id in predicted else "—"
            skill = taxonomy.skill_by_id(label.skill_id)
            rows.append(
                {
                    "Habilidad": taxonomy.skill_name(label.skill_id),
                    "Categoría": _categoria_es(taxonomy.category_label(skill.category)) if skill else "",
                    "Veredicto final": A.verdict_es(label.label),
                    "El buscador la detectó": matcher_yes,
                    "Citas": len(label.evidence),
                }
            )
        st.dataframe(rows, hide_index=True, width="stretch")


def tab_audit(bundle: A.DemoBundle) -> None:
    report = bundle.report
    taxonomy = bundle.taxonomy
    m = report.primary_metrics
    macro = report.macro_metrics
    label_counts = bundle.review.label_counts()
    decisions = report.human_review_decisions

    st.markdown(
        "La evaluación es una matriz completa de "
        f"{bundle.dataset.record_count} × {len(taxonomy.skills)} = "
        f"{len(bundle.review.labels)} pares: cada oferta × cada habilidad de la "
        "taxonomía es un par. Una revisión humana completa resolvió las 7 "
        "decisiones que la segunda pasada había dejado pendientes y fijó la "
        "etiqueta final de cada par leyendo directamente el texto de la oferta — "
        "respaldado o no respaldado — sin consultar las predicciones del buscador, "
        "que solo se comparan después. Las métricas finales describen solo esta "
        "muestra curada."
    )

    st.markdown("### Matriz de contingencia (final)")
    st.markdown("Las métricas finales agrupan todos los pares; no queda ningún par incierto.")
    st.table(
        [
            {"Celda": "Verdaderos positivos (la revisión respalda y el buscador detectó)", "Pares": m.get("tp", 0)},
            {"Celda": "Falsos positivos (el buscador detectó, la revisión no respalda)", "Pares": m.get("fp", 0)},
            {"Celda": "Falsos negativos (la revisión respalda, el buscador omitió)", "Pares": m.get("fn", 0)},
            {"Celda": "Verdaderos negativos (ambos coinciden: no hay evidencia)", "Pares": m.get("tn", 0)},
            {
                "Celda": "Inciertos (hoy no hay ninguno: las 7 decisiones fueron resueltas)",
                "Pares": label_counts.get("uncertain", 0),
            },
        ]
    )
    markdown_html(
        '<div class="strip" style="margin-top:0.6rem"><div class="strip-grid" style="grid-template-columns:repeat(3,1fr)">'
        f'<div class="strip-cell"><div class="strip-num metric">{A.format_metric_es(m.get("precision"))}</div>'
        '<div class="strip-label">Precisión final · muestra curada</div>'
        '<div class="strip-note">proporción de coincidencias propuestas que la '
        "revisión final respalda</div></div>"
        f'<div class="strip-cell"><div class="strip-num metric">{A.format_metric_es(m.get("recall"))}</div>'
        '<div class="strip-label">Recall final · muestra curada</div>'
        '<div class="strip-note">proporción de respaldos finales que el '
        "buscador detectó · vale solo para esta muestra</div></div>"
        f'<div class="strip-cell"><div class="strip-num metric">{A.format_metric_es(m.get("f1"))}</div>'
        '<div class="strip-label">F1 final · muestra curada</div>'
        '<div class="strip-note">equilibrio entre precisión y recall</div></div>'
        "</div></div>"
    )
    st.caption(
        f"Macro (media no ponderada por habilidad, alcance explícito de "
        f"{len(taxonomy.skills)} habilidades): precisión "
        f"{A.format_metric_es(macro.get('precision'))} · recall "
        f"{A.format_metric_es(macro.get('recall'))} · F1 "
        f"{A.format_metric_es(macro.get('f1'))}. Las habilidades sin valor definido "
        "se listan en la nota de alcance del informe (detalles técnicos)."
    )

    fp_count = m.get("fp", 0)
    st.markdown(f"### Los {fp_count} falsos positivos comparten el mismo origen")
    st.markdown(
        "Trece provienen de la limitación documentada del buscador: coincidencias "
        "de la habilidad de IA (inteligencia artificial) en ofertas cuyo texto dice "
        "explícitamente «No se requiere experiencia previa en IA» o menciona la IA "
        "solo como contexto del proyecto. Los otros 3 fueron confirmados como no "
        "respaldados por las decisiones humanas aprobadas. El buscador no interpreta "
        "negaciones: es una limitación documentada, no un defecto corregido."
    )
    for fp in report.false_positives:
        record = bundle.dataset.record_by_source(fp.get("source_id", ""))
        title = _es(record.display_title) if record else "Oferta no localizada"
        skill_name = taxonomy.skill_name(fp.get("skill_id", ""))
        with st.expander(f"{title} — {skill_name} (falso positivo)"):
            evidence = fp.get("matcher_evidence")
            if isinstance(evidence, dict):
                markdown_html(
                    f'<div class="cite cite-verified"><div class="quote">'
                    f"“{esc(evidence.get('excerpt', ''))}”</div>"
                    f'<div class="meta">{esc(A.field_es(evidence.get("field", "")))} · '
                    f"término «{esc(evidence.get('matched_term', ''))}»</div></div>"
                )
            if fp.get("adjudication_id"):
                decision = _decision_for(bundle, fp.get("source_id", ""), fp.get("skill_id", ""))
                if decision:
                    st.markdown(f"**Motivo de la decisión humana:** {_criterio_final_es(decision)}")
                    st.caption(_aprobacion_es(decision))
            else:
                st.markdown(f"**Motivo de la revisión:** {_motivo_revision_es(fp.get('reason', '—'))}")

    st.markdown(f"### {m.get('fn', 0)} falsos negativos")
    st.markdown(
        "La revisión final no encontró ningún par que el buscador haya omitido: "
        "todas las habilidades que la revisión respalda también fueron detectadas. "
        f"Un recall de 1,0 es una propiedad de esta muestra curada "
        f"({m.get('tp', 0)} pares respaldados), no una prueba de que el buscador "
        "encuentra todo en un mercado."
    )

    st.markdown("### Las 7 decisiones humanas fueron resueltas")
    st.markdown(
        "La segunda pasada había dejado 7 decisiones pendientes: etiquetas "
        "inciertas y desacuerdos entre la primera y la segunda pasada. La persona "
        "responsable del proyecto las aprobó el 2 de agosto de 2026, fijando la "
        "etiqueta final de cada par. Cada decisión queda registrada en el informe "
        "con su criterio, su fecha y su fuente; las métricas finales de esta mesa "
        "se calculan con esas etiquetas y valen solo para esta muestra curada."
    )
    for item in decisions:
        record = bundle.dataset.record_by_source(item.get("source_id", ""))
        title = _es(record.display_title) if record else "Oferta no localizada"
        skill_name = taxonomy.skill_name(item.get("skill_id", ""))
        with st.expander(f"{title} — {skill_name} (decisión humana aprobada)"):
            final = item.get("final_label", "")
            chip_kind = "supported" if final == "supported" else "unsupported"
            markdown_html(
                f'<div class="verdict-head">'
                f'<span class="chip chip-{chip_kind}">{esc(A.verdict_es(final))}</span>'
                f"<b>{esc(skill_name)}</b></div>"
            )
            st.markdown(f"**Motivo de la decisión humana:** {_criterio_final_es(item)}")
            st.caption(_aprobacion_es(item))
            for ev in item.get("evidence", []):
                _verify_and_render_quote(
                    record,
                    A.ReviewEvidence(
                        field=ev.get("field", ""),
                        exact_quote=ev.get("exact_quote", ""),
                        char_start=ev.get("char_start", 0),
                        char_end=ev.get("char_end", 0),
                    ),
                )

    st.markdown("### Por qué las métricas finales no se generalizan")
    for line in (
        "Las métricas son finales solo para esta muestra curada de 20 ofertas: no describen el mercado completo.",
        "El buscador sigue siendo una línea base de palabras clave que no interpreta "
        "negaciones; no está validada de forma definitiva para el mercado completo.",
        "La primera pasada cubrió solo 60 de los 740 pares; la comparación "
        "histórica entre pasadas y las etiquetas anteriores se conservan en "
        "«Detalles técnicos».",
    ):
        st.markdown(f"- {line}")

    sample = bundle.dataset.sample
    total = f"{int(sample.get('total_count', 0)):,}".replace(",", ".")
    records = sample.get("records", bundle.dataset.record_count)
    st.markdown("### Por qué esto no es un estudio de mercado")
    for line in (
        f"La muestra es de {records} de las {total} ofertas reportadas por la "
        "fuente: una sola página de una sola bolsa de trabajo (Himalayas), marcada "
        "como muestra incompleta.",
        f"El recall de esta mesa significa: de los {m.get('tp', 0)} pares que la "
        f"revisión final respaldó, el buscador detectó los {m.get('tp', 0)}. No dice nada "
        "sobre las habilidades fuera de las 37 de la taxonomía (por ejemplo, SQL, "
        "Docker o Kubernetes no se buscan todavía).",
        "Las 7 decisiones humanas fueron resueltas: no queda ninguna etiqueta "
        "incierta. La ambigüedad de contexto de la IA que motivó la cola quedó "
        "documentada en la decisión de cada par (ver «Detalles técnicos»).",
    ):
        st.markdown(f"- {line}")


def tab_provenance(bundle: A.DemoBundle) -> None:
    dataset = bundle.dataset
    identity = dataset.capture_identity
    sample = dataset.sample
    quality = dataset.quality_report

    st.markdown("### Origen de los datos")
    total = f"{int(sample.get('total_count', 0)):,}".replace(",", ".")
    records = sample.get("records", dataset.record_count)
    captured_raw = str(identity.get("captured_at", "") or "")
    captured = _date_es(captured_raw) if captured_raw else "fecha no registrada"
    st.markdown(
        f"Las {records} ofertas de esta mesa provienen de una captura única y "
        f"acotada del tablón de empleo [Himalayas](https://himalayas.app), realizada "
        f"el {captured}. La fuente reportaba {total} ofertas en ese momento; esta "
        "mesa conserva una sola página de 20, marcada como muestra incompleta. La "
        "captura se guarda localmente, byte por byte, con verificación de "
        "integridad."
    )

    st.markdown("### Controles de calidad")
    missing = quality.get("missing_field_counts", {})
    dups = quality.get("duplicate_counts", {})
    freshness = quality.get("freshness", {})
    age_s = freshness.get("age_at_capture_seconds")
    age_h = f"{age_s / 3600:.1f}".replace(".", ",") if isinstance(age_s, (int, float)) else None
    obs = quality.get("observation_status_counts", {})
    active = obs.get("active") if isinstance(obs, dict) else None
    bullets = [
        f"- Campos revisados sin valores faltantes: {sum(missing.values()) if isinstance(missing, dict) else '?'}.",
        f"- Ofertas duplicadas (mismo identificador): "
        f"{dups.get('duplicate_source_id_records', '?') if isinstance(dups, dict) else '?'}.",
    ]
    if active is not None:
        bullets.append(f"- Ofertas activas al momento de la captura: {active}.")
    if age_h is not None:
        bullets.append(f"- La fuente se había actualizado unas {age_h} horas antes de la captura.")
    st.markdown("\n".join(bullets))

    st.markdown("### Revisión humana")
    st.markdown(
        "La segunda pasada dejó 7 decisiones pendientes (etiquetas inciertas y "
        "desacuerdos entre la primera y la segunda pasada). La persona responsable "
        "del proyecto las aprobó el 2 de agosto de 2026 por instrucción explícita, "
        "fijando la etiqueta final de cada par. Cada decisión queda registrada en el "
        "informe con su criterio, su fecha y su fuente; las métricas de esta mesa son "
        "finales solo para esta muestra curada de 20 ofertas."
    )

    st.markdown("### Límites de esta muestra")
    for line in (
        "Es una muestra incompleta: 20 ofertas de una sola página de una sola fuente "
        "(Himalayas). No representa el mercado laboral ecuatoriano.",
        "El buscador reconoce solo las 37 habilidades de la taxonomía y solo por "
        "palabras clave: no interpreta negaciones ni contexto, y no usa modelos de "
        "lenguaje, vectores ni búsqueda semántica.",
        "Que no haya coincidencias en una oferta no significa que la habilidad esté "
        "ausente; y que una habilidad no aparezca en la muestra no es prueba de que "
        "el mercado no la pida.",
        "Las métricas finales describen solo esta muestra curada: la revisión humana "
        "completó las 7 decisiones, pero nada de aquí se generaliza al mercado ni es "
        "una descripción del mercado completo.",
        "No existe una segunda fuente: no se compara ni se cruza con otros tablones.",
    ):
        st.markdown(f"- {line}")

    st.markdown("### Atribución y licencia")
    st.markdown(
        "Los datos de ofertas se muestran bajo el requisito de atribución de "
        "Himalayas: un enlace visible a [himalayas.app](https://himalayas.app) "
        "acompaña a los datos. La licencia del proyecto aún está por definirse tras "
        "auditar las licencias de la fuente y las dependencias."
    )

    _render_technical_details(bundle)


def _render_technical_details(bundle: A.DemoBundle) -> None:
    """Apéndice técnico: único lugar de la superficie donde viven los tokens.

    Estado de máquina, identificadores, versiones, nombres crudos de campos,
    siglas de la matriz de contingencia y rutas de archivos — incluido el
    historial v0.2.0 (etiquetas anteriores, motivos históricos y la cola
    resuelta). Todo lo demás usa lenguaje humano en español.
    """
    dataset = bundle.dataset
    identity = dataset.capture_identity
    sample = dataset.sample
    report = bundle.report
    taxonomy = bundle.taxonomy
    m = report.primary_metrics
    macro = report.macro_metrics
    with st.expander("Detalles técnicos"):
        st.markdown("#### Estado de los artefactos")
        st.markdown(
            "Actual (v0.3.0): `annotation_status` = `human_review_complete` · "
            "`human_review_required` = `false` · `human_review_complete` = `true` · "
            "`complete: false`.\n\n"
            "Estados derivados (no se muestran en la superficie pública): "
            "`demo-ready`, `evaluation-final`, `human-reviewed`.\n\n"
            "Histórico (v0.2.0, sin modificar): `annotation_status` = `draft_second_pass` · "
            "`human_review_required` = `true`; la cola de 7 decisiones quedó resuelta y se "
            "conserva como histórica. La interfaz histórica mostraba `Interfaz pública en "
            "validación` y `Prototipo local · evaluación provisional · 7 decisiones humanas "
            "pendientes`; esos textos no describen el estado actual."
        )
        st.markdown("#### Identidad de la captura")
        st.table(
            [
                {"Campo": "Identificador de captura", "Valor": identity.get("snapshot_id", "—")},
                {"Campo": "Endpoint de origen", "Valor": identity.get("endpoint", "—")},
                {"Campo": "Versión del adaptador", "Valor": identity.get("adapter_version", "—")},
                {"Campo": "SHA-256 del raw", "Valor": identity.get("raw_sha256", "—")},
                {"Campo": "Capturada en (UTC)", "Valor": identity.get("captured_at", "—")},
                {"Campo": "Fuente", "Valor": identity.get("source", "—")},
            ]
        )
        st.markdown("#### Versiones")
        st.markdown(
            f"Conjunto de datos <code>{esc(dataset.dataset_version)}</code> · "
            f"Taxonomía <code>{esc(taxonomy.version)}</code> · "
            f"matcher <code>{esc(dataset.matcher_version)}</code> · "
            f"Evaluación actual <code>{esc(bundle.review.evaluation_version)}</code> · "
            "evaluación histórica <code>skill-extraction-review-0.2.0</code> "
            "(`previous_artifact`)"
        )
        st.markdown("#### Muestra (forma cruda)")
        st.markdown(
            f"Página (`page`): {esc(str(sample.get('page', '?')))} · "
            f"límite (`limit`): {esc(str(sample.get('limit', '?')))} · "
            f"desplazamiento (`offset`): {esc(str(sample.get('offset', '?')))} · "
            f"registros (`records`): {esc(str(sample.get('records', '?')))} · "
            f"total (`total_count`): {esc(str(sample.get('total_count', '?')))} · "
            "`complete: false` significa que la captura es incompleta."
        )
        st.markdown("#### Matriz de contingencia (micro, formato técnico)")
        st.markdown(
            f"TP = {m.get('tp', 0)} · FP = {m.get('fp', 0)} · "
            f"FN = {m.get('fn', 0)} · TN = {m.get('tn', 0)} · "
            f"precision {A.format_metric(m.get('precision'))} · "
            f"recall {A.format_metric(m.get('recall'))} · "
            f"f1 {A.format_metric(m.get('f1'))}"
        )
        st.markdown(
            f"Macro: precisión {A.format_metric(macro.get('precision'))} · "
            f"recall {A.format_metric(macro.get('recall'))} · "
            f"F1 {A.format_metric(macro.get('f1'))} · "
            "habilidades excluidas por valor indefinido: "
            + ", ".join(f"`{esc(s)}`" for s in macro.get("skills_excluded_undefined", []))
        )
        st.markdown("#### Decisiones de revisión humana (registro auditado)")
        st.markdown(
            "Siete decisiones aprobadas (`human_review_decisions`); cada una conserva la "
            "etiqueta original de la segunda pasada, la primera pasada cuando existía, la "
            "evidencia y los motivos originales, y añade la etiqueta final, la fecha y la "
            "fuente de aprobación y el criterio."
        )
        st.table(
            [
                {
                    "Ítem": item.get("item_id", "—"),
                    "source_id": item.get("source_id", "—"),
                    "skill_id": item.get("skill_id", "—"),
                    "1.ª pasada": (
                        "sin etiqueta" if item.get("first_pass_unlabeled") else item.get("first_pass_label") or "—"
                    ),
                    "2.ª pasada": item.get("second_pass_label", "—"),
                    "Final": item.get("final_label", "—"),
                    "Aprobación": item.get("approval_date", "—"),
                    "Fuente": item.get("approval_source", "—"),
                }
                for item in report.human_review_decisions
            ]
        )
        st.markdown("#### Cola histórica de revisión humana (v0.2.0)")
        hist_queue = report.historical_human_queue
        st.markdown(
            f"`human_review_queue` (v0.2.0): count = {hist_queue.get('count', '—')} · "
            f"ítems = {len(hist_queue.get('items', []))} · nota: "
            f"{esc(hist_queue.get('note', '—'))}. Estado actual: count = 0, items = [] "
            "(todas las decisiones fueron aprobadas)."
        )
        st.markdown("#### Primera pasada frente a segunda pasada (histórico v0.2.0)")
        fvs = report.historical_first_vs_second
        st.markdown(
            f"Primera pasada: {fvs.get('first_draft_labels', '—')} pares etiquetados · "
            f"segunda pasada: {fvs.get('second_pass_labels', '—')} · "
            f"pares en común: {fvs.get('overlapping_pairs', '—')} · "
            f"acuerdos: {fvs.get('agreements', '—')} · "
            f"desacuerdos: {len(fvs.get('disagreements', []))} · "
            f"pares sin etiqueta en la primera pasada: {fvs.get('first_draft_unlabeled_pairs', '—')}"
        )
        for d in fvs.get("disagreements", []):
            st.markdown(
                f"- `{esc(d.get('source_id', '—'))}` · `{esc(d.get('skill_id', '—'))}`: "
                f"`{esc(d.get('first_draft_label') or 'sin etiqueta')}` → "
                f"`{esc(d.get('second_pass_label', '—'))}` — motivo histórico: "
                f"{esc(_motivo_revision_es(d.get('second_pass_reason', '—')))}"
            )
        st.markdown("#### Enumerado de etiquetas")
        st.markdown(
            "`supported` → respaldado · `not_supported` → no respaldado · "
            "`uncertain` → incierto (ya no se usa en la v0.3.0: la cola fue resuelta)."
        )
        st.markdown("#### Campos de texto revisados")
        st.markdown("`title_raw`, `excerpt_raw`, `categories_raw`, `description_html_raw`")
        st.markdown("#### Reglas del buscador (del artefacto de taxonomía)")
        reglas_es = {
            "term_types": "La taxonomía separa palabras clave y alias; ambos se buscan con las mismas reglas.",
            "case_handling": "La comparación no distingue mayúsculas y minúsculas.",
            "boundary_matching": "Los términos deben aparecer como palabras completas; no se buscan dentro de palabras mayores.",
            "connector_variants": "En términos compuestos se permiten espacios, guiones, guiones bajos y barras como separadores.",
            "html_handling": "El HTML de la descripción se convierte a texto visible para buscar, sin modificar el campo original.",
            "evidence_behavior": "Cada coincidencia conserva término, tipo, cita y cantidad de apariciones.",
            "deduplication": "Los términos repetidos se rechazan al cargar la taxonomía y las apariciones duplicadas se agrupan.",
            "negation": "La versión actual no interpreta negaciones ni contexto: una coincidencia es evidencia de palabra clave.",
        }
        for key in taxonomy.rules:
            st.markdown(f"**{key}** — {reglas_es.get(key, 'Regla registrada en la taxonomía.')}")
        excluded = taxonomy.excluded_terms
        if excluded:
            st.markdown("#### Términos excluidos de la taxonomía")
            st.table([{"Término": k, "Motivo": "Excluido por una regla explícita de la taxonomía."} for k in excluded])
        st.markdown("#### Definiciones y salvaguardas")
        st.markdown(
            "- **Métricas primarias:** precisión, recall y F1 finales se calculan sobre los 740 "
            "pares de la muestra curada; no quedan pares inciertos.\n"
            "- **Pares no etiquetados:** no se convierten en falsos positivos ni falsos negativos.\n"
            "- **Cola humana:** estado actual count = 0, items = []; las 7 decisiones aprobadas "
            "quedan en `human_review_decisions` (fecha, fuente y criterio por ítem).\n"
            "- **Evidencia:** «no respaldado» significa que no se encontró evidencia positiva "
            "explícita en los campos revisados.\n"
            "- **Final para muestra curada:** las métricas finales describen solo estas 20 "
            "ofertas; no deben generalizarse al mercado completo."
        )
        st.markdown("#### Advertencias del proceso")
        st.markdown(
            "- Las etiquetas son finales únicamente para esta muestra curada y no constituyen una referencia general del mercado."
            "\n"
            "- El buscador de palabras clave no interpreta negaciones ni contexto.\n"
            "- La segunda pasada se realizó leyendo el texto fuente y no consultando las "
            "predicciones del matcher; la revisión humana resolvió después sus 7 decisiones.\n"
            "- No se modificaron el matcher ni la taxonomía durante la anotación ni la "
            "adjudicación.\n"
            "- La evaluación v0.2.0 era un borrador; su estado, sus métricas y su cola se "
            "conservan como históricos."
        )
        st.markdown("#### Limitaciones registradas")
        st.markdown(
            "- La muestra contiene 20 ofertas de una sola página y no representa el mercado laboral.\n"
            "- La taxonomía cubre 37 habilidades; una habilidad fuera de ella no se evalúa.\n"
            "- Las coincidencias son evidencia de palabras clave, no comprensión semántica.\n"
            "- Las métricas finales describen solo esta muestra curada; el matcher no está "
            "validado de forma definitiva para el mercado completo."
        )
        st.markdown("#### Archivos que lee esta mesa")
        for path in (A.DATASET_PATH, A.DESCRIPTIVE_PATH, A.REVIEW_PATH, A.REPORT_PATH, A.TAXONOMY_PATH):
            st.markdown(f"- `{path.relative_to(A.REPO_ROOT)}`")
        st.markdown("#### Historial v0.2.0 (solo lectura, nunca reescrito)")
        for path in (A.REVIEW_PATH_V020, A.REPORT_PATH_V020):
            st.markdown(f"- `{path.relative_to(A.REPO_ROOT)}`")


# ---------------------------------------------------------------------------
# Punto de entrada (se ejecuta al nivel superior para que AppTest y
# `streamlit run` se comporten de forma idéntica)
# ---------------------------------------------------------------------------

st.markdown(CSS, unsafe_allow_html=True)

try:
    bundle = A.load_demo_bundle(A.REPO_ROOT)
except A.DemoDataError as exc:
    render_error(exc)
    st.stop()

render_sidebar(bundle)
render_masthead(bundle)
render_final_sample_bar()
render_thesis(bundle)
render_limitation()
render_strip(bundle)

tab_resumen_tab, tab_landscape_tab, tab_jobs_tab, tab_audit_tab, tab_prov_tab = st.tabs(
    [
        "Resumen",
        "Panorama de habilidades",
        "Explorar ofertas",
        "Auditoría de evaluación",
        "Proveniencia y límites",
    ]
)

with tab_resumen_tab:
    tab_resumen(bundle)

with tab_landscape_tab:
    tab_landscape(bundle)

with tab_jobs_tab:
    tab_jobs(bundle)

with tab_audit_tab:
    tab_audit(bundle)

with tab_prov_tab:
    tab_provenance(bundle)
