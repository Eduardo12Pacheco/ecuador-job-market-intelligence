# Mesa de evidencia — Brief de superficie (histórico v0.2)

> Este brief conserva la dirección de diseño previa a la adjudicación humana.
> La interfaz actual muestra `Revisión humana completa` y métricas finales solo
> para la muestra curada; los textos de validación y provisionalidad descritos
> aquí son históricos.

Destino: `app/evidence_desk.py` (app local de Streamlit).

## Alcance y modo de la visita

- **Alcance:** primera superficie visible y ejecutable del proyecto — una mesa
  de evidencia local de operar/leer sobre los artefactos existentes de la
  muestra de desarrollo, rediseñada como superficie pública profesional en
  español (`Interfaz pública en validación`; nunca declarada `demo-ready`). No
  es una landing page de marketing.
- **Modo de la visita:** operar/leer. La visita la realiza un reclutador,
  revisor técnico o gerente de contratación que debe entender el mecanismo en
  un minuto.
- **Trabajo:** explorar las 20 ofertas capturadas, ver la extracción
  determinista de habilidades técnicas, inspeccionar las citas de evidencia
  exactas y entender qué demuestra — y qué no — la evaluación provisional,
  todo en español profesional llano.

## Audiencia, acción, prueba, restricciones

- **Audiencia:** persona evaluadora del portafolio que no lee código
  (principal); revisor con dominio técnico (secundaria, atendida por el
  expansor «Detalles técnicos»).
- **Acción/tarea:** leer la tesis → verificar las cifras reales → profundizar
  en las habilidades detectadas y las citas exactas de una oferta → leer la
  sección de auditoría → juzgar la evaluación con honestidad.
- **Prueba/contenido:** los cinco artefactos confirmados bajo `data/`
  (conjunto de datos analítico, análisis descriptivo, revisión de segunda
  pasada + informe, taxonomía) más los metadatos de la muestra fuente. Sin
  llamadas externas; el aviso de prototipo y la frase de límite de la muestra
  son prominentes; las métricas provisionales son imposibles de pasar por
  alto.
- **Restricciones:** solo controles y gráficas nativas de Streamlit (sin
  dependencias nuevas); un módulo cargador pequeño y testeable fuera del
  script; estados de datos faltantes elegantes; sin cambios de matcher,
  taxonomía ni artefactos; atribución visible a Himalayas. Los tokens de
  máquina (estados, versiones, identificadores, claves de campos crudos,
  siglas de contingencia) aparecen SOLO dentro del único
  `st.expander("Detalles técnicos")`; los veredictos están traducidos
  (`respaldado`, `no respaldado`, `incierto`) mientras los datos de los
  artefactos permanecen verbatim.

## Dirección elegida (delegada/fijada)

Mesa de evidencia editorial contenida en español: lienzo blanco roto, banda
superior de pizarra profunda, una señal ámbar/terracota reservada a los estados
pendientes o inciertos, secciones con filetes, sans serif del sistema,
monoespaciada solo para citas de evidencia, desplazamientos e identificadores
técnicos, barra lateral reducida (bloque compacto de fuente/atribución), sin
muros de tarjetas genéricos, sin teatro de indicadores, sin degradados ni
emojis decorativos.

- Señal distintiva: la **franja de evidencia** con filetes con las cifras
  locales reales y el sello provisional, más los bloques de cita de la
  evidencia del buscador frente al veredicto de la segunda pasada por oferta.
- La dirección fue fijada por el brief superior; el lanzamiento de semillas de
  concepto queda eximido (la dirección fijada por el brief prevalece sobre el
  lanzamiento).
- Primer viewport: banda superior de pizarra profunda (título, etiqueta de la
  mesa, propósito, atribución de la fuente) → aviso de prototipo (`Prototipo
  local · evaluación provisional · 7 decisiones humanas pendientes`) → tesis →
  llamada al límite de la muestra (`Esto no es un estudio del mercado laboral
  ecuatoriano…`) → franja de evidencia → pestañas (Resumen · Panorama de
  habilidades · Explorar ofertas · Auditoría de evaluación · Proveniencia y
  límites).

## Entrega histórica

Las siete decisiones de revisión descritas en este brief fueron aprobadas y
materializadas en los artefactos v0.3.0. La pestaña de auditoría actual lee ese
estado final; este brief permanece sin cambios como registro del historial de
diseño.
