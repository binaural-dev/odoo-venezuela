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

Cuando una llamada a la API TFHKA (método `call_tfhka_api` en factura, retención o guía) recibe HTTP 401, el sistema DEBE (MUST) regenerar el token con `generate_token_tfhka` y reintentar la misma llamada; cualquier otro error HTTP o de conexión DEBE (MUST) abortar la operación con un error visible al usuario.

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

Con `sequence_validation_tfhka` activo, antes de emitir una factura el sistema DEBE (MUST) consultar el último documento en TFHKA (`/UltimoDocumento`) y lanzar un error si el siguiente número de TFHKA no coincide con el `sequence_number` de la factura en Odoo.

#### Scenario: Secuencias desincronizadas

- **WHEN** el siguiente número según TFHKA difiere del número de secuencia de la factura y la validación de secuencia está activa
- **THEN** se lanza un `UserError` mostrando ambos números y no se emite el documento

### Requirement: Alerta confirmable de secuencia en retenciones

En la emisión digital de un comprobante de retención, si el siguiente número según TFHKA no coincide con el correlativo del comprobante y la validación de secuencia está activa, el sistema DEBE (MUST) abrir el wizard `account.retention.alert.wizard` en lugar de emitir; solo si el usuario confirma, la emisión se re-ejecuta con el contexto `account_retention_alert` y se registra en el chatter que la diferencia de secuencia fue aceptada.

#### Scenario: Usuario confirma la diferencia

- **WHEN** el wizard de alerta se confirma con `action_confirm`
- **THEN** la retención se emite digitalmente y se publican en el chatter la aceptación de la diferencia y la confirmación de digitalización

#### Scenario: Usuario cancela

- **WHEN** el usuario cierra el wizard con `action_cancel`
- **THEN** la retención no se emite y permanece sin digitalizar

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

Cuando la moneda de la compañía no es VEF, el payload de emisión de la factura DEBE (MUST) tomar los totales principales de los campos `foreign_*` de `tax_totals` (el espejo en VEF) e incluir el bloque `totalesOtraMoneda` con los totales en la moneda de la compañía y `tipoCambio` igual a `foreign_rate` redondeado a 2 decimales, incluyendo los subtotales de impuestos e IGTF cuando aplica.

#### Scenario: Compañía en USD

- **WHEN** se digitaliza una factura de una compañía cuya moneda base no es VEF
- **THEN** el documento se emite con los montos principales del espejo en VEF y el bloque `totalesOtraMoneda` con la tasa de cambio de la factura

### Requirement: Emisión digital de comprobantes de retención IVA e ISLR

El método `generate_document_digital` de `account.retention` DEBE (MUST) emitir el comprobante con el tipo de documento recibido por contexto (`05` retención IVA, `06` retención ISLR) incluyendo sujeto retenido, totales (`totalRetenido`/`totalIVA` para IVA, `TotalISRL` para ISLR) y el detalle por línea (montos, base, número de control de la factura; para IVA porcentaje y monto de IVA, para ISLR el código de concepto rellenado a 3 dígitos). Tras el éxito DEBE (MUST) marcar `is_digitalized`, guardar el `numeroControl` en `control_number_tfhka` y registrar mensaje en el chatter; una retención ya digitalizada DEBE (MUST) rechazarse con error.

#### Scenario: Retención ya digitalizada

- **WHEN** se intenta emitir digitalmente una retención con `is_digitalized = True`
- **THEN** se lanza un `UserError` indicando que el documento ya fue digitalizado

#### Scenario: Emisión exitosa de retención IVA

- **WHEN** la API acepta la emisión de una retención IVA
- **THEN** la retención queda digitalizada con su número de control TFHKA registrado

### Requirement: Digitalización automática de guías de despacho

Al validar un `stock.picking` (`button_validate`), si la compañía tiene `invoice_digital_tfhka` activo, el picking es guía de despacho (`is_dispatch_guide`), no está digitalizado y no es una recepción (`picking_type_id.code != "incoming"`), el sistema DEBE (MUST) emitirlo digitalmente como documento tipo `04`, validando la secuencia contra la secuencia `guide.number` de la compañía cuando `sequence_validation_tfhka` está activo. Tras el éxito DEBE (MUST) marcar `is_digitalized`, guardar `control_number_tfhka` y asignar el `guide_number`, que con facturación digital activa solo se asigna a pickings ya digitalizados.

#### Scenario: Validación de una entrega con guía

- **WHEN** se valida un picking de salida marcado como guía de despacho en una compañía con facturación digital activa
- **THEN** se emite la guía tipo `04` a TFHKA y el picking queda digitalizado con número de control y número de guía asignados

#### Scenario: Secuencia de guía desincronizada

- **WHEN** el siguiente número de TFHKA no coincide con el próximo número de la secuencia `guide.number` y la validación de secuencia está activa
- **THEN** se lanza un `UserError` con ambos números y la guía no se emite

### Requirement: Bloqueo de publicación con documentos anteriores sin digitalizar

Al confirmar la publicación de una factura mediante el wizard `move.action.post.alert.wizard`, con facturación digital activa el sistema DEBE (MUST) buscar el documento publicado más antiguo del mismo diario y tipo que siga sin digitalizar y lanzar un error que lo identifique (factura, nota de débito o nota de crédito), impidiendo continuar hasta digitalizarlo.

#### Scenario: Factura anterior pendiente

- **WHEN** se confirma la publicación y existe una factura anterior publicada del mismo diario sin `is_digitalized`
- **THEN** se lanza un `UserError` nombrando el documento pendiente de digitalizar
