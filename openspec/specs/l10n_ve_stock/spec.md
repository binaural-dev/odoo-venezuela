# l10n_ve_stock

## Purpose

Adapta el inventario de Odoo a la operación venezolana: validaciones de precio e impuesto en productos, disponibilidad para la venta por almacén, ubicación física con prioridad de picking, controles de ajustes/desechos/movimientos con stock insuficiente, grupos de bloqueo operativo y reporte de inventario valorizado a fecha. Extiende `product.template`, `product.product`, `product.category`, `stock.location`, `stock.warehouse`, `stock.picking.type`, `stock.picking`, `stock.move`, `stock.move.line`, `stock.quant`, `stock.scrap`, `res.company`, `res.config.settings` y el wizard `stock.quantity.history`. Depende de `stock`, `product`, `l10n_ve_rate` y `stock_delivery`. Define además flags de compañía (`validate_without_product_quantity`, `limit_product_qty_out`, `group_product_available_quantity_on_sale`) cuyo comportamiento se implementa en `l10n_ve_sale`.

## Requirements

### Requirement: Precio de venta mayor a cero

El sistema DEBE (MUST) impedir, vía constraint `_check_list_price` sobre `list_price` de `product.template`, que un producto tenga precio de venta menor o igual a cero. La validación también se dispara al crear o escribir `list_price` desde `product.product`, y se omite cuando el contexto trae `install_mode`.

#### Scenario: Precio en cero

- **WHEN** se guarda un producto con `list_price` igual o menor a 0
- **THEN** se lanza un error de validación indicando que el precio no puede ser negativo ni cero

#### Scenario: Carga en modo instalación

- **WHEN** el producto se crea con el contexto `install_mode` activo
- **THEN** la validación de precio no se aplica

### Requirement: Un solo impuesto de venta por compañía en el producto

El sistema DEBE (MUST) validar, en `create` y en `write` de `taxes_id` de `product.template` (método `_validate_single_sale_tax`), que el producto no tenga más de un impuesto de venta por compañía.

#### Scenario: Segundo impuesto de la misma compañía

- **WHEN** se asignan dos impuestos de venta de la misma compañía a un producto
- **THEN** se lanza un error indicando que el producto debe tener un solo impuesto

### Requirement: Unicidad de código de barras por compañía

La constraint `_check_barcode_uniqueness` de `product.product` DEBE (MUST) evaluar los duplicados de `barcode` filtrando por `company_id`, de modo que el mismo código de barras pueda existir en compañías distintas pero no repetirse dentro de la misma compañía.

#### Scenario: Duplicado en la misma compañía

- **WHEN** se asigna a un producto un `barcode` ya usado por otro producto de la misma compañía
- **THEN** se lanza un error de validación listando los códigos duplicados

#### Scenario: Mismo código en otra compañía

- **WHEN** el `barcode` ya existe pero en un producto de otra compañía
- **THEN** el registro se guarda sin error

### Requirement: Cantidad disponible para la venta

El campo `quantity` de `product.template` (`_compute_available_quantity`) DEBE (MUST) calcularse según el flag de compañía `use_free_qty_odoo`: si está desactivado, es la suma de `available_quantity` de los quants en mano (`on_hand`) cuya ubicación es la ubicación de stock del almacén (`lot_stock_id`) o hija directa de ella, truncada a 0 si el total es negativo; si está activado, es el `free_qty` estándar de Odoo (suma del `free_qty` de las variantes).

#### Scenario: Cálculo propio por almacén

- **WHEN** `use_free_qty_odoo` está desactivado y el producto tiene existencia en ubicaciones de stock de almacenes
- **THEN** `quantity` suma la cantidad disponible (no reservada) de esas ubicaciones y nunca es negativa

#### Scenario: Cálculo estándar de Odoo

- **WHEN** `use_free_qty_odoo` está activado
- **THEN** `quantity` es igual a `free_qty`

### Requirement: Categorías de producto multi-compañía

Las categorías de producto (`product.category`) DEBEN (MUST) tener un campo `company_id` (por defecto la compañía activa) y una regla de registro global (`product_category_multi_company_rule`) que limita la visibilidad a categorías de las compañías del usuario o sin compañía.

#### Scenario: Categoría de otra compañía

- **WHEN** un usuario consulta categorías y existe una con `company_id` de una compañía a la que no tiene acceso
- **THEN** esa categoría no aparece en sus resultados

### Requirement: Prioridad no negativa en ubicaciones

La constraint `_check_priority` de `stock.location` DEBE (MUST) impedir guardar una ubicación con `priority` menor a 0 (el campo tiene default 10 y trazabilidad por chatter).

#### Scenario: Prioridad negativa

- **WHEN** se asigna una `priority` negativa a una ubicación
- **THEN** se lanza un error de validación

### Requirement: Ordenamiento de movimientos por prioridad de ubicación física

Los modelos `stock.move` y `stock.move.line` DEBEN (MUST) ordenarse por el campo almacenado `priority_location` ascendente, que es la `priority` de la `physical_location_id` del producto (`product.template.priority_location`).

#### Scenario: Líneas de un traslado

- **WHEN** un traslado contiene productos con ubicaciones físicas de distinta prioridad
- **THEN** los movimientos y líneas se listan de menor a mayor `priority_location`

### Requirement: Reserva dirigida a la ubicación física del producto

Cuando el flag de compañía `use_physical_location` está activo, `_update_reserved_quantity` de `stock.quant` DEBE (MUST) reservar únicamente en los quants de la `physical_location_id` del producto siempre que esa ubicación exista entre los quants candidatos, asignando en ella la totalidad de la cantidad demandada incluso si excede lo disponible en esa ubicación. Si el flag está inactivo, el producto no tiene ubicación física entre los quants, o el contexto trae `skip_physical_location`, se aplica el comportamiento estándar de Odoo.

#### Scenario: Producto con ubicación física

- **WHEN** `use_physical_location` está activo y se reserva un producto cuya `physical_location_id` tiene quants en la ubicación origen
- **THEN** la reserva se registra completa sobre el quant de la ubicación física

#### Scenario: Flag desactivado

- **WHEN** `use_physical_location` está inactivo
- **THEN** la reserva sigue la lógica estándar de Odoo

### Requirement: Reserva física limitada al paso PICK

En `action_assign` de `stock.picking`, los traslados cuyo `type_delivery_step` es distinto de `pick` DEBEN (MUST) ejecutarse con el contexto `skip_physical_location`, de modo que la reserva dirigida a la ubicación física solo aplique al paso de picking.

#### Scenario: Reserva de un traslado de salida

- **WHEN** se comprueba disponibilidad de un traslado con `type_delivery_step` distinto de `pick`
- **THEN** la reserva usa el flujo estándar aunque `use_physical_location` esté activo

### Requirement: Ajustes de inventario no negativos

Cuando el flag de compañía `not_allow_negative_inventory_adjustments` está activo, `_apply_inventory` de `stock.quant` DEBE (MUST) impedir aplicar un ajuste cuya `inventory_quantity` sea negativa.

#### Scenario: Cantidad física negativa

- **WHEN** se aplica un ajuste de inventario con cantidad contada negativa y el flag activo
- **THEN** se lanza un error de validación nombrando el producto y el ajuste no se aplica

### Requirement: Desecho limitado a la disponibilidad

Salvo que el flag de compañía `allow_scrap_more_than_available` esté activo, `action_validate` de `stock.scrap` DEBE (MUST) impedir validar un desecho cuando `check_available_qty` indica que la cantidad supera la existencia del producto en la ubicación.

#### Scenario: Desecho mayor al disponible

- **WHEN** se valida un desecho por más cantidad de la disponible en la ubicación y el flag está inactivo
- **THEN** se lanza un error indicando que no se puede desechar más que la cantidad disponible

### Requirement: Desecho limitado a lo fabricado

Cuando el flag de compañía `not_allow_scrap_more_than_what_was_manufactured` está activo y el desecho está vinculado a una orden de producción (`production_id`), `action_validate` de `stock.scrap` DEBE (MUST) impedir que la suma de los desechos hechos (`state = done`) más el desecho actual supere la cantidad producida (`qty_produced`).

#### Scenario: Desecho acumulado mayor a lo producido

- **WHEN** los desechos validados de la producción más el actual superan `qty_produced`
- **THEN** se lanza un error indicando que no se puede desechar más de lo fabricado

### Requirement: Bloqueo de validación con stock insuficiente

Cuando el flag de compañía `not_allow_negative_stock_movement` está activo, `button_validate` de `stock.picking` DEBE (MUST) verificar en traslados internos y de salida (`_check_stock_availability_for_pickings`) que, agrupando las líneas por producto, lote y ubicación origen, la cantidad a mover no deje la existencia (`qty_available`) en negativo; la verificación no se ejecuta cuando la validación devuelve el asistente de backorder.

#### Scenario: Salida que deja stock negativo

- **WHEN** se valida un traslado de salida cuyas cantidades superan la existencia en la ubicación origen y el flag está activo
- **THEN** se lanza un error de validación listando los productos (y lotes) con stock insuficiente

### Requirement: Bloqueo de expediciones para el grupo restringido

Los usuarios del grupo `l10n_ve_stock.group_block_type_inventory_transfers_expeditions` DEBEN (MUST) tener bloqueado, vía `validate_block_transfers_expedition` en `create`/`write` de `stock.picking`: crear traslados de tipo salida (`outgoing`), agregar productos a un traslado de salida, y registrar cantidades hechas mayores a la demanda (`product_uom_qty`).

#### Scenario: Creación de una salida

- **WHEN** un usuario del grupo crea un traslado con tipo de operación de salida
- **THEN** se lanza un error indicando que no tiene permiso para hacer traslados de expedición

#### Scenario: Cantidad mayor a la demanda

- **WHEN** un usuario del grupo escribe en una línea de una salida una cantidad mayor a la demandada
- **THEN** se lanza un error indicando que no puede transferir más que la demanda

### Requirement: Bloqueo de creación de productos para el grupo restringido

El `create` de `product.product` DEBE (MUST) lanzar un error cuando el usuario pertenece al grupo `l10n_ve_stock.group_block_type_inventory_transfers_expeditions`.

#### Scenario: Usuario del grupo crea un producto

- **WHEN** un usuario del grupo intenta crear un producto
- **THEN** se lanza un error indicando que no puede crear productos

### Requirement: Eliminación de transferencias bloqueada por ACL

El módulo DEBE (MUST) sobreescribir las ACL estándar `stock.access_stock_picking_manager` y `stock.access_stock_picking_user` dejando `perm_unlink` en 0, de modo que ni usuarios ni gerentes de inventario puedan eliminar registros de `stock.picking`.

#### Scenario: Gerente de inventario intenta eliminar

- **WHEN** un usuario del grupo `stock.group_stock_manager` intenta eliminar un traslado
- **THEN** el sistema niega la operación por falta de permiso de eliminación

### Requirement: Clasificación de tipos de operación por paso logístico

El campo almacenado `type_steps` de `stock.picking.type` DEBE (MUST) computarse comparando el tipo de operación contra los tipos del almacén (`in_type_id`, `out_type_id`, `int_type_id`, `pick_type_id`, `pack_type_id`) con valores `in`/`out`/`int`/`pick`/`pack`, y el campo almacenado `type_delivery_step` de `stock.picking` DEBE (MUST) derivarse del tipo de operación del traslado. Estos campos los consume `l10n_ve_stock_account` para el flujo de guías de despacho.

#### Scenario: Tipo de operación de salida

- **WHEN** un tipo de operación es el `out_type_id` de su almacén
- **THEN** su `type_steps` es `out` y los traslados de ese tipo tienen `type_delivery_step` igual a `out`

### Requirement: Reporte de inventario valorizado a una fecha

El wizard extendido `stock.quantity.history` DEBE (MUST) generar (método `generate_report`) el reporte `l10n_ve_stock.inventory_valuation_report` con las cantidades de cada producto almacenable a la fecha `inventory_datetime`, calculadas desde las líneas de movimiento hechas (`_compute_quantities_dict_for_report`) y filtradas por la ubicación `warehouse_search_id`; cuando `except_products_at_zero` está activo excluye los productos con existencia menor o igual a cero, y cuando el módulo `binaural_last_cost` está instalado agrega las columnas de último costo.

#### Scenario: Generación a fecha pasada

- **WHEN** se genera el reporte con una fecha anterior a hoy
- **THEN** las cantidades reflejan las entradas y salidas hechas hasta esa fecha

#### Scenario: Exclusión de productos en cero

- **WHEN** se marca `except_products_at_zero`
- **THEN** el reporte solo incluye productos con existencia mayor a cero

### Requirement: Dirección física del almacén en los traslados

Los almacenes (`stock.warehouse`) DEBEN (MUST) poder registrar una dirección detallada en `physical_address`, y cada traslado DEBE (MUST) exponer las direcciones computadas `source_physical_address` y `destination_physical_address` tomadas del almacén de la ubicación origen y destino respectivamente.

#### Scenario: Traslado entre almacenes con dirección

- **WHEN** un traslado tiene ubicaciones origen y destino pertenecientes a almacenes con `physical_address` definida
- **THEN** el traslado muestra ambas direcciones en los campos computados
