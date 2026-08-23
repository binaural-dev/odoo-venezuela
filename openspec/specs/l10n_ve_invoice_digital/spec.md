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

### Requirement: Emisión digital de facturas, notas de débito y notas de crédito

El método `generate_document_digital` de `account.move` DEBE (MUST) emitir el documento contra el endpoint `/Emision` solo si la compañía tiene `invoice_digital_tfhka` activo, determinando el tipo de documento: `01` para factura de cliente, `03` si la factura tiene `debit_origin_id` (nota de débito) y `02` para nota de crédito con `reversed_entry_id`; otros tipos de movimiento no se emiten. Tras una emisión exitosa DEBE (MUST) marcar `is_digitalized`, asignar al `correlative` el `numeroControl` devuelto por TFHKA y registrar un mensaje en el chatter.

#### Scenario: Factura de cliente digitalizada

- **WHEN** se emite digitalmente una factura de cliente publicada y la API responde con éxito
- **THEN** la factura queda con `is_digitalized = True`, su `correlative` es el número de control devuelto y se publica un mensaje de confirmación en el chatter

#### Scenario: Compañía sin facturación digital activa

- **WHEN** se invoca la emisión digital con `invoice_digital_tfhka` desactivado
- **THEN** el método retorna sin llamar a la API

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

En la emisión digital de un comprobante de retención, el número a comparar DEBE (MUST) obtenerse como `int(number[6:])`, es decir el correlativo del comprobante sin su prefijo `AAAAMM` de seis caracteres (no el `number` completo ni el campo `correlative`); la consulta de numeración y de último documento del comprobante se hacen siempre sin serie (`serie: ""`, tramo "NO APLICA"). Si ese correlativo no coincide con el siguiente número de TFHKA, la validación de secuencia de la compañía está activa y el contexto `account_retention_alert` no está presente, el sistema DEBE (MUST) retornar la acción que abre el wizard `account.retention.alert.wizard` en lugar de emitir; solo si el usuario confirma, la emisión se re-ejecuta con el contexto `account_retention_alert` y se registra en el chatter que la diferencia de secuencia fue aceptada además del mensaje de digitalización.

#### Scenario: Usuario confirma la diferencia

- **WHEN** el wizard de alerta se confirma con `action_confirm`
- **THEN** la retención se emite digitalmente y se publican en el chatter la aceptación de la diferencia y la confirmación de digitalización

#### Scenario: Usuario cancela

- **WHEN** el usuario cierra el wizard con `action_cancel`
- **THEN** el wizard se cierra sin llamar a la API y la retención permanece sin digitalizar

#### Scenario: Comparación del correlativo sin prefijo de período

- **WHEN** el comprobante tiene `number = "20250800000123"` y TFHKA reporta como siguiente el documento 123
- **THEN** no se abre el wizard, porque la comparación se hace contra `123` (los caracteres a partir del séptimo) y no contra el número completo

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

El método `generate_document_digital` de `account.retention` DEBE (MUST) emitir el comprobante con el tipo de documento recibido por contexto (`05` retención IVA desde el botón de la vista IVA, `06` retención ISLR desde la vista ISLR) incluyendo sujeto retenido, totales y el detalle por línea. En los totales, `totalBaseImponible` es `total_invoice_amount` y `tipoComprobante` queda vacío cuando hay `total_iva_amount` y en `"1"` cuando no lo hay; para el tipo `05` se envían `totalRetenido` (`total_retention_amount`) y `totalIVA` (`total_iva_amount`), mientras que para cualquier otro tipo se envía `TotalISRL` tomado también de **`total_iva_amount`** (no del total retenido). En el detalle, `numeroDocumento` es el `sequence_number` de la factura, `numeroControl` su `correlative`, `montoTotal`/`baseImponible`/`retenido` los montos de la línea y `moneda` el nombre de la moneda de la compañía; para `05` se agregan `montoIVA` (`iva_amount`), `porcentaje` (`aliquot` de la línea) y `retenidoIVA` (`related_percentage_tax_base`, el porcentaje del tipo de retención), y para `06` el `CodigoConcepto` rellenado a 3 dígitos tomado del campo `code` de la línea (relacionado a las líneas del concepto de pago, sin filtrar por tipo de persona, a diferencia del reporte XLSM) más `porcentaje` (`related_percentage_fees`). Tras el éxito DEBE (MUST) marcar `is_digitalized`, guardar el `numeroControl` en `control_number_tfhka` y registrar mensaje en el chatter; una retención ya digitalizada DEBE (MUST) rechazarse con error, salvo que la compañía tenga `invoice_digital_tfhka` desactivado, caso en el que el método retorna sin validar nada.

#### Scenario: Retención ya digitalizada

- **WHEN** se intenta emitir digitalmente una retención con `is_digitalized = True` en una compañía con facturación digital activa
- **THEN** se lanza un `UserError` indicando que el documento ya fue digitalizado

#### Scenario: Emisión exitosa de retención IVA

- **WHEN** la API acepta la emisión de una retención IVA
- **THEN** la retención queda digitalizada con su número de control TFHKA registrado

#### Scenario: Total del comprobante ISLR

- **WHEN** se emite digitalmente una retención ISLR (tipo `06`)
- **THEN** el campo `TotalISRL` del payload lleva el valor de `total_iva_amount` del comprobante

#### Scenario: Facturación digital desactivada

- **WHEN** se invoca la emisión digital de una retención con `invoice_digital_tfhka` desactivado
- **THEN** el método retorna sin llamar a la API y sin lanzar el error de documento ya digitalizado

### Requirement: Digitalización automática de guías de despacho

Al validar un `stock.picking` (`button_validate`), si la compañía tiene `invoice_digital_tfhka` activo, el picking es guía de despacho (`is_dispatch_guide`), no está digitalizado y no es una recepción (`picking_type_id.code != "incoming"`), el sistema DEBE (MUST) emitirlo digitalmente como documento tipo `04`, comparando el siguiente número de TFHKA contra el `number_next_actual` de la secuencia `guide.number` de la compañía (buscada con `sudo`) y lanzando error solo cuando `sequence_validation_tfhka` está activo. Tras el éxito DEBE (MUST) guardar `control_number_tfhka`, marcar `is_digitalized` y ejecutar `_set_guide_number`, que asigna `guide_number` **solo si el picking tiene `dispatch_guide_controls`**: con facturación digital activa lo asigna únicamente a pickings ya digitalizados, y sin ella lo asigna directamente.

#### Scenario: Validación de una entrega con guía

- **WHEN** se valida un picking de salida marcado como guía de despacho, con `dispatch_guide_controls`, en una compañía con facturación digital activa
- **THEN** se emite la guía tipo `04` a TFHKA y el picking queda digitalizado con número de control y número de guía asignados

#### Scenario: Secuencia de guía desincronizada

- **WHEN** el siguiente número de TFHKA no coincide con el `number_next_actual` de la secuencia `guide.number` y la validación de secuencia está activa
- **THEN** se lanza un `UserError` con ambos números y la guía no se emite

#### Scenario: Picking digitalizado sin controles de guía

- **WHEN** se digitaliza con éxito un picking que no tiene `dispatch_guide_controls`
- **THEN** queda con `is_digitalized` y `control_number_tfhka`, pero sin `guide_number` asignado

### Requirement: Bloqueo de publicación con documentos sin digitalizar del mismo diario

Al confirmar la publicación de una factura mediante el wizard `move.action.post.alert.wizard`, con facturación digital activa y solo cuando el documento tiene `sequence_number > 1`, el sistema DEBE (MUST) buscar el documento publicado del mismo diario, compañía y `move_type` con **cualquier** `sequence_number` distinto al propio que siga con `is_digitalized = False`, tomando el de secuencia más baja (`order="sequence_number asc", limit=1`), y lanzar un error que lo identifique como factura, nota de débito (`out_invoice` con `debit_origin_id`) o nota de crédito (`out_refund`), impidiendo continuar hasta digitalizarlo. El filtro no restringe la búsqueda a secuencias anteriores, por lo que el documento reportado puede ser posterior al que se está publicando.

#### Scenario: Factura anterior pendiente

- **WHEN** se confirma la publicación y existe otra factura publicada del mismo diario sin `is_digitalized`
- **THEN** se lanza un `UserError` nombrando el documento pendiente de digitalizar

#### Scenario: Documento posterior sin digitalizar

- **WHEN** el único documento sin digitalizar del diario tiene un `sequence_number` mayor que el de la factura que se publica
- **THEN** igualmente se lanza el `UserError`, porque el dominio compara por desigualdad y no por anterioridad

#### Scenario: Primer documento del diario

- **WHEN** la factura que se publica tiene `sequence_number = 1`
- **THEN** no se ejecuta la búsqueda y la publicación continúa

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
