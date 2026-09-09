# l10n_ve_sale

## Purpose

Adapta el flujo de ventas (`sale.order`, `sale.order.line`, `sale.report`) a la operación venezolana en doble moneda: tasa alterna por orden, montos espejo en moneda alterna, validaciones de confirmación (stock, crédito, facturas vencidas), facturación por lotes, división de entregas y restricciones de interfaz por grupos. Depende de `base`, `l10n_ve_base`, `sale`, `l10n_ve_rate` (moneda alterna y `compute_rate`), `l10n_ve_contact` (prefijo de RIF), `l10n_ve_invoice` (límite de productos por factura), `l10n_ve_filter_partner` (mixin de filtro de contactos) y `l10n_ve_stock` (límite de líneas por entrega). Los montos alternos de `tax_totals` provienen de la extensión de impuestos de `l10n_ve_accountant`.

## Requirements

### Requirement: Moneda alterna y tasa por defecto en la orden

Toda orden de venta (`sale.order`) DEBE (MUST) inicializar `foreign_currency_id` con la moneda alterna de la compañía (`foreign_currency_id` de `res.company`, de `l10n_ve_rate`) y los campos `foreign_rate` y `foreign_inverse_rate` con el resultado de `compute_rate` de `res.currency.rate` a la fecha de la orden (o la fecha actual si no hay fecha). Los defaults de tasa (`default_rate` y `default_inverse_rate`) usan la moneda alterna de la compañía y, si esta no está configurada, recurren al bolívar (`base.VEF`) como moneda de respaldo; en ese caso `foreign_currency_id` queda vacío.

#### Scenario: Creación de una orden con moneda alterna configurada

- **WHEN** se crea una orden de venta y la compañía tiene moneda alterna configurada
- **THEN** `foreign_currency_id` queda en la moneda alterna de la compañía y `foreign_rate`/`foreign_inverse_rate` toman la tasa vigente devuelta por `compute_rate`

### Requirement: Recálculo de tasa condicionado por configuración

El cómputo `_compute_rate` de la orden DEBE (MUST) recalcular `foreign_rate` y `foreign_inverse_rate` (vía `compute_rate` de `l10n_ve_rate`) cuando cambian `foreign_currency_id` o `date_order`, EXCEPTO cuando: (a) la orden tiene `manually_set_rate` activo, (b) la orden proviene del sitio web (`website_id` establecido), o (c) la compañía tiene `update_sale_order_rate_using_date_order` desactivado y la tasa ya es distinta de cero. El flag `update_sale_order_rate_using_date_order` es configurable por compañía desde ajustes (related en `res.config.settings` con `readonly=False`).

#### Scenario: Cambio de fecha con actualización habilitada

- **WHEN** cambia `date_order` de una orden sin tasa manual y la compañía tiene `update_sale_order_rate_using_date_order` activo
- **THEN** `foreign_rate` y `foreign_inverse_rate` se recalculan con la tasa vigente a la nueva fecha

#### Scenario: Cambio de fecha con actualización deshabilitada y tasa ya fijada

- **WHEN** cambia `date_order` y la compañía tiene `update_sale_order_rate_using_date_order` desactivado con `foreign_rate` distinto de cero
- **THEN** la tasa de la orden no se modifica

#### Scenario: Orden con tasa manual

- **WHEN** la orden tiene `manually_set_rate` activo
- **THEN** el recálculo automático no toca sus tasas

### Requirement: Tasa inversa al editar la tasa manualmente

Al modificar `foreign_rate` en el formulario (onchange `_onchange_foreign_rate`), el sistema DEBE (MUST) fijar `foreign_inverse_rate = 1 / foreign_rate` únicamente cuando `foreign_currency_id` de la orden es USD (`base.USD`); con cualquier otra moneda alterna `foreign_inverse_rate` toma el mismo valor de `foreign_rate`. Si la tasa introducida es cero no se recalcula nada.

#### Scenario: Moneda alterna USD

- **WHEN** el usuario escribe una tasa distinta de cero y la moneda alterna de la orden es USD
- **THEN** `foreign_inverse_rate` queda en el inverso matemático de la tasa

#### Scenario: Moneda alterna distinta de USD

- **WHEN** el usuario escribe una tasa y la moneda alterna no es USD
- **THEN** `foreign_inverse_rate` queda igual a `foreign_rate`

### Requirement: Trazabilidad del cambio manual de tasa

El sistema DEBE (MUST) dejar constancia en el chatter de la orden cuando la tasa se aparta de la registrada: al crear una orden con `manually_set_rate` activo cuya `foreign_rate` difiere de la tasa del sistema para su fecha, y al escribir una nueva `foreign_rate` en una orden con `manually_set_rate` activo cuando la nueva difiere de la anterior. En cada escritura de `foreign_rate` (tenga o no la orden tasa manual) el sistema DEBE (MUST) guardar la tasa previa en `last_foreign_rate`; el mensaje del chatter solo se publica cuando `manually_set_rate` está activo.

#### Scenario: Creación con tasa manual distinta a la del sistema

- **WHEN** se crea una orden con `manually_set_rate` activo y `foreign_rate` distinta a la devuelta por `compute_rate` para su fecha
- **THEN** se publica un mensaje en el chatter indicando el cambio de tasa

#### Scenario: Edición de la tasa manual

- **WHEN** se escribe una `foreign_rate` diferente en una orden con `manually_set_rate` activo
- **THEN** `last_foreign_rate` guarda la tasa anterior y se publica un mensaje con la tasa anterior y la nueva

### Requirement: Traslado de la tasa de la orden a la factura

Al preparar la factura desde la orden (`_prepare_invoice`), el sistema DEBE (MUST) copiar `foreign_rate` y `foreign_inverse_rate` de la orden a la factura, y marcar la factura con `manually_set_rate` cuando la orden lo tiene activo o la compañía tiene activo `use_invoice_rate_from_sale_order` (configurable desde ajustes). El método `_update_invoices_rate` DEBE (MUST) sincronizar las tasas de las facturas de la orden solo cuando `use_invoice_rate_from_sale_order` está activo.

#### Scenario: Compañía que usa la tasa de la orden

- **WHEN** la compañía tiene `use_invoice_rate_from_sale_order` activo y se factura una orden
- **THEN** la factura se crea con las tasas de la orden y con `manually_set_rate` activo, de modo que la factura no recalcula la tasa a su propia fecha

#### Scenario: Sincronización con el flag desactivado

- **WHEN** se invoca `_update_invoices_rate` y la compañía no tiene `use_invoice_rate_from_sale_order` activo
- **THEN** las facturas de la orden no se modifican

### Requirement: Impuesto único por línea de orden

Cuando la compañía tiene activo el flag `unique_tax` (definido en `l10n_ve_accountant`), el sistema DEBE (MUST) impedir, vía constraint sobre `order_line`, guardar órdenes cuyas líneas de producto (sin `display_type`) no tengan exactamente un impuesto en `tax_ids`.

#### Scenario: Línea con más de un impuesto

- **WHEN** se guarda una orden con una línea de producto con dos impuestos y la compañía tiene `unique_tax` activo
- **THEN** se lanza un error de validación indicando que todos los productos deben tener un solo impuesto

### Requirement: Límite de líneas por orden confirmada

Cuando la compañía tiene `are_sale_lines_limited` activo y `maximum_sales_line_limit` mayor que cero (ambos configurables desde ajustes), el sistema DEBE (MUST) impedir que una orden en estado distinto de `draft` o `cancel` supere ese número de líneas.

#### Scenario: Orden confirmada que excede el límite

- **WHEN** una orden pasa a un estado distinto de borrador/cancelado con más líneas que `maximum_sales_line_limit`
- **THEN** se lanza un error indicando el límite de líneas

#### Scenario: Presupuesto en borrador

- **WHEN** una orden en estado `draft` supera el límite
- **THEN** no se lanza ningún error

### Requirement: Montos alternos de la orden

La orden DEBE (MUST) exponer `foreign_taxable_income` (base imponible alterna, tomada de `base_amount_foreign_currency` de `tax_totals`), `foreign_untaxed_total` y `foreign_total_billed` en la moneda alterna. Cuando la moneda de la orden es una tercera moneda (distinta de la moneda de la compañía y de la alterna), `foreign_untaxed_total` y `foreign_total_billed` se calculan convirtiendo `amount_untaxed` y `amount_total` a la moneda alterna con `_convert` a la fecha de la orden; en caso contrario se toman de las claves alternas de `tax_totals` (`base_amount_foreign_currency`, `total_amount_foreign_currency`).

#### Scenario: Orden en moneda de la compañía o en la alterna

- **WHEN** la orden tiene líneas y su moneda es la de la compañía o la alterna
- **THEN** los totales alternos provienen de las claves `*_foreign_currency` de `tax_totals`

#### Scenario: Orden en una tercera moneda

- **WHEN** la moneda de la orden no es ni la de la compañía ni la alterna
- **THEN** los totales alternos se obtienen convirtiendo los montos de la orden a la moneda alterna a la fecha de la orden

### Requirement: Montos firmados en moneda de la compañía

La orden DEBE (MUST) calcular `amount_untaxed_total_signed` y `amount_total_signed` en la moneda de la compañía: si la moneda de la orden difiere de la de la compañía se convierten `amount_untaxed` y `amount_total` con `_convert` a la fecha de la orden; si coinciden, son los mismos montos.

#### Scenario: Orden en moneda extranjera

- **WHEN** una orden está en una moneda distinta a la de la compañía
- **THEN** los montos firmados muestran el equivalente convertido a la moneda de la compañía

### Requirement: Precio y subtotal alterno por línea

Cada línea (`sale.order.line`) DEBE (MUST) calcular `foreign_price`: si la moneda de la línea es la de la compañía, convierte `price_unit` a la moneda alterna a la fecha de la orden; si la moneda de la línea ya es la alterna, `foreign_price = price_unit`; con una tercera moneda, convierte desde esa moneda a la alterna. El `foreign_subtotal` DEBE (MUST) ser `foreign_price * (1 - discount/100) * product_uom_qty` en la moneda alterna.

#### Scenario: Línea en moneda de la compañía

- **WHEN** la línea está en la moneda de la compañía con moneda alterna configurada
- **THEN** `foreign_price` es la conversión del precio unitario a la moneda alterna a la fecha de la orden

#### Scenario: Línea en la moneda alterna

- **WHEN** la moneda de la línea es la misma moneda alterna
- **THEN** `foreign_price` es igual a `price_unit` sin conversión

#### Scenario: Subtotal alterno con descuento

- **WHEN** una línea tiene descuento y cantidad
- **THEN** `foreign_subtotal` aplica el descuento sobre `foreign_price` y multiplica por la cantidad

### Requirement: Recalculo de precio unitario al cambiar la moneda de la orden

El cómputo de `price_unit` de la línea DEBE (MUST) dispararse también al cambiar `order_id.currency_id`, preservando sin recalcular las líneas con precio fijado manualmente (`technical_price_unit` distinto de `price_unit`, salvo contexto `force_price_recomputation`), las líneas con cantidad ya facturada (`qty_invoiced > 0`) y las líneas de gasto con política de costo.

#### Scenario: Cambio de moneda con línea ya facturada

- **WHEN** cambia la moneda de la orden y una línea tiene `qty_invoiced` mayor que cero
- **THEN** el precio unitario de esa línea no se recalcula

### Requirement: Confirmación requiere productos

La acción `action_confirm` DEBE (MUST) rechazar con error la confirmación de una orden sin líneas o cuyas líneas son todas de tipo visual (`display_type`).

#### Scenario: Orden sin productos

- **WHEN** se confirma una orden que solo tiene secciones o notas
- **THEN** se lanza un error indicando que debe agregarse un producto

### Requirement: Bloqueo de venta sin existencias

Cuando la compañía tiene activo `not_allow_sell_products` (configurable desde ajustes) y no se pasa el contexto `skip_not_allow_sell_products_validation`, `action_confirm` DEBE (MUST) impedir confirmar órdenes con líneas de productos almacenables de tipo `consu` cuya cantidad demandada supere `qty_available`.

#### Scenario: Cantidad demandada mayor al stock

- **WHEN** se confirma una orden con una línea de producto almacenable cuya cantidad supera las unidades disponibles y la compañía tiene `not_allow_sell_products` activo
- **THEN** se lanza un error de validación indicando las unidades disponibles frente a las demandadas

#### Scenario: Validación omitida por contexto

- **WHEN** la confirmación se ejecuta con el contexto `skip_not_allow_sell_products_validation`
- **THEN** la validación de existencias no se aplica

### Requirement: Bloqueo por límite de crédito del cliente

Dentro del bloque de validaciones activado por `not_allow_sell_products`, cuando la compañía usa límite de crédito (`account_use_credit_limit`) y el cliente tiene activo `use_partner_credit_limit_order` (campo de `l10n_ve_accountant`), `action_confirm` DEBE (MUST) impedir la confirmación si `credit` del cliente más `amount_total` de la orden supera su `credit_limit`.

#### Scenario: Crédito excedido

- **WHEN** la cuenta por cobrar del cliente más el total del presupuesto supera su límite de crédito
- **THEN** se lanza un error de validación detallando la cuenta por cobrar, el monto del presupuesto, el total y el límite

### Requirement: Bloqueo por facturas impagas o monto vencido

Dentro del mismo bloque de validaciones, `_block_valid_confirm` DEBE (MUST) impedir la confirmación cuando el cliente tiene facturas de venta publicadas con monto mayor a cero que: (a) están en el estado de pago configurado en `block_order_invoice_payment_state` de la compañía (`not_paid` o `in_payment`), o (b) están vencidas y la suma de sus residuales supera `block_order_invoice_total_amount_overdue` cuando este umbral está configurado. Ambos parámetros son configurables desde ajustes.

#### Scenario: Facturas en el estado de pago bloqueante

- **WHEN** el cliente tiene facturas publicadas en el estado de pago configurado
- **THEN** se lanza un error indicando la cantidad de facturas y el estado

#### Scenario: Monto vencido sobre el umbral

- **WHEN** la suma de los residuales de facturas vencidas del cliente supera el monto configurado
- **THEN** se lanza un error indicando el monto vencido y el máximo permitido

### Requirement: División de entregas por límite de líneas

Al confirmar la orden, cuando la compañía tiene `limit_product_qty_out` mayor que cero (campo de `l10n_ve_stock`), el sistema DEBE (MUST) repartir los movimientos del picking generado en bloques de ese tamaño: el primer bloque permanece en el picking original y por cada bloque adicional se crea un nuevo `stock.picking` con los mismos datos de cabecera (ubicaciones, tipo de operación, origen, contacto, responsable).

#### Scenario: Orden que supera el límite de líneas de entrega

- **WHEN** se confirma una orden cuyo picking tiene más movimientos que `limit_product_qty_out`
- **THEN** se crean pickings adicionales, cada uno con a lo sumo `limit_product_qty_out` movimientos

### Requirement: Facturación por lotes según límite de productos por factura

`_get_invoiceable_lines` DEBE (MUST) truncar las líneas facturables al máximo `max_product_invoice` de la compañía (campo de `l10n_ve_invoice`), salvo que el contexto traiga `ignore_limit`; y `_create_invoices` DEBE (MUST) crear tantas facturas como haga falta, repitiendo la creación mientras queden líneas facturables, de modo que una orden que excede el límite se factura en varias facturas.

#### Scenario: Orden con más productos que el límite

- **WHEN** se factura una orden con más líneas facturables que `max_product_invoice`
- **THEN** se generan varias facturas, cada una con a lo sumo el límite de líneas, hasta cubrir toda la orden

#### Scenario: Límite ignorado por contexto

- **WHEN** la facturación se ejecuta con el contexto `ignore_limit`
- **THEN** las líneas facturables no se truncan

### Requirement: Estado de facturación parcial

El campo `invoice_status` de la orden DEBE (MUST) incluir la opción `partially_billed` y asignarla a las órdenes confirmadas (`sale`/`done`) cuya cantidad facturada total es mayor que cero pero menor que el total facturable (cantidad pedida para productos con política `order`, cantidad entregada para política de entrega).

#### Scenario: Orden facturada por partes

- **WHEN** una orden confirmada tiene parte de sus cantidades facturadas pero no todas
- **THEN** su `invoice_status` es `partially_billed`

### Requirement: Cancelación automática de presupuestos antiguos

El módulo DEBE (MUST) proveer el cron "Cancel Orders After Day" (inactivo por defecto, frecuencia diaria) que ejecuta `cancel_order_after_date`, cancelando las órdenes creadas hace más de un día que no están en estado `sale`, `done` ni `cancel`.

#### Scenario: Presupuesto de más de un día con el cron activo

- **WHEN** el cron está activo y existe un presupuesto creado antes de ayer que sigue sin confirmar
- **THEN** el presupuesto se cancela automáticamente

### Requirement: RIF del cliente en la orden

La orden DEBE (MUST) calcular el campo `vat` concatenando `prefix_vat` (campo de `l10n_ve_contact`) y `vat` del cliente, en mayúsculas; si el cliente no tiene prefijo se usa solo su `vat`.

#### Scenario: Cliente con prefijo de RIF

- **WHEN** el cliente tiene `prefix_vat` "J" y `vat` "123456789"
- **THEN** el campo `vat` de la orden muestra "J123456789"

### Requirement: Lista de precios restringida a la compañía

El campo `pricelist_id` de la orden DEBE (MUST) limitar su dominio a listas de precios de la compañía de la orden o sin compañía (`[('company_id', 'in', (company_id, False))]`).

#### Scenario: Selección de lista de precios

- **WHEN** el usuario selecciona una lista de precios en la orden
- **THEN** solo puede elegir listas de la compañía de la orden o compartidas (sin compañía)

### Requirement: Recalcular precios al cambiar la lista de precios

Al cambiar `pricelist_id` en el formulario (onchange `_onchange_pricelist_id`), el sistema DEBE (MUST) recalcular los precios de las líneas (`_recompute_prices`) y, si se estableció una lista, publicar en el chatter una nota con el enlace a la lista aplicada.

#### Scenario: Cambio de lista de precios

- **WHEN** el usuario cambia la lista de precios de la orden
- **THEN** los precios de los productos se recalculan según la nueva lista y queda una nota en el chatter

### Requirement: Precios con y sin impuesto en ítems de lista de precios

Cada `product.pricelist.item` DEBE (MUST) exponer `price_with_tax` y `price_without_tax`, calculados aplicando `compute_all` de los impuestos de venta de la plantilla de producto sobre `fixed_price` (`total_included` y `total_excluded` respectivamente); si la plantilla no tiene impuestos, ambos son `fixed_price`.

#### Scenario: Ítem de producto con IVA

- **WHEN** un ítem de precio fijo pertenece a un producto con impuesto de venta
- **THEN** `price_with_tax` muestra el precio con el impuesto incluido y `price_without_tax` el precio sin impuesto

### Requirement: Precio fijo no negativo en ítems de lista

El sistema DEBE (MUST) impedir, vía constraint sobre `fixed_price` de `product.pricelist.item`, guardar ítems con precio fijo negativo.

#### Scenario: Precio negativo

- **WHEN** se guarda un ítem de lista de precios con `fixed_price` menor que cero
- **THEN** se lanza un error de validación indicando que el precio no puede ser negativo

### Requirement: Totales alternos en el análisis de ventas

El reporte `sale.report` DEBE (MUST) incluir las medidas `foreign_untaxed_total` (suma de `foreign_subtotal` de las líneas) y `foreign_total_billed` (suma de `foreign_subtotal` más la porción de impuestos prorrateada con `price_total - price_subtotal` sobre `price_subtotal`), agrupadas también por `foreign_currency_id` de la orden.

#### Scenario: Análisis de ventas con moneda alterna

- **WHEN** se consulta el análisis de ventas de órdenes con montos alternos
- **THEN** las medidas alternas agregan los subtotales alternos de las líneas y su total con impuestos, por moneda alterna

### Requirement: Búsqueda de órdenes incluye registros archivados

El método `search_read` de `sale.order` DEBE (MUST) ejecutarse con `active_test=False`, de modo que las lecturas vía `search_read` incluyan también las órdenes archivadas.

#### Scenario: Lectura con registros archivados

- **WHEN** un cliente RPC o una vista invoca `search_read` sobre órdenes de venta
- **THEN** el resultado incluye las órdenes archivadas que cumplen el dominio

### Requirement: Gerentes de ventas sin permiso de eliminación

El módulo DEBE (MUST) redefinir las ACL `sale.access_sale_order_manager` y `sale_stock.access_stock_picking_sales` dejando `perm_unlink` en 0, de modo que el grupo `sales_team.group_sale_manager` conserve lectura, escritura y creación sobre `sale.order` y `stock.picking` pero no pueda eliminarlos.

#### Scenario: Gerente de ventas intenta eliminar una orden

- **WHEN** un usuario con solo el grupo de gerente de ventas intenta eliminar una orden de venta o un picking
- **THEN** el sistema le niega el acceso de eliminación

### Requirement: Menú de ítems de lista de precios por grupo

El menú "Price List Items" bajo el catálogo de ventas DEBE (MUST) ser visible únicamente para los usuarios del grupo `l10n_ve_sale.group_view_pricelist_items`, y abrir la vista de lista dedicada de `product.pricelist.item`.

#### Scenario: Usuario sin el grupo

- **WHEN** un usuario sin el grupo "See Pricelist Items" navega el menú de ventas
- **THEN** el menú "Price List Items" no aparece

### Requirement: Impuestos de línea de solo lectura en el formulario

En el formulario de la orden, la columna `tax_ids` de las líneas DEBE (MUST) estar en solo lectura para todos los usuarios, de modo que los impuestos de cada línea provienen de la configuración del producto/posición fiscal y no pueden editarse manualmente desde la orden.

#### Scenario: Usuario intenta cambiar el impuesto de una línea

- **WHEN** cualquier usuario edita una línea de producto en el formulario de la orden
- **THEN** la celda de impuestos no es editable

### Requirement: Página de moneda alterna por grupo

La página "Foreign currency" del formulario de la orden (tasas y totales alternos con el widget de totales de `l10n_ve_accountant`) DEBE (MUST) mostrarse solo a los usuarios del grupo `l10n_ve_sale.group_foreign_currency_view_sales`.

#### Scenario: Usuario con el grupo

- **WHEN** un usuario del grupo "Foreign Currency View Sales" abre una orden
- **THEN** ve la página con `foreign_rate` y los totales en moneda alterna

### Requirement: Grupo que fija la lista de precios como solo lectura

Para los usuarios del grupo `l10n_ve_sale.pricelist_sale_order_group` ("Hide pricelist (sale)"), el campo `pricelist_id` de la orden DEBE (MUST) mostrarse en solo lectura; para el resto es editable mientras la orden está en borrador.

#### Scenario: Usuario del grupo

- **WHEN** un usuario del grupo abre un presupuesto
- **THEN** no puede cambiar la lista de precios

### Requirement: Grupo que oculta los términos de pago

Para los usuarios del grupo `l10n_ve_sale.payment_terms_sale_order_group` ("Hide Payment terms (sale)"), el campo `payment_term_id` DEBE (MUST) quedar oculto en el formulario de la orden.

#### Scenario: Usuario del grupo

- **WHEN** un usuario del grupo abre una orden de venta
- **THEN** el campo de términos de pago no se muestra

### Requirement: Grupo que oculta los botones de crear factura

Para los usuarios del grupo `l10n_ve_sale.create_invoice_sale_order_group` ("Hide Create Invoice (sale)"), los botones "Create Invoice" del formulario de la orden DEBEN (MUST) quedar ocultos; para el resto, el botón principal es visible cuando `invoice_status` es `to invoice` o `partially_billed`.

#### Scenario: Usuario del grupo

- **WHEN** un usuario del grupo abre una orden por facturar
- **THEN** no ve los botones de crear factura

#### Scenario: Orden parcialmente facturada

- **WHEN** un usuario sin el grupo abre una orden con `invoice_status` en `partially_billed`
- **THEN** el botón "Create Invoice" está disponible

### Requirement: Grupo que oculta el filtro de contactos

Para los usuarios del grupo `l10n_ve_sale.contact_filter_sale_order_group` ("Hide Contact filter (sale)"), el selector `filter_partner` (mixin de `l10n_ve_filter_partner`) DEBE (MUST) quedar oculto en el formulario de la orden; para el resto es editable mientras la orden no está confirmada.

#### Scenario: Usuario del grupo

- **WHEN** un usuario del grupo abre una orden
- **THEN** el selector de filtro de contacto no se muestra, aunque el filtrado por defecto (`customer`) sigue aplicándose al dominio del cliente
