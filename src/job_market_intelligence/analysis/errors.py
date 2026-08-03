"""Errores tipados del paquete de análisis offline.

El paquete de análisis es determinista y de cierre: las violaciones de forma de
la taxonomía, los desajustes de integridad entre una captura persistida y su
manifiesto y las salidas en conflicto elevan errores tipados en lugar de adivinar
en silencio.
"""

from __future__ import annotations


class AnalysisError(Exception):
    """Clase base de todos los fallos del paquete de análisis."""


class TaxonomyError(AnalysisError):
    """El artefacto de taxonomía está malformado o viola las reglas de unicidad."""


class DatasetError(AnalysisError):
    """El conjunto de datos de desarrollo no se puede construir o escribir según lo especificado."""


class DatasetIntegrityError(DatasetError):
    """Una captura persistida contradice su manifiesto (hash, página o reloj)."""


class DescriptiveError(AnalysisError):
    """El contrato del análisis descriptivo está violado.

    Se eleva cuando un conjunto de datos no es el ``development_sample``
    documentado de 20 registros (tipo equivocado, forma de muestra equivocada,
    identidad de snapshot distinta o ``complete: true``), cuando la versión del
    artefacto de taxonomía no coincide con la del conjunto de datos o cuando las
    métricas derivadas contradicen el informe de calidad embebido. El análisis
    descriptivo es de cierre: nunca analiza un conjunto de datos que no sea la
    muestra documentada exacta.
    """


class EvaluationError(AnalysisError):
    """El contrato de la evaluación de borrador de extracción de habilidades está violado.

    Se eleva cuando un artefacto de evaluación de borrador está malformado
    (enumerado de etiquetas inválido, etiquetas ``(source_id, skill_id)``
    duplicadas, forma de evidencia inválida), cuando no anota la muestra de
    desarrollo documentada exacta (tipo de conjunto de datos, identidad de
    snapshot, versión de taxonomía o forma de muestra no coincidentes), cuando
    una etiqueta referencia un id de fuente o un id de habilidad inexistentes,
    cuando una cita/offset de evidencia exacta no reproduce el valor del campo
    del conjunto de datos o cuando el artefacto de evaluación no está serializado
    canónicamente. El evaluador es de cierre: nunca calcula métricas contra un
    conjunto de datos no coincidente ni una cita no verificable.
    """
