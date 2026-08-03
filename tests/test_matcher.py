"""Pruebas offline del matcher determinista de referencia por palabras clave.

El matcher es un conjunto de reglas transparente, no una caja negra heurística:

- La coincidencia no distingue mayúsculas (ambos lados se normalizan con casefold).
- Los alias coinciden solo en límites de palabra y nunca dentro de palabras más
  largas: ``java`` no puede coincidir con ``javascript``, ``ml`` no puede
  coincidir con ``html`` ni con ``similar``, ``git`` no puede coincidir con ``github``.
- Los espacios en blanco, ``-``, ``_`` y ``/`` entre palabras de un alias son
  intercambiables, de modo que ``machine learning`` coincide con ``machine-learning``.
- Los alias con puntuación (``c++``, ``c#``, ``n8n``) se comparan literalmente;
  las grafías versionadas como ``C++17`` no se comparan deliberadamente en 0.1.0
  (comportamiento conservador y documentado).
- ``description_html_raw`` se convierte a texto visible solo para la comparación;
  el campo crudo nunca se modifica.
- Las ocurrencias duplicadas colapsan en una sola entrada de evidencia con un
  conteo de ocurrencias; una habilidad aparece como máximo una vez por registro.
- Los campos faltantes o vacíos se omiten y se reportan, nunca se convierten en evidencia.
- Los registros sin coincidencias son ``no_evidence`` con una lista de habilidades
  vacía; eso no es evidencia de ausencia.
"""

from __future__ import annotations

from job_market_intelligence.analysis.matcher import (
    MATCHER_VERSION,
    SEARCHED_FIELDS,
    field_text,
    match_job,
    term_pattern,
    visible_text,
)
from job_market_intelligence.analysis.taxonomy import SkillDefinition, Taxonomy
from job_market_intelligence.ingestion.parser import parse_job

from conftest import FIXED_CAPTURED_AT, default_job

SNAPSHOT = "snap-test"


def skill(
    skill_id: str,
    name: str,
    aliases: list[str] | None = None,
    keywords: list[str] | None = None,
    category: str = "test",
) -> dict:
    """Auxiliar de prueba; compatible hacia atrás con la forma antigua de solo aliases
    (cuando se omite ``keywords``, toma por defecto ``aliases``)."""
    if keywords is None and aliases is None:
        raise ValueError("skill() needs keywords, aliases, or both")
    if keywords is None:
        keywords = list(aliases)
    if aliases is None:
        aliases = []
    return {
        "skill_id": skill_id,
        "name": name,
        "category": category,
        "keywords": keywords,
        "aliases": aliases,
    }


def make_taxonomy(*skills: dict) -> Taxonomy:
    return Taxonomy(
        version="test-taxonomy-0.1.0",
        skills=tuple(SkillDefinition(**s) for s in skills),
        rules=(("boundary_matching", "aliases never match inside larger words"),),
        excluded_terms=(("go", "collides with the English verb"),),
    )


def parsed_job(**overrides):
    return parse_job(
        default_job(0, 0, **overrides),
        snapshot_id=SNAPSHOT,
        captured_at=FIXED_CAPTURED_AT,
    )


PYTHON = skill("skill.python", "Python", ["python"])
JAVA = skill("skill.java", "Java", ["java"])
JAVASCRIPT = skill("skill.javascript", "JavaScript", ["javascript"])
MACHINE_LEARNING = skill(
    "skill.machine_learning", "Machine Learning", keywords=["machine learning"], aliases=["ml"]
)
CPP = skill("skill.cpp", "C++", keywords=["c++"], aliases=["cpp"])
CSHARP = skill("skill.csharp", "C#", keywords=["c#"], aliases=["csharp"])
GIT = skill("skill.git", "Git", ["git"])
IOS = skill("skill.ios", "iOS", ["ios"])


class TestCaseAndVariants:
    def test_case_insensitive_match(self) -> None:
        result = match_job(parsed_job(description="<p>Python Developer</p>"), make_taxonomy(PYTHON))
        assert result.evidence_status == "matched"
        assert result.skills == ("skill.python",)
        assert result.evidence[0].term_type == "keyword"

    def test_mixed_case_variant_matches(self) -> None:
        result = match_job(parsed_job(description="<p>pYtHoN expert</p>"), make_taxonomy(PYTHON))
        assert result.skills == ("skill.python",)

    def test_uppercase_variant_matches(self) -> None:
        result = match_job(parsed_job(description="<p>PYTHON</p>"), make_taxonomy(PYTHON))
        assert result.skills == ("skill.python",)

    def test_alias_short_form_matches(self) -> None:
        result = match_job(
            parsed_job(description="<p>Strong ML fundamentals</p>"), make_taxonomy(MACHINE_LEARNING)
        )
        assert result.skills == ("skill.machine_learning",)
        assert result.evidence[0].matched_term == "ml"
        assert result.evidence[0].term_type == "alias"

    def test_keyword_term_type_reported(self) -> None:
        result = match_job(
            parsed_job(description="<p>machine learning systems</p>"), make_taxonomy(MACHINE_LEARNING)
        )
        assert result.evidence[0].matched_term == "machine learning"
        assert result.evidence[0].term_type == "keyword"

    def test_canonical_name_is_not_an_alias(self) -> None:
        # Solo se comparan los aliases; el nombre canónico de visualización no se
        # busca a menos que también esté listado como alias.
        result = match_job(parsed_job(description="<p>Machine Learning engineer</p>"), make_taxonomy(PYTHON))
        assert result.evidence_status == "no_evidence"


class TestBoundarySafety:
    def test_java_never_matches_inside_javascript(self) -> None:
        result = match_job(
            parsed_job(description="<p>JavaScript expert</p>"), make_taxonomy(JAVA, JAVASCRIPT)
        )
        assert result.skills == ("skill.javascript",)

    def test_ml_never_matches_inside_html_or_similar(self) -> None:
        text = "<p>building with html, yml and similar tooling</p>"
        result = match_job(parsed_job(description=text), make_taxonomy(MACHINE_LEARNING))
        assert result.evidence_status == "no_evidence"

    def test_git_never_matches_inside_github(self) -> None:
        result = match_job(parsed_job(description="<p>GitHub Actions</p>"), make_taxonomy(GIT))
        assert result.evidence_status == "no_evidence"

    def test_go_word_does_not_match_googled_terms(self) -> None:
        # 'go' está excluido de la taxonomía versionada; esta prueba documenta la
        # regla de límites que lo protege: incluso si existiera un alias, 'good' y
        # 'google' nunca deben coincidir.
        go = skill("skill.go", "Go", ["go"])
        result = match_job(parsed_job(description="<p>good google go</p>"), make_taxonomy(go))
        assert result.skills == ("skill.go",)  # solo el 'go' aislado

    def test_ios_never_matches_inside_biometrics(self) -> None:
        result = match_job(parsed_job(description="<p>biometrics signals</p>"), make_taxonomy(IOS))
        assert result.evidence_status == "no_evidence"

    def test_ai_never_matches_inside_common_words(self) -> None:
        ai = skill("skill.ai", "Artificial Intelligence (AI)", ["ai"])
        text = "<p>email, said, train, available, main, again, detail</p>"
        result = match_job(parsed_job(description=text), make_taxonomy(ai))
        assert result.evidence_status == "no_evidence"

    def test_ai_matches_only_standalone_occurrences(self) -> None:
        ai = skill("skill.ai", "Artificial Intelligence (AI)", ["ai"])
        result = match_job(parsed_job(description="<p>AI systems and ai-native apps</p>"), make_taxonomy(ai))
        assert result.skills == ("skill.ai",)
        assert result.evidence[0].occurrence_count == 2


class TestPunctuationAndConnectors:
    def test_cpp_matches_punctuation_form(self) -> None:
        result = match_job(parsed_job(description="<p>C++ developer</p>"), make_taxonomy(CPP))
        assert result.skills == ("skill.cpp",)

    def test_cpp_versioned_spelling_is_not_matched(self) -> None:
        # Comportamiento conservador documentado de 0.1.0: 'C++17' no coincide con 'c++'.
        result = match_job(parsed_job(description="<p>C++17 developer</p>"), make_taxonomy(CPP))
        assert result.evidence_status == "no_evidence"

    def test_cpp_text_alias_matches(self) -> None:
        result = match_job(parsed_job(description="<p>modern cpp</p>"), make_taxonomy(CPP))
        assert result.skills == ("skill.cpp",)
        assert result.evidence[0].matched_term == "cpp"
        assert result.evidence[0].term_type == "alias"

    def test_csharp_matches_with_dot_net_suffix(self) -> None:
        result = match_job(parsed_job(description="<p>C#.NET engineer</p>"), make_taxonomy(CSHARP))
        assert result.skills == ("skill.csharp",)

    def test_hyphen_variant_matches_multiword_alias(self) -> None:
        result = match_job(
            parsed_job(description="<p>machine-learning workflows</p>"), make_taxonomy(MACHINE_LEARNING)
        )
        assert result.skills == ("skill.machine_learning",)

    def test_underscore_variant_matches_multiword_alias(self) -> None:
        result = match_job(
            parsed_job(description="<p>machine_learning pipelines</p>"), make_taxonomy(MACHINE_LEARNING)
        )
        assert result.skills == ("skill.machine_learning",)

    def test_n8n_matches_literal_and_domain_form(self) -> None:
        n8n = skill("skill.n8n", "n8n", ["n8n"])
        result = match_job(parsed_job(description="<p>automation with n8n.io</p>"), make_taxonomy(n8n))
        assert result.skills == ("skill.n8n",)

    def test_sso_long_alias_matches_hyphenated_text(self) -> None:
        sso = skill("skill.sso", "SSO", keywords=["sso"], aliases=["single sign on"])
        result = match_job(
            parsed_job(description="<p>SSO/SAML and single sign-on support</p>"), make_taxonomy(sso)
        )
        assert result.skills == ("skill.sso",)
        assert [(e.matched_term, e.term_type) for e in result.evidence] == [
            ("sso", "keyword"),
            ("single sign on", "alias"),
        ]

    def test_rbac_long_alias_and_short_alias_dedupe_to_one_skill(self) -> None:
        rbac = skill("skill.rbac", "RBAC", keywords=["rbac"], aliases=["role based access control"])
        result = match_job(
            parsed_job(description="<p>role-based access control (RBAC)</p>"), make_taxonomy(rbac)
        )
        assert result.skills == ("skill.rbac",)
        assert len(result.evidence) == 2
        # La iteración de términos sigue el orden de definición: primero keywords, luego aliases.
        assert result.evidence[0].matched_term == "rbac"
        assert result.evidence[0].term_type == "keyword"
        assert result.evidence[1].matched_term == "role based access control"
        assert result.evidence[1].term_type == "alias"


class TestHtmlHandling:
    def test_tags_stripped_and_entities_unescaped(self) -> None:
        text = visible_text("<p>We use <strong>Python</strong> &amp;amp; more</p>")
        assert text == "We use Python &amp; more"
        assert "<" not in text and ">" not in text

    def test_matching_uses_visible_text_of_html_description(self) -> None:
        result = match_job(
            parsed_job(description="<p>We use <strong>Python</strong> &amp; React</p>"),
            make_taxonomy(PYTHON, skill("skill.react", "React", ["react"])),
        )
        assert result.skills == ("skill.python", "skill.react")

    def test_html_to_visible_text_collapses_whitespace(self) -> None:
        text = visible_text("<p>Python\n   \n React</p>")
        assert text == "Python React"


class TestDeduplication:
    def test_duplicate_occurrences_collapse_with_count(self) -> None:
        result = match_job(
            parsed_job(description="<p>Python and more Python</p>"), make_taxonomy(PYTHON)
        )
        assert result.skills == ("skill.python",)
        assert len(result.evidence) == 1
        entry = result.evidence[0]
        assert entry.occurrence_count == 2
        assert entry.matched_term == "python"
        assert entry.term_type == "keyword"

    def test_same_skill_in_two_fields_is_one_skill_two_evidence_entries(self) -> None:
        job = parsed_job(title="Python Engineer", description="<p>Python expert</p>")
        result = match_job(job, make_taxonomy(PYTHON))
        assert result.skills == ("skill.python",)
        assert {entry.field for entry in result.evidence} == {"title_raw", "description_html_raw"}

    def test_two_terms_of_same_skill_in_one_field(self) -> None:
        job = parsed_job(description="<p>machine learning and ML systems</p>")
        result = match_job(job, make_taxonomy(MACHINE_LEARNING))
        assert result.skills == ("skill.machine_learning",)
        entries = [(entry.matched_term, entry.term_type) for entry in result.evidence]
        assert entries == [("machine learning", "keyword"), ("ml", "alias")]

    def test_keywords_iterated_before_aliases(self) -> None:
        # Aunque 'ml' aparece antes en el texto, el término de palabra clave se
        # itera primero, así el orden de la evidencia sigue siendo determinista.
        job = parsed_job(description="<p>ML and machine learning systems</p>")
        result = match_job(job, make_taxonomy(MACHINE_LEARNING))
        entries = [(entry.matched_term, entry.term_type) for entry in result.evidence]
        assert entries == [("machine learning", "keyword"), ("ml", "alias")]


class TestMissingFields:
    def test_missing_excerpt_skipped_and_reported(self) -> None:
        job = parsed_job(excerpt=None, description="<p>Python</p>")
        result = match_job(job, make_taxonomy(PYTHON))
        assert "excerpt_raw" in result.skipped_fields
        assert "excerpt_raw" not in result.searched_fields
        assert "description_html_raw" in result.searched_fields

    def test_empty_categories_skipped_and_reported(self) -> None:
        job = parsed_job(categories=[], description="<p>Python</p>")
        result = match_job(job, make_taxonomy(PYTHON))
        assert "categories_raw" in result.skipped_fields

    def test_searched_and_skipped_partition_fields(self) -> None:
        job = parsed_job(excerpt=None, description="<p>Python</p>")
        result = match_job(job, make_taxonomy(PYTHON))
        assert set(result.searched_fields) | set(result.skipped_fields) == set(SEARCHED_FIELDS)
        assert set(result.searched_fields) & set(result.skipped_fields) == set()

    def test_field_text_returns_none_for_missing_or_empty(self) -> None:
        job = parsed_job(excerpt=None, description="", title="", categories=[])
        assert field_text(job, "title_raw") is None
        assert field_text(job, "excerpt_raw") is None
        assert field_text(job, "categories_raw") is None
        assert field_text(job, "description_html_raw") is None


class TestNoEvidence:
    def test_no_match_is_explicit_no_evidence(self) -> None:
        job = parsed_job(description="<p>We are hiring a bilingual writer</p>")
        result = match_job(job, make_taxonomy(PYTHON))
        assert result.evidence_status == "no_evidence"
        assert result.skills == ()
        assert result.evidence == ()

    def test_excerpt_contains_the_match(self) -> None:
        result = match_job(
            parsed_job(description="<p>We are looking for a Python developer today</p>"),
            make_taxonomy(PYTHON),
        )
        entry = result.evidence[0]
        assert "Python" in entry.excerpt
        assert len(entry.excerpt) <= 2 * 30 + len("python") + 2  # ventana de contexto + puntos suspensivos


class TestDeterminism:
    def test_repeated_matching_is_identical(self) -> None:
        job = parsed_job(
            title="ML Engineer",
            excerpt="Python and PyTorch",
            description="<p>machine learning with python</p>",
        )
        taxonomy = make_taxonomy(MACHINE_LEARNING, PYTHON, skill("skill.pytorch", "PyTorch", ["pytorch"]))
        first = match_job(job, taxonomy)
        second = match_job(job, taxonomy)
        assert first == second

    def test_evidence_ordering_field_then_taxonomy(self) -> None:
        job = parsed_job(
            title="Python Engineer",
            excerpt="pytorch expert",
            description="<p>machine learning systems</p>",
        )
        taxonomy = make_taxonomy(MACHINE_LEARNING, PYTHON, skill("skill.pytorch", "PyTorch", ["pytorch"]))
        result = match_job(job, taxonomy)
        assert [e.skill_id for e in result.evidence] == [
            "skill.python",  # title_raw
            "skill.pytorch",  # excerpt_raw
            "skill.machine_learning",  # description_html_raw
        ]
        assert [e.field for e in result.evidence] == [
            "title_raw",
            "excerpt_raw",
            "description_html_raw",
        ]
        assert result.skills == ("skill.python", "skill.pytorch", "skill.machine_learning")

    def test_taxonomy_version_carried_into_result(self) -> None:
        result = match_job(parsed_job(description="<p>Python</p>"), make_taxonomy(PYTHON))
        assert result.taxonomy_version == "test-taxonomy-0.1.0"

    def test_matcher_version_constant(self) -> None:
        assert MATCHER_VERSION == "keyword-baseline-0.1.0"

    def test_term_pattern_is_deterministic(self) -> None:
        assert term_pattern("machine learning").pattern == term_pattern("machine learning").pattern
        assert term_pattern("c++").pattern == r"(?<![\w])c\+\+(?![\w])"
