# l10n_ve_stock_account

## Purpose

Conecta el inventario con la facturación venezolana: guías de despacho con numeración propia y razones de traslado, generación de facturas/notas desde traslados (manual, masiva y por cron), flujo de consignación con almacén y ubicaciones por cliente, donaciones y alerta de guías no facturadas. Extiende `stock.picking`, `stock.move`, `stock.move.line`, `stock.warehouse`, `stock.location`, `sale.order`, `sale.order.line`, `account.move`, `account.move.line`, `res.partner`, `res.company` y `res.config.settings`, y define el modelo `transfer.reason` y los wizards `picking.invoice.wizard` y `stock.picking.self.consumption.wizard`. Depende de `l10n_ve_stock` (usa `type_delivery_step`), `l10n_ve_invoice`, `l10n_ve_accountant` (usa `taxpayer_type`), `l10n_ve_sale`, `l10n_ve_donation` y `sale_stock`.

## Requirements

### Requirement: Catálogo de razones de traslado de solo lectura

El sistema DEBE (MUST) proveer el modelo `transfer.reason` con las razones cargadas por data (`donation`, `sale`, `transfer`, `export`, `self_consumption`, `consignment`, `repair_improvement`, `external_storage`, `other_causes`), con campos `name`, `code` y `active` de solo lectura y ACL de usuarios internos limitada a lectura (sin crear, escribir ni eliminar).

#### Scenario: Usuario interno intenta modificar una razón

- **WHEN** un usuario del grupo `base.group_user` intenta crear o editar un registro de `transfer.reason`
- **THEN** el sistema niega la operación por falta de permisos

### Requirement: Razones de traslado permitidas según la operación

El campo `allowed_reason_ids` de `stock.picking` (`_compute_allowed_reason_ids`) DEBE (MUST) limitar las razones seleccionables según la operación: salida con venta ofrece `sale` (por defecto) y `export`, o solo `self_consumption` si es donación; salida sin venta ofrece `self_consumption`, `other_causes`, `repair_improvement` y `external_storage`; interno ofrece `consignment`, `transfer` y `other_causes`, forzando `consignment` (en modo solo lectura) cuando el destino es un almacén de consignación. Si la razón asignada no está entre las permitidas, se reemplaza por la primera permitida.

#### Scenario: Despacho de una venta

- **WHEN** un traslado de salida proviene de una orden de venta y no es donación
- **THEN** las razones disponibles son venta y exportación, con venta asignada por defecto

#### Scenario: Traslado interno hacia almacén de consignación

- **WHEN** el destino de un traslado interno pertenece al almacén de consignación
- **THEN** la razón se fija en consignación y queda de solo lectura

### Requirement: Razón de traslado obligatoria en internos

La constraint `_check_transfer_reason_required` DEBE (MUST) impedir guardar un traslado con `operation_code` interno sin `transfer_reason_id`.

#### Scenario: Interno sin razón

- **WHEN** se guarda un traslado interno sin razón de traslado
- **THEN** se lanza un error de validación

### Requirement: Determinación de guía de despacho

El campo `is_dispatch_guide` de `stock.picking` (`_compute_is_dispatch_guide`) DEBE (MUST) quedar en `False` cuando el documento de la venta es `invoice`, en `True` cuando es `dispatch_guide`, y en `True` cuando la razón de traslado es consignación u otras causas; además, al seleccionar la razón `self_consumption` el flag DEBE (MUST) apagarse (`_compute_show_other_causes_transfer_reason`).

#### Scenario: Venta con documento guía de despacho

- **WHEN** el traslado proviene de una venta con `document = dispatch_guide`
- **THEN** `is_dispatch_guide` queda en `True`

#### Scenario: Razón de autoconsumo

- **WHEN** se asigna la razón con código `self_consumption`
- **THEN** `is_dispatch_guide` queda en `False`

### Requirement: Numeración de la guía de despacho por secuencia

Al completar un traslado (`_action_done`), los pickings con `dispatch_guide_controls` activo DEBEN (MUST) recibir un `guide_number` tomado de la secuencia con código `guide.number` de su compañía (`get_sequence_guide_num`); si la compañía no tiene esa secuencia, se crea automáticamente con prefijo `GUIDE` y padding 5. `dispatch_guide_controls` solo se activa en traslados hechos cuyo documento es `dispatch_guide` o con `is_dispatch_guide` activo.

#### Scenario: Validación de una guía de despacho

- **WHEN** se valida un traslado marcado como guía de despacho
- **THEN** el traslado recibe el siguiente número de la secuencia `guide.number` de su compañía

#### Scenario: Compañía sin secuencia

- **WHEN** la compañía del traslado no tiene secuencia `guide.number`
- **THEN** el sistema la crea con prefijo `GUIDE` y padding 5 antes de asignar el número

### Requirement: Documento por defecto de la venta según el cliente

Cada cliente (`res.partner`) DEBE (MUST) tener un `default_document` (`dispatch_guide` o `invoice`, por defecto `invoice`) y las órdenes de venta DEBEN (MUST) tomar su campo `document` de ese valor, tanto por defecto (`_default_document`) como al cambiar el cliente (onchange de `partner_id`).

#### Scenario: Cliente configurado con guía de despacho

- **WHEN** se crea una orden de venta para un cliente con `default_document = dispatch_guide`
- **THEN** el campo `document` de la orden queda en `dispatch_guide`

### Requirement: Estado de facturación de la guía

El campo `state_guide_dispatch` de `stock.picking` DEBE (MUST) iniciar en `to_invoice`, pasar a `invoiced` cuando se genera una factura o nota desde el traslado (`create_invoice`, `create_bill`, `create_customer_credit`, `create_vendor_credit`, `create_multi_invoice`), y pasar a `emited` al validar un traslado interno con razón `transfer` (traslado entre almacenes) en `button_validate`.

#### Scenario: Facturación de la guía

- **WHEN** se crea la factura desde un traslado
- **THEN** su `state_guide_dispatch` cambia a `invoiced`

#### Scenario: Traslado entre almacenes

- **WHEN** se valida un traslado interno con razón traslado entre almacenes
- **THEN** su `state_guide_dispatch` cambia a `emited`

### Requirement: Factura de cliente desde el traslado de salida

El método `create_invoice` DEBE (MUST) crear, para traslados de salida, una factura `out_invoice` en el diario de clientes configurado en la compañía (`customer_journal_id`, con error si falta), con líneas construidas desde los movimientos (`_get_invoice_lines_for_invoice`): precio e impuestos de la línea de venta si existe (cantidad = `qty_delivered`), o precio de lista e impuesto de venta de la compañía en su defecto, exigiendo cuenta de ingreso en el producto o su categoría; la factura queda vinculada por `transfer_ids`/`picking_ids` con `from_picking = True`, hereda la lista de precios de la venta, y la orden de venta se marca facturada (`_update_order_sale_invoiced`).

#### Scenario: Guía con orden de venta

- **WHEN** se crea la factura desde una guía de despacho originada en una venta
- **THEN** las líneas usan el precio e impuestos de la línea de venta y la orden queda con `invoice_status = invoiced`

#### Scenario: Diario no configurado

- **WHEN** la compañía no tiene `customer_journal_id`
- **THEN** se lanza un error pidiendo configurar el diario en ajustes

#### Scenario: Producto sin cuenta de ingreso

- **WHEN** un producto del traslado no tiene cuenta de ingreso ni en el producto ni en su categoría
- **THEN** se lanza un error nombrando el producto

### Requirement: Factura de proveedor desde la recepción

El método `create_bill` DEBE (MUST) crear, para traslados de entrada, una factura `in_invoice` en el diario de proveedores configurado (`vendor_journal_id`, con error si falta), con líneas por movimiento usando el precio de lista del producto y el impuesto de compra de la compañía (`account_purchase_tax_id`), marcando el traslado como `invoiced`.

#### Scenario: Recepción sin diario configurado

- **WHEN** se intenta crear la factura de proveedor y la compañía no tiene `vendor_journal_id`
- **THEN** se lanza un error pidiendo configurar el diario

### Requirement: Notas de crédito desde traslados devueltos

Los métodos `create_customer_credit` y `create_vendor_credit` DEBEN (MUST) crear notas de crédito desde traslados devueltos: `out_refund` en el diario de clientes para traslados de entrada, e `in_refund` en el diario de proveedores para traslados de salida, con líneas por movimiento a precio de lista, marcando el traslado como `invoiced`.

#### Scenario: Nota de crédito de cliente

- **WHEN** se ejecuta `create_customer_credit` sobre un traslado de entrada
- **THEN** se crea una nota de crédito `out_refund` vinculada al traslado

### Requirement: Marcado de devoluciones

El wizard `stock.return.picking` DEBE (MUST) marcar con `is_return = True` el traslado generado por `_create_return`, y el campo `type_of_return` del traslado original DEBE (MUST) computarse desde las cantidades devueltas (`qty_return` de `stock.move`): `n/a` sin devoluciones, `total` cuando todas las líneas devolvieron su cantidad completa y `partial` en cualquier otro caso.

#### Scenario: Devolución completa

- **WHEN** se devuelve la cantidad total de todas las líneas de un traslado
- **THEN** el traslado original queda con `type_of_return = total` y el nuevo con `is_return = True`

#### Scenario: Devolución parcial

- **WHEN** se devuelve solo parte de las cantidades
- **THEN** el traslado original queda con `type_of_return = partial`

### Requirement: Tipo de comprobante ofrecido según operación y devolución

La visibilidad de los botones de facturación (`_compute_button_visibility`) DEBE (MUST) exigir traslado hecho, sin facturas vinculadas y `state_guide_dispatch = to_invoice`, y ofrecer: en entradas, factura de proveedor si no es devolución o nota de crédito si lo es; en salidas, factura de cliente solo si no es devolución, el documento de la venta no es `invoice` y la devolución no es total, o nota de crédito si es devolución; en internos de consignación, la factura interna.

#### Scenario: Salida ya facturada por la venta

- **WHEN** un traslado de salida proviene de una venta con `document = invoice`
- **THEN** el botón de crear factura no se muestra

#### Scenario: Entrada sin devolución

- **WHEN** un traslado de entrada hecho no es devolución y no tiene facturas
- **THEN** solo se ofrece crear la factura de proveedor

### Requirement: Bloqueo de refacturación con factura publicada

Antes de crear cualquier comprobante desde un traslado, `_validate_one_invoice_posted` DEBE (MUST) impedir la operación si el traslado ya tiene una factura vinculada en estado `posted`.

#### Scenario: Guía con factura publicada

- **WHEN** se intenta crear otra factura desde un traslado con una factura publicada
- **THEN** se lanza un error indicando que la guía ya tiene una factura publicada

### Requirement: Factura combinada de múltiples guías

La opción `unique` del wizard `picking.invoice.wizard` DEBE (MUST) crear una sola factura para varios traslados seleccionados validando que todos estén hechos, pertenezcan al mismo cliente y tengan el mismo tipo de comprobante; `create_multi_invoice` exige además una única lista de precios y el diario de clientes configurado, agrupa las líneas por producto sumando cantidades (`group_products`) y marca todos los traslados como `invoiced`.

#### Scenario: Guías del mismo cliente

- **WHEN** se seleccionan varias guías hechas del mismo cliente con la misma lista de precios y se elige factura única
- **THEN** se crea una sola factura con las cantidades agrupadas por producto y todas las guías quedan facturadas

#### Scenario: Clientes distintos

- **WHEN** los traslados seleccionados pertenecen a más de un cliente
- **THEN** se lanza un error indicando que deben tener el mismo cliente

#### Scenario: Listas de precios distintas

- **WHEN** los traslados tienen más de una lista de precios
- **THEN** se lanza un error indicando que la factura combinada exige la misma lista de precios

### Requirement: Facturación individual masiva

La opción `multiple` del wizard `picking.invoice.wizard` DEBE (MUST) validar que todos los traslados seleccionados estén en `state_guide_dispatch = to_invoice` y pertenezcan al mismo cliente, y crear para cada uno el comprobante que le corresponde según sus flags de visibilidad (factura, factura de proveedor o nota de crédito), con error si algún traslado no admite comprobante.

#### Scenario: Lote de guías por facturar

- **WHEN** se seleccionan varias guías por facturar del mismo cliente y se elige factura por traslado
- **THEN** se crea un comprobante independiente por cada traslado

### Requirement: Facturación automática por cron

El cron "Generate Invoices from Pickings" (inactivo por defecto) DEBE (MUST) ejecutar `_cron_generate_invoices_from_pickings`, que solo factura cuando el día actual coincide con el configurado en `invoice_cron_type` (`last_day`: último día del mes; `last_business_day`: último día hábil, retrocediendo sábados y domingos) y la hora actual está a lo sumo a media hora de `invoice_cron_time`. Procesa los traslados hechos con `state_guide_dispatch = to_invoice` y sin facturas, generando factura de cliente para no-entradas sin devolución, factura de proveedor para no-salidas sin devolución, nota de crédito de cliente para no-salidas devueltas y nota de crédito de proveedor para no-entradas devueltas; los errores se registran en el chatter del traslado sin detener el proceso.

#### Scenario: Ejecución en el día y hora configurados

- **WHEN** el cron corre el último día hábil del mes a la hora configurada con `invoice_cron_type = last_business_day`
- **THEN** se generan los comprobantes de los traslados pendientes de facturar

#### Scenario: Error en un traslado

- **WHEN** la facturación de un traslado falla
- **THEN** el error se publica en el chatter de ese traslado y el cron continúa con los demás

### Requirement: Precio en bolívares para la guía de despacho

El método `price_unit_ves_for_dispatch_guide` de `stock.move` DEBE (MUST) devolver el precio unitario de la línea de venta convertido a la moneda de la compañía cuando la venta está en otra moneda, usando como fecha de conversión la fecha de realización del traslado (`date_done`) si el flag de compañía `indexed_dispatch_guide` está activo, o la fecha de la orden (`date_order`) en caso contrario; `_get_line_values` DEBE (MUST) calcular con ese precio el subtotal, el descuento y el impuesto de la línea para el reporte de guía.

#### Scenario: Guía indexada

- **WHEN** `indexed_dispatch_guide` está activo y la venta está en una moneda distinta a la de la compañía
- **THEN** el precio se convierte con la tasa de la fecha de validación del traslado

#### Scenario: Guía no indexada

- **WHEN** `indexed_dispatch_guide` está inactivo
- **THEN** el precio se convierte con la tasa de la fecha de la orden de venta

### Requirement: Alerta de guías de despacho no facturadas

El método `alert_views` de `stock.picking` DEBE (MUST) contar las guías pendientes (`_get_domain_for_return_picking`: hechas, paso distinto de interno, razón distinta de autoconsumo, `state_guide_dispatch = to_invoice`, documento de venta distinto de factura, sin devolución total) de las compañías indicadas, y anunciar la fecha límite según el `taxpayer_type` de la compañía: contribuyente `special` vence el día 15 si aún no pasó, o el último día del mes; `ordinary` y `formal` vencen el último día del mes.

#### Scenario: Contribuyente especial antes del 15

- **WHEN** se consulta la alerta antes del día 15 en una compañía con `taxpayer_type = special`
- **THEN** el mensaje indica la cantidad de guías no facturadas con fecha límite el 15 del mes

#### Scenario: Contribuyente ordinario

- **WHEN** la compañía es contribuyente ordinario
- **THEN** la fecha límite anunciada es el último día del mes

### Requirement: Almacén de consignación único

La constraint `_check_unique_consignation_warehouse` de `stock.warehouse` DEBE (MUST) impedir marcar `is_consignation_warehouse` en más de un almacén.

#### Scenario: Segundo almacén de consignación

- **WHEN** se marca como consignación un almacén existiendo ya otro marcado
- **THEN** se lanza un error indicando que solo puede haber un almacén de consignación

### Requirement: Ubicaciones de consignación internas y con cliente

La constraint `_check_internal_location_only` de `stock.location` DEBE (MUST) exigir que las ubicaciones dentro del almacén de consignación sean de uso interno y tengan un cliente asignado en `partner_id`.

#### Scenario: Ubicación sin cliente

- **WHEN** se crea una ubicación en el almacén de consignación sin `partner_id`
- **THEN** se lanza un error de validación

### Requirement: Validación de stock en ventas de consignación

En órdenes de venta cuyo almacén es de consignación, las constraints de `sale.order` y `sale.order.line` DEBEN (MUST) exigir, para cada producto no servicio, que exista stock con cantidad positiva en una ubicación interna asignada al cliente de la orden, y que la cantidad vendida no supere `free_qty_today`.

#### Scenario: Producto sin stock en la ubicación del cliente

- **WHEN** se agrega a la orden un producto sin quants positivos en la ubicación de consignación del cliente
- **THEN** se lanza un error indicando que el producto no está disponible en la ubicación de consignación

#### Scenario: Cantidad mayor a la consignada

- **WHEN** la cantidad de la línea supera la existencia disponible
- **THEN** se lanza un error indicando que no puede vender más que el stock consignado

### Requirement: Venta de consignación forzada a factura

El campo `is_consignation` de `sale.order` DEBE (MUST) activarse cuando el almacén de la orden es de consignación, y en ese caso el campo `document` DEBE (MUST) forzarse a `invoice`.

#### Scenario: Orden sobre el almacén de consignación

- **WHEN** se asigna a la orden el almacén de consignación
- **THEN** `is_consignation` queda activo y `document` queda en `invoice`

### Requirement: Cliente tomado de la ubicación destino en consignación

Cuando un traslado tiene razón consignación, es guía de despacho y `is_consignment` activo (`partner_required`), el sistema DEBE (MUST) asignar como `partner_id` el cliente de la ubicación destino (`_assign_partner_from_location`), tanto al crear como al modificar la ubicación destino o la razón.

#### Scenario: Traslado a la ubicación de un cliente

- **WHEN** se selecciona como destino una ubicación de consignación con cliente asignado
- **THEN** el `partner_id` del traslado se fija automáticamente a ese cliente

### Requirement: Ubicación origen desde la consignación del cliente

Para traslados en borrador o confirmados sin ubicación origen cuya venta es de consignación, `_compute_location_id` DEBE (MUST) asignar como origen la ubicación interna de consignación asignada al cliente de la orden.

#### Scenario: Entrega de una venta de consignación

- **WHEN** se genera el traslado de una venta de consignación
- **THEN** la ubicación origen es la ubicación de consignación del cliente

### Requirement: Donación con cliente de la compañía y razón autoconsumo

Al marcar `is_donation` en un traslado, el onchange DEBE (MUST) fijar como `partner_id` el contacto de la propia compañía, apagar `is_dispatch_guide` y asignar la razón `self_consumption`; además el onchange de `partner_id` DEBE (MUST) impedir seleccionar un contacto distinto al de la compañía mientras es donación, y el flag se hereda de la venta (`sale_id.is_donation`, definido en `l10n_ve_donation`).

#### Scenario: Cambio de contacto en una donación

- **WHEN** en un traslado de donación se selecciona un contacto distinto al de la compañía
- **THEN** se lanza un error indicando que el contacto debe ser la propia compañía

### Requirement: Número de guía en la factura

El campo `guide_number` de `account.move` DEBE (MUST) computarse concatenando con `/` los números de guía de los traslados vinculados en `picking_ids`.

#### Scenario: Factura de varias guías

- **WHEN** una factura se crea desde varios traslados con número de guía
- **THEN** su `guide_number` contiene todos los números separados por `/`

### Requirement: Cantidad facturada por línea de movimiento

El campo `qty_invoiced` de `stock.move.line` DEBE (MUST) computarse como la suma de las cantidades de las líneas de facturas publicadas (`state = posted`) vinculadas al traslado por `transfer_ids` para el mismo producto.

#### Scenario: Guía facturada parcialmente

- **WHEN** existe una factura publicada que cubre parte del producto de la línea
- **THEN** `qty_invoiced` refleja la cantidad facturada en esas facturas
