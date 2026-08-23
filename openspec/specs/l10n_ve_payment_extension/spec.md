# l10n_ve_payment_extension

## Purpose

Módulo de retenciones venezolanas (IVA, ISLR y municipales): define el comprobante de retención (`account.retention`) y sus líneas (`account.retention.line`), los catálogos legales (conceptos de pago `payment.concept`, tarifas `fees.retention`, tramos acumulados `accumulated.fees`, tipos de persona `type.person`, tipos de retención `account.withholding.type`, actividades económicas `economic.activity` y unidad tributaria `tax.unit`), la generación y conciliación automática de pagos de retención, y los reportes legales (TXT IVA SENIAT, ARCV, XLSM ISLR, comprobantes PDF). Extiende `account.move`, `account.move.line`, `account.payment`, `account.payment.register`, `account.journal`, `res.partner`, `res.company`, `res.config.settings`, `product.template` y `product.category`. Depende de `account`, `l10n_ve_rate`, `l10n_ve_accountant`, `l10n_ve_invoice`, `l10n_ve_location`, `l10n_ve_contact`, `l10n_ve_tax_payer`, `product` y `stock`.

## Requirements

### Requirement: Comprobante de retención con tipos y ciclo de estados

El comprobante `account.retention` DEBE (MUST) tener un tipo de retención (`type_retention`: `iva`, `islr`, `municipal`), un tipo de documento origen (`type`: variantes in/out de factura, nota de crédito, débito y contingencia) y un estado (`state`) con ciclo `draft` → `emitted` → `cancel`: `action_post` lo emite, `action_cancel` lo cancela y `action_draft` lo devuelve a borrador. Un comprobante en estado `emitted` NO puede eliminarse: `unlink` DEBE (MUST) lanzar un error exigiendo cancelarlo primero.

#### Scenario: Eliminación de comprobante emitido

- **WHEN** se intenta eliminar un comprobante en estado `emitted`
- **THEN** se lanza un `ValidationError` indicando que debe cancelarse antes de eliminarse

#### Scenario: Emisión de un comprobante en borrador

- **WHEN** se ejecuta `action_post` sobre un comprobante válido en borrador
- **THEN** el comprobante pasa a estado `emitted`

### Requirement: Numeración automática de comprobantes

Para los comprobantes sin número, el sistema DEBE (MUST) asignar en `_set_sequence` un correlativo con formato `AAAAMM` (año y mes de la fecha contable) seguido del siguiente valor de la secuencia por compañía: `retention.iva.control.number` con padding 8 para IVA (resultando 14 dígitos), `retention.islr.control.number` con padding 5 para ISLR y `retention.municipal.control.number` para municipal; el correlativo se guarda en `number` y `name`. La secuencia se crea automáticamente si no existe.

#### Scenario: Comprobante IVA de proveedor sin número

- **WHEN** se crea un comprobante de retención IVA de proveedor sin `number`
- **THEN** recibe un número de 14 dígitos compuesto por año, mes y la secuencia de 8 dígitos

### Requirement: Formato de 14 dígitos del número de comprobante IVA

El sistema DEBE (MUST) validar en `action_post` que el `number` de todo comprobante IVA sea exactamente 14 dígitos numéricos, y el constraint `_check_number` DEBE (MUST) aplicar el mismo formato a los comprobantes de cliente (`out_invoice`, `out_refund`) con número fuera del estado borrador.

#### Scenario: Número IVA con formato inválido

- **WHEN** se intenta emitir un comprobante IVA cuyo número no cumple 14 dígitos numéricos
- **THEN** se lanza un `ValidationError` indicando el formato requerido

### Requirement: Número obligatorio en retenciones de cliente

El sistema DEBE (MUST) impedir emitir un comprobante de tipo cliente (`out_invoice`, `out_refund`, `out_debit`) sin `number`, ya que el número lo emite el agente de retención externo.

#### Scenario: Retención de cliente sin número

- **WHEN** se ejecuta `action_post` sobre una retención de cliente sin número de comprobante
- **THEN** se lanza un `UserError` pidiendo insertar un número

### Requirement: Carga automática de líneas de retención IVA por partner

Al seleccionar el partner en un comprobante IVA en borrador, el sistema DEBE (MUST) cargar automáticamente líneas de retención desde las facturas del partner que estén publicadas, con impuestos mayores a cero, sin `iva_voucher_number`, con `amount_residual` mayor a 0 y sin líneas en otra retención IVA en estado `draft` o `emitted` (proveedor: `in_invoice`/`in_refund`; cliente: `out_invoice`/`out_refund`). Si no existe ninguna factura elegible DEBE (MUST) lanzar un error.

#### Scenario: Proveedor con facturas pendientes

- **WHEN** se selecciona un proveedor con facturas publicadas con IVA sin retención previa vigente
- **THEN** el comprobante se llena con una línea por cada grupo de impuesto de cada factura elegible

#### Scenario: Partner sin facturas elegibles

- **WHEN** se selecciona un partner sin facturas con impuestos por retener
- **THEN** se lanza un `UserError` indicando que no hay facturas con impuestos por retener

### Requirement: Cálculo de la retención IVA por grupo de impuestos

El sistema DEBE (MUST) calcular cada línea de retención IVA por grupo de impuesto de la factura (`compute_retention_lines_data` / `_onchange_move_id`): `iva_amount` es el impuesto del grupo, `invoice_amount` su base imponible, `related_percentage_tax_base` el porcentaje del tipo de retención del partner (`withholding_type_id.value`) y `retention_amount = |iva_amount × porcentaje / 100|`, con sus equivalentes en moneda alterna calculados con el mismo porcentaje. El módulo instala los tipos de retención `75%` y `100%` como data. Una factura sin impuestos DEBE (MUST) rechazarse, y crear una retención IVA desde una factura cuyo partner no tiene tipo de retención DEBE (MUST) lanzar un error.

#### Scenario: Contribuyente especial al 75%

- **WHEN** se calcula la retención IVA de una factura con IVA 16% para un partner con tipo de retención 75%
- **THEN** la línea queda con monto retenido igual al 75% del IVA del grupo de impuesto

#### Scenario: Partner sin tipo de retención

- **WHEN** se genera la retención IVA desde una factura de un partner sin `withholding_type_id`
- **THEN** se lanza un `UserError` indicando que el partner no tiene tipo de retención

### Requirement: Autollenado configurable del monto en retención IVA de cliente

Para facturas de cliente (`out_invoice`/`out_refund`), el monto retenido calculado DEBE (MUST) precargarse en la línea solo si la compañía tiene activo `auto_fill_retention_amount_iva`; en caso contrario la línea se carga con `retention_amount` y `foreign_retention_amount` en 0 para que el usuario los transcriba del comprobante recibido. En facturas de proveedor el monto siempre se precarga.

#### Scenario: Compañía sin autollenado

- **WHEN** se cargan líneas de retención IVA de una factura de cliente con `auto_fill_retention_amount_iva` desactivado
- **THEN** las líneas quedan con monto retenido 0

#### Scenario: Compañía con autollenado

- **WHEN** el flag está activo y se cargan líneas de retención IVA de cliente
- **THEN** las líneas quedan con el monto calculado según el tipo de retención del partner

### Requirement: Parámetros ISLR según el tipo de persona del sujeto retenido

Al asignar un concepto de pago a una línea ISLR, el sistema DEBE (MUST) tomar los parámetros (`pay_from`, `percentage_tax_base`, porcentaje y sustraendo de la tarifa) de la línea de concepto (`payment.concept.line`) cuyo `type_person_id` coincide con el tipo de persona del sujeto: el del partner del comprobante (o de la factura) en retenciones de proveedor, y el del partner de la propia compañía en retenciones de cliente (`out_invoice`). Emitir una retención ISLR DEBE (MUST) exigir que el sujeto tenga `type_person_id` y que las líneas tengan concepto de pago.

#### Scenario: Concepto con línea para el tipo de persona

- **WHEN** una línea ISLR de proveedor recibe un concepto que tiene una línea para el tipo de persona del proveedor
- **THEN** la línea de retención copia `related_pay_from`, `related_percentage_tax_base`, `related_percentage_fees` y `related_amount_subtract_fees` de esa línea de concepto

#### Scenario: Sujeto sin tipo de persona

- **WHEN** se emite una retención ISLR cuyo partner no tiene tipo de persona
- **THEN** se lanza un `UserError` pidiendo seleccionar un tipo de persona

### Requirement: Fórmula de retención ISLR con tarifa simple

Para tarifas sin tasa acumulada, el monto retenido de una línea ISLR DEBE (MUST) calcularse como `|base imponible × (% base imponible / 100) × (% tarifa / 100) − sustraendo|` (`_compute_retention_amount`), aplicando la misma fórmula sobre la base en moneda alterna para `foreign_retention_amount`; cuando la moneda base de la compañía no es VEF, el resultado se convierte entre monedas con `_convert` a la fecha de la factura.

#### Scenario: Persona jurídica con tarifa porcentual

- **WHEN** una línea ISLR tiene base 1000, porcentaje de base imponible 100, tarifa 5% y sustraendo 0
- **THEN** el monto retenido es 50

#### Scenario: Tarifa con sustraendo

- **WHEN** la tarifa aplica sustraendo y el resultado de base × porcentajes es menor que el sustraendo
- **THEN** el monto retenido es el valor absoluto de la diferencia

### Requirement: Fórmula de retención ISLR con tarifa acumulada por tramos en UT

Para tarifas con `accumulated_rate`, el sistema DEBE (MUST): (1) acumular la base imponible del ejercicio fiscal sumando las facturas publicadas anteriores del mismo partner y tipo con retenciones ISLR más la factura actual; (2) expresar esa base en unidades tributarias dividiéndola entre el valor de la UT de la tarifa (`tax_unit_ids.value`) y aplicar el `percentage_tax_base`; (3) seleccionar el tramo de `accumulated.fees` cuyo rango `start`–`stop` contiene la base acumulada, tratando `stop = 0` como tramo infinito (aplica si la base es mayor o igual a `start`); y (4) usar el porcentaje del tramo y un sustraendo igual a `subtract_ut × valor UT`. El monto retenido se calcula convirtiendo la base a UT, aplicando porcentajes y restando el sustraendo en UT, todo multiplicado de vuelta por el valor de la UT. Una tarifa acumulada sin unidad tributaria válida DEBE (MUST) lanzar un error.

#### Scenario: Base acumulada dentro de un tramo intermedio

- **WHEN** la base acumulada en UT del ejercicio cae dentro del rango `start`–`stop` de un tramo
- **THEN** la línea usa el porcentaje de ese tramo y el sustraendo `subtract_ut × valor UT`

#### Scenario: Base acumulada sobre el último tramo

- **WHEN** la base acumulada supera el `start` del tramo con `stop = 0`
- **THEN** se aplica ese tramo infinito

#### Scenario: Tarifa acumulada sin unidad tributaria

- **WHEN** se calcula una línea con tarifa acumulada cuyo registro no tiene unidad tributaria
- **THEN** se lanza un `UserError` indicando que la tarifa no tiene una unidad tributaria válida

### Requirement: Cálculo del sustraendo de la tarifa

Cuando una tarifa (`fees.retention`) tiene activo `apply_subtracting`, su campo `amount_subtract` DEBE (MUST) calcularse como `valor de la UT × 83.3334 × porcentaje de la tarifa / 100`; con el flag desactivado el sustraendo es 0.

#### Scenario: Tarifa del 3% con sustraendo

- **WHEN** una tarifa con `apply_subtracting` activo tiene porcentaje 3 y la UT vale 9
- **THEN** `amount_subtract` es `9 × 83.3334 × 3 / 100`

### Requirement: Validaciones de la tarifa de retención

El sistema DEBE (MUST) impedir guardar una tarifa con `accumulated_rate` activo sin tramos en `accumulated_rate_ids`, y rechazar porcentajes de tarifa negativos (constraint `_check_data_accumulated`).

#### Scenario: Tarifa acumulada sin tramos

- **WHEN** se guarda una tarifa marcada como acumulada sin líneas de tramos
- **THEN** se lanza un `ValidationError` exigiendo ingresar las tarifas acumuladas

### Requirement: Unicidad y vigencia de la unidad tributaria

El modelo `tax.unit` (extendido con `available_date` obligatoria) DEBE (MUST): impedir dos unidades tributarias con la misma fecha de publicación; mantener activa (`status`) únicamente la de fecha de publicación más reciente, desactivando las demás automáticamente; impedir editar una unidad tributaria inactiva (salvo su propio `status`); y, al cambiar el valor o la vigencia, reasignar la UT y recalcular el sustraendo de las tarifas activas con `apply_subtracting`, dejando constancia en el chatter.

#### Scenario: Dos unidades con la misma fecha

- **WHEN** se crea una unidad tributaria con la misma `available_date` que otra existente
- **THEN** se lanza un error indicando que no puede haber dos unidades tributarias con la misma fecha

#### Scenario: Nueva unidad más reciente

- **WHEN** se crea una unidad tributaria con fecha posterior a las existentes
- **THEN** la nueva queda activa, las anteriores se desactivan y las tarifas con sustraendo se recalculan con el nuevo valor

#### Scenario: Edición de unidad inactiva

- **WHEN** se intenta modificar un campo distinto de `status` en una unidad tributaria inactiva
- **THEN** se lanza un error indicando que no se puede editar una unidad tributaria inactiva

### Requirement: Disponibilidad de retención ISLR en la factura

Una factura DEBE (MUST) considerarse elegible para retención ISLR (`is_isrl_retention_available`) solo cuando alguna de sus líneas tiene un producto de tipo servicio con concepto de pago (`product.template.payment_concept`); al perder la elegibilidad, el flag `generate_islr_retention` se desactiva automáticamente.

#### Scenario: Factura solo de bienes

- **WHEN** una factura no tiene líneas de servicios con concepto de pago
- **THEN** `is_isrl_retention_available` es falso y no puede marcarse para generar retención ISLR

### Requirement: Validaciones para generar la retención ISLR desde la factura

El método `validate_islr` DEBE (MUST) exigir que la factura esté publicada, que tenga al menos una línea con concepto de pago, que el sujeto (el partner de la compañía en facturas de cliente, el proveedor en las demás) tenga tipo de persona, y que la factura no tenga ya una retención ISLR emitida; si existe una en borrador, se reutiliza en lugar de crear otra.

#### Scenario: Factura con retención ISLR ya emitida

- **WHEN** se intenta generar una retención ISLR sobre una factura que ya tiene una retención ISLR emitida
- **THEN** se lanza un `UserError` indicando que no puede crearse otra

#### Scenario: Factura en borrador

- **WHEN** se intenta generar la retención sobre una factura no publicada
- **THEN** se lanza un `UserError` exigiendo el estado publicado

### Requirement: La base de una línea ISLR no puede exceder la base de la factura

Al emitir un comprobante ISLR de proveedor, el sistema DEBE (MUST) validar (`_check_retention_vs_move`) que la base imponible (`invoice_amount`) de cada línea no sea mayor que la base imponible (`base_amount`) de su factura.

#### Scenario: Base de línea inflada

- **WHEN** una línea ISLR tiene base imponible mayor que la base de la factura y se intenta emitir
- **THEN** se lanza un `UserError` indicando que la base de la línea supera la de la factura

### Requirement: La retención no puede exceder el saldo pendiente de la factura

Al emitir un comprobante, el sistema DEBE (MUST) validar por factura que la suma de `retention_amount` de sus líneas no supere el valor absoluto de `amount_residual_signed`; si lo supera, la emisión se detiene (notificación de error, o mensaje en el chatter y retorno fallido en ejecuciones automatizadas). Adicionalmente, en compañías con moneda base VEF, escribir en una línea de retención de cliente un monto retenido mayor al residual de una factura no pagada DEBE (MUST) lanzar un error (`check_retention_amount`).

#### Scenario: Retención mayor al residual al emitir

- **WHEN** se emite un comprobante cuya retención por factura supera el saldo pendiente de esa factura
- **THEN** la emisión no se completa y se informa el error con los montos y la factura

#### Scenario: Edición de línea de cliente sobre el residual

- **WHEN** en una compañía con base VEF se guarda una línea de retención de cliente con monto mayor al residual de la factura
- **THEN** se lanza un `ValidationError`

### Requirement: Prohibición de montos en cero al emitir

El sistema DEBE (MUST) impedir, vía constraint sobre las líneas, que un comprobante fuera del estado borrador tenga líneas con `retention_amount`, `invoice_total` o `invoice_amount` en 0.

#### Scenario: Emisión con línea en cero

- **WHEN** un comprobante pasa a emitido con una línea cuyo monto retenido es 0
- **THEN** se lanza un `ValidationError` indicando que no se puede crear una retención con monto 0

### Requirement: Generación y conciliación automática de pagos al emitir

Al emitir un comprobante, el sistema DEBE (MUST) crear un `account.payment` por cada factura involucrada (agrupando sus líneas por `move_id`), marcado con `is_retention`, con el diario de retención de la compañía correspondiente al tipo de retención y flujo (proveedor/cliente), en la moneda de la compañía, con monto igual a la suma de los `retention_amount` de sus líneas; los pagos se publican y se concilian automáticamente contra la línea por cobrar/por pagar de la factura. Si el diario correspondiente no está configurado, la emisión DEBE (MUST) fallar con error.

#### Scenario: Comprobante con dos facturas

- **WHEN** se emite un comprobante IVA de proveedor con líneas de dos facturas
- **THEN** se crean dos pagos de retención, uno por factura, publicados y conciliados con su factura

#### Scenario: Compañía sin diario de retención

- **WHEN** se emite un comprobante y la compañía no tiene configurado el diario de retención del tipo y flujo correspondiente
- **THEN** se lanza un `UserError` indicando la falta de configuración de diarios

### Requirement: Nombre identificable del asiento del pago de retención

El asiento del pago de retención DEBE (MUST) renombrarse (`_synchronize_to_moves`) con el prefijo `RIV` (IVA), `RIS` (ISLR) o `RM` (municipal), seguido del número del comprobante y del nombre de la factura; en ISLR se agregan los primeros caracteres del concepto de pago y en municipal la actividad económica y su ramo.

#### Scenario: Pago de retención IVA emitido

- **WHEN** se sincroniza el asiento de un pago de retención IVA con número de comprobante y línea asociada
- **THEN** el asiento queda nombrado `RIV-<número>-<factura>`

### Requirement: Escritura del número de comprobante en la factura

Al emitir un comprobante, el sistema DEBE (MUST) escribir su número en las facturas de sus líneas: `iva_voucher_number`, `islr_voucher_number` o `municipal_voucher_number` según el tipo de retención; al cancelar el comprobante esos campos DEBEN (MUST) limpiarse.

#### Scenario: Emisión de comprobante IVA

- **WHEN** se emite un comprobante IVA sobre una factura
- **THEN** la factura queda con `iva_voucher_number` igual al número del comprobante

#### Scenario: Cancelación del comprobante

- **WHEN** se cancela el comprobante
- **THEN** el número de comprobante registrado en la factura se limpia

### Requirement: Generación automática de retenciones al publicar la factura

Al publicar una factura (`action_post` de `account.move`), el sistema DEBE (MUST) crear automáticamente: la retención ISLR si `generate_islr_retention` está activo y no hay `islr_voucher_number`; la retención IVA si `generate_iva_retention` está activo y no hay `iva_voucher_number` (validando diario configurado e impuestos aplicables); y la retención municipal en facturas de proveedor con líneas municipales no emitidas. Para facturas de proveedor, la retención creada DEBE (MUST) emitirse automáticamente salvo que la compañía tenga activo `create_retentions_of_suppliers_in_draft`, en cuyo caso queda en borrador.

#### Scenario: Factura de proveedor con retención IVA automática

- **WHEN** se publica una factura de proveedor con `generate_iva_retention` activo y la compañía no crea retenciones en borrador
- **THEN** se crea la retención IVA, se emite automáticamente y la factura recibe el número de comprobante

#### Scenario: Compañía con retenciones en borrador

- **WHEN** `create_retentions_of_suppliers_in_draft` está activo y se publica la factura
- **THEN** la retención se crea en estado borrador sin emitirse

#### Scenario: Factura sin impuestos con retención IVA marcada

- **WHEN** se publica una factura marcada para retención IVA sin impuestos aplicables
- **THEN** se lanza un `UserError` indicando que no puede generarse la retención

### Requirement: Protección de los pagos de retención

El sistema DEBE (MUST) impedir, mientras el comprobante no esté cancelado: pasar a borrador o cancelar directamente un pago con `is_retention` (`action_draft`/`action_cancel` de `account.payment`), pasar a borrador su asiento (`button_draft` de `account.move`) y romper su conciliación desde la factura (`js_remove_outstanding_partial`); estas operaciones solo proceden con el contexto interno `bypass_retention_lock` que usa la cancelación del comprobante.

#### Scenario: Cancelación directa del pago

- **WHEN** un usuario intenta cancelar un pago de retención cuyo comprobante sigue emitido
- **THEN** se lanza un `UserError` indicando que debe cancelarse primero el comprobante

#### Scenario: Desconciliación desde la factura

- **WHEN** se intenta eliminar desde la factura la conciliación de un pago de retención
- **THEN** se lanza un `UserError` indicando que debe cancelarse el comprobante

### Requirement: Cancelación del comprobante revierte sus pagos

`action_cancel` DEBE (MUST): desconciliar los apuntes conciliados de los pagos del comprobante, pasarlos a borrador y cancelarlos (con `bypass_retention_lock`), desmarcarlos como retención y desvincularlos, limpiar los números de comprobante en las facturas y dejar el comprobante en estado `cancel` sin pagos asociados.

#### Scenario: Cancelar comprobante emitido con pagos conciliados

- **WHEN** se cancela un comprobante emitido cuyos pagos están conciliados con facturas
- **THEN** los pagos quedan cancelados y desvinculados, las facturas pierden el número de comprobante y el comprobante queda en `cancel`

### Requirement: Cálculo de la retención municipal por actividad económica

En líneas municipales, al asignar la actividad económica el sistema DEBE (MUST) tomar su alícuota (`economic.activity.aliquot`) y calcular `retention_amount = invoice_amount × alícuota / 100` (y el equivalente en moneda alterna), recalculando al cambiar la base o la alícuota; la actividad económica por defecto de la línea proviene del partner. Además, al modificar las líneas de una factura de proveedor con retenciones municipales, los montos DEBEN (MUST) recalcularse.

#### Scenario: Actividad con alícuota 2%

- **WHEN** una línea municipal con base 1000 recibe una actividad económica con alícuota 2
- **THEN** el monto retenido es 20

### Requirement: Catálogo de actividades económicas válido

El modelo `economic.activity` DEBE (MUST) exigir alícuota mayor que cero y unicidad del código por municipio (constraints SQL `aliquot_mayor_cero` y `code_uniq`); el ramo económico (`economic.branch`) DEBE (MUST) tener nombre único.

#### Scenario: Actividad duplicada en el municipio

- **WHEN** se crea una actividad con el mismo código y municipio que otra existente
- **THEN** la base de datos rechaza el registro por el constraint de unicidad

### Requirement: Código de concepto de pago único

Las líneas de concepto de pago (`payment.concept.line`) DEBEN (MUST) tener un código único a nivel de sistema (constraint SQL `unique_code`), y cada línea exige tipo de persona y concepto asociado.

#### Scenario: Código repetido

- **WHEN** se crea una línea de concepto con un código ya existente
- **THEN** el registro se rechaza indicando que el código de concepto ya existe

### Requirement: Retención IVA de cliente desde el registro de pagos

El wizard `account.payment.register` DEBE (MUST) permitir marcar el pago como retención IVA (`is_retention`): al activarlo carga las líneas de retención desde las facturas seleccionadas, forzando el diario de retención IVA de clientes y deshabilitando el agrupamiento; DEBE (MUST) rechazar la operación si alguna factura no tiene impuestos o ya tiene una retención IVA en borrador o emitida. Al confirmar, crea los pagos marcados como retención con monto tomado de las líneas, crea un comprobante `account.retention` tipo `iva`/`out_invoice` con el número de referencia indicado y lo emite (la publicación y conciliación las realiza la emisión del comprobante). Los diarios de retención de proveedor DEBEN (MUST) quedar excluidos de los diarios seleccionables del wizard.

#### Scenario: Registro de retención de cliente

- **WHEN** el usuario registra un pago de retención IVA sobre una factura de cliente con impuestos, indicando la referencia del comprobante del cliente
- **THEN** se crea y emite un comprobante IVA `out_invoice` con esa referencia, con sus pagos conciliados a la factura

#### Scenario: Factura con retención vigente

- **WHEN** se marca `is_retention` y alguna factura seleccionada ya tiene retención IVA en borrador o emitida
- **THEN** el wizard muestra el error y desactiva la opción de retención

### Requirement: Retenciones de facturación a terceros solo sobre facturas publicadas

Para comprobantes marcados `is_third_party_retention`, el sistema DEBE (MUST) impedir crearlos o modificarlos cuando alguna factura de sus líneas no está publicada.

#### Scenario: Creación sobre factura en borrador

- **WHEN** se crea una retención de terceros cuyas líneas apuntan a una factura en borrador
- **THEN** se lanza un `UserError` indicando que no pueden crearse retenciones para facturas en borrador o canceladas

### Requirement: Generación masiva de retenciones ISLR

El wizard `batch.retentions.wizard` DEBE (MUST) separar las facturas seleccionadas en válidas (publicadas, elegibles para ISLR y sin ninguna retención ISLR previa) e inválidas, y generar retenciones ISLR solo para las válidas: una por factura, o una por partner agrupando sus facturas si `group_retentions` está activo; las retenciones de proveedor se emiten automáticamente según la configuración `create_retentions_of_suppliers_in_draft` y la marca por línea. Si no hay facturas válidas DEBE (MUST) lanzar un error.

#### Scenario: Lote sin facturas válidas

- **WHEN** se procesa el lote y ninguna factura cumple las condiciones
- **THEN** se lanza un `UserError` indicando que no hay retenciones válidas para procesar

#### Scenario: Lote agrupado por proveedor

- **WHEN** se procesa un lote con `group_retentions` activo y varias facturas de un mismo proveedor
- **THEN** se crea un único comprobante ISLR con las líneas de todas las facturas de ese proveedor

### Requirement: Exportación TXT de retenciones IVA para el SENIAT

El wizard `wizard.retention.iva` DEBE (MUST) validar antes de generar el TXT que exista rango de fechas, que la compañía tenga RIF (`vat`) y que existan comprobantes IVA de proveedor emitidos en el período; el archivo se entrega por el controlador de descarga con los datos por línea (RIF del agente, período, factura, número de control, comprobante, alícuota, base, IVA retenido y monto exento), usando los montos en moneda alterna cuando la moneda base de la compañía no es VEF.

#### Scenario: Período sin retenciones

- **WHEN** se genera el TXT de un período sin comprobantes IVA de proveedor emitidos
- **THEN** se lanza un `UserError` indicando que no se encontraron retenciones en el período

#### Scenario: Compañía sin RIF

- **WHEN** se genera el TXT y la compañía no tiene `vat`
- **THEN** se lanza un `UserError` indicando la falta del RIF

### Requirement: Reporte ARCV de retenciones ISLR por proveedor

El wizard `arcv.report` DEBE (MUST) generar el comprobante ARCV de un proveedor agrupando las líneas de retención ISLR emitidas (`type = in_invoice`) del rango de fechas por año, mes y porcentaje de tarifa, totalizando base retenida y monto retenido (en moneda base y alterna) por grupo, e incluyendo el monto pagado de las facturas no asociado a retenciones.

#### Scenario: Proveedor con retenciones en dos meses

- **WHEN** se imprime el ARCV de un proveedor con retenciones ISLR emitidas en dos meses distintos
- **THEN** el reporte muestra una fila por combinación período/porcentaje con sus totales

### Requirement: Reporte XLSM de ISLR del período

El wizard `wizard.retention.islr` DEBE (MUST) generar el Excel con macro (XLSM) de las retenciones ISLR de proveedor emitidas en el período (una fila por línea con RIF retenido, factura, número de control, fecha, código de concepto según el tipo de persona, monto de operación y porcentaje), y lanzar un error si no existen retenciones en el período seleccionado.

#### Scenario: Período sin retenciones ISLR

- **WHEN** se genera el reporte y no hay comprobantes ISLR de proveedor emitidos en el rango
- **THEN** se lanza un `ValidationError` indicando que no se encontraron retenciones en el período

### Requirement: Bloqueo de impresión del comprobante en borrador

El sistema DEBE (MUST) impedir descargar el PDF del comprobante de retención (`l10n_ve_payment_extension.retention_voucher_template`) cuando el comprobante está en estado borrador (override de `_render_qweb_pdf` en `ir.actions.report`).

#### Scenario: Descarga de comprobante en borrador

- **WHEN** se intenta imprimir el comprobante de una retención en estado `draft`
- **THEN** se lanza un `ValidationError` indicando que no puede descargarse en borrador

### Requirement: Aislamiento multi-compañía de las retenciones

Los comprobantes y sus líneas DEBEN (MUST) estar restringidos por reglas de registro globales (`ir.rule`) a las compañías del usuario (`company_id` en `company_ids` o vacío), y ambos modelos llevan `company_id` obligatorio con la compañía activa por defecto.

#### Scenario: Usuario de otra compañía

- **WHEN** un usuario sin acceso a la compañía de un comprobante consulta las retenciones
- **THEN** ese comprobante y sus líneas no aparecen en los resultados
