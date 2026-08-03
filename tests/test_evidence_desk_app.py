"""Pruebas offline de la mesa de evidencia en español.

La superficie actual está revisada por humanos y es final solo para la muestra
curada; los tokens históricos v0.2.0 quedan en el apéndice técnico.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

streamlit = pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
APP = REPO_ROOT / "app" / "evidence_desk.py"
STREAMLIT_CONFIG = REPO_ROOT / ".streamlit" / "config.toml"

TABS_ES = (
    "Resumen",
    "Panorama de habilidades",
    "Explorar ofertas",
    "Auditoría de evaluación",
    "Proveniencia y límites",
)

ADVERTENCIA = "Muestra curada · métricas finales para 20 ofertas · no representa el mercado completo"
LIMITE = (
    "Esto no es un estudio del mercado laboral ecuatoriano. "
    "Es una muestra de 20 ofertas de una sola página y una sola fuente."
)

# Tokens de implementación que solo pueden aparecer dentro de «Detalles técnicos»:
# identificadores de artefactos, versiones, campos crudos, estados de máquina y
# las siglas de la matriz de contingencia.
TECHNICAL_TOKEN_PATTERNS = [
    re.compile(r"\bdraft_second_pass\b"),
    re.compile(r"\bhuman_review_required\b"),
    re.compile(r"\bhuman_review_complete\b"),
    re.compile(r"\bannotation_status\b"),
    re.compile(r"\bcomplete: false\b"),
    re.compile(r"\bcap_0370798f7af4b0e3\b"),
    re.compile(r"\btechnical-skills-0\.1\.0\b"),
    re.compile(r"\bkeyword-baseline-0\.1\.0\b"),
    re.compile(r"\bskill-extraction-review-0\.2\.0\b"),
    re.compile(r"\btitle_raw\b"),
    re.compile(r"\bexcerpt_raw\b"),
    re.compile(r"\bcategories_raw\b"),
    re.compile(r"\bdescription_html_raw\b"),
    re.compile(r"\bTP\b"),
    re.compile(r"\bFP\b"),
    re.compile(r"\bFN\b"),
    re.compile(r"\bTN\b"),
]

# Etiquetas de interfaz en inglés que no deben aparecer en la superficie pública.
FORBIDDEN_ENGLISH = (
    "Overview",
    "Skill landscape",
    "Job explorer",
    "Evaluation & audit",
    "Provenance & limits",
    "Job records",
    "Taxonomy skills",
    "Annotated candidate pairs",
    "Human-review items pending",
    "Evidence strip",
    "demo-ready",
    "Not stated",
    "Not disclosed",
    "Untitled role",
    "Unknown company",
    "Provisional",
    "Precision",
    "supported",
    "not_supported",
    "uncertain",
)


def _render() -> AppTest:
    at = AppTest.from_file(str(APP), default_timeout=30)
    at.run()
    return at


def _strip_tags(value: str) -> str:
    """Texto visible aproximado: quita las etiquetas HTML (no la copia)."""
    return re.sub(r"<[^>]+>", " ", value)


def _ui_copy(at: AppTest) -> str:
    """Copia propia de la interfaz: texto público sin las líneas de datos.

    Los motivos y las preguntas de revisión son contenido de los artefactos
    (se conservan verbatim como datos); esta función los excluye para poder
    comprobar que la copia redactada por la interfaz nunca usa palabras
    inglesas ni tokens técnicos.
    """
    parts: list[str] = []

    def walk(block: object) -> None:
        children = getattr(block, "children", None)
        if not isinstance(children, dict):
            return
        for el in children.values():
            if getattr(el, "type", "") == "expander":
                continue
            if getattr(el, "type", "") == "markdown":
                if el.value.startswith("<style>"):
                    continue
                text = _strip_tags(el.value)
                if text.startswith(("**Motivo", "**Segunda pasada:", "**Primera pasada:")):
                    continue
                if "Decisión necesaria:" in text:
                    continue
                parts.append(text)
            elif getattr(el, "type", "") == "caption":
                parts.append(_strip_tags(el.value))
            walk(el)

    walk(at.main)
    parts.extend(_strip_tags(m.value) for m in at.sidebar.markdown)
    return " ".join(parts)


def _technical_region_lines(source: str) -> tuple[int, int]:
    """Líneas [inicio, fin) de la función «Detalles técnicos» del script."""
    lines = source.splitlines()
    start = next(
        i for i, line in enumerate(lines) if line.startswith("def _render_technical_details")
    )
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith("def ")),
        len(lines),
    )
    return start, end


class TestEstructuraPublica:
    """La estructura pública: pestañas en español, tesis, advertencia y límites."""

    def test_app_renders_without_exception(self) -> None:
        at = _render()
        assert not at.exception
        assert [t.label for t in at.tabs] == list(TABS_ES)

    def test_configuracion_de_streamlit_es_minima(self) -> None:
        config = STREAMLIT_CONFIG.read_text(encoding="utf-8")
        assert '[client]' in config
        assert 'toolbarMode = "minimal"' in config
        assert 'showErrorDetails = "none"' in config
        assert '[browser]' in config
        assert 'gatherUsageStats = false' in config
        assert '[server]' in config
        assert 'headless = true' in config

    def test_todas_las_pestanas_renderizan_contenido(self) -> None:
        at = _render()
        md = " ".join(m.value for m in at.markdown)
        for heading in (
            "## Las cifras, explicadas",
            "### Cómo funciona el buscador",
            "### Lo que detectó el buscador",
            "### Matriz de contingencia (final)",
            "### Origen de los datos",
        ):
            assert heading in md, heading

    def test_primer_viewport_titulo_etiquetas_y_conceptos(self) -> None:
        at = _render()
        md = _ui_copy(at)
        for required in (
            "Inteligencia del mercado laboral ecuatoriano",
            "Mesa de evidencia",
            "Ofertas analizadas",
            "Habilidades de la taxonomía",
            "Pares revisados",
            "Decisiones humanas resueltas",
            "Precisión final · muestra curada",
            "Recall final · muestra curada",
            "F1 final · muestra curada",
        ):
            assert required in md, required

    def test_advertencia_de_muestra_curada_prominente(self) -> None:
        at = _render()
        assert ADVERTENCIA in _ui_copy(at)

    def test_limite_de_muestra_presente_y_claro(self) -> None:
        at = _render()
        assert LIMITE in _ui_copy(at)

    def test_estado_actual_de_revision_humana(self) -> None:
        at = _render()
        md = _ui_copy(at)
        assert "Revisión humana completa" in md
        assert "Evaluación final · muestra curada" in md
        assert "demo-ready" not in md
        assert "7 decisiones humanas pendientes" not in md

    def test_cifras_y_metricas_requeridas_presentes(self) -> None:
        at = _render()
        md = _ui_copy(at)
        for value in ("20", "37", "740", "40", "16", "684", "0,7143", "1,0", "0,8333", "7"):
            assert value in md, value
        for phrase in (
            "Verdaderos positivos",
            "Falsos positivos",
            "Falsos negativos",
            "Verdaderos negativos",
        ):
            assert phrase in md, phrase
        assert "7 decisiones humanas resueltas" in md
        assert "7 decisiones humanas pendientes" not in md

    def test_veredictos_traducidos_sin_enumerado_en_ingles(self) -> None:
        at = _render()
        md = _ui_copy(at)
        for verdict in ("respaldado", "no respaldado"):
            assert verdict in md, verdict
        assert "0 inciertos" in md
        for token in ("supported", "not_supported", "uncertain"):
            assert token not in md, token

    def test_sin_etiquetas_de_interfaz_en_ingles(self) -> None:
        at = _render()
        md = _ui_copy(at)
        for label in FORBIDDEN_ENGLISH:
            assert label not in md, label

    def test_motivos_y_preguntas_de_revision_se_presentan_en_espanol(self) -> None:
        at = _render()
        md = " ".join(m.value for m in at.markdown)
        assert "Caso de requisito negativo" in md
        assert "Las grabaciones se usan después en aplicaciones de aprendizaje automático" in md
        assert "Decisión necesaria:" not in md
        assert "Negative-requirement case:" not in md
        assert "First draft:" not in md


class TestTokensTecnicos:
    """Los tokens de implementación solo viven dentro de «Detalles técnicos»."""

    def test_tokens_solo_en_la_seccion_tecnica_a_nivel_de_fuente(self) -> None:
        source = APP.read_text(encoding="utf-8")
        start, end = _technical_region_lines(source)
        lines = source.splitlines()
        region_text = "\n".join(lines[start:end])
        outside_text = "\n".join(lines[:start] + lines[end:])
        # La sección técnica contiene literalmente una muestra representativa.
        assert re.search(r"\bdraft_second_pass\b", region_text) is not None
        assert re.search(r"\bTP\b", region_text) is not None
        # Ningún token aparece fuera de la sección técnica.
        for pattern in TECHNICAL_TOKEN_PATTERNS:
            assert pattern.search(outside_text) is None, pattern.pattern

    def test_tokens_ausentes_de_la_superficie_publica_renderizada(self) -> None:
        at = _render()
        md = _ui_copy(at)
        for pattern in TECHNICAL_TOKEN_PATTERNS:
            assert pattern.search(md) is None, pattern.pattern

    def test_detalles_tecnicos_existe_como_expander(self) -> None:
        at = _render()
        assert any(e.label == "Detalles técnicos" for e in at.expander)

    def test_barra_lateral_compacta_sin_tokens(self) -> None:
        at = _render()
        md = " ".join(m.value for m in at.sidebar.markdown)
        assert "Himalayas" in md
        for token in ("annotation_status", "draft_second_pass", "cap_0370", "data/"):
            assert token not in md, token
        for label in ("Status", "Versions", "Artifacts read"):
            assert label not in md, label


class TestExploradorDeOfertas:
    """El explorador ofrece las 20 ofertas y renderiza evidencia sin excepción."""

    def test_ofrece_las_20_ofertas_y_renderiza_su_evidencia(self) -> None:
        at = _render()
        assert len(at.selectbox) == 1
        assert len(at.selectbox[0].options) == 20
        # Busca una oferta cuyos veredictos lleven citas de la segunda pasada y
        # comprueba que la evidencia se renderiza sin excepción.
        verified = False
        for index in range(20):
            at.selectbox[0].select_index(index)
            at.run()
            assert not at.exception
            md = _ui_copy(at)
            if "cita verificada" in md and "[" in md and "“" in md:
                verified = True
                break
        assert verified, "ninguna oferta mostró una cita verificada con desplazamientos"


class TestAuditoria:
    """La auditoría muestra los falsos positivos y las aprobaciones humanas."""

    def test_dieciseis_falsos_positivos_y_siete_aprobaciones_como_expansores(self) -> None:
        at = _render()
        fp_expanders = [e for e in at.expander if e.label.endswith("(falso positivo)")]
        approved_expanders = [
            e for e in at.expander if e.label.endswith("(decisión humana aprobada)")
        ]
        assert len(fp_expanders) == 16
        assert len(approved_expanders) == 7

    def test_matriz_de_contingencia_con_nombres_humanos(self) -> None:
        at = _render()
        md = _ui_copy(at)
        for cell in (
            "Verdaderos positivos",
            "Falsos positivos",
            "Falsos negativos",
            "Verdaderos negativos",
            "Inciertos",
        ):
            assert cell in md, cell


class TestConfigStreamlit:
    """Configuración local mínima de Streamlit (publicación de la mesa).

    La mesa se renderiza en local sin la barra de herramientas, sin el menú
    de Deploy y sin recolección de estadísticas de uso; los errores no se
    muestran con detalles internos.
    """

    CONFIG = REPO_ROOT / ".streamlit" / "config.toml"

    def test_config_existe_y_declara_la_publicacion_minima(self) -> None:
        import tomllib

        assert self.CONFIG.is_file(), "falta .streamlit/config.toml"
        with self.CONFIG.open("rb") as fh:
            cfg = tomllib.load(fh)
        assert cfg["client"]["toolbarMode"] == "minimal"
        assert cfg["client"]["showErrorDetails"] == "none"
        assert cfg["browser"]["gatherUsageStats"] is False
        assert cfg["server"]["headless"] is True
