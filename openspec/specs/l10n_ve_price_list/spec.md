# l10n_ve_price_list

## Purpose

Controla mediante grupos de seguridad quién puede cambiar la lista de precios en facturas, quién puede editar precios unitarios en órdenes de venta y facturas de cliente, y quién ve el precio de venta en la ficha del producto. Extiende `account.move`, `account.move.line`, `sale.order.line` y `product.template`. Depende de `account`, `account_invoice_pricelist` (campo `pricelist_id` en facturas) y `l10n_ve_sale`.

## Requirements

### Requirement: Cambio de lista de precios en facturas restringido por grupo

El campo `pricelist_id` de la factura DEBE (MUST) ser editable solo mientras la factura está en borrador y, cuando la factura proviene de otro documento (`invoice_origin` establecido), solo por usuarios del grupo `l10n_ve_price_list.group_pricelist_change_permission` (flag calculado `can_edit_pricelist` en `account.move`; el grupo incluye por defecto a root y admin). Además, cuando `fields_get` se invoca sobre un recordset con registros, DEBE (MUST) marcar el campo como de solo lectura si el usuario no pertenece al grupo (invocado sobre un recordset vacío — el caso habitual de carga de vistas — no altera el atributo; la restricción efectiva la aplica la vista). El campo queda oculto en facturas de proveedor (`move_type` igual a `in_invoice`).

#### Scenario: Factura originada en una orden, usuario sin el grupo

- **WHEN** un usuario sin el grupo abre en borrador una factura con `invoice_origin`
- **THEN** el campo de lista de precios está en solo lectura

#### Scenario: Usuario del grupo en factura borrador

- **WHEN** un usuario del grupo abre una factura de cliente en borrador
- **THEN** puede cambiar la lista de precios

#### Scenario: Factura publicada

- **WHEN** la factura no está en estado borrador
- **THEN** el campo de lista de precios no es editable para ningún usuario

### Requirement: Edición de precios unitarios en facturas restringida por grupo

En las líneas de factura, el campo `price_unit` DEBE (MUST) estar en solo lectura para documentos distintos de facturas de proveedor cuando el usuario no pertenece al grupo `l10n_ve_price_list.group_editing_prices_sales_orders_and_invoices` (flag calculado `can_edit_prices` en `account.move.line`; el grupo incluye por defecto a root y admin).

#### Scenario: Usuario sin el grupo en factura de cliente

- **WHEN** un usuario sin el grupo edita las líneas de una factura de cliente
- **THEN** el precio unitario está en solo lectura

#### Scenario: Factura de proveedor

- **WHEN** el documento es una factura de proveedor (`in_invoice`)
- **THEN** el precio unitario permanece editable aunque el usuario no tenga el grupo

### Requirement: Edición de precios unitarios en órdenes de venta restringida por grupo

En las líneas de la orden de venta, el campo `price_unit` DEBE (MUST) estar en solo lectura cuando el usuario no pertenece al grupo `l10n_ve_price_list.group_editing_prices_sales_orders_and_invoices` (flag calculado `can_edit_prices` en `sale.order.line`), sobre la vista de orden de `l10n_ve_sale`.

#### Scenario: Usuario sin el grupo

- **WHEN** un usuario sin el grupo edita las líneas de una orden de venta
- **THEN** el precio unitario está en solo lectura y los precios provienen de la lista de precios

### Requirement: Ocultamiento del precio de venta del producto por grupo

Para los usuarios del grupo `l10n_ve_price_list.group_hide_product_sale_prices`, la ficha del producto DEBE (MUST) ocultar el precio de venta (`list_price`, su etiqueta y el bloque de precio por unidad), vía el flag calculado `hide_list_price` en `product.template`.

#### Scenario: Usuario del grupo

- **WHEN** un usuario del grupo "Hide product sale prices" abre la ficha de un producto
- **THEN** el precio de venta no se muestra en el formulario
