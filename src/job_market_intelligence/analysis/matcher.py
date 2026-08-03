r"""Matcher determinista de línea base de palabras clave (sin embeddings, sin LLMs, sin lógica difusa).

El matcher implementa las reglas explícitas declaradas en el artefacto de taxonomía.
Cada regla es inspeccionable; no hay heurísticas ocultas.

Reglas de coincidencia (0.1.0):

- **Tipos de término**: cada habilidad declara ``keywords`` (términos canónicos de
  búsqueda) y ``aliases`` (ortografías y abreviaturas alternativas). Ambos se buscan
  con las mismas reglas; los keywords se iteran antes que los aliases, y un término es
  único en toda la taxonomía (el cargador rechaza duplicados).
- **Manejo de mayúsculas**: el término y el texto buscado se convierten ambos con
  casefold, de modo que la coincidencia no distingue mayúsculas.
- **Coincidencia de fronteras**: cada patrón de término se envuelve en los lookarounds
  ``(?<![\w])`` / ``(?![\w])`` sobre el texto casefold, de modo que un término nunca
  coincide dentro de una palabra mayor: ``java`` no puede coincidir con ``javascript``,
  ``ml`` no puede coincidir con ``html``/``similar``, ``git`` no puede coincidir con
  ``github``.
- **Variantes de conectores**: los espacios, ``-``, ``_`` y ``/`` entre las palabras de
  un término multi-palabra son intercambiables (``machine learning`` coincide con
  ``machine-learning`` y ``machine_learning``). La puntuación dentro de un término de
  un solo token (``c++``, ``c#``, ``n8n``) se coincide literalmente; las ortografías
  versionadas como ``C++17`` no se coinciden deliberadamente en 0.1.0.
- **Campos buscados**: ``title_raw``, ``excerpt_raw``, ``categories_raw`` (unidos con
  espacios) y ``description_html_raw`` (convertido a texto visible). Los campos
  faltantes o vacíos se omiten y se reportan en ``skipped_fields``; nunca se coerzan
  a evidencia.
- **Manejo de HTML**: ``description_html_raw`` se convierte a texto visible solo para
  coincidir (etiquetas eliminadas, entidades HTML desescapadas, espacios colapsados).
  El campo crudo nunca se modifica.
- **Comportamiento de evidencia**: una entrada de evidencia por ``(campo, término coincidente)``
  con el tipo del término (``keyword`` o ``alias``), el extracto de primera aparición y un
  conteo de apariciones; una habilidad se lista como máximo una vez por registro; la
  evidencia se ordena por orden de campo buscado y luego por orden de definición de la
  taxonomía (keywords antes que aliases).
- **Deduplicación**: los términos duplicados (keywords o aliases) se rechazan al cargar
  la taxonomía; las apariciones duplicadas del mismo término en un campo colapsan en una
  entrada de evidencia con ``occurrence_count``.
- **Sin coincidencia**: un registro sin ninguna coincidencia es ``evidence_status =
  "no_evidence"`` con una lista de habilidades vacía. La ausencia de evidencia no es
  evidencia de ausencia.
- **Negación**: 0.1.0 no interpreta negación ni contexto; una coincidencia es solo
  evidencia de palabras clave.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from functools import lru_cache

from ..ingestion.models import CanonicalJob
from .taxonomy import Taxonomy

#: Versión del comportamiento de coincidencia; cambia cuando cambian las reglas.
MATCHER_VERSION = "keyword-baseline-0.1.0"

#: Campos buscados, en orden determinista (primero el título, al final la descripción).
SEARCHED_FIELDS = ("title_raw", "excerpt_raw", "categories_raw", "description_html_raw")

#: Caracteres tratados como internos de palabra por la regla de frontera. Los patrones
#: de alias solo coinciden donde los caracteres circundantes no son caracteres de palabra.
_WORD_CHAR = r"\w"

#: Caracteres de conector intercambiables entre las palabras de un alias multi-palabra.
_CONNECTOR_RE = r"[\s\-_/]+"

#: Caracteres de contexto conservados alrededor de cada coincidencia en el extracto.
EXCERPT_CONTEXT_CHARS = 30

_TAG_RE = re.compile(r"<[^>]*>")
_WS_RE = re.compile(r"\s+")


def visible_text(html_source: str) -> str:
    """Convierte un fragmento HTML a texto visible para coincidir.

    Las etiquetas se eliminan, las entidades HTML se desescapan y los espacios se
    colapsan. Se usa solo para coincidir; el campo crudo ``description_html_raw``
    nunca se modifica.
    """
    text = _TAG_RE.sub(" ", html_source)
    text = html.unescape(text)
    return _WS_RE.sub(" ", text).strip()


def term_tokens(term: str) -> tuple[str, ...]:
    """Divide un término keyword/alias en palabras casefold separadas por conectores."""
    return tuple(token for token in re.split(_CONNECTOR_RE, term.strip().casefold()) if token)


@lru_cache(maxsize=512)
def term_pattern(term: str) -> re.Pattern[str]:
    """Construye el patrón seguro en fronteras y flexible a conectores de un término.

    El patrón se aplica a texto casefold, de modo que el término debe convertirse con
    casefold primero (``term_tokens`` lo hace). Los términos multi-palabra permiten
    secuencias de conectores entre palabras; la puntuación dentro de un solo token se
    coincide literalmente.
    """
    tokens = term_tokens(term)
    if not tokens:
        raise ValueError(f"el término debe contener al menos una palabra; se obtuvo {term!r}")
    body = re.escape(tokens[0])
    for token in tokens[1:]:
        body += _CONNECTOR_RE + re.escape(token)
    return re.compile(r"(?<![{0}]){1}(?![{0}])".format(_WORD_CHAR, body))


def field_text(job: CanonicalJob, field: str) -> str | None:
    """Devuelve el texto buscable de un campo canónico, o ``None`` cuando el
    campo falta o está vacío (omitido, nunca coercionado)."""
    if field == "title_raw":
        return job.title_raw or None
    if field == "excerpt_raw":
        return job.excerpt_raw or None
    if field == "categories_raw":
        joined = " ".join(job.categories_raw).strip()
        return joined or None
    if field == "description_html_raw":
        text = visible_text(job.description_html_raw)
        return text or None
    raise ValueError(f"campo buscado desconocido {field!r}; se esperaba uno de {SEARCHED_FIELDS}")


def _excerpt(text: str, start: int, end: int) -> str:
    """Un extracto corto y determinista alrededor del tramo de coincidencia.

    El tramo proviene del texto casefold; para este corpus (dominado por ASCII)
    el mismo tramo indexa el texto visible original, lo que mantiene los extractos
    legibles y deterministas.
    """
    left = max(0, start - EXCERPT_CONTEXT_CHARS)
    right = min(len(text), end + EXCERPT_CONTEXT_CHARS)
    prefix = "…" if left > 0 else ""
    suffix = "…" if right < len(text) else ""
    return f"{prefix}{text[left:right]}{suffix}"


@dataclass(frozen=True)
class SkillMatch:
    """Una entrada de evidencia deduplicada para un registro.

    ``matched_term`` es la cadena keyword/alias que coincidió y ``term_type``
    registra si es un ``keyword`` o un ``alias``. ``occurrence_count`` registra
    cuántas veces coincidió este término en este campo; solo se conserva el
    extracto de la primera aparición.
    """

    skill_id: str
    field: str
    matched_term: str
    term_type: str  # "keyword" | "alias"
    excerpt: str
    occurrence_count: int


@dataclass(frozen=True)
class JobSkillResult:
    """El resultado de coincidencia determinista completo de un registro canónico."""

    evidence_status: str  # "matched" | "no_evidence"
    skills: tuple[str, ...]
    evidence: tuple[SkillMatch, ...]
    searched_fields: tuple[str, ...]
    skipped_fields: tuple[str, ...]
    taxonomy_version: str


def match_job(job: CanonicalJob, taxonomy: Taxonomy) -> JobSkillResult:
    """Coincide un registro canónico contra la taxonomía.

    Determinista por construcción: los campos se iteran en el orden de
    :data:`SEARCHED_FIELDS`, las habilidades en el orden de definición de la taxonomía
    y los términos de cada habilidad en el orden keywords-luego-aliases.
    """
    evidence: list[SkillMatch] = []
    skills: list[str] = []
    seen_skills: set[str] = set()
    searched: list[str] = []
    skipped: list[str] = []

    for field in SEARCHED_FIELDS:
        text = field_text(job, field)
        if text is None:
            skipped.append(field)
            continue
        searched.append(field)
        folded = text.casefold()
        for skill in taxonomy.skills:
            # Primero keywords, luego aliases. La deduplicación defensiva evita que
            # un término presente en ambas listas coincida dos veces (el cargador
            # ya rechaza esos duplicados para los artefactos confirmados).
            terms: list[tuple[str, str]] = []
            seen_terms: set[str] = set()
            for term, term_type in (
                *((t, "keyword") for t in skill.keywords),
                *((t, "alias") for t in skill.aliases),
            ):
                if term not in seen_terms:
                    seen_terms.add(term)
                    terms.append((term, term_type))
            for term, term_type in terms:
                pattern = term_pattern(term)
                first = pattern.search(folded)
                if first is None:
                    continue
                occurrence_count = len(pattern.findall(folded))
                evidence.append(
                    SkillMatch(
                        skill_id=skill.skill_id,
                        field=field,
                        matched_term=term,
                        term_type=term_type,
                        excerpt=_excerpt(text, first.start(), first.end()),
                        occurrence_count=occurrence_count,
                    )
                )
                if skill.skill_id not in seen_skills:
                    seen_skills.add(skill.skill_id)
                    skills.append(skill.skill_id)

    return JobSkillResult(
        evidence_status="matched" if skills else "no_evidence",
        skills=tuple(skills),
        evidence=tuple(evidence),
        searched_fields=tuple(searched),
        skipped_fields=tuple(skipped),
        taxonomy_version=taxonomy.version,
    )
