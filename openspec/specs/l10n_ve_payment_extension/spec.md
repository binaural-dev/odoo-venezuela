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

En `create` el sistema DEBE (MUST) ejecutar `_set_sequence` sobre todo comprobante sin `number` —sin distinguir tipo ni flujo, por lo que también numera los comprobantes de cliente— asignando un correlativo con formato `AAAAMM` (año y mes de `date_accounting`) seguido del siguiente valor de la secuencia de la compañía activa: `retention.iva.control.number` con padding 8 para IVA (resultando 14 dígitos) y `retention.islr.control.number` con padding 5 para ISLR; el correlativo se guarda en `number` y `name`. Además, `action_post` vuelve a invocar `_set_sequence` solo para los comprobantes de proveedor (`in_invoice`, `in_refund`, `in_debit`). La secuencia se crea automáticamente si no existe, pero para municipal la búsqueda usa el código `retention.municipal.control.number` mientras la creación registra la secuencia con el código `retention.iva.control.number` y padding 5, por lo que la búsqueda nunca la reencuentra y cada numeración municipal crea una secuencia nueva que arranca de su primer valor.

#### Scenario: Comprobante IVA de proveedor sin número

- **WHEN** se crea un comprobante de retención IVA de proveedor sin `number`
- **THEN** recibe un número de 14 dígitos compuesto por año, mes y la secuencia de 8 dígitos

#### Scenario: Comprobante de cliente creado sin número

- **WHEN** se crea por código un comprobante de tipo cliente sin `number`
- **THEN** también recibe el correlativo `AAAAMM` + secuencia, porque `_set_sequence` en `create` no filtra por tipo

#### Scenario: Numeración municipal repetida

- **WHEN** se numeran dos comprobantes municipales en una compañía sin secuencia municipal previa
- **THEN** cada uno crea una secuencia nueva registrada con el código de IVA y ambos reciben el mismo valor inicial de secuencia

### Requirement: Formato de 14 dígitos del número de comprobante IVA

El sistema DEBE (MUST) validar en `action_post` que el `number` de todo comprobante IVA sea exactamente 14 dígitos numéricos, y el constraint `_check_number` DEBE (MUST) aplicar el mismo formato a los comprobantes de cliente (`out_invoice`, `out_refund`) con número fuera del estado borrador.

#### Scenario: Número IVA con formato inválido

- **WHEN** se intenta emitir un comprobante IVA cuyo número no cumple 14 dígitos numéricos
- **THEN** se lanza un `ValidationError` indicando el formato requerido

### Requirement: Número obligatorio en retenciones de cliente

El sistema DEBE (MUST) impedir emitir un comprobante de tipo cliente (`out_invoice`, `out_refund`, `out_debit`) sin `number`, ya que el número lo emite el agente de retención externo. Esta validación se evalúa en `action_post` **después** de la comprobación de retención contra el saldo pendiente y opera solo sobre el valor vigente del campo: como `create` ya numeró todo comprobante que se guardó sin número, el error se produce en la práctica cuando el número fue vaciado o nunca se persistió, no como sustituto de la numeración automática.

#### Scenario: Retención de cliente sin número

- **WHEN** se ejecuta `action_post` sobre una retención de cliente cuyo `number` está vacío
- **THEN** se lanza un `UserError` pidiendo insertar un número

#### Scenario: Retención de cliente numerada automáticamente

- **WHEN** se guarda una retención de cliente sin indicar número y luego se emite
- **THEN** no se lanza el `UserError`, porque `create` le asignó el correlativo automático

### Requirement: Carga automática de líneas de retención IVA por partner

Al cambiar el partner, `onchange_partner_id` DEBE (MUST) primero validar los diarios de retención de la compañía (`_validate_retention_journals`) para todos los comprobantes del recordset —por lo que la falta de configuración de diarios se manifiesta ya al seleccionar el partner— y luego: en comprobantes marcados `is_third_party_retention` con líneas existentes, recalcular esas líneas con `_onchange_move_id` sin reemplazarlas; y en los comprobantes normales de tipo IVA en borrador con partner, reemplazar las líneas cargándolas desde las facturas del partner que estén publicadas, de la misma compañía, con impuestos mayores a cero, sin `iva_voucher_number`, con `amount_residual` mayor a 0 y sin líneas en otra retención IVA en estado `draft` o `emitted` (proveedor: `in_invoice`/`in_refund`; cliente: `out_invoice`/`out_refund`), registrando las facturas elegibles en `available_invoice_ids` y, en el flujo de proveedor, fijando `date_accounting` en la fecha de hoy. Si no existe ninguna factura elegible DEBE (MUST) lanzar un error.

#### Scenario: Comprobante de facturación a terceros

- **WHEN** se cambia el partner de un comprobante con `is_third_party_retention` y líneas existentes
- **THEN** las líneas se conservan y se recalculan con el tipo de retención del nuevo partner, sin cargar facturas nuevas

#### Scenario: Compañía sin diarios configurados al elegir partner

- **WHEN** se selecciona el partner en un comprobante cuyo tipo y flujo no tienen diario de retención configurado
- **THEN** se lanza un `UserError` de configuración de diarios antes de intentar cargar líneas

#### Scenario: Proveedor con facturas pendientes

- **WHEN** se selecciona un proveedor con facturas publicadas con IVA sin retención previa vigente
- **THEN** el comprobante se llena con una línea por cada grupo de impuesto de cada factura elegible

#### Scenario: Partner sin facturas elegibles

- **WHEN** se selecciona un partner sin facturas con impuestos por retener
- **THEN** se lanza un `UserError` indicando que no hay facturas con impuestos por retener

### Requirement: Cálculo de la retención IVA por grupo de impuestos

El sistema DEBE (MUST) calcular cada línea de retención IVA por grupo de impuesto de la factura, recorriendo solo los grupos que tengan impuestos con monto mayor a cero en las líneas de la factura: `iva_amount` es el impuesto del grupo, `invoice_amount` su base imponible, `invoice_total` el total de la factura, `aliquot` la alícuota del primer impuesto del grupo, `related_percentage_tax_base` el porcentaje del tipo de retención y `retention_amount = |iva_amount × porcentaje / 100|`, con los equivalentes en moneda alterna calculados con el mismo porcentaje (sin valor absoluto). El porcentaje se toma del `withholding_type_id.value` del partner **de la factura** en `compute_retention_lines_data`, mientras que el onchange por línea (`_onchange_move_id`) prefiere el partner del comprobante y cae en el de la factura solo si el comprobante no tiene partner; si no hay tipo de retención el porcentaje usado es 0 y la línea queda en 0 sin error. El módulo instala los tipos de retención `75%` y `100%` como data. Una factura sin impuestos con monto mayor a cero DEBE (MUST) interrumpir el cálculo, aunque el mensaje de error se arma con `invoice_id.number` —campo inexistente en `account.move`— por lo que la interrupción se manifiesta como error de atributo y no como el `UserError` previsto; en el onchange de la línea el mismo caso solo devuelve un aviso "The invoice has no tax." sin bloquear. El error explícito por partner sin tipo de retención existe únicamente en la creación de retenciones IVA desde la factura (`_create_retention`).

#### Scenario: Contribuyente especial al 75%

- **WHEN** se calcula la retención IVA de una factura con IVA 16% para un partner con tipo de retención 75%
- **THEN** la línea queda con monto retenido igual al 75% del IVA del grupo de impuesto

#### Scenario: Partner sin tipo de retención al crear desde la factura

- **WHEN** se genera la retención IVA desde una factura (`_create_retention`) cuyo partner no tiene `withholding_type_id`
- **THEN** se lanza un `UserError` indicando que el partner no tiene tipo de retención

#### Scenario: Partner sin tipo de retención al cargar líneas

- **WHEN** se cargan líneas de retención IVA de un partner sin `withholding_type_id` por el onchange de la línea
- **THEN** la línea se crea con porcentaje y monto retenido en 0, sin lanzar error

#### Scenario: Factura sin impuestos en la carga masiva

- **WHEN** `compute_retention_lines_data` recibe una factura sin impuestos con monto mayor a cero
- **THEN** la operación se interrumpe al construir el mensaje del error, sin llegar a crear líneas

### Requirement: Autollenado configurable del monto en retención IVA de cliente

El respeto del flag `auto_fill_retention_amount_iva` DEBE (MUST) depender de la vía de carga: en `compute_retention_lines_data` (carga masiva desde el partner, desde la factura y desde el registro de pagos) el flag se aplica a las facturas `out_invoice` **y** `out_refund`, dejando `retention_amount` y `foreign_retention_amount` en 0 cuando está desactivado; en el onchange por línea `_onchange_move_id` el flag solo se consulta cuando el `move_type` es exactamente `out_invoice`, de modo que al elegir manualmente una nota de crédito de cliente (`out_refund`) el monto calculado se precarga aunque el flag esté desactivado. En facturas de proveedor el monto siempre se precarga.

#### Scenario: Compañía sin autollenado

- **WHEN** se cargan líneas de retención IVA de una factura `out_invoice` con `auto_fill_retention_amount_iva` desactivado
- **THEN** las líneas quedan con monto retenido 0

#### Scenario: Compañía con autollenado

- **WHEN** el flag está activo y se cargan líneas de retención IVA de cliente
- **THEN** las líneas quedan con el monto calculado según el tipo de retención del partner

#### Scenario: Nota de crédito de cliente elegida en la línea

- **WHEN** con el flag desactivado el usuario selecciona en una línea de retención IVA una nota de crédito de cliente (`out_refund`)
- **THEN** la línea queda con el monto retenido calculado, porque el onchange solo evalúa el flag para `out_invoice`

### Requirement: Parámetros ISLR según el tipo de persona del sujeto retenido

Al asignar un concepto de pago a una línea ISLR, el sistema DEBE (MUST) tomar los parámetros (`pay_from`, `percentage_tax_base`, porcentaje y sustraendo de la tarifa) de la línea de concepto (`payment.concept.line`) cuyo `type_person_id` coincide con el tipo de persona del sujeto: el del partner del comprobante (o de la factura) en retenciones de proveedor, y el del partner de la propia compañía en retenciones de cliente (`out_invoice`). Emitir una retención ISLR DEBE (MUST) exigir que el sujeto tenga `type_person_id` y que las líneas tengan concepto de pago.

#### Scenario: Concepto con línea para el tipo de persona

- **WHEN** una línea ISLR de proveedor recibe un concepto que tiene una línea para el tipo de persona del proveedor
- **THEN** la línea de retención copia `related_pay_from`, `related_percentage_tax_base`, `related_percentage_fees` y `related_amount_subtract_fees` de esa línea de concepto

#### Scenario: Sujeto sin tipo de persona

- **WHEN** se emite una retención ISLR cuyo partner no tiene tipo de persona
- **THEN** se lanza un `UserError` pidiendo seleccionar un tipo de persona

### Requirement: Fórmula de retención ISLR con tarifa simple

Para tarifas sin tasa acumulada (y también cuando la tarifa es acumulada pero no se resolvió un valor de unidad tributaria), `_compute_retention_amount` DEBE (MUST) calcular `|base × (% base imponible / 100) × (% tarifa / 100) − sustraendo|` usando `invoice_amount` para `retention_amount` y `foreign_invoice_amount` para `foreign_retention_amount`. `foreign_retention_amount` se obtiene **siempre** pasando ese resultado por `_convert` desde la moneda de la compañía hacia la moneda alterna a la fecha contable del asiento (`move_id.date`, no `invoice_date`), sea la moneda base VEF o no; y cuando la moneda base de la compañía no es VEF también `retention_amount` se entrega convertido con ese mismo `_convert`. En consecuencia el resultado aritmético directo solo se observa en `retention_amount` de compañías con base VEF.

#### Scenario: Persona jurídica con tarifa porcentual en compañía con base VEF

- **WHEN** una línea ISLR de una compañía con moneda base VEF tiene base 1000, porcentaje de base imponible 100, tarifa 5% y sustraendo 0
- **THEN** `retention_amount` es 50

#### Scenario: Compañía con base distinta de VEF

- **WHEN** la misma línea pertenece a una compañía cuya moneda base no es VEF
- **THEN** `retention_amount` es el resultado de la fórmula convertido con `_convert` de la moneda de la compañía a la moneda alterna a la fecha del asiento

#### Scenario: Tarifa con sustraendo

- **WHEN** la tarifa aplica sustraendo y el resultado de base × porcentajes es menor que el sustraendo
- **THEN** el monto retenido es el valor absoluto de la diferencia

#### Scenario: Tarifa acumulada sin valor de unidad tributaria resuelto

- **WHEN** la línea de concepto es acumulada pero no se pudo leer el valor de la unidad tributaria de la tarifa
- **THEN** el cálculo cae en esta fórmula simple en lugar de la fórmula por tramos en UT

### Requirement: Fórmula de retención ISLR con tarifa acumulada por tramos en UT

Para tarifas con `accumulated_rate`, la selección del tramo (`_compute_related_fields`) DEBE (MUST): (1) determinar el inicio del ejercicio fiscal con `fiscalyear_last_day`/`fiscalyear_last_month` de la compañía y buscar las facturas publicadas del mismo partner, de la misma compañía, con `move_type` igual al **tipo del comprobante** (`retention_id.type`) y fecha entre el inicio del ejercicio y la fecha de la factura actual, conservando solo las que ya tienen líneas de retención ISLR; (2) acumular su base: si la moneda de la compañía es exactamente USD se suman las bases por grupo de `groups_by_foreign_subtotal` de esas facturas más la actual, y en cualquier otro caso se suman los `amount_untaxed` de las anteriores junto con el de la factura actual; (3) dividir ese total entre el valor de la UT de la tarifa (`tax_unit_ids.value`, un Many2one) y multiplicarlo por `percentage_tax_base / 100`; y (4) elegir, sobre los tramos ordenados por `start`, el primero cuyo rango `start`–`stop` contenga ese valor, tratando `stop = 0` como tramo infinito (aplica si el valor es mayor o igual a `start`), tomando su porcentaje y un sustraendo igual a `subtract_ut × valor UT`. Si ningún tramo coincide, el sistema DEBE (MUST) dejar en cero `related_pay_from`, `related_percentage_tax_base`, `related_percentage_fees`, `related_amount_subtract_fees` y `foreign_currency_rate` sin lanzar error, con lo que la retención resulta 0. Una tarifa acumulada sin unidad tributaria DEBE (MUST) lanzar un error al computar estos campos. El monto retenido (`_compute_retention_amount`) se calcula sobre la base de la **propia línea** (no sobre la acumulada): base en UT redondeada, por el porcentaje de base imponible, por el porcentaje del tramo, menos el sustraendo expresado en UT, todo multiplicado de vuelta por el valor de la UT y en valor absoluto; se usa `invoice_amount` en compañías con base VEF y `foreign_invoice_amount` en las demás, y el importe de la otra moneda se obtiene con `_convert` a la fecha del asiento.

#### Scenario: Base acumulada dentro de un tramo intermedio

- **WHEN** la base acumulada en UT del ejercicio cae dentro del rango `start`–`stop` de un tramo
- **THEN** la línea usa el porcentaje de ese tramo y el sustraendo `subtract_ut × valor UT`

#### Scenario: Base acumulada sobre el último tramo

- **WHEN** la base acumulada supera el `start` del tramo con `stop = 0`
- **THEN** se aplica ese tramo infinito

#### Scenario: Base acumulada fuera de todos los tramos

- **WHEN** la base acumulada en UT no cae en ningún tramo definido de la tarifa
- **THEN** los porcentajes y el sustraendo de la línea quedan en 0 y el monto retenido resulta 0, sin error

#### Scenario: Monto calculado sobre la base de la línea

- **WHEN** la base acumulada del ejercicio ubica la línea en un tramo del 3%
- **THEN** el monto retenido se calcula con la base de esa línea (no con la base acumulada) convertida a UT

#### Scenario: Tarifa acumulada sin unidad tributaria

- **WHEN** se calculan los campos relacionados de una línea con tarifa acumulada cuyo registro no tiene unidad tributaria
- **THEN** se lanza un `UserError` indicando que la tarifa no tiene una unidad tributaria válida

### Requirement: Cálculo del sustraendo de la tarifa

Cuando una tarifa (`fees.retention`) tiene activo `apply_subtracting`, su campo `amount_subtract` DEBE (MUST) calcularse como `valor de la UT × 83.3334 × porcentaje de la tarifa / 100`; con el flag desactivado el sustraendo es 0.

#### Scenario: Tarifa del 3% con sustraendo

- **WHEN** una tarifa con `apply_subtracting` activo tiene porcentaje 3 y la UT vale 9
- **THEN** `amount_subtract` es `9 × 83.3334 × 3 / 100`

### Requirement: Validaciones de la tarifa de retención

El sistema DEBE (MUST) impedir guardar una tarifa con `accumulated_rate` activo sin tramos en `accumulated_rate_ids`, y rechazar porcentajes de tarifa negativos (constraint `_check_data_accumulated`, escrito sin iterar el recordset, por lo que solo puede evaluarse sobre un registro a la vez). La tarifa DEBE (MUST) tener unidad tributaria: `tax_unit_ids` es un Many2one **obligatorio** (pese al nombre en plural) restringido por dominio a unidades tributarias con `status = True`. Un porcentaje mayor a 100 no se rechaza con error sino con un aviso de onchange que devuelve el campo a 0.

#### Scenario: Tarifa acumulada sin tramos

- **WHEN** se guarda una tarifa marcada como acumulada sin líneas de tramos
- **THEN** se lanza un `ValidationError` exigiendo ingresar las tarifas acumuladas

#### Scenario: Porcentaje mayor a 100

- **WHEN** el usuario escribe 150 en el porcentaje de la tarifa
- **THEN** se muestra un aviso indicando que el porcentaje no puede superar 100% y el campo vuelve a 0

#### Scenario: Tarifa sin unidad tributaria

- **WHEN** se intenta guardar una tarifa sin unidad tributaria
- **THEN** la creación falla por ser un campo obligatorio del modelo

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

El método `validate_islr` DEBE (MUST) exigir que la factura esté publicada, que tenga al menos una línea cuyo producto tenga concepto de pago (aquí **sin** exigir que el producto sea de tipo servicio, a diferencia del cálculo de `is_isrl_retention_available`), que el sujeto (el partner de la compañía en facturas de cliente `out_invoice`, el proveedor en las demás) exista y tenga tipo de persona, y que la factura no tenga ya una retención ISLR emitida (considerando solo retenciones no canceladas); si existe una en borrador, se reutiliza y se abre en lugar de crear otra.

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

### Requirement: Prohibición de montos en cero en líneas de un comprobante no borrador

El constraint `_constraint_amounts_in_zero` de `account.retention.line` DEBE (MUST) rechazar, para líneas que ya pertenecen a un comprobante cuyo `state` no es `draft`, tener `retention_amount`, `invoice_total` o `invoice_amount` en 0 (los campos en moneda alterna disparan el constraint pero no se evalúan, y las líneas sin `retention_id` se omiten). El constraint se dispara únicamente al escribir esos campos de la línea: el `state` es un campo relacionado no almacenado y no forma parte de sus disparadores, por lo que emitir el comprobante (que solo escribe en `account.retention`) NO reevalúa la restricción y un comprobante puede quedar emitido con líneas en 0.

#### Scenario: Emisión con línea en cero

- **WHEN** un comprobante con una línea de monto retenido 0 pasa a emitido mediante `action_post`
- **THEN** el comprobante se emite sin que el constraint se dispare

#### Scenario: Edición de una línea de un comprobante emitido

- **WHEN** se escribe 0 en el monto retenido, el total facturado o la base de una línea de un comprobante ya emitido
- **THEN** se lanza un `ValidationError` indicando que no se puede crear una retención con monto 0

### Requirement: Generación y conciliación automática de pagos al emitir

Al emitir un comprobante que aún no tiene pagos, el sistema DEBE (MUST) crear un `account.payment` por cada factura involucrada (agrupando sus líneas por `move_id`), marcado con `is_retention` y `payment_type_retention`, con el diario de retención de la compañía correspondiente al tipo de retención y al flujo (las variantes `in_refund`/`in_debit` se resuelven con el diario de `in_invoice` y las `out_refund`/`out_debit` con el de `out_invoice`), en la moneda de la compañía y con fecha `date_accounting`; el sentido del pago se deriva de si el documento es una nota de crédito del mismo flujo. Los pagos se crean sin monto y este se asigna después con `compute_retention_amount_from_retention_lines`, como suma simple (sin valor absoluto) de los `retention_amount` de las líneas vinculadas. Luego DEBE (MUST) publicarlos todos y conciliarlos contra la línea por cobrar/por pagar del asiento del pago asignándola a las facturas de sus líneas; si el comprobante no generó ningún pago, la conciliación DEBE (MUST) fallar con un `UserError`. Para comprobantes ISLR, antes de crear los pagos se exige que el partner tenga tipo de persona y que exista al menos una línea con concepto de pago. Si el diario correspondiente no está configurado, la emisión DEBE (MUST) fallar con error. Un comprobante que ya tiene pagos se omite en esta etapa.

#### Scenario: Comprobante sin pagos generados

- **WHEN** se emite un comprobante que no produjo ningún pago (por ejemplo sin líneas)
- **THEN** se lanza un `UserError` indicando que no se encontraron pagos para conciliar

#### Scenario: Comprobante con dos facturas

- **WHEN** se emite un comprobante IVA de proveedor con líneas de dos facturas
- **THEN** se crean dos pagos de retención, uno por factura, publicados y conciliados con su factura

#### Scenario: Compañía sin diario de retención

- **WHEN** se emite un comprobante y la compañía no tiene configurado el diario de retención del tipo y flujo correspondiente
- **THEN** se lanza un `UserError` indicando la falta de configuración de diarios

### Requirement: Nombre identificable del asiento del pago de retención

El asiento del pago de retención DEBE (MUST) renombrarse (`_synchronize_to_moves`) con el prefijo `RIV` (IVA), `RIS` (ISLR) o `RM` (municipal), seguido del número del comprobante y del nombre de la factura de su **primera** línea; en ISLR se agregan los primeros 5 caracteres del nombre del concepto de pago y en municipal el nombre de la actividad económica y de su ramo. El asiento también queda marcado como `is_manually_modified`. El renombrado se omite cuando el pago no tiene líneas de retención o su comprobante no tiene número.

#### Scenario: Pago de retención IVA emitido

- **WHEN** se sincroniza el asiento de un pago de retención IVA con número de comprobante y línea asociada
- **THEN** el asiento queda nombrado `RIV-<número>-<factura>`

#### Scenario: Pago de retención sin número de comprobante

- **WHEN** se sincroniza el asiento de un pago cuyo comprobante todavía no tiene número
- **THEN** el nombre del asiento se deja sin modificar

### Requirement: Escritura del número de comprobante en la factura

Al emitir un comprobante, el sistema DEBE (MUST) escribir su número en las facturas de sus líneas: `iva_voucher_number`, `islr_voucher_number` o `municipal_voucher_number` según el tipo de retención; al cancelar el comprobante esos campos DEBEN (MUST) limpiarse.

#### Scenario: Emisión de comprobante IVA

- **WHEN** se emite un comprobante IVA sobre una factura
- **THEN** la factura queda con `iva_voucher_number` igual al número del comprobante

#### Scenario: Cancelación del comprobante

- **WHEN** se cancela el comprobante
- **THEN** el número de comprobante registrado en la factura se limpia

### Requirement: Generación automática de retenciones al publicar la factura

Al publicar una factura (`action_post` de `account.move`), el sistema DEBE (MUST) crear automáticamente: la retención ISLR (`auto_create_islr_retention`) si `generate_islr_retention` está activo y no hay `islr_voucher_number`; la retención IVA si `generate_iva_retention` está activo y no hay `iva_voucher_number` (validando el diario IVA del flujo correspondiente, que existan impuestos aplicables y que el partner tenga `withholding_type_id`); y, solo en facturas de proveedor (`in_invoice`/`in_refund`), la retención municipal cuando hay líneas municipales no emitidas y no hay `municipal_voucher_number`. La emisión automática DEBE (MUST) ocurrir únicamente cuando `create_retentions_of_suppliers_in_draft` está desactivado **y** el `move_type` es exactamente `in_invoice`: las notas de crédito y débito de proveedor y las facturas de cliente crean la retención pero la dejan en borrador. Pese a ello, en los flujos IVA e ISLR el número del comprobante se escribe en `iva_voucher_number` / `islr_voucher_number` de la factura inmediatamente después de crearlo, incluso si la retención quedó en borrador (el flujo municipal no escribe su número en esta ruta). La creación automática de ISLR exige además el diario ISLR **de proveedor** de la compañía y el `type_person_id` del partner de la factura, también cuando la factura es de cliente.

#### Scenario: Factura de proveedor con retención IVA automática

- **WHEN** se publica una factura de proveedor `in_invoice` con `generate_iva_retention` activo y la compañía no crea retenciones en borrador
- **THEN** se crea la retención IVA, se emite automáticamente y la factura recibe el número de comprobante

#### Scenario: Compañía con retenciones en borrador

- **WHEN** `create_retentions_of_suppliers_in_draft` está activo y se publica la factura
- **THEN** la retención se crea en estado borrador sin emitirse, y la factura queda igualmente con el número de comprobante IVA o ISLR

#### Scenario: Nota de crédito de proveedor con retención marcada

- **WHEN** se publica una `in_refund` con `generate_iva_retention` activo y la compañía no crea retenciones en borrador
- **THEN** la retención IVA se crea pero NO se emite, porque la emisión automática solo aplica a `in_invoice`

#### Scenario: Factura de cliente con retención ISLR automática sin diario de proveedor

- **WHEN** se publica una factura de cliente con `generate_islr_retention` activo y la compañía no tiene configurado el diario ISLR de proveedor
- **THEN** se lanza un `UserError` exigiendo ese diario aunque el flujo sea de cliente

#### Scenario: Factura sin impuestos con retención IVA marcada

- **WHEN** se publica una factura marcada para retención IVA sin impuestos aplicables
- **THEN** se lanza un `UserError` indicando que no puede generarse la retención

### Requirement: Protección de los pagos de retención

El sistema DEBE (MUST) impedir pasar a borrador o cancelar un pago marcado con `is_retention` (`action_draft`/`action_cancel` de `account.payment`), pasar a borrador su asiento (`button_draft` de `account.move`, evaluando `origin_payment_id`) y romper su conciliación desde la factura (`js_remove_outstanding_partial`, que también contempla `origin_payment_advanced_payment_id`). La guarda se evalúa sobre el estado del **pago** (`is_retention` y `state != "cancel"`) y no sobre el estado del comprobante, por lo que también bloquea los pagos de comprobantes en borrador; el mensaje de error, en cambio, nombra el comprobante vinculado. Estas operaciones solo proceden con el contexto interno `bypass_retention_lock` que usa la cancelación del comprobante.

#### Scenario: Cancelación directa del pago

- **WHEN** un usuario intenta cancelar un pago de retención cuyo comprobante sigue emitido
- **THEN** se lanza un `UserError` indicando que debe cancelarse primero el comprobante

#### Scenario: Pago de un comprobante en borrador

- **WHEN** se intenta pasar a borrador un pago con `is_retention` cuyo comprobante está en estado `draft`
- **THEN** se lanza igualmente el `UserError`, porque la guarda solo mira que el pago no esté cancelado

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

Cada línea de concepto de pago (`payment.concept.line`) DEBE (MUST) tener un código único a nivel de sistema (constraint SQL `unique_code` sobre `code`, campo obligatorio), y exige tipo de persona (limitado a los activos) y concepto de pago asociado (limitado a los de estado activo, con `ondelete="cascade"`). Un porcentaje de base imponible mayor a 100 no se rechaza con error: un aviso de onchange lo devuelve a 0.

#### Scenario: Código repetido

- **WHEN** se crea una línea de concepto con un código ya existente
- **THEN** el registro se rechaza indicando que el código de concepto ya existe

### Requirement: Retención IVA de cliente desde el registro de pagos

El wizard `account.payment.register` DEBE (MUST) permitir marcar el pago como retención IVA (`is_retention`): al activarlo carga las líneas de retención desde las facturas del contexto, fuerza el diario de retención IVA de clientes, apaga `group_payment` y bloquea la edición de los campos del pago (`edit_retention_fields = False`). Cuando alguna factura no tiene impuestos con monto mayor a cero, o ya tiene una línea en una retención IVA en borrador o emitida, el onchange NO lanza excepción: devuelve un aviso (`warning`) y vuelve a poner `is_retention` en falso, sin cargar líneas. Al confirmar, crea los pagos marcados como retención con monto tomado de las líneas de su propia factura, omite la publicación y la conciliación estándar, y crea un comprobante `account.retention` tipo `iva`/`out_invoice` copiando `retention_ref` en `code`, `number` y `correlative`, que luego emite (la publicación y conciliación las realiza la emisión del comprobante). Como la emisión valida el formato del número IVA, una referencia que no sea exactamente 14 dígitos numéricos DEBE (MUST) hacer fallar la confirmación. Los diarios de retención de proveedor (IVA, ISLR y municipal) DEBEN (MUST) quedar excluidos de los diarios seleccionables del wizard, sea o no un pago de retención.

#### Scenario: Registro de retención de cliente

- **WHEN** el usuario registra un pago de retención IVA sobre una factura de cliente con impuestos, indicando una referencia de 14 dígitos del comprobante del cliente
- **THEN** se crea y emite un comprobante IVA `out_invoice` con esa referencia, con sus pagos conciliados a la factura

#### Scenario: Factura con retención vigente

- **WHEN** se marca `is_retention` y alguna factura seleccionada ya tiene retención IVA en borrador o emitida
- **THEN** el wizard muestra un aviso, desactiva la opción de retención y no carga líneas

#### Scenario: Referencia de comprobante con formato inválido

- **WHEN** se confirma el registro con una `retention_ref` que no tiene 14 dígitos numéricos
- **THEN** la emisión del comprobante lanza el `ValidationError` de formato del número IVA

### Requirement: Retenciones de facturación a terceros solo sobre facturas publicadas

Para comprobantes marcados `is_third_party_retention`, el sistema DEBE (MUST) impedir crearlos o modificarlos cuando alguna factura de sus líneas no está publicada.

#### Scenario: Creación sobre factura en borrador

- **WHEN** se crea una retención de terceros cuyas líneas apuntan a una factura en borrador
- **THEN** se lanza un `UserError` indicando que no pueden crearse retenciones para facturas en borrador o canceladas

### Requirement: Generación masiva de retenciones ISLR

El wizard `batch.retentions.wizard` DEBE (MUST) separar las facturas seleccionadas en válidas (`is_isrl_retention_available`, sin retención ISLR emitida, `count_islr_retention = 0` y estado `posted`) e inválidas —a las inválidas les apaga la marca `post_retention`— y generar retenciones **siempre de tipo ISLR** en `create_muti_retencion` (el campo `type_retention` del wizard solo alimenta el nombre mostrado, no el tipo creado): una por factura, o una por partner agrupando sus facturas si `group_retentions` está activo. Las facturas válidas sin conceptos de pago se omiten en silencio. En el modo por factura, la retención se emite cuando `create_retentions_of_suppliers_in_draft` está desactivado, el `move_type` es de proveedor (`in_invoice`, `in_refund`, `in_debit`) y la línea tiene `post_retention`; en el modo agrupado, la condición de emisión consulta `post_retention` sobre el `account.move` de referencia —campo que no existe en `account.move`, solo en las líneas del wizard— por lo que el intento de emisión automática agrupada falla con un error de atributo. En ambos modos el número del comprobante se escribe en `islr_voucher_number` de las facturas. Si no hay facturas válidas DEBE (MUST) lanzar un error.

#### Scenario: Lote sin facturas válidas

- **WHEN** se procesa el lote y ninguna factura cumple las condiciones
- **THEN** se lanza un `UserError` indicando que no hay retenciones válidas para procesar

#### Scenario: Lote agrupado por proveedor

- **WHEN** se procesa un lote con `group_retentions` activo y varias facturas de un mismo proveedor
- **THEN** se crea un único comprobante ISLR con las líneas de todas las facturas de ese proveedor

#### Scenario: Lote agrupado con emisión automática

- **WHEN** en el modo agrupado alguna línea tiene `post_retention` y la compañía no crea retenciones en borrador para una factura de proveedor
- **THEN** la ejecución falla al evaluar `post_retention` sobre la factura de referencia, que no expone ese campo

#### Scenario: Factura válida sin conceptos de pago

- **WHEN** una factura clasificada como válida no devuelve conceptos de pago desde sus líneas
- **THEN** se omite sin crear comprobante y sin avisar al usuario

### Requirement: Exportación TXT de retenciones IVA para el SENIAT

El wizard `wizard.retention.iva` DEBE (MUST) validar antes de generar el TXT que exista rango de fechas, que la compañía tenga RIF (`vat`) y que existan comprobantes emitidos en el período con `type_retention = iva` y `type = in_invoice` de la compañía activa, filtrando por el campo `date` (fecha del comprobante) y no por la fecha contable; los comprobantes de proveedor cuyo tipo sea `in_refund` o `in_debit` quedan fuera tanto del conteo como del archivo. El archivo se entrega por el controlador `/web/binary/download_retention_iva_txt` con una fila por línea de retención, separada por tabuladores en orden fijo (RIF del agente tomado del partner de la compañía, período `AAAAMM`, fecha de factura, tipo de operación "C", tipo de documento, RIF del proveedor con `prefix_vat`, número de documento, número de control, monto total, base imponible, IVA retenido, documento afectado, número de comprobante, monto exento, alícuota y número de expediente "0"), usando los montos en moneda alterna cuando la moneda base de la compañía no es VEF.

#### Scenario: Período sin retenciones

- **WHEN** se genera el TXT de un período sin comprobantes IVA de proveedor emitidos
- **THEN** se lanza un `UserError` indicando que no se encontraron retenciones en el período

#### Scenario: Período con solo retenciones sobre notas de crédito

- **WHEN** en el período únicamente existen comprobantes IVA emitidos con `type = in_refund`
- **THEN** el wizard los ignora y lanza el error de período sin retenciones

#### Scenario: Compañía sin RIF

- **WHEN** se genera el TXT y la compañía no tiene `vat`
- **THEN** se lanza un `UserError` indicando la falta del RIF

### Requirement: Reporte ARCV de retenciones ISLR por proveedor

El wizard `arcv.report` DEBE (MUST) generar el comprobante ARCV de un proveedor agrupando las líneas de retención ISLR emitidas (`type = in_invoice`) del rango de fechas por año, mes y porcentaje de tarifa, totalizando base retenida y monto retenido (en moneda base y alterna) por grupo, e incluyendo el monto pagado de las facturas no asociado a retenciones.

#### Scenario: Proveedor con retenciones en dos meses

- **WHEN** se imprime el ARCV de un proveedor con retenciones ISLR emitidas en dos meses distintos
- **THEN** el reporte muestra una fila por combinación período/porcentaje con sus totales

### Requirement: Reporte XLSM de ISLR del período

El wizard `wizard.retention.islr` DEBE (MUST) generar el Excel con macro (XLSM) de los comprobantes con `type_retention = islr`, `type = in_invoice` y estado `emitted` cuya `date_accounting` cae en el rango, con una fila por línea (RIF retenido con `prefix_vat`, número de factura y número de control recortados a sus últimos 10 caracteres sin guiones, fecha de operación, código de concepto de la línea de concepto que coincide con el tipo de persona del partner, monto de operación y porcentaje de la tarifa de esa línea), ordenadas por fecha, y lanzar un `ValidationError` si no existen comprobantes en el período. El dominio construido desde `print_report` NO filtra por compañía: el alcance queda determinado por las reglas de registro del usuario, de modo que el archivo puede incluir comprobantes de otras compañías permitidas mientras el encabezado imprime el RIF y el período de la compañía activa. El monto de operación se toma de `foreign_invoice_amount` cuando la moneda alterna de la compañía es VEF y de `invoice_amount` en caso contrario.

#### Scenario: Período sin retenciones ISLR

- **WHEN** se genera el reporte y no hay comprobantes ISLR de proveedor emitidos en el rango
- **THEN** se lanza un `ValidationError` indicando que no se encontraron retenciones en el período

#### Scenario: Usuario con acceso a varias compañías

- **WHEN** un usuario con acceso a dos compañías genera el XLSM desde una de ellas
- **THEN** el archivo incluye las retenciones ISLR emitidas de ambas compañías, con el encabezado de la compañía activa

### Requirement: Bloqueo de impresión del comprobante en borrador

El sistema DEBE (MUST) impedir descargar el PDF del comprobante de retención (`l10n_ve_payment_extension.retention_voucher_template`) cuando el comprobante está en estado borrador (override de `_render_qweb_pdf` en `ir.actions.report`).

#### Scenario: Descarga de comprobante en borrador

- **WHEN** se intenta imprimir el comprobante de una retención en estado `draft`
- **THEN** se lanza un `ValidationError` indicando que no puede descargarse en borrador

### Requirement: Aislamiento multi-compañía de las retenciones

El comprobante y sus líneas DEBE (MUST) restringirlos una regla de registro global (`ir.rule`) por modelo a las compañías del usuario (`company_id` en `company_ids` o vacío), con `company_id` obligatorio y por defecto la compañía activa en ambos modelos (en el comprobante además `readonly`). La verificación de coherencia entre compañías de Odoo solo está activa en `account.retention` (`_check_company_auto = True`): en `account.retention.line` y en el wizard `wizard.retention.islr` el atributo se escribió como `check_company = True`, que no es reconocido por el ORM y por lo tanto no valida nada.

#### Scenario: Usuario de otra compañía

- **WHEN** un usuario sin acceso a la compañía de un comprobante consulta las retenciones
- **THEN** ese comprobante y sus líneas no aparecen en los resultados

#### Scenario: Línea con factura de otra compañía

- **WHEN** se asigna a una línea de retención una factura de una compañía distinta a la de la línea
- **THEN** el ORM no bloquea la asignación, porque la línea no declara `_check_company_auto`

### Requirement: Borrado en cascada de líneas de retención y de sus pagos

Las relaciones de `account.retention.line` DEBEN (MUST) declararse con `ondelete="cascade"` hacia el comprobante (`retention_id`), la factura (`move_id`), el concepto de pago (`payment_concept_id`) y la actividad económica (`economic_activity_id`), de modo que eliminar cualquiera de esos registros elimina también las líneas de retención que lo referencian. Además, `unlink` de la línea DEBE (MUST) eliminar el `account.payment` asociado (`payment_id`) antes de borrarse, y `unlink` del pago DEBE (MUST) desvincular sus líneas de retención; el `retention_id` del pago también es `ondelete="cascade"`, por lo que borrar un comprobante en borrador arrastra sus pagos.

#### Scenario: Eliminación de una línea con pago

- **WHEN** se elimina una línea de retención que tiene un pago asociado
- **THEN** el pago se elimina junto con la línea

#### Scenario: Eliminación de un catálogo referenciado

- **WHEN** se elimina un concepto de pago o una actividad económica usados por líneas de retención
- **THEN** esas líneas de retención se eliminan por la cascada de la base de datos

### Requirement: Propagación de la condición de retención de la compañía al contacto

Al escribir `condition_withholding_id` en `res.company`, el sistema DEBE (MUST) copiar ese valor al `withholding_type_id` del partner de la compañía, de modo que el porcentaje usado en las retenciones IVA de cliente (que se lee del partner) quede alineado con la configuración de la compañía.

#### Scenario: Cambio de la condición de retención en ajustes

- **WHEN** se guarda en la compañía una nueva condición de retención
- **THEN** el partner de la compañía queda con ese mismo tipo de retención en `withholding_type_id`

#### Scenario: Compañía sin partner

- **WHEN** se escribe la condición de retención en una compañía sin partner asociado
- **THEN** la escritura se completa sin propagar el valor
