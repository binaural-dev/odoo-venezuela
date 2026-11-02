# l10n_ve_invoice_digital

## Purpose

Integra la facturación con el proveedor de imprenta digital The Factory HKA (TFHKA): emite digitalmente facturas, notas de débito, notas de crédito, comprobantes de retención y guías de despacho contra la API de TFHKA. Extiende `account.move`, `account.retention` (de `l10n_ve_payment_extension`), `stock.picking`, `res.company` y `res.config.settings`, y agrega el wizard `account.retention.alert.wizard`. Depende de `account`, `l10n_ve_igtf`, `account_debit_note`, `l10n_ve_invoice`, `l10n_ve_iot_mf`, `l10n_ve_stock_account`, `l10n_ve_payment_extension` y `stock`.

## Requirements

### Requirement: Configuración TFHKA por compañía y generación de token

Cada compañía DEBE (MUST) poder configurar sus credenciales TFHKA (`username_tfhka`, `password_tfhka`, `url_tfhka`), el interruptor general `invoice_digital_tfhka` y la validación de secuencia `sequence_validation_tfhka` (por defecto `True`) desde ajustes (campos related con `readonly=False` en `res.config.settings`). El método `generate_token_tfhka` DEBE (MUST) validar que usuario, clave y URL estén configurados, autenticarse contra el endpoint `/Autenticacion` y almacenar el token recibido en `token_auth_tfhka`.

#### Scenario: Credenciales incompletas

- **WHEN** se solicita generar el token sin usuario, clave o URL configurados
- **THEN** se lanza un error indicando el dato faltante y no se llama a la API

#### Scenario: Autenticación exitosa

- **WHEN** la API responde con código 200 y un campo `token`
- **THEN** el token se guarda en `token_auth_tfhka` de la compañía

### Requirement: Renovación automática del token expirado

Cuando una llamada a la API TFHKA (método `call_tfhka_api`, duplicado en factura, retención y guía) recibe HTTP 401, el sistema DEBE (MUST) regenerar el token con `generate_token_tfhka` y reintentar la misma llamada de forma recursiva sin límite de intentos; cualquier otro error HTTP o de conexión DEBE (MUST) abortar la operación con un `UserError` visible al usuario. En las respuestas HTTP 200 el éxito se determina por `codigo == "200"` **como cadena** (a diferencia de `generate_token_tfhka`, que compara `codigo` con el entero `200`), y el par `codigo == "203"` con `validaciones` se interpreta como "sin documentos previos" devolviendo 0 únicamente para el endpoint `ultimo_documento`; cualquier otro `codigo` DEBE (MUST) abortar con el mensaje y las validaciones de la API. Antes de cualquier llamada, la URL y el token de la compañía deben estar configurados (`get_base_url` / `get_token`).

#### Scenario: Token expirado

- **WHEN** la API responde 401 durante una emisión
- **THEN** se genera un token nuevo y se reintenta la petición con el token renovado

#### Scenario: Error de conexión

- **WHEN** la petición a la API falla por un error de red
- **THEN** se lanza un `UserError` con el detalle y el documento no se marca como digitalizado

### Requirement: Cola de digitalización TFHKA con cron unificado

`account.move`, `account.retention` y `stock.picking` DEBEN (MUST) heredar el modelo abstracto `tfhka.digitalization.mixin`, que agrega el campo `tfhka_digitalization_state` (`none / queued / processing / success / error / data_error / not_applicable`) y `tfhka_queued_at`. Confirmar o publicar un documento elegible DEBE (MUST) únicamente encolarlo (`_tfhka_enqueue_digitalization`, un `write` de campo sin llamada HTTP) y NO DEBE (MUST NOT) emitirlo inline en ese mismo request. Un cron unificado (`_tfhka_cron_process_queue_multi`, corriendo cada minuto sobre `account.move`, `account.retention` y `stock.picking`) es el único punto que llama a TFHKA: por cada modelo procesa los documentos en estado `queued` en orden `tfhka_queued_at asc, id asc` (FIFO, más antiguo primero), intercalando un documento de cada modelo por vuelta en vez de agotar la cola de un modelo antes de pasar al siguiente. Para un modelo dado, NUNCA DEBE (MUST NOT) haber más de un documento en `processing` ni más de uno en `error`/`data_error` a la vez: si el modelo ya tiene un documento en `error` o `data_error`, el cron NO DEBE (MUST NOT) procesar el resto de su cola hasta que ese documento se resuelva (reintento exitoso), sin afectar la cola de los otros modelos. Si la digitalización de un documento falla por el error de negocio de límite de tasa de TFHKA, el sistema DEBE (MUST) reintentar una única vez tras esperar `RATE_LIMIT_RETRY_WAIT` segundos antes de marcarlo `error`.

#### Scenario: Confirmar una factura la encola, no la emite

- **WHEN** se publica una factura elegible para digitalización
- **THEN** queda en estado `queued` y la publicación se completa sin haber llamado a la API de TFHKA

#### Scenario: Un modelo con error no bloquea a los demás

- **WHEN** `account.move` tiene un documento en `error` y `account.retention` tiene documentos `queued` sin errores propios
- **THEN** el cron sigue digitalizando la cola de `account.retention` en esa misma corrida, mientras la de `account.move` permanece detenida

#### Scenario: Reintento por límite de tasa

- **WHEN** TFHKA responde con su error de negocio de límite de tasa al digitalizar un documento
- **THEN** el sistema espera y reintenta una vez esa misma llamada antes de decidir éxito o error

### Requirement: Recuperación de digitalizaciones interrumpidas

Al inicio de cada corrida del cron, por cada modelo, el sistema DEBE (MUST) buscar documentos en `processing` (solo puede haberlos si una corrida anterior fue interrumpida a mitad de una llamada, p. ej. por `limit_time_cron`) y resolverlos antes de tocar la cola de `queued`, en orden `date_state asc` (el más antiguo primero). Para cada uno DEBE (MUST) buscar en `tfhka.api.log` una llamada exitosa a `/Emision` posterior al inicio de ese intento: si existe, DEBE (MUST) reconstruir el resultado exitoso a partir de esa respuesta ya registrada (sin reenviar el documento, evitando un duplicado) y marcarlo `success`; si no existe y ya pasó el período de gracia de un minuto, DEBE (MUST) marcarlo `error` indicando que no hay confirmación de que TFHKA lo haya recibido; si aún no pasó ese período, DEBE (MUST) dejarlo intacto en `processing` y detener por completo el procesamiento de ese modelo en esta corrida (ni siquiera evalúa la cola de `queued`), porque el intento puede seguir genuinamente en curso.

#### Scenario: Interrupción con respuesta ya recibida por TFHKA

- **WHEN** el cron muere mientras un documento está en `processing`, pero TFHKA sí procesó la emisión antes del corte (hay un log exitoso posterior al inicio del intento)
- **THEN** la siguiente corrida marca el documento `success` a partir del log, sin reenviarlo

#### Scenario: Interrupción sin respuesta tras el período de gracia

- **WHEN** un documento lleva más de un minuto en `processing` y no hay ningún log exitoso posterior al inicio del intento
- **THEN** se marca `error` con un mensaje que advierte verificar con TFHKA antes de reintentar

### Requirement: Estado `not_applicable` para facturas fuera de alcance de digitalización

Al encolar tras publicar (`_tfhka_enqueue_eligible_for_digitalization`), una factura de cliente (`out_invoice`/`out_refund`) en una compañía con `invoice_digital_tfhka` activo cuyo diario NO tenga `digital_invoice` DEBE (MUST) marcarse `not_applicable` en vez de quedar en `none` indefinidamente (indistinguible de "todavía no publicada"). Una factura ya digitalizada NUNCA DEBE (MUST NOT) marcarse `not_applicable`, y este marcado NO DEBE (MUST NOT) depender de si la compañía usa el modo "digitalización con pago" (`digitalization_with_payment_tfhka`) -- ese modo solo cambia cómo se encola una factura elegible, no si un diario no digital sigue siendo un caso sin salida.

#### Scenario: Factura en diario no digital

- **WHEN** se publica una factura de cliente en una compañía con TFHKA activo, cuyo diario no tiene facturación digital habilitada
- **THEN** la factura queda en `tfhka_digitalization_state = 'not_applicable'`, no en `'none'` ni en la cola

### Requirement: Alerta de documentos bloqueados para usuarios internos

El sistema DEBE (MUST) exponer, para usuarios internos únicamente y respetando los derechos de acceso y las reglas de registro normales (sin `sudo()`), la lista de documentos de `account.move`/`account.retention`/`stock.picking` cuyo `tfhka_digitalization_state` esté en `error` o `data_error`, acotada a las compañías de la sesión actual, para el banner mostrado en toda página (`views/tfhka_digitalization_alert.xml`). Para un usuario no interno (portal/público) el método DEBE (MUST) devolver una lista vacía sin ejecutar ninguna búsqueda.

#### Scenario: Usuario interno con documentos bloqueados

- **WHEN** un usuario interno con acceso a la compañía de una factura en `error` visita cualquier página
- **THEN** el banner lista esa factura, enlazando a su registro

#### Scenario: Usuario portal

- **WHEN** un usuario portal/público carga una página
- **THEN** no se ejecuta ninguna búsqueda de documentos bloqueados y el banner no muestra nada

### Requirement: Emisión digital de facturas, notas de débito y notas de crédito

Al publicar una factura de cliente, nota de débito o nota de crédito elegible (diario con `digital_invoice`, compañía con `invoice_digital_tfhka` activo, no ya digitalizada, y sin el modo "digitalización con pago"), el sistema DEBE (MUST) únicamente encolarla (`_tfhka_enqueue_eligible_for_digitalization`); la emisión real contra `/Emision` ocurre exclusivamente en el cron de la cola (ver "Cola de digitalización TFHKA con cron unificado"), nunca en el request de publicación. El método `generate_document_digital` de `account.move` sigue determinando el tipo de documento (`01` factura de cliente, `03` con `debit_origin_id`, `02` con `reversed_entry_id`) y, tras una emisión exitosa del cron, marca `is_digitalized`, asigna al `correlative` el `numeroControl` devuelto por TFHKA y registra un mensaje en el chatter -- eso no cambia, solo el momento y quién dispara la llamada.

#### Scenario: Factura de cliente digitalizada

- **WHEN** el cron digitaliza una factura de cliente previamente encolada y la API responde con éxito
- **THEN** la factura queda con `is_digitalized = True`, su `correlative` es el número de control devuelto y se publica un mensaje de confirmación en el chatter

#### Scenario: Compañía sin facturación digital activa

- **WHEN** se publica una factura con `invoice_digital_tfhka` desactivado
- **THEN** no se encola ningún documento y nada se emite

### Requirement: Validación de secuencia Odoo contra TFHKA en facturas

Antes de emitir una factura el sistema DEBE (MUST) consultar siempre `/ConsultaNumeraciones` y `/UltimoDocumento` (ambas llamadas se hacen con independencia de `sequence_validation_tfhka`) y calcular el siguiente número como `numeroDocumento + 1`; el flag `sequence_validation_tfhka` solo condiciona el error: con el flag activo, si ese siguiente número difiere del `sequence_number` de la factura en Odoo DEBE (MUST) lanzarse un `UserError`, y con el flag desactivado la emisión continúa usando el número calculado por TFHKA. Si la compañía tiene `group_sales_invoicing_series` y el diario tiene `series_correlative_sequence_id`, la serie enviada es el prefijo de la secuencia del diario depurado de caracteres no alfanuméricos, y si esa secuencia no tiene prefijo DEBE (MUST) lanzarse un error de serie no configurada.

#### Scenario: Secuencias desincronizadas

- **WHEN** el siguiente número según TFHKA difiere del número de secuencia de la factura y la validación de secuencia está activa
- **THEN** se lanza un `UserError` mostrando ambos números y no se emite el documento

#### Scenario: Validación de secuencia desactivada

- **WHEN** `sequence_validation_tfhka` está desactivado y los números no coinciden
- **THEN** igualmente se consultaron `/ConsultaNumeraciones` y `/UltimoDocumento`, y el documento se emite con el número calculado a partir del último documento de TFHKA

#### Scenario: Serie configurada sin prefijo

- **WHEN** la compañía maneja series de facturación y el diario tiene secuencia de serie pero su secuencia no define prefijo
- **THEN** se lanza un `UserError` indicando que la serie seleccionada no está configurada

### Requirement: Alerta confirmable de secuencia en retenciones

En la digitalización de un comprobante de retención (disparada por el cron de la cola, nunca inline), el número a comparar DEBE (MUST) obtenerse como `int(number[6:])`, es decir el correlativo del comprobante sin su prefijo `AAAAMM` de seis caracteres; la consulta de numeración y de último documento del comprobante se hacen siempre sin serie (`serie: ""`, tramo "NO APLICA"). Si ese correlativo no coincide con el siguiente número de TFHKA, la validación de secuencia de la compañía está activa y el contexto `account_retention_alert` no está presente, el sistema DEBE (MUST) lanzar `TfhkaSequenceMismatchError` en vez de emitir -- como corre en el cron, sin un humano presente que pueda contestar un wizard en el acto, el mixin clasifica esa excepción como `data_error` y detiene ahí la cola de retenciones. El botón manual `account.retention.action_tfhka_review_sequence_mismatch` (visible cuando el estado es `data_error`) DEBE (MUST) recalcular esa misma brecha de forma sincrónica (sin emitir nada) y abrir el wizard `account.retention.alert.wizard` con el mensaje; solo si el usuario confirma (`action_confirm`), la retención se reencola con `tfhka_auto_accept_sequence_mismatch = True`, y el contexto `account_retention_alert` hace que el siguiente intento del cron omita la comparación y digitalice, registrando en el chatter que la diferencia de secuencia fue aceptada además del mensaje de digitalización.

#### Scenario: Secuencia desincronizada detenida en el cron

- **WHEN** el cron intenta digitalizar una retención cuya secuencia no coincide con la de TFHKA, sin `tfhka_auto_accept_sequence_mismatch`
- **THEN** la retención queda en `data_error`, con `is_digitalized` en `False` y sin haberse enviado nada a TFHKA

#### Scenario: Usuario revisa y confirma la diferencia

- **WHEN** un usuario abre `action_tfhka_review_sequence_mismatch` sobre una retención en `data_error` por mismatch de secuencia y confirma el wizard
- **THEN** la retención vuelve a `queued`, y el siguiente tick del cron la emite exitosamente registrando en el chatter la aceptación de la diferencia

#### Scenario: Comparación del correlativo sin prefijo de período

- **WHEN** el comprobante tiene `number = "20250800000123"` y TFHKA reporta como siguiente el documento 123
- **THEN** no se lanza `TfhkaSequenceMismatchError`, porque la comparación se hace contra `123` (los caracteres a partir del séptimo) y no contra el número completo

### Requirement: Verificación del rango de numeración disponible

Antes de emitir cualquier documento, el sistema DEBE (MUST) consultar `/ConsultaNumeraciones` (método `query_numbering`) y lanzar un error de rango agotado cuando en la numeración aplicable (la serie usada, o "NO APLICA" si no hay serie) el correlativo actual no es menor que el límite `hasta`.

#### Scenario: Numeración agotada

- **WHEN** el correlativo reportado por TFHKA es mayor o igual al límite del rango
- **THEN** se lanza un `UserError` indicando que el rango de numeración está agotado y no se emite el documento

### Requirement: Datos obligatorios del receptor para digitalizar

Para construir el bloque del comprador o sujeto retenido, el sistema DEBE (MUST) exigir que el contacto tenga RIF (`vat`), país (`country_code`), teléfono (`mobile` o `phone`) y correo (`email`), lanzando un error si falta alguno. El número de identificación se normaliza quitando guiones y puntos, y el prefijo se toma de `prefix_vat` cuando existe.

#### Scenario: Cliente sin RIF

- **WHEN** se intenta digitalizar un documento cuyo contacto no tiene `vat`
- **THEN** se lanza un `UserError` indicando que el campo NIF no puede estar vacío para la digitalización

### Requirement: Fecha de vencimiento no anterior a la fecha de digitalización

En la emisión de facturas, si la factura tiene `invoice_date_due` anterior a la fecha de emisión digital, el sistema DEBE (MUST) lanzar un error de validación; sin fecha de vencimiento se usa la fecha de emisión.

#### Scenario: Factura vencida antes de emitir

- **WHEN** se digitaliza una factura cuya fecha de vencimiento es anterior a la fecha actual
- **THEN** se lanza un `ValidationError` indicando que la fecha de expiración no puede ser menor a la de digitalización

### Requirement: Máximo cinco formas de pago en el documento digital

Al construir los totales del documento, si la factura tiene más de 5 formas de pago registradas (widget de pagos), el sistema DEBE (MUST) lanzar un error, pues TFHKA acepta un máximo de 5 formas de pago.

#### Scenario: Factura con seis pagos

- **WHEN** se digitaliza una factura con más de cinco pagos asociados
- **THEN** se lanza un `UserError` indicando el máximo de formas de pago permitido

### Requirement: Totales en moneda alterna cuando la compañía no lleva VEF

Cuando la moneda de la compañía no es VEF, el payload de emisión de la factura DEBE (MUST) tomar los totales principales de los campos `foreign_*` de `tax_totals` (el espejo en VEF) e incluir el bloque `totalesOtraMoneda` con los totales expresados en la moneda de la compañía y `tipoCambio` igual a `foreign_rate` redondeado a 2 decimales. En ese bloque el campo `moneda` se llena con `company_id.foreign_currency_id.name` (la moneda espejo, típicamente VEF) y no con el nombre de la moneda de la compañía a la que corresponden esos montos; el `moneda` de `identificacionDocumento` es la constante `"VEF"` en todos los casos. Los subtotales de impuestos se envían cruzados (`impuestosSubtotal` principal con los grupos en moneda espejo y el del bloque alterno con los grupos en moneda de compañía) y el IGTF se repite con los mismos `totalIGTF`/`totalIGTF_VES` en ambos bloques.

#### Scenario: Compañía en USD

- **WHEN** se digitaliza una factura de una compañía cuya moneda base no es VEF
- **THEN** el documento se emite con los montos principales del espejo en VEF y el bloque `totalesOtraMoneda` con los montos en la moneda de la compañía y la tasa de cambio de la factura

#### Scenario: Etiqueta de moneda del bloque alterno

- **WHEN** una compañía en USD con moneda espejo VEF digitaliza una factura
- **THEN** el bloque `totalesOtraMoneda` viaja con `moneda = "VEF"` (el nombre de `foreign_currency_id`) aunque sus montos estén en USD

#### Scenario: Compañía en VEF

- **WHEN** la moneda de la compañía es VEF
- **THEN** los totales se toman de los campos no `foreign_*` y el payload no incluye el bloque `totalesOtraMoneda`

### Requirement: Emisión digital de comprobantes de retención IVA e ISLR

Al publicar un comprobante de retención elegible en el flujo automático, o al usar el botón manual, el sistema DEBE (MUST) únicamente encolarlo; la emisión real contra `/Emision` ocurre exclusivamente en el cron de la cola. El método `generate_document_digital` de `account.retention` sigue construyendo el tipo de documento (`05` IVA / `06` ISLR) y delegando en `tfhka.retention.service.send_retention`, que arma sujeto retenido, totales y detalle por línea exactamente igual que antes: `totalBaseImponible` es `total_invoice_amount` y `tipoComprobante` queda vacío cuando hay `total_iva_amount` y en `"1"` cuando no lo hay; para el tipo `05` se envían `totalRetenido` (`total_retention_amount`) y `totalIVA` (`total_iva_amount`), mientras que para cualquier otro tipo se envía `TotalISRL` tomado también de **`total_iva_amount`** (no del total retenido). En el detalle, `numeroDocumento` es el `sequence_number` de la factura, `numeroControl` su `correlative`, `montoTotal`/`baseImponible`/`retenido` los montos de la línea y `moneda` el nombre de la moneda de la compañía; para `05` se agregan `montoIVA` (`iva_amount`), `porcentaje` (`aliquot` de la línea) y `retenidoIVA` (`related_percentage_tax_base`, el porcentaje del tipo de retención), y para `06` el `CodigoConcepto` rellenado a 3 dígitos tomado del campo `code` de la línea (relacionado a las líneas del concepto de pago, sin filtrar por tipo de persona, a diferencia del reporte XLSM) más `porcentaje` (`related_percentage_fees`). Tras el éxito el cron DEBE (MUST) marcar `is_digitalized`, guardar el `numeroControl` en `control_number_tfhka` y registrar mensaje en el chatter; una retención ya digitalizada DEBE (MUST) rechazarse con error al intentar reenviarla, salvo que la compañía tenga `invoice_digital_tfhka` desactivado, caso en el que el método retorna sin validar nada.

#### Scenario: Retención ya digitalizada

- **WHEN** se intenta encolar o reenviar una retención con `is_digitalized = True` en una compañía con facturación digital activa
- **THEN** se lanza un `UserError` indicando que el documento ya fue digitalizado

#### Scenario: Emisión exitosa de retención IVA

- **WHEN** el cron digitaliza una retención IVA previamente encolada y la API acepta la emisión
- **THEN** la retención queda digitalizada con su número de control TFHKA registrado

#### Scenario: Total del comprobante ISLR

- **WHEN** el cron digitaliza una retención ISLR (tipo `06`)
- **THEN** el campo `TotalISRL` del payload lleva el valor de `total_iva_amount` del comprobante

#### Scenario: Facturación digital desactivada

- **WHEN** se invoca la emisión digital de una retención con `invoice_digital_tfhka` desactivado
- **THEN** el método retorna sin llamar a la API y sin lanzar el error de documento ya digitalizado

### Requirement: Digitalización automática de guías de despacho

Al validar un `stock.picking` (`button_validate`) elegible (compañía con `invoice_digital_tfhka` activo, guía de despacho (`is_dispatch_guide`), no digitalizada, no es recepción (`picking_type_id.code != "incoming"`)), el sistema DEBE (MUST) únicamente encolarlo; la emisión real como documento tipo `04` ocurre exclusivamente en el cron de la cola, comparando en ese momento el siguiente número de TFHKA contra el `number_next_actual` de la secuencia `guide.number` de la compañía (buscada con `sudo`) y lanzando error solo cuando `sequence_validation_tfhka` está activo. Tras el éxito el cron DEBE (MUST) guardar `control_number_tfhka`, marcar `is_digitalized` y ejecutar `_set_guide_number`, que sigue asignando `guide_number` **solo si el picking tiene `dispatch_guide_controls`**: con facturación digital activa lo asigna únicamente a pickings ya digitalizados, y sin ella lo asigna directamente.

#### Scenario: Validación de una entrega con guía

- **WHEN** se valida un picking de salida marcado como guía de despacho, con `dispatch_guide_controls`, en una compañía con facturación digital activa
- **THEN** el picking queda `queued`, y el cron lo digitaliza como tipo `04`, dejándolo con número de control y número de guía asignados

#### Scenario: Secuencia de guía desincronizada

- **WHEN** el siguiente número de TFHKA no coincide con el `number_next_actual` de la secuencia `guide.number` y la validación de secuencia está activa
- **THEN** el cron marca el picking en error con ambos números y la guía no se emite

#### Scenario: Picking digitalizado sin controles de guía

- **WHEN** el cron digitaliza con éxito un picking que no tiene `dispatch_guide_controls`
- **THEN** queda con `is_digitalized` y `control_number_tfhka`, pero sin `guide_number` asignado

### Requirement: Conjunto cerrado de grupos y alícuotas de impuesto admitidos

La construcción de los subtotales de impuestos y de los ítems DEBE (MUST) traducir cada grupo de impuesto y cada alícuota mediante diccionarios de mapeo fijos: los grupos aceptados por nombre exacto son `IVA 8%` → código `R`, `IVA 16%` → `G`, `IVA 31%` → `A`, y `Exento` / `IVA 0%` → `E` (con alícuotas `8.0`, `16.0`, `31.0` y `0.0`), y a nivel de ítem las tasas aceptadas son `0.0` → `E`, `8.0` → `R`, `16.0` → `G` y `31.0` → `A`; el IGTF se envía con código `IGTF` y su alícuota se busca en el mismo mapeo por el nombre del impuesto (donde solo existe la entrada `3.0 %`). El acceso es por clave directa, sin valor por defecto: cualquier grupo de impuesto o alícuota fuera de ese conjunto (por ejemplo un IVA renombrado o una alícuota distinta) interrumpe la digitalización con un error de clave inexistente antes de llamar a la API.

#### Scenario: Grupo de impuesto con nombre distinto

- **WHEN** se digitaliza una factura cuyo grupo de impuesto se llama distinto de los nombres mapeados (por ejemplo "IVA General 16%")
- **THEN** la construcción de los totales falla con un error de clave y el documento no se emite

#### Scenario: Factura con IVA 16% y renglón exento

- **WHEN** se digitaliza una factura con grupos `IVA 16%` y `Exento`
- **THEN** los subtotales viajan con códigos `G` y `E` y alícuotas `16.0` y `0.0`

#### Scenario: Ítem con alícuota no mapeada

- **WHEN** una línea de la factura tiene un impuesto con alícuota distinta de 0, 8, 16 o 31
- **THEN** el detalle del ítem no se puede construir y la digitalización se interrumpe
