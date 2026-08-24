# l10n_ve_accountant

## Purpose

Núcleo contable de la localización venezolana: lleva la contabilidad espejo en la moneda alterna de la compañía (tasa, débito/crédito alterno por apunte, totales alternos en facturas y `tax_totals`), agrega las validaciones fiscales venezolanas (impuesto único por línea, límite de crédito, unicidad de nombres de asientos), la configuración de alícuotas de IVA por compañía, las unidades tributarias (`tax.unit`) y los reportes de detalle de facturas y pagos. Extiende `account.move`, `account.move.line`, `account.tax`, `account.payment`, `account.payment.register`, `account.journal`, `account.bank.statement.line`, `account.partial.reconcile`, `account.invoice.report`, `product.template`, `res.company`, `res.partner` y `res.currency`. Depende de `account`, `account_reports`, `sale`, `purchase`, `l10n_ve_base`, `l10n_ve_rate` (de donde consume `foreign_currency_id` de la compañía y los métodos `compute_rate`/`compute_inverse_rate` de `res.currency.rate`) y `l10n_ve_contact`. Es la base de `l10n_ve_invoice` y `l10n_ve_igtf`.

## Requirements

### Requirement: Moneda alterna por defecto en documentos contables

Los asientos (`account.move`), pagos (`account.payment`) y el wizard de registro de pagos (`account.payment.register`) DEBEN (MUST) inicializar su campo `foreign_currency_id` con la moneda alterna de la compañía activa (`foreign_currency_id` de `res.company`, definido en `l10n_ve_rate`).

#### Scenario: Creación de una factura

- **WHEN** se crea un documento contable en una compañía con moneda alterna configurada
- **THEN** el campo `foreign_currency_id` del documento queda con la moneda alterna de la compañía

### Requirement: Cálculo automático de la tasa según la fecha del documento

El sistema DEBE (MUST) calcular `foreign_rate` y `foreign_inverse_rate` de cada `account.move` invocando `res.currency.rate.compute_rate` sobre la moneda alterna del documento (`foreign_currency_id`) con la fecha del documento: para documentos de venta usa `invoice_date` y para el resto (compras, asientos) usa `date`; si la fecha no está definida usa la fecha actual. El recálculo (`_compute_rate`) depende únicamente de `invoice_date`, y en la creación del asiento se omite para los documentos `in_invoice`, que conservan la tasa por defecto calculada a la fecha de hoy. Los documentos con `manually_set_rate` activo quedan excluidos del recálculo.

#### Scenario: Factura de venta

- **WHEN** se establece o cambia la fecha de factura de un documento de venta sin tasa manual
- **THEN** `foreign_rate` y `foreign_inverse_rate` se recalculan con la tasa vigente a esa fecha

#### Scenario: Factura de proveedor recién creada

- **WHEN** se crea un documento `in_invoice`
- **THEN** la creación no dispara el recálculo de tasa y el documento conserva la tasa por defecto de la fecha actual

#### Scenario: Tasa fijada manualmente

- **WHEN** un documento tiene `manually_set_rate` en verdadero
- **THEN** el recálculo automático no modifica su tasa

### Requirement: Prohibición de tasas negativas o cero

El sistema DEBE (MUST) rechazar en el formulario del asiento una `foreign_rate` negativa y una `foreign_inverse_rate` negativa o igual a cero (onchanges `_onchange_foreign_rate` y `_onchange_foreign_inverse_rate` de `account.move`), y al editar `foreign_rate` recalcular `foreign_inverse_rate` mediante `compute_inverse_rate` de `l10n_ve_rate`.

#### Scenario: Tasa negativa

- **WHEN** un usuario introduce una tasa negativa en el asiento
- **THEN** se lanza un error de validación indicando que la tasa no puede ser negativa

#### Scenario: Tasa inversa cero

- **WHEN** un usuario introduce una tasa inversa igual a cero
- **THEN** se lanza un error de validación indicando que la tasa no puede ser cero

### Requirement: Las notas de crédito heredan la tasa del documento reversado

Al crear un `account.move` de tipo `out_refund` o `in_refund` con `reversed_entry_id`, el sistema DEBE (MUST) copiar `foreign_rate` y `foreign_inverse_rate` del documento reversado en lugar de usar la tasa de la fecha de la nota. Las notas de débito, que se crean como `in_invoice`/`out_invoice` con `debit_origin_id`, no heredan la tasa por esta vía.

#### Scenario: Nota de crédito de una factura

- **WHEN** se crea una nota de crédito a partir de una factura con tasa registrada
- **THEN** la nota de crédito queda con la misma `foreign_rate` y `foreign_inverse_rate` que la factura origen

#### Scenario: Nota de débito

- **WHEN** se crea una nota de débito con `debit_origin_id`
- **THEN** su tasa no se copia del documento de origen

### Requirement: Trazabilidad del cambio manual de tasa

Cuando un documento con `manually_set_rate` activo se crea o modifica con una `foreign_rate` distinta de la tasa vigente (o de la última tasa registrada en `last_foreign_rate`), el sistema DEBE (MUST) publicar un mensaje en el chatter indicando la tasa anterior y la nueva.

#### Scenario: Edición de la tasa manual

- **WHEN** se escribe una nueva `foreign_rate` en un asiento con tasa manual
- **THEN** se registra en el chatter un mensaje "The rate has been updated from X to Y"

### Requirement: Precio y subtotal en moneda alterna por línea

Cada línea de asiento (`account.move.line`) DEBE (MUST) calcular `foreign_price` según la moneda del documento: si es la moneda de la compañía, `price_unit * foreign_inverse_rate`; si es la moneda alterna, el propio `price_unit`; si es una tercera moneda, la conversión vía `_convert` a la fecha de la factura. A partir de `foreign_price` DEBE (MUST) calcular `foreign_subtotal` y `foreign_price_total` aplicando descuento, cantidad e impuestos (`compute_all` en la moneda alterna).

#### Scenario: Línea en moneda de la compañía

- **WHEN** una línea de factura está en la moneda de la compañía con tasa inversa registrada
- **THEN** `foreign_price` es el precio unitario multiplicado por `foreign_inverse_rate` y `foreign_subtotal` refleja cantidad y descuento

#### Scenario: Línea en moneda alterna

- **WHEN** la moneda del documento es la moneda alterna de la compañía
- **THEN** `foreign_price` es igual a `price_unit` sin conversión

### Requirement: Débito y crédito alterno por apunte contable

Cada apunte DEBE (MUST) calcular `foreign_debit`/`foreign_credit` (y su `foreign_balance` derivado) según la jerarquía de `_get_foreign_value`, evaluada en este orden: (1) líneas `payment_term`/`tax` usan `foreign_balance`; (2) líneas `line_section`/`line_note` valen 0; (3) el ajuste manual `foreign_debit_adjustment` y (4) el ajuste manual `foreign_credit_adjustment`; (5) líneas cuya moneda es la alterna **y** con `amount_currency` distinto de cero usan `amount_currency`; (6) asientos que no son facturas usan `_get_non_invoice_foreign_value`; (7) líneas `product`/`cogs` usan `foreign_subtotal` con el signo contable del documento; cualquier otro caso devuelve `None` y el apunte no se modifica. Los apuntes del diario de diferencia cambiaria de la compañía y los marcados con `not_foreign_recalculate` quedan excluidos del recálculo.

En asientos que no son facturas, `_get_non_invoice_foreign_value` DEBE (MUST) devolver, en este orden: el negativo de la suma de `amount_currency` de las líneas en moneda alterna cuando esa suma no es cero y existe exactamente una línea en moneda de la compañía; la conversión del balance a la moneda alterna a la fecha del apunte cuando la moneda de la línea no es la alterna; y en el resto de casos el balance multiplicado por `foreign_inverse_rate`.

#### Scenario: Ajuste manual

- **WHEN** un usuario establece `foreign_debit_adjustment` en una línea que no es de impuesto ni de término de pago
- **THEN** `foreign_debit` toma el valor absoluto del ajuste y no se recalcula por tasa

#### Scenario: Ajuste manual en una línea de término de pago

- **WHEN** la línea con ajuste manual tiene `display_type` `payment_term` o `tax`
- **THEN** el importe alterno se toma de `foreign_balance` y el ajuste manual no se aplica

#### Scenario: Asiento manual sin factura

- **WHEN** se crea un asiento de diario en moneda de la compañía sin líneas en moneda alterna
- **THEN** el débito/crédito alterno de cada línea es el balance multiplicado por `foreign_inverse_rate`

#### Scenario: Asiento espejo de una línea en moneda alterna

- **WHEN** un asiento no factura tiene líneas en moneda alterna y exactamente una línea en moneda de la compañía
- **THEN** esa línea recibe como importe alterno el negativo de la suma de `amount_currency` de las líneas en moneda alterna

#### Scenario: Línea excluida del recálculo

- **WHEN** una línea tiene `not_foreign_recalculate` activo
- **THEN** sus importes alternos no se modifican al recalcular el asiento

### Requirement: Distribución del contravalor alterno en líneas de término de pago

Al sincronizar las líneas dinámicas de una factura **en borrador** (`_distribute_foreign_pt_residual` solo actúa sobre `state = draft` que además sea factura y tenga moneda alterna configurada), el sistema DEBE (MUST) distribuir el total alterno entre las líneas `payment_term` proporcionalmente a su balance nativo (asignando el remanente de redondeo a la última línea), forzando que la suma de `foreign_debit` iguale a la de `foreign_credit` del asiento y marcando cada línea reescrita con `not_foreign_recalculate` para que no vuelva a recalcularse por tasa. El total a repartir se toma del **neto** de las líneas que no son `payment_term` ni `cogs` (suma de `foreign_debit` menos suma de `foreign_credit`, y viceversa para el otro lado), volviendo al bruto de cada lado cuando ese neto resulta negativo. Para documentos en una tercera moneda (ni la de la compañía ni la alterna) el total se obtiene convirtiendo `amount_total` a la moneda alterna a la fecha de factura, y una línea no-PT absorbe la diferencia de redondeo.

#### Scenario: Factura con dos cuotas

- **WHEN** una factura en borrador tiene dos líneas de término de pago
- **THEN** cada una recibe una porción del total alterno proporcional a su balance, la suma de ambas iguala el total alterno de las demás líneas y ambas quedan con `not_foreign_recalculate` activo

#### Scenario: Factura con líneas COGS

- **WHEN** el asiento incluye pares autobalanceados de líneas `cogs`
- **THEN** esas líneas se excluyen del total a repartir y no descuadran el importe alterno de las cuotas

#### Scenario: Factura ya publicada

- **WHEN** el asiento no está en borrador
- **THEN** la distribución no se ejecuta

#### Scenario: Factura en tercera moneda

- **WHEN** la factura está en una moneda distinta a la de la compañía y a la alterna
- **THEN** el total alterno distribuido es la conversión de `amount_total` a la moneda alterna a la fecha de factura

### Requirement: Contravalor alterno en los términos de pago calculados

`_compute_needed_terms` de `account.move` DEBE (MUST) agregar a cada entrada de `needed_terms` la clave `foreign_balance`, convirtiendo el `balance` de la entrada desde la moneda de la compañía a `foreign_currency_id` a la fecha de tasa de la factura (`_get_invoice_currency_rate_date`, o la fecha de hoy si no hay). El cálculo se omite cuando `needed_terms` no es un diccionario, cuando el documento no es factura o no tiene líneas, o cuando el documento no tiene moneda alterna.

#### Scenario: Factura con término de pago

- **WHEN** se recalculan los términos de pago de una factura con moneda alterna configurada
- **THEN** cada entrada de `needed_terms` incluye `foreign_balance` con el balance convertido a la moneda alterna a la fecha de tasa del documento

#### Scenario: Documento sin moneda alterna

- **WHEN** el documento no tiene `foreign_currency_id`
- **THEN** las entradas de `needed_terms` no reciben `foreign_balance`

### Requirement: Corrección de redondeo multi-moneda (porción real)

Para facturas en moneda distinta a la de la compañía, el sistema DEBE (MUST) corregir las diferencias de redondeo entre la suma de balances redondeados línea a línea y la conversión del total a la tasa cruda: distribuye la diferencia entre las líneas de producto proporcionalmente a su balance (`_apply_product_real_portion`), corrige los balances de las líneas de impuesto (`amount_currency / rate` redondeado) y ajusta las líneas de término de pago para que el asiento cierre, acumulando el ajuste en `real_portion_amount` e incrementando `real_portion_count`.

#### Scenario: Factura multi-línea en divisa

- **WHEN** la suma de balances redondeados de las líneas de producto difiere de la conversión redondeada del total en la unidad de redondeo
- **THEN** la diferencia se reparte entre las líneas de producto y el asiento queda balanceado al valor esperado

### Requirement: Totales de factura en moneda alterna

Las facturas DEBEN (MUST) exponer `foreign_total_billed`, `foreign_untaxed_total` y `foreign_taxable_income` calculados desde las claves `total_amount_foreign_currency` / `base_amount_foreign_currency` de `tax_totals`; cuando la factura está en una tercera moneda, `foreign_total_billed` y `foreign_untaxed_total` se obtienen convirtiendo `amount_total` / `amount_untaxed` a la moneda alterna a la fecha de factura.

#### Scenario: Factura en moneda de la compañía

- **WHEN** una factura publicada está en la moneda de la compañía
- **THEN** `foreign_total_billed` es el `total_amount_foreign_currency` del resumen de impuestos

#### Scenario: Factura en tercera moneda

- **WHEN** la factura está en una moneda que no es la de la compañía ni la alterna
- **THEN** `foreign_total_billed` es la conversión de `amount_total` a la moneda alterna

### Requirement: Resumen de impuestos con montos en moneda alterna y VES

`_get_tax_totals_summary` de `account.tax` DEBE (MUST) extender el resumen estándar con: los montos base/impuesto/total en la moneda alterna (`base_amount_foreign_currency`, `tax_amount_foreign_currency`, `total_amount_foreign_currency`, calculados con una segunda corrida del resumen sobre las líneas base foráneas), sus equivalentes por subtotal y por grupo de impuestos, las versiones formateadas en moneda del documento, en VES y en moneda alterna, y el total de descuento formateado cuando alguna línea tiene descuento. Además DEBE (MUST) corregir `base_amount` de facturas multi-moneda para que coincida con la suma de balances de las líneas de producto corregidos por la porción real.

#### Scenario: Factura con moneda alterna configurada

- **WHEN** se calcula `tax_totals` de una factura
- **THEN** el resultado incluye `base_amount_foreign_currency`, `tax_amount_foreign_currency` y `total_amount_foreign_currency` junto a sus valores formateados

### Requirement: Unicidad del nombre del asiento por partner, compañía y diario

El sistema DEBE (MUST) crear un índice único (`account_move_unique_name` / `account_move_unique_name_ve`) sobre (`name`, `partner_id`, `company_id`, `journal_id`) para asientos publicados con nombre distinto de `/`, renombrando previamente los duplicados históricos de documentos de compra con sufijos `(n)`.

#### Scenario: Factura de proveedor duplicada

- **WHEN** se intenta publicar un documento con el mismo `name`, mismo partner, misma compañía y mismo diario que otro ya publicado
- **THEN** la base de datos rechaza la operación por el índice único

### Requirement: Impuesto único por línea de factura

Cuando la compañía tiene activo `unique_tax`, cada línea de producto de una factura (todo `move_type` distinto de `entry`) DEBE (MUST) tener exactamente un impuesto (constraint `_check_taxes_id` de `account.move`).

#### Scenario: Línea con dos impuestos

- **WHEN** se guarda una factura con una línea de producto con dos impuestos y `unique_tax` activo
- **THEN** se lanza un error de validación "This product must have only one tax."

### Requirement: Producto obligatorio en líneas de factura

Toda línea con `display_type` `product` de un documento distinto de `entry` DEBE (MUST) tener un producto asignado (constraint `_check_product_id`).

#### Scenario: Línea sin producto

- **WHEN** se guarda una factura con una línea de producto sin `product_id`
- **THEN** se lanza un error de validación indicando que todas las líneas deben indicar el producto

### Requirement: Descuento máximo por línea

El sistema DEBE (MUST) impedir guardar líneas de factura con producto cuyo `discount` sea mayor o igual a 100% (constraint `_check_max_discount` de `account.move.line`).

#### Scenario: Descuento del 100%

- **WHEN** una línea con producto tiene descuento 100 o superior
- **THEN** se lanza un error indicando que no se permiten descuentos de 100% o más

### Requirement: Cantidad y precio no negativos en el formulario

El formulario de líneas DEBE (MUST) rechazar cantidades negativas (`_onchange_quantity`) y precios unitarios negativos (`_onchange_price_unit`) con un error de validación.

#### Scenario: Cantidad negativa

- **WHEN** un usuario introduce una cantidad negativa en una línea
- **THEN** se lanza un error de validación al salir del campo

### Requirement: Confirmación de facturas de venta con alerta previa

`action_post` de `account.move` DEBE (MUST) interceptar la confirmación cuando falta la clave de contexto `move_action_post_alert` y el recordset contiene algún documento `out_invoice`/`out_refund`, devolviendo la acción del wizard `move.action.post.alert.wizard` con `default_move_id` del primer documento de venta encontrado y abortando la publicación de todo el recordset; la publicación solo procede cuando el usuario confirma en el wizard (que reinvoca `action_post` con la clave en contexto).

#### Scenario: Confirmación directa

- **WHEN** un usuario pulsa confirmar en una factura de cliente
- **THEN** se abre el wizard de alerta y la factura no se publica hasta confirmar en él

#### Scenario: Confirmación masiva mixta

- **WHEN** se confirman a la vez documentos de venta y de compra sin la clave de contexto
- **THEN** se abre el wizard para el primer documento de venta y ningún documento del lote se publica en esa llamada

### Requirement: Límite de crédito del cliente al confirmar

Cuando la compañía tiene `account_use_credit_limit` y el partner `use_partner_credit_limit`, `action_post` DEBE (MUST) impedir confirmar el asiento si el crédito actual del partner (`partner_id.credit`) más el residual del asiento supera su `credit_limit`. La verificación se aplica a todos los asientos del recordset sin filtrar por tipo de documento, de modo que también alcanza a documentos de compra del mismo partner.

#### Scenario: Límite excedido

- **WHEN** la suma del saldo por cobrar del cliente y el residual de la factura supera el límite de crédito
- **THEN** se lanza un error de validación con los montos y la factura no se confirma

#### Scenario: Documento de compra del mismo partner

- **WHEN** se confirma una factura de proveedor de un partner con límite de crédito activo ya excedido
- **THEN** la confirmación también se bloquea con el mismo error

### Requirement: Registro de pago para una sola tasa a la vez

`action_register_payment` de `account.move` DEBE (MUST) rechazar la operación cuando los documentos seleccionados tienen más de una `foreign_rate` distinta, y propagar `default_foreign_rate` y `default_foreign_inverse_rate` al contexto del wizard.

#### Scenario: Facturas con tasas distintas

- **WHEN** se registran pagos sobre facturas con dos tasas alternas diferentes
- **THEN** se lanza un error "You can only register payments for one foreign rate at a time."

### Requirement: El pago sincroniza su tasa al asiento

Al crear un `account.payment` y al sincronizar cambios de `foreign_rate`/`foreign_inverse_rate` (`_synchronize_to_moves`), el sistema DEBE (MUST) escribir esas tasas en el `move_id` del pago. El pago calcula sus tasas por defecto con `compute_rate` a la fecha del pago, y expone `other_rate`/`other_rate_inverse` con la tasa de la moneda del pago cuando esta no es ni la de la compañía ni la alterna.

#### Scenario: Creación de un pago

- **WHEN** se crea un pago con tasa alterna
- **THEN** el asiento del pago queda con la misma `foreign_rate` y `foreign_inverse_rate`

#### Scenario: Pago en tercera moneda

- **WHEN** el pago está en una moneda distinta a la de la compañía y a la alterna
- **THEN** `other_rate` y `other_rate_inverse` reflejan la tasa de esa moneda a la fecha del pago

### Requirement: Cancelación de pagos preservando la trazabilidad fiscal

`action_cancel` de `account.payment` DEBE (MUST) eliminar el asiento del pago solo cuando está en borrador y nunca fue publicado (`posted_before` falso); en cualquier otro caso el asiento se cancela con `button_cancel` en lugar de eliminarse, y el pago pasa a estado `canceled`. Complementariamente, `account.move` DEBE (MUST) impedir eliminar asientos con `posted_before` verdadero salvo contexto `force_delete` (`_unlink_except_posted_or_was_posted`).

#### Scenario: Cancelar un pago publicado

- **WHEN** se cancela un pago cuyo asiento fue publicado alguna vez
- **THEN** el asiento queda en estado cancelado y no se elimina de la base de datos

#### Scenario: Eliminar un asiento que fue publicado

- **WHEN** se intenta eliminar un asiento con `posted_before` verdadero sin `force_delete`
- **THEN** se lanza un error y el asiento no se elimina

### Requirement: Bloqueo del partner del pago tras publicar

Al publicar un pago, el sistema DEBE (MUST) marcar `block_change_partner_after_post` en verdadero para bloquear el cambio de beneficiario del pago publicado.

#### Scenario: Publicación del pago

- **WHEN** se ejecuta `action_post` de un pago
- **THEN** `block_change_partner_after_post` queda en verdadero

### Requirement: Tipos de diario restringidos al grupo de soporte

Al crear un diario o cambiar su tipo, los usuarios sin el grupo `l10n_ve_accountant.group_support_user` DEBEN (MUST) quedar limitados a los tipos `bank`, `general` y `cash` (`_validate_support_user_group` de `account.journal`).

#### Scenario: Usuario sin grupo crea diario de venta

- **WHEN** un usuario sin el grupo de soporte crea un diario de tipo venta
- **THEN** se lanza un error de permisos y el diario no se crea

### Requirement: Métodos de pago bancarios con cuenta obligatoria

Todo método de pago (entrante o saliente) de un diario de tipo `bank` DEBE (MUST) tener `payment_account_id` asignada (constraint `_check_payment_method_line_accounts`), salvo durante la carga de plantillas contables o instalación.

#### Scenario: Método sin cuenta

- **WHEN** se guarda un diario bancario con una línea de método de pago sin cuenta
- **THEN** se lanza un error "All payment methods must have an assigned account."

### Requirement: Un único diario de compra internacional

El sistema DEBE (MUST) permitir a lo sumo un diario con `is_purchase_international` activo (constraint `_check_single_international_purchase_journal` de `account.journal`). Al cambiar el diario de una factura a uno no internacional, las líneas pierden la marca `international_purchase_exent_product`.

#### Scenario: Segundo diario internacional

- **WHEN** se marca `is_purchase_international` en un diario cuando ya existe otro con la marca
- **THEN** se lanza un error de validación indicando que solo se permite uno

### Requirement: Impuesto exento automático en compras internacionales

Cuando una línea de factura tiene `international_purchase_exent_product` activo y la compañía tiene configurado `exent_aliquot_purchase_international`, `_get_computed_taxes` DEBE (MUST) devolver ese impuesto exento en lugar del impuesto por defecto del producto.

#### Scenario: Producto exento en compra internacional

- **WHEN** se marca la línea como producto exento de compra internacional
- **THEN** el impuesto calculado de la línea es el `exent_aliquot_purchase_international` de la compañía

### Requirement: Exactamente un impuesto por producto

Al crear o modificar un `product.template`, el sistema DEBE (MUST) garantizar que `taxes_id` y `supplier_taxes_id` queden con exactamente un impuesto: si el resultado neto de los comandos M2M no deja ninguno, asigna el impuesto por defecto de la compañía (`account_sale_tax_id`/`account_purchase_tax_id`) o lanza un error si no existe; si deja más de uno, lanza un error consolidado (`_enforce_single_tax_vals`).

#### Scenario: Producto con dos impuestos de venta

- **WHEN** se guarda un producto con dos impuestos de cliente
- **THEN** se lanza un error indicando que se requiere exactamente un impuesto por política fiscal

#### Scenario: Producto sin impuesto con default configurado

- **WHEN** se guarda un producto sin impuestos y la compañía tiene impuesto por defecto
- **THEN** el producto queda con el impuesto por defecto de la compañía

### Requirement: Indexación de pagos configurable

La compañía DEBE (MUST) poder configurar el criterio de tasa aplicado al registrar pagos (`indexaxion_payment_mode`: `indexed`, `not_indexed`, `to_agreed`; y `indexed_default`). En el wizard de pagos, cuando `indexed_default` está desactivado y la moneda del wizard difiere de la de la compañía, `_get_conversion_date` DEBE (MUST) devolver la menor fecha de factura de las líneas a pagar (tasa de la fecha de factura) en lugar de la fecha de pago.

#### Scenario: Pago no indexado

- **WHEN** el wizard se abre con `indexed_default` falso sobre una factura en divisa
- **THEN** las conversiones a la moneda del wizard usan la tasa de la fecha de factura más antigua

#### Scenario: Pago indexado

- **WHEN** `indexed_default` está activo
- **THEN** las conversiones usan la tasa de la fecha de pago

### Requirement: Tasa del wizard de registro de pagos según su moneda

El wizard `account.payment.register` DEBE (MUST) calcular `foreign_rate` y `foreign_inverse_rate` con `compute_rate` usando la moneda del wizard cuando difiere de la de la compañía, o la moneda alterna de la compañía en caso contrario, y propagar ambas tasas a los valores del pago creado (`_create_payment_vals_from_wizard`).

#### Scenario: Pago desde el wizard

- **WHEN** se crea un pago desde el wizard con tasa calculada
- **THEN** el pago resultante tiene la `foreign_rate` y `foreign_inverse_rate` del wizard

### Requirement: Los usuarios de soporte fiscal no pueden archivar impuestos

Una regla de registro (`tax_support_no_archive_rule`) DEBE (MUST) limitar al grupo `group_fiscal_config_support` a los impuestos activos (`active = True`) en lectura/escritura/creación, sin permiso de eliminación, impidiendo en la práctica archivar impuestos.

#### Scenario: Archivar un impuesto

- **WHEN** un usuario del grupo de soporte fiscal intenta archivar un impuesto
- **THEN** la regla de registro bloquea la operación al salir el registro de su dominio

### Requirement: Acceso a asientos limitado a borradores para el grupo de facturación

Una regla de registro (`account_move_unlink_draft_only`) DEBE (MUST) aplicar al grupo `account.group_account_invoice` el dominio `[('state','=','draft')]` sobre `account.move` con los cuatro permisos activos (`perm_read`, `perm_write`, `perm_create` y `perm_unlink`), de modo que la restricción no se limita a la eliminación: los asientos que no están en borrador quedan fuera del alcance de ese grupo también en lectura y escritura.

#### Scenario: Eliminar factura publicada

- **WHEN** un facturador intenta eliminar un asiento que no está en borrador
- **THEN** la regla de registro impide la eliminación

#### Scenario: Lectura de un asiento publicado

- **WHEN** un usuario cuyo único grupo contable es `account.group_account_invoice` consulta un asiento publicado
- **THEN** la regla lo excluye del dominio y el acceso es denegado

### Requirement: Fecha de factura desacoplada de la fecha contable

El campo `invoice_date_display` DEBE (MUST) ser la fuente de la fecha contable (`_get_accounting_date_source` devuelve `invoice_date_display` o `date`), permitiendo que `invoice_date` quede reservada al cálculo de tasa; en documentos de venta, cambiar `invoice_date_display` sincroniza `invoice_date` con el mismo valor.

#### Scenario: Cambio de fecha en factura de venta

- **WHEN** un usuario cambia `invoice_date_display` en una factura de cliente
- **THEN** `invoice_date` toma la misma fecha y la fecha contable se deriva de ella

### Requirement: Importe alterno manual en líneas de extracto bancario

Cuando una línea de extracto (`account.bank.statement.line`) tiene `foreign_amount` distinto de cero, los apuntes generados DEBEN (MUST) tomar ese importe como débito/crédito alterno según su signo, marcados con `not_foreign_recalculate` para que no se recalculen por tasa.

#### Scenario: Extracto con importe alterno

- **WHEN** se registra una línea de extracto con `foreign_amount` positivo
- **THEN** la línea de liquidez recibe ese monto como `foreign_debit` y la contrapartida como `foreign_credit`, ambas sin recálculo posterior
