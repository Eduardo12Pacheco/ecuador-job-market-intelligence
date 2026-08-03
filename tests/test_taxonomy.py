"""Pruebas offline del cargador de la taxonomía versionada de habilidades técnicas.

El artefacto confirmado ``data/taxonomy/technical-skills-0.1.0.json`` es la
fuente de verdad: el cargador valida su forma, y cada regla del matcher está
documentada dentro del artefacto para que el comportamiento siga siendo
inspeccionable. Cada habilidad declara tanto ``keywords`` (términos de búsqueda
canónicos) como ``aliases`` (grafías y abreviaturas alternativas). Los términos
duplicados (keywords o aliases) y los identificadores de habilidad duplicados
se rechazan al cargar (fallo cerrado determinista), nunca se deduplican en
silencio.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from job_market_intelligence.analysis.taxonomy import (
    TAXONOMY_ARTIFACT_DEFAULT_PATH,
    Taxonomy,
    TaxonomyError,
    load_taxonomy,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_PATH = REPO_ROOT / TAXONOMY_ARTIFACT_DEFAULT_PATH

DOCUMENTED_RULES = {
    "case_handling",
    "boundary_matching",
    "connector_variants",
    "fields_searched",
    "html_handling",
    "evidence_behavior",
    "deduplication",
    "missing_fields",
    "no_match",
    "negation",
    "term_types",
}


def sample_skills() -> list[dict]:
    return [
        {
            "skill_id": "skill.python",
            "name": "Python",
            "category": "programming_language",
            "keywords": ["python"],
            "aliases": [],
        },
        {
            "skill_id": "skill.javascript",
            "name": "JavaScript",
            "category": "programming_language",
            "keywords": ["javascript"],
            "aliases": ["js"],
        },
    ]


def sample_taxonomy_doc(**overrides) -> dict:
    doc = {
        "version": "technical-skills-test-0.1.0",
        "categories": ["programming_language"],
        "skills": sample_skills(),
        "rules": {
            "case_handling": "case-insensitive",
            "boundary_matching": "aliases never match inside larger words",
        },
        "excluded_terms": {"go": "collides with the English verb"},
    }
    doc.update(overrides)
    return doc


def write_tmp_taxonomy(tmp_path: Path, doc: dict) -> Path:
    path = tmp_path / "taxonomy.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


class TestCommittedArtifact:
    def test_artifact_exists_and_loads(self) -> None:
        assert ARTIFACT_PATH.exists(), (
            "el artefacto de taxonomía confirmado debe existir en " + str(ARTIFACT_PATH)
        )
        taxonomy = load_taxonomy(ARTIFACT_PATH)
        assert taxonomy.version == "technical-skills-0.1.0"

    def test_artifact_entries_declare_keywords_and_aliases(self) -> None:
        taxonomy = load_taxonomy(ARTIFACT_PATH)
        assert len(taxonomy.skills) > 0
        for skill in taxonomy.skills:
            assert skill.skill_id
            assert skill.name
            assert skill.category
            assert skill.keywords, f"{skill.skill_id} debe declarar keywords no vacías"
            assert isinstance(skill.aliases, tuple)

    def test_artifact_skill_ids_unique(self) -> None:
        taxonomy = load_taxonomy(ARTIFACT_PATH)
        ids = [skill.skill_id for skill in taxonomy.skills]
        assert len(ids) == len(set(ids))

    def test_artifact_terms_unique_across_keywords_and_aliases(self) -> None:
        taxonomy = load_taxonomy(ARTIFACT_PATH)
        terms = [
            term for skill in taxonomy.skills for term in (*skill.keywords, *skill.aliases)
        ]
        assert len(terms) == len(set(terms)), "los términos duplicados no deben publicarse"

    def test_artifact_documents_every_matching_rule(self) -> None:
        taxonomy = load_taxonomy(ARTIFACT_PATH)
        assert DOCUMENTED_RULES <= set(dict(taxonomy.rules))

    def test_artifact_documents_excluded_terms(self) -> None:
        taxonomy = load_taxonomy(ARTIFACT_PATH)
        excluded = dict(taxonomy.excluded_terms)
        assert "go" in excluded
        assert excluded["go"]

    def test_term_index_covers_every_keyword_and_alias(self) -> None:
        taxonomy = load_taxonomy(ARTIFACT_PATH)
        index = taxonomy.term_index()
        for skill in taxonomy.skills:
            for term in skill.keywords:
                assert index[term] == (skill.skill_id, "keyword")
            for term in skill.aliases:
                assert index[term] == (skill.skill_id, "alias")


class TestLoaderValidation:
    def test_duplicate_term_across_skills_rejected_deterministically(self, tmp_path) -> None:
        skills = sample_skills() + [
            {
                "skill_id": "skill.pythonista",
                "name": "Pythonista",
                "category": "programming_language",
                "keywords": ["pythonista"],
                "aliases": ["python"],  # colisiona con el keyword de skill.python
            }
        ]
        path = write_tmp_taxonomy(tmp_path, sample_taxonomy_doc(skills=skills))
        with pytest.raises(TaxonomyError, match="python"):
            load_taxonomy(path)

    def test_duplicate_keyword_and_alias_in_same_skill_rejected(self, tmp_path) -> None:
        skills = [
            {
                "skill_id": "skill.x",
                "name": "X",
                "category": "programming_language",
                "keywords": ["x"],
                "aliases": ["x"],
            }
        ]
        path = write_tmp_taxonomy(tmp_path, sample_taxonomy_doc(skills=skills))
        with pytest.raises(TaxonomyError, match="'x'"):
            load_taxonomy(path)

    def test_duplicate_skill_id_rejected(self, tmp_path) -> None:
        skills = sample_skills() + [
            {
                "skill_id": "skill.python",
                "name": "Python 2",
                "category": "programming_language",
                "keywords": ["python2"],
                "aliases": [],
            }
        ]
        path = write_tmp_taxonomy(tmp_path, sample_taxonomy_doc(skills=skills))
        with pytest.raises(TaxonomyError, match="skill.python"):
            load_taxonomy(path)

    def test_empty_keywords_rejected(self, tmp_path) -> None:
        skills = [
            {
                "skill_id": "skill.x",
                "name": "X",
                "category": "programming_language",
                "keywords": [],
                "aliases": ["x"],
            }
        ]
        path = write_tmp_taxonomy(tmp_path, sample_taxonomy_doc(skills=skills))
        with pytest.raises(TaxonomyError):
            load_taxonomy(path)

    def test_missing_keywords_key_rejected(self, tmp_path) -> None:
        skills = [
            {
                "skill_id": "skill.x",
                "name": "X",
                "category": "programming_language",
                "aliases": ["x"],
            }
        ]
        path = write_tmp_taxonomy(tmp_path, sample_taxonomy_doc(skills=skills))
        with pytest.raises(TaxonomyError, match="keywords"):
            load_taxonomy(path)

    def test_missing_aliases_key_rejected(self, tmp_path) -> None:
        skills = [
            {
                "skill_id": "skill.x",
                "name": "X",
                "category": "programming_language",
                "keywords": ["x"],
            }
        ]
        path = write_tmp_taxonomy(tmp_path, sample_taxonomy_doc(skills=skills))
        with pytest.raises(TaxonomyError, match="aliases"):
            load_taxonomy(path)

    def test_missing_version_rejected(self, tmp_path) -> None:
        doc = sample_taxonomy_doc()
        del doc["version"]
        path = write_tmp_taxonomy(tmp_path, doc)
        with pytest.raises(TaxonomyError):
            load_taxonomy(path)

    def test_malformed_shape_rejected(self, tmp_path) -> None:
        path = tmp_path / "bad.json"
        path.write_text('{"skills": "not-a-list"}', encoding="utf-8")
        with pytest.raises(TaxonomyError):
            load_taxonomy(path)

    def test_unknown_category_rejected(self, tmp_path) -> None:
        skills = sample_skills()
        skills[0]["category"] = "not_a_declared_category"
        path = write_tmp_taxonomy(tmp_path, sample_taxonomy_doc(skills=skills))
        with pytest.raises(TaxonomyError, match="category"):
            load_taxonomy(path)

    def test_version_survives_load(self, tmp_path) -> None:
        path = write_tmp_taxonomy(tmp_path, sample_taxonomy_doc())
        taxonomy = load_taxonomy(path)
        assert taxonomy.version == "technical-skills-test-0.1.0"
        assert isinstance(taxonomy, Taxonomy)
