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

La constraint `_check_barcode_uniqueness` de `product.product` DEBE (MUST) evaluar los duplicados de `barcode` filtrando por `("company_id", "=", self.company_id.id)`, de modo que el mismo código de barras pueda existir en compañías distintas pero no repetirse dentro de la misma compañía. A diferencia de la constraint estándar de Odoo, esta versión NO compara contra los códigos de barras de los empaques (`packaging`), y al usar `self.company_id` como valor único solo es fiable cuando todos los registros validados comparten compañía: para productos sin compañía el filtro se resuelve como `company_id = False`.

#### Scenario: Duplicado en la misma compañía

- **WHEN** se asigna a un producto un `barcode` ya usado por otro producto de la misma compañía
- **THEN** se lanza un error de validación listando los códigos duplicados

#### Scenario: Mismo código en otra compañía

- **WHEN** el `barcode` ya existe pero en un producto de otra compañía
- **THEN** el registro se guarda sin error

#### Scenario: Producto sin compañía frente a uno de una compañía

- **WHEN** se guarda un producto sin `company_id` con un `barcode` que ya usa un producto asignado a una compañía
- **THEN** no se detecta duplicado, porque la búsqueda se limita a `company_id = False`

### Requirement: Cantidad disponible para la venta

El campo almacenado `quantity` de `product.template` (`_compute_available_quantity`) DEBE (MUST) calcularse según el flag `use_free_qty_odoo` de la compañía activa (`self.env.company`, no la del producto): si está desactivado, es la suma de `available_quantity` de los quants en mano (`on_hand`) del producto que no sean de tipo servicio y cuya ubicación es la ubicación de stock del almacén (`lot_stock_id`) o hija directa de ella, truncada a 0 si el total es negativo; si está activado, es el `free_qty` propio del módulo (suma del `free_qty` de las variantes).

#### Scenario: Cálculo propio por almacén

- **WHEN** `use_free_qty_odoo` está desactivado y el producto tiene existencia en ubicaciones de stock de almacenes
- **THEN** `quantity` suma la cantidad disponible (no reservada) de esas ubicaciones y nunca es negativa

#### Scenario: Quant en una sub-ubicación de segundo nivel

- **WHEN** el quant está en una ubicación nieta de `lot_stock_id` (la comparación solo cubre la ubicación misma y su padre inmediato)
- **THEN** esa cantidad no se suma a `quantity`

#### Scenario: Cálculo estándar de Odoo

- **WHEN** `use_free_qty_odoo` está activado
- **THEN** `quantity` es igual a `free_qty`

### Requirement: Categorías de producto multi-compañía

El módulo DEBE (MUST) dotar a `product.category` de un campo `company_id` (por defecto la compañía activa) y de una regla de registro global (`product_category_multi_company_rule`, cargada con `noupdate="1"`) que limita la visibilidad a las categorías de las compañías del usuario o sin compañía.

#### Scenario: Categoría de otra compañía

- **WHEN** un usuario consulta categorías y existe una con `company_id` de una compañía a la que no tiene acceso
- **THEN** esa categoría no aparece en sus resultados

### Requirement: Prioridad no negativa en ubicaciones

La constraint `_check_priority` de `stock.location` DEBE (MUST) impedir guardar una ubicación con `priority` menor a 0 (el campo tiene default 10 y trazabilidad por chatter).

#### Scenario: Prioridad negativa

- **WHEN** se asigna una `priority` negativa a una ubicación
- **THEN** se lanza un error de validación

### Requirement: Ordenamiento de movimientos por prioridad de ubicación física

Cada uno de los modelos `stock.move` y `stock.move.line` DEBE (MUST) declarar `_order = "priority_location asc"` sobre el campo almacenado `priority_location`, relacionado con la `priority` de la `physical_location_id` del producto (`product.template.priority_location`). El `_order` reemplaza por completo el orden estándar de Odoo (no lo antepone), y `stock.move.line` DEBE (MUST) exponer además `priority_location` a la app de códigos de barras vía `_get_fields_stock_barcode`.

#### Scenario: Líneas de un traslado

- **WHEN** un traslado contiene productos con ubicaciones físicas de distinta prioridad
- **THEN** los movimientos y líneas se listan de menor a mayor `priority_location`

### Requirement: Reserva dirigida a la ubicación física del producto

Cuando el flag de compañía `use_physical_location` está activo, `_update_reserved_quantity` de `stock.quant` DEBE (MUST) reservar únicamente en los quants de la `physical_location_id` del producto siempre que esa ubicación exista entre los quants candidatos, asignando en ella la totalidad de la cantidad demandada incluso si excede lo disponible en esa ubicación. En esta rama la guarda estándar de Odoo que impide reservar (o liberar) más de lo existente está deshabilitada, por lo que la sobre-reserva NO produce error. Si el flag está inactivo, el producto no tiene ubicación física entre los quants, o el contexto trae `skip_physical_location`, se aplica el comportamiento estándar de Odoo.

#### Scenario: Producto con ubicación física

- **WHEN** `use_physical_location` está activo y se reserva un producto cuya `physical_location_id` tiene quants en la ubicación origen
- **THEN** la reserva se registra completa sobre el quant de la ubicación física

#### Scenario: Reserva mayor a la existencia en la ubicación física

- **WHEN** se pide reservar más cantidad de la que existe en la `physical_location_id`
- **THEN** no se lanza error y el `reserved_quantity` del quant queda por encima de su `quantity`

#### Scenario: Flag desactivado

- **WHEN** `use_physical_location` está inactivo
- **THEN** la reserva sigue la lógica estándar de Odoo

### Requirement: Reserva física no excluida en el resto de los pasos logísticos

`action_assign` de `stock.picking` DEBE (MUST) delegar en `super()` sobre `self` sin contexto adicional: el bucle que recorre los traslados con `type_delivery_step` distinto de `pick` solo reasigna una variable local con `with_context(skip_physical_location=True)` y la descarta, por lo que la bandera NO llega a `_update_reserved_quantity` y la reserva dirigida a la ubicación física se aplica en todos los pasos, no solo en el picking.

#### Scenario: Reserva de un traslado de salida

- **WHEN** se comprueba disponibilidad de un traslado con `type_delivery_step` distinto de `pick` y `use_physical_location` está activo
- **THEN** la reserva se dirige igualmente a la ubicación física del producto porque el contexto `skip_physical_location` nunca se propaga a `super().action_assign()`

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

Cuando el flag de compañía `not_allow_scrap_more_than_what_was_manufactured` está activo, el desecho está vinculado a una orden de producción (`production_id`) y esa producción ya tiene desechos asociados (`scrap_ids` no vacío), `action_validate` de `stock.scrap` DEBE (MUST) impedir la validación si se cumple cualquiera de estas tres condiciones: los desechos hechos (`state = done`) ya alcanzan o superan `qty_produced`, la suma de esos desechos más el actual supera `qty_produced`, o el desecho actual por sí solo supera `qty_produced`.

#### Scenario: Desecho acumulado mayor a lo producido

- **WHEN** los desechos validados de la producción más el actual superan `qty_produced`
- **THEN** se lanza un error indicando que no se puede desechar más de lo fabricado

#### Scenario: Desechos previos iguales a lo producido

- **WHEN** los desechos ya validados igualan exactamente `qty_produced`
- **THEN** se lanza el error incluso si el desecho actual es cero, porque la comparación es `>=`

### Requirement: Bloqueo de validación con stock insuficiente

Cuando el flag de compañía `not_allow_negative_stock_movement` está activo, `button_validate` de `stock.picking` DEBE (MUST) ejecutar primero `super().button_validate()` y, si el resultado no es el asistente de backorder (`stock.backorder.confirmation`), verificar con `_check_stock_availability_for_pickings` que la cantidad a mover no deje la existencia en negativo, para finalmente volver a invocar `super().button_validate()`. La verificación DEBE (MUST) considerar únicamente el caso de un solo traslado cuyo `picking_type_id.code` sea `internal` u `outgoing` (al comparar un recordset de tipos de operación contra la lista, la validación se omite silenciosamente cuando se validan varios traslados a la vez), agrupar las líneas de movimiento por producto, lote y ubicación origen, contabilizar solo líneas de productos `consu` con cantidad hecha mayor a cero, y comparar el total agrupado contra el `qty_available` del producto en el contexto de esa ubicación y lote. Como la comprobación corre después de que `super()` ya aplicó los movimientos, el `qty_available` consultado ya viene descontado y la cantidad a mover se resta por segunda vez.

#### Scenario: Salida que deja stock negativo

- **WHEN** se valida un solo traslado de salida cuyas cantidades superan la existencia en la ubicación origen y el flag está activo
- **THEN** se lanza un error de validación listando los productos (y lotes) con stock insuficiente y la transacción se revierte

#### Scenario: Validación de varios traslados a la vez

- **WHEN** se validan simultáneamente dos o más traslados con el flag activo
- **THEN** `_check_stock_availability_for_pickings` no compara nada porque el recordset de tipos de operación no coincide con `['internal', 'outgoing']`

### Requirement: Bloqueo de creación de expediciones para el grupo restringido

`validate_block_transfers_expedition` DEBE (MUST) impedir a los usuarios del grupo `l10n_ve_stock.group_block_type_inventory_transfers_expeditions` crear traslados cuyo tipo de operación tenga `code = outgoing`. La rama de `write` DEBE (MUST) buscar los cambios en las claves `move_line_nosuggest_ids` y `move_ids_without_package`, campos que ya no existen en `stock.picking` en Odoo 19, por lo que `matched_key` nunca se resuelve y la modificación de líneas de una salida (agregar productos o registrar cantidad mayor a la demanda `product_uom_qty`) no queda bloqueada en la práctica. La comparación alternativa contra `reserved_uom_qty` es código inalcanzable porque el `elif` repite la misma condición del `if`.

#### Scenario: Creación de una salida

- **WHEN** un usuario del grupo crea un traslado con tipo de operación de salida
- **THEN** se lanza un error indicando que no tiene permiso para hacer traslados de expedición

#### Scenario: Cantidad mayor a la demanda

- **WHEN** un usuario del grupo escribe en una línea de una salida una cantidad mayor a la demandada
- **THEN** la escritura se acepta: ninguna de las claves vigiladas está presente en `vals` y el bloqueo no se dispara

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

### Requirement: ACL global de ubicaciones sin grupo

El módulo DEBE (MUST) declarar la ACL `access_stock_location_manager` sobre `stock.location` con `group_id` vacío y los cuatro permisos en 1, de modo que cualquier usuario con acceso al modelo (no solo los gerentes de inventario) pueda leer, escribir, crear y eliminar ubicaciones.

#### Scenario: Usuario sin grupos de inventario

- **WHEN** un usuario interno que no pertenece a ningún grupo de inventario crea o elimina una `stock.location`
- **THEN** la ACL sin grupo se lo permite porque aplica a todos los usuarios

### Requirement: Clasificación de tipos de operación por paso logístico

El campo almacenado `type_steps` de `stock.picking.type` DEBE (MUST) computarse comparando el tipo de operación contra los tipos del almacén (`in_type_id`, `out_type_id`, `int_type_id`, `pick_type_id`, `pack_type_id`) con valores `in`/`out`/`int`/`pick`/`pack`, y el campo almacenado `type_delivery_step` de `stock.picking` DEBE (MUST) derivarse del tipo de operación del traslado. Estos campos los consume `l10n_ve_stock_account` para el flujo de guías de despacho.

#### Scenario: Tipo de operación de salida

- **WHEN** un tipo de operación es el `out_type_id` de su almacén
- **THEN** su `type_steps` es `out` y los traslados de ese tipo tienen `type_delivery_step` igual a `out`

### Requirement: Reporte de inventario valorizado a una fecha

El wizard extendido `stock.quantity.history` DEBE (MUST) generar (método `generate_report`) el reporte `l10n_ve_stock.inventory_valuation_report` seleccionando los productos con el dominio `[("type", "=", "product")]` —valor que ya no existe en la selección de `product.template.type` de Odoo 19 (`consu`/`service`/`combo`), por lo que el conjunto resultante es vacío y el reporte sale sin líneas— acotado además a la compañía activa y sin compañía solo cuando existe más de una compañía en la base. Las cantidades DEBEN (MUST) calcularse con `_compute_quantities_dict_for_report` en el contexto de la ubicación `warehouse_search_id`, cuya fórmula es la suma actual de los quants de esas ubicaciones MÁS las cantidades de líneas de movimiento hechas entrantes MENOS las salientes con fecha hasta `inventory_datetime` (no es una foto histórica: parte de la existencia actual y vuelve a sumar el histórico). Cuando `except_products_at_zero` está activo el reporte DEBE (MUST) incluir solo los productos con existencia mayor a cero, y cuando el módulo `binaural_last_cost` está instalado DEBE (MUST) agregar las columnas de último costo a la lista de campos.

#### Scenario: Generación a fecha pasada

- **WHEN** se genera el reporte con una fecha anterior a hoy
- **THEN** no se listan productos, porque ningún producto tiene `type = "product"` en Odoo 19

#### Scenario: Exclusión de productos en cero

- **WHEN** se marca `except_products_at_zero`
- **THEN** el reporte solo incluye productos con existencia mayor a cero

#### Scenario: Columnas de último costo acumuladas

- **WHEN** se genera el reporte varias veces en el mismo proceso con `binaural_last_cost` instalado
- **THEN** las columnas de último costo se agregan de nuevo en cada llamada, porque la lista de campos es una constante de módulo mutada en sitio

### Requirement: Dirección física del almacén en los traslados

Los almacenes (`stock.warehouse`) DEBEN (MUST) poder registrar una dirección detallada en `physical_address`, y cada traslado DEBE (MUST) exponer las direcciones computadas `source_physical_address` y `destination_physical_address` tomadas del almacén de la ubicación origen y destino respectivamente.

#### Scenario: Traslado entre almacenes con dirección

- **WHEN** un traslado tiene ubicaciones origen y destino pertenecientes a almacenes con `physical_address` definida
- **THEN** el traslado muestra ambas direcciones en los campos computados
