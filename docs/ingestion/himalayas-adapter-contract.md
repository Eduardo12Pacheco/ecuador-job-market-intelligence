# Contrato de ingesta de Himalayas

Estado: aprobado para el contrato del MVP. Este documento define la forma canónica del registro y el primer contrato del adaptador de Himalayas. El adaptador y la persistencia local opcional de páginas crudas y manifiestos están implementados y verificados offline, y existe una ruta de captura acotada de una sola página (`HimalayaAdapter.collect_and_persist_page`) implementada, probada offline y ejecutada una vez contra la API en vivo. La validación cubre el fixture local de la página 1 y una captura en vivo autorizada de la página 1; pasan 126 pruebas. No se ha capturado ni publicado ningún feed completo como snapshot completo, y este proyecto no afirma representar todo el mercado laboral.

## Decisión

La primera línea base recolectará el feed completo de empleos remotos desde `https://himalayas.app/jobs/api`, página por página, sin filtros de palabras clave. La relevancia de Ecuador se clasificará a partir de `locationRestrictions`; los datos de zonas horarias nunca se usarán como evidencia de elegibilidad geográfica.

El adaptador conservará las respuestas crudas exactas de la API y los metadatos de recolección antes de producir registros canónicos. La línea base sigue siendo Python-primero, determinista, testeable offline y libre de LLMs, embeddings, agentes e infraestructura cloud.

## Ruta rápida

1. Solicitar el endpoint de navegación documentado con `limit=20` y valores crecientes de `offset`.
2. Persistir cada respuesta exitosa como página cruda exacta más un manifiesto de recolección.
3. Validar la forma de la respuesta, el avance de la paginación, las marcas de tiempo de la fuente y los identificadores estables.
4. Normalizar cada empleo al registro canónico de abajo.
5. Clasificar el alcance geográfico y emitir indicadores de calidad; no inferir hechos faltantes.
6. Mantener el conjunto de fixtures completo ejecutable sin acceso a red.

## Estado de la implementación

- **Contrato:** aprobado para el MVP.
- **Implementación local:** el adaptador tipado de Himalayas y la persistencia opcional y acotada de páginas crudas y manifiestos están completos en local, con 126 pruebas offline en verde.
- **Alcance de validación:** el fixture local de la página 1 y una captura en vivo autorizada de la página 1 han sido validados; no se ha capturado ningún feed completo.
- **Captura acotada de una sola página:** una solicitud en vivo autorizada usó `limit=20` y `offset=0`, devolvió 20 registros de `totalCount=94520` y se persistió como captura parcial con bytes crudos y SHA-256 verificados.
- **Captura del feed completo:** pendiente de una decisión de autorización explícita separada y fuera del alcance actual; no se publica ningún snapshot completo.

## Clasificación del alcance

`locationRestrictions` es la fuente del alcance geográfico:

| Valor de la fuente | `location_scope` canónico | Significado |
|---|---|---|
| Lista no vacía que contiene `Ecuador` | `explicit_ec` | La fuente permite explícitamente postulantes en Ecuador. |
| Lista vacía | `worldwide` | Himalayas documenta una lista vacía como disponibilidad mundial. |
| Lista no vacía sin `Ecuador` | `other_country` | La fuente lista restricciones que no incluyen Ecuador. |
| Valor faltante, nulo o malformado | `unknown` | No hay suficiente evidencia de la fuente para clasificar la oferta. |

Los siguientes campos no son prueba geográfica: `timezoneRestrictions`, el idioma, la ubicación de la empresa, la moneda ni el texto de la descripción del empleo. Pueden conservarse como evidencia y usarse para análisis posteriores, pero no para `location_scope`. No se debe coerzar un valor faltante o nulo de `locationRestrictions` a una lista vacía; lo faltante/nulo permanece `unknown`, mientras que una lista vacía devuelta explícitamente es `worldwide` según la documentación de la fuente. La implementación debe re-verificar este significado documentado y registrar cualquier divergencia como evento de calidad.

## Esquema del snapshot de recolección

Un snapshot describe una ejecución completa del adaptador. Está separado de los empleos individuales para que `updatedAt` siga siendo un valor a nivel de API.

| Campo | Tipo | Obligatorio | Significado |
|---|---|---|---:|---|
| `snapshot_id` | string | sí | Identificador estable de esta ejecución de recolección. |
| `source` | string | sí | `himalayas`. |
| `endpoint` | URL | sí | El endpoint de navegación documentado. |
| `request_params` | objeto JSON | sí | `limit`, `offset` y cualquier parámetro de solicitud explícito. |
| `captured_at` | marca de tiempo UTC | sí | Cuándo se recibió la respuesta. |
| `http_status` | integer | sí | Estado HTTP de la respuesta de la página. |
| `content_type` | string | sí | Tipo de contenido de la respuesta. |
| `api_updated_at_raw` | integer/string/null | sí | `updatedAt` de nivel superior exactamente como lo devolvió la API. |
| `api_updated_at_utc` | marca de tiempo UTC/null | sí | Momento de refresco de la API interpretado, si el parseo tiene éxito. |
| `api_timestamp_unit` | enum | sí | Observado: `unix_seconds`, `unix_milliseconds` o `unknown`. |
| `total_count` | integer | sí | Total del feed reportado por la fuente. |
| `page_count` | integer | sí | Número de páginas recolectadas. |
| `job_count` | integer | sí | Número de empleos crudos recolectados. |
| `raw_page_paths` | list[string] | sí | Rutas locales al repositorio de las respuestas crudas exactas. |
| `raw_page_sha256` | list[string] | sí | Hash SHA-256 de cada página cruda exacta, en orden de recolección. |
| `run_status` | enum | sí | `complete`, `partial` o `failed`. |
| `adapter_version` | string | sí | Versión del adaptador que produjo el snapshot. |

Un archivo de página cruda debe conservar el cuerpo JSON original. El manifiesto registra la solicitud, la respuesta, la interpretación de marcas de tiempo y los hashes sin reemplazar la evidencia cruda.

## Esquema canónico del empleo

El registro canónico es una proyección normalizada de un empleo de la fuente. Los valores crudos de la fuente siguen disponibles; la normalización nunca debe sobrescribirlos.

| Campo | Tipo | Obligatorio | Significado |
|---|---|---|---:|---|
| `canonical_id` | string | sí | Hash determinista de `source` y `source_id`. |
| `source` | string | sí | `himalayas`. |
| `source_id` | string | sí | `guid` de Himalayas. |
| `source_url` | URL | sí | URL del anuncio en la fuente. Para el payload actual, es igual a `guid`. |
| `application_url` | URL | sí | `applicationLink` de Himalayas. Conservar por separado incluso cuando es igual a `source_url`. |
| `snapshot_id` | string | sí | Snapshot de recolección que observó este registro. |
| `title_raw` | string | sí | Título original. |
| `company_raw` | string | sí | Nombre original de la empresa. |
| `company_slug_raw` | string/null | no | Slug de la empresa en la fuente. |
| `excerpt_raw` | string/null | no | Extracto de la fuente. |
| `description_html_raw` | string | sí | Descripción HTML original sanitizada. |
| `location_restrictions_raw` | list[string] | sí | Valores originales de restricción por país. |
| `location_scope` | enum | sí | `explicit_ec`, `worldwide`, `other_country` o `unknown`. |
| `timezone_restrictions_raw` | list[number] | no | Valores de zona horaria de la fuente; nunca se usan como prueba de país. |
| `employment_type_raw` | string/null | no | Tipo de empleo original. |
| `seniority_raw` | list[string] | no | Valores originales de senioridad. |
| `categories_raw` | list[string] | no | Categorías originales de la fuente. |
| `salary_min_raw` | number/null | no | Salario mínimo original. |
| `salary_max_raw` | number/null | no | Salario máximo original. |
| `salary_period_raw` | string/null | no | Período de pago original. |
| `currency_raw` | string/null | no | Moneda original. |
| `published_at_raw` | integer/string/null | sí | `pubDate` original. |
| `published_at_utc` | marca de tiempo UTC/null | sí | Momento de publicación interpretado. |
| `expires_at_raw` | integer/string/null | sí | `expiryDate` original. |
| `expires_at_utc` | marca de tiempo UTC/null | sí | Momento de expiración interpretado. |
| `first_seen_at` | marca de tiempo UTC | sí | Primera observación en este proyecto. |
| `last_seen_at` | marca de tiempo UTC | sí | Observación exitosa más reciente. |
| `observation_status` | enum | sí | `active`, `expired`, `missing` o `invalid`. |
| `quality_flags` | list[string] | sí | Hallazgos explícitos de calidad de datos. |

Los campos derivados — como la descripción en texto plano, la familia de rol normalizada, el tipo de empleo normalizado, la conversión de salario y las coincidencias de tecnología — pertenecen a capas limpias posteriores. Deben conservar las entradas crudas y la versión de transformación.

## Contrato de marcas de tiempo

El fixture actual contiene valores de 10 dígitos en segundos Unix para `updatedAt`, `pubDate` y `expiryDate`, aunque la documentación publicada contiene una redacción inconsistente sobre milisegundos. El adaptador debe:

- conservar los valores numéricos originales;
- detectar segundos frente a milisegundos de forma defensiva;
- convertir los valores interpretados a UTC;
- registrar la unidad detectada en el manifiesto del snapshot;
- rechazar fechas inverosímiles en lugar de interpretarlas en silencio;
- exigir que todos los campos numéricos de marcas de tiempo de un snapshot usen la misma unidad detectada; una divergencia es un evento de calidad;
- tratar el `updatedAt` de nivel superior como metadatos de refresco de la API, nunca como fecha de modificación de un empleo individual.

## Contrato de paginación

El adaptador debe usar el feed de navegación completo, no búsquedas por palabras clave:

- Endpoint: `https://himalayas.app/jobs/api`.
- Solicitar `limit=20`, que es el máximo documentado actual; nunca exceder la documentación de la fuente.
- Empezar en `offset=0` y avanzar por el número de registros devueltos o por el límite solicitado.
- Detenerse solo cuando el rango recolectado alcance `totalCount`.
- Conservar cada página y sus parámetros de solicitud.
- Detectar una firma de página repetida, un offset repetido o un cursor que no avanza y fallar la ejecución como `partial` en lugar de hacer un bucle.
- Tratar un `totalCount` o `updatedAt` cambiado durante una ejecución como evento de calidad.
- Respetar la cadencia documentada de refresco de 24 horas y los límites de tasa; no hacer sondeos repetidos con fines de experimentación.

La primera ejecución del feed completo clasificará todas las ofertas devueltas en los cuatro valores de `location_scope`. No presentará el resultado como un conteo de todo el mercado ecuatoriano.

## Contrato de identidad y deduplicación

- `guid` es el identificador de la fuente para Himalayas y actualmente es igual a `applicationLink`.
- Conservar ambos valores porque las fuentes futuras pueden distinguir la identidad del anuncio de la URL de postulación.
- Dentro de Himalayas, los valores de `guid` duplicados deben colapsar a un empleo canónico conservando todas las observaciones.
- Una futura clave de deduplicación entre fuentes puede combinar URL canónica, empresa/título normalizado y hash de descripción. No debe reemplazar los identificadores de la fuente.
- Una tasa de duplicados de una página o una fuente no debe reportarse como tasa de duplicados entre fuentes.

## Comportamiento ante fallos

El adaptador debe fallar de forma cerrada para un snapshot completo cuando:

- la respuesta HTTP no es exitosa;
- el JSON es inválido;
- `jobs` no es una lista;
- faltan o son inválidos los campos de paginación de nivel superior obligatorios;
- la paginación no avanza;
- falta una identidad de empleo obligatoria;
- el parseo de marcas de tiempo produce un valor inverosímil.

Un `source_id` faltante invalida el registro y marca el snapshot `partial`. Un campo marcado como obligatorio en el esquema canónico que falte se conserva en la evidencia cruda, recibe un indicador de calidad y `observation_status=invalid`, y también marca el snapshot canónico `partial`; no debe rellenarse en silencio con un valor inferido. Las páginas exitosas pueden permanecer como evidencia cruda, pero un snapshot parcial no debe publicarse como conjunto de datos analítico completo.

## Atribución y límites de acceso

- Usar solo el endpoint de API documentado.
- No rastrear `/apply` ni páginas HTML de empleos como parte de la ingesta.
- Mantener un enlace visible de atribución a Himalayas dondequiera que se muestren datos de empleos.
- No enviar anuncios de Himalayas a bolsas de trabajo de terceros.
- No recolectar perfiles de candidatos, currículos, datos de postulación ni información de contacto.
- Almacenar URLs de la fuente y marcas de tiempo de recolección para trazabilidad.

## Lista de verificación de aceptación antes de implementar

- [ ] El esquema canónico distingue `explicit_ec`, `worldwide`, `other_country` y `unknown`.
- [ ] La primera ejecución usa `/jobs/api` con paginación, no búsqueda por palabras clave.
- [ ] La página cruda y el manifiesto de recolección conservan la evidencia exacta y los metadatos de la solicitud.
- [ ] `updatedAt` se almacena a nivel de snapshot y no se interpreta como tiempo de modificación por empleo.
- [ ] Las marcas de tiempo en segundos Unix están cubiertas por pruebas offline, incluida la discrepancia de la documentación.
- [ ] Están definidas las comprobaciones de identidad duplicada y de página repetida.
- [ ] Las ejecuciones parciales no pueden confundirse con conjuntos de datos completos.
- [ ] La atribución y la restricción de no-envío-a-terceros están representadas en la configuración de la fuente.
- [ ] No se requieren LLM, embeddings, agentes ni servicios cloud.

## Captura acotada de una sola página (opt-in)

Junto al adaptador de feed completo, el contrato ofrece una ruta de captura
estrictamente acotada y opt-in para una sola página:

- Punto de entrada: `HimalayaAdapter.collect_and_persist_page(store=...)`,
  donde `store` es un `LocalCaptureStore`. Esta ruta está separada de
  `collect_complete_feed`; nunca cambia la semántica del feed completo.
- Emite exactamente un GET de `https://himalayas.app/jobs/api` con
  `limit=20&offset=0`. Los parámetros son fijos y no seleccionables por quien
  llama.
- Nunca pagina, nunca reintenta y nunca llama a `/jobs/api/search`.
- Reutiliza el parseo de respuestas existente y la construcción de `RawPage`:
  los bytes exactos de la respuesta, los parámetros de solicitud, el estado
  HTTP, el tipo de contenido, el `updatedAt` crudo e interpretado y los conteos
  total/devolución se conservan sin cambios.
- Persiste exactamente una página cruda más el manifiesto a través de
  `LocalCaptureStore.persist_page` con `complete: false` y el aviso
  `bounded_single_page_capture`, registrando endpoint, parámetros de solicitud
  (incluidos `limit`/`offset`), estado HTTP, tipo de contenido exacto, marca de
  tiempo de captura UTC, `updatedAt` crudo/interpretado, conteo total, conteo
  de registros devueltos, SHA-256 crudo y ruta cruda relativa al repositorio,
  versión del adaptador, URL de atribución, el aviso y el estado parcial
  (`complete: false`). Una sola página es evidencia, nunca una captura de feed
  completo ni una afirmación de mercado completo.
- Los fallos cierran antes de cualquier escritura: los errores de
  solicitud/transporte y las respuestas no-2xx elevan `HimalayasHttpError`, las
  respuestas malformadas elevan `MalformedResponseError` (o `TimestampError`),
  los desajustes de offset elevan `PaginationError` y los rechazos de
  persistencia (por ejemplo `OverwriteError`) se propagan sin cambios. No hay
  reintento automático.
- El método devuelve un `PageCaptureResult` tipado que transporta el `RawPage`,
  el recibo de persistencia `CaptureResult` (rutas deterministas, id de
  captura, SHA-256 crudo) y el sobre del manifiesto (fuente, endpoint, versión
  del adaptador, URL de atribución, `run_status=partial`, aviso), de modo que
  el resultado se pueda informar y los bytes/hash/manifiesto se puedan verificar
  sin otra solicitud.

Estado: implementado y cubierto por pruebas offline
(`tests/test_bounded_capture.py`). Se ejecutó una solicitud en vivo autorizada
con `limit=20` y `offset=0`; devolvió 20 registros, escribió 84 341 bytes crudos
y produjo un SHA-256 verificado de
`0370798f7af4b0e39ab92fd0d486577f58cdd415812e612d6b86657ac07ab101`.
La ruta cruda es
`data/raw/himalayas/jobs_api_6b8244a52a80/00000000.json` y la ruta del manifiesto
es `data/manifests/himalayas/jobs_api_6b8244a52a80/00000000.manifest.json`.
No se hizo una segunda solicitud. La captura del feed completo sigue fuera del
alcance de esta ruta.

## Siguiente paso

La captura autorizada de una sola página está completa. Cualquier página o
captura adicional requiere una autorización explícita separada; no se permite
ninguna continuación automática. La captura del feed completo sigue fuera del
alcance actual y requiere una decisión separada.
