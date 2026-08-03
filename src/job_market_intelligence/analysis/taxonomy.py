"""Taxonomía versionada de habilidades técnicas: definiciones declarativas + cargador tipado.

La fuente de verdad es un artefacto JSON versionado
(``data/taxonomy/technical-skills-0.1.0.json`` por defecto). El artefacto
contiene:

- la ``version`` de la taxonomía (por ejemplo ``technical-skills-0.1.0``);
- ``categories`` (el conjunto cerrado al que debe pertenecer cada categoría de habilidad);
- ``skills``: identificadores estables (``skill.python``, nunca nombres para mostrar),
  nombres canónicos, categorías, **palabras clave** (términos canónicos de búsqueda),
  **alias** (ortografías y abreviaturas alternativas) y notas;
- ``rules``: las reglas de coincidencia explícitas (manejo de mayúsculas, coincidencia
  de fronteras, variantes de conectores, campos buscados, manejo de HTML, comportamiento
  de evidencia, deduplicación, campos faltantes, representación de no-coincidencia y la
  ausencia de parseo de negación en 0.1.0);
- ``excluded_terms``: términos deliberadamente FUERA del catálogo y por qué (por ejemplo
  ``go``, que la coincidencia de fronteras no puede distinguir del verbo inglés).

El cargador es de cierre y determinista: los identificadores de habilidad duplicados o
los términos duplicados — tanto en ``keywords`` como en ``aliases`` — se rechazan con
:class:`TaxonomyError` en tiempo de carga en lugar de deduplicarse en silencio, toda
habilidad debe declarar tanto ``keywords`` como ``aliases`` (keywords no vacías) y toda
habilidad debe referenciar una categoría declarada.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import TaxonomyError

#: Ruta de artefacto por defecto, relativa a la raíz del repositorio. El
#: artefacto confirmado es la fuente de verdad; el cargador nunca inventa una versión.
TAXONOMY_ARTIFACT_DEFAULT_PATH = "data/taxonomy/technical-skills-0.1.0.json"


@dataclass(frozen=True)
class SkillDefinition:
    """Una entrada del catálogo: id estable, nombre canónico, categoría y términos de búsqueda.

    ``keywords`` son los términos canónicos de búsqueda; ``aliases`` son
    ortografías y abreviaturas alternativas. Ambos se coinciden con las mismas
    reglas seguras en fronteras (primero keywords, luego aliases) y ambos son
    únicos en toda la taxonomía por construcción.
    """

    skill_id: str
    name: str
    category: str
    keywords: tuple[str, ...]
    aliases: tuple[str, ...] = ()
    notes: str | None = None


@dataclass(frozen=True)
class Taxonomy:
    """Una taxonomía validada y hashable lista para coincidir.

    ``rules`` y ``excluded_terms`` se conservan como pares ordenados ``(key, value)``
    para que el objeto siga siendo hashable; ``rules_dict`` y
    ``excluded_terms_dict`` los exponen como mapeos simples para la salida.
    """

    version: str
    skills: tuple[SkillDefinition, ...]
    categories: tuple[str, ...] = ()
    rules: tuple[tuple[str, str], ...] = ()
    excluded_terms: tuple[tuple[str, str], ...] = ()

    @property
    def rules_dict(self) -> dict[str, str]:
        return dict(self.rules)

    @property
    def excluded_terms_dict(self) -> dict[str, str]:
        return dict(self.excluded_terms)

    def skill_by_id(self, skill_id: str) -> SkillDefinition | None:
        for skill in self.skills:
            if skill.skill_id == skill_id:
                return skill
        return None

    def term_index(self) -> dict[str, tuple[str, str]]:
        """Mapea cada término keyword/alias a su ``(skill_id, term_type)``.

        Los términos son únicos por construcción: el cargador rechaza duplicados
        entre keywords y aliases.
        """
        index: dict[str, tuple[str, str]] = {}
        for skill in self.skills:
            for term in skill.keywords:
                index[term] = (skill.skill_id, "keyword")
            for term in skill.aliases:
                index[term] = (skill.skill_id, "alias")
        return index


def _require_string(doc: dict, key: str, label: str) -> str:
    value = doc.get(key)
    if not isinstance(value, str) or not value.strip():
        raise TaxonomyError(f"{label} debe ser una cadena no vacía; se obtuvo {value!r}")
    return value


def _parse_rules(raw: Any) -> tuple[tuple[str, str], ...]:
    if not isinstance(raw, dict) or not raw:
        raise TaxonomyError("'rules' debe ser un objeto JSON no vacío")
    pairs: list[tuple[str, str]] = []
    for key, value in raw.items():
        if not isinstance(key, str) or not key.strip():
            raise TaxonomyError("las claves de 'rules' deben ser cadenas no vacías")
        if isinstance(value, str):
            text = value
        elif isinstance(value, list) and all(isinstance(item, str) for item in value):
            text = ", ".join(value)
        else:
            raise TaxonomyError(f"la regla {key!r} debe ser una cadena o una lista de cadenas")
        pairs.append((key, text))
    return tuple(pairs)


def _parse_excluded(raw: Any) -> tuple[tuple[str, str], ...]:
    if raw is None:
        return ()
    if not isinstance(raw, dict):
        raise TaxonomyError("'excluded_terms' debe ser un objeto JSON cuando está presente")
    pairs = []
    for term, rationale in raw.items():
        if not isinstance(term, str) or not term.strip():
            raise TaxonomyError("las claves de 'excluded_terms' deben ser cadenas no vacías")
        if not isinstance(rationale, str) or not rationale.strip():
            raise TaxonomyError(f"el término excluido {term!r} necesita una justificación no vacía")
        pairs.append((term, rationale))
    return tuple(pairs)


def load_taxonomy(path: str | Path) -> Taxonomy:
    """Carga y valida un artefacto de taxonomía desde un archivo JSON.

    Eleva :class:`TaxonomyError` ante cualquier violación de forma, id de habilidad
    duplicado, alias duplicado o categoría no declarada. El :class:`Taxonomy`
    devuelto lleva la propia versión del artefacto; aquí no se inventa ninguna.
    """
    try:
        raw_text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise TaxonomyError(f"no se puede leer el artefacto de taxonomía {path}: {exc}") from exc
    try:
        doc = json.loads(raw_text)
    except ValueError as exc:
        raise TaxonomyError(f"el artefacto de taxonomía {path} no es JSON válido: {exc}") from exc
    return taxonomy_from_dict(doc)


def taxonomy_from_dict(doc: dict) -> Taxonomy:
    """Valida un documento de taxonomía parseado (usado por pruebas y por el cargador)."""
    if not isinstance(doc, dict):
        raise TaxonomyError(f"el documento de taxonomía debe ser un objeto JSON; se obtuvo {type(doc).__name__}")
    version = _require_string(doc, "version", "'version'")

    categories_raw = doc.get("categories", [])
    if not isinstance(categories_raw, list) or not all(
        isinstance(cat, str) and cat.strip() for cat in categories_raw
    ):
        raise TaxonomyError("'categories' debe ser una lista no vacía de cadenas no vacías")
    categories = tuple(categories_raw)

    skills_raw = doc.get("skills")
    if not isinstance(skills_raw, list) or not skills_raw:
        raise TaxonomyError("'skills' debe ser un arreglo JSON no vacío")

    skills: list[SkillDefinition] = []
    seen_ids: set[str] = set()
    seen_terms: set[str] = set()
    for entry in skills_raw:
        if not isinstance(entry, dict):
            raise TaxonomyError("cada entrada de 'skills' debe ser un objeto JSON")
        skill_id = _require_string(entry, "skill_id", f"skill entry {entry!r}: 'skill_id'")
        name = _require_string(entry, "name", f"skill {skill_id!r}: 'name'")
        category = _require_string(entry, "category", f"skill {skill_id!r}: 'category'")
        if category not in categories:
            raise TaxonomyError(
                f"la habilidad {skill_id!r} referencia la categoría no declarada {category!r}; "
                f"categorías declaradas: {sorted(categories)}"
            )
        if skill_id in seen_ids:
            raise TaxonomyError(f"skill_id duplicado {skill_id!r} en la taxonomía")
        seen_ids.add(skill_id)

        # Cada entrada debe declarar visiblemente ambos campos: keywords son los
        # términos canónicos de búsqueda (obligatorios, no vacíos); aliases son
        # ortografías alternativas (pueden estar vacíos).
        keywords_raw = entry.get("keywords")
        if not isinstance(keywords_raw, list) or not keywords_raw:
            raise TaxonomyError(
                f"habilidad {skill_id!r}: 'keywords' debe ser una lista no vacía "
                "(términos canónicos de búsqueda)"
            )
        aliases_raw = entry.get("aliases")
        if not isinstance(aliases_raw, list):
            raise TaxonomyError(
                f"habilidad {skill_id!r}: 'aliases' debe ser una lista (puede estar vacía); "
                "deben declararse tanto 'keywords' como 'aliases'"
            )
        terms: list[str] = []
        for term in (*keywords_raw, *aliases_raw):
            if not isinstance(term, str) or not term.strip():
                raise TaxonomyError(f"habilidad {skill_id!r}: keywords/aliases deben ser cadenas no vacías")
            if term in seen_terms:
                raise TaxonomyError(
                    f"término duplicado {term!r} en la taxonomía (keywords y aliases son únicos "
                    f"en todas las habilidades)"
                )
            seen_terms.add(term)

        notes_raw = entry.get("notes")
        notes = notes_raw if isinstance(notes_raw, str) and notes_raw.strip() else None
        skills.append(
            SkillDefinition(
                skill_id=skill_id,
                name=name,
                category=category,
                keywords=tuple(keywords_raw),
                aliases=tuple(aliases_raw),
                notes=notes,
            )
        )

    return Taxonomy(
        version=version,
        skills=tuple(skills),
        categories=categories,
        rules=_parse_rules(doc.get("rules")),
        excluded_terms=_parse_excluded(doc.get("excluded_terms")),
    )
