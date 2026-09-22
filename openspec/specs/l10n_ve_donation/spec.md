# l10n_ve_donation

## Purpose

Gestiona el flujo completo de donaciones: pedidos de venta marcados como donación, facturas de donación que se anulan automáticamente con una nota de crédito valorada contra la cuenta de gasto de donación, salidas de inventario por donación (variante del scrap) con su asiento contable, y el certificado de donación en PDF. Extiende `account.move`, `account.move.line`, `product.template`, `res.company`, `res.config.settings`, `sale.order`, `stock.location`, `stock.move`, `stock.picking.type`, `stock.scrap` y `stock.warehouse`. Depende de `l10n_ve_accountant`, `l10n_ve_stock`, `l10n_ve_invoice` y `l10n_ve_sale`. Define el grupo de seguridad `l10n_ve_donation.group_donation_manager` (Donation Manager).

## Requirements

### Requirement: Cuenta de donación por compañía

Cada compañía (`res.company`) DEBE (MUST) poder definir una cuenta de donación en el campo `donation_account_id` (Many2one a `account.account`, con dominio restringido a cuentas de tipo `expense`), editable desde los ajustes generales (campo related `donation_account_id` en `res.config.settings` con `readonly=False`).

#### Scenario: Configuración desde ajustes

- **WHEN** un administrador selecciona una cuenta de gasto como "Donation Account" en ajustes y guarda
- **THEN** el campo `donation_account_id` de la compañía activa queda establecido a esa cuenta

### Requirement: Producto de donación único

El sistema DEBE (MUST) impedir, vía constraint sobre `is_donation_product` de `product.template`, que exista más de un producto marcado como producto de donación.

#### Scenario: Segundo producto de donación

- **WHEN** se marca `is_donation_product` en un producto y ya existe otro producto con `is_donation_product` activo
- **THEN** se lanza un error de validación indicando que ya existe un producto de donación

### Requirement: Almacén de donación único

El sistema DEBE (MUST) impedir, vía constraint sobre `is_donation_warehouse` de `stock.warehouse`, que exista más de un almacén marcado como almacén de donación.

#### Scenario: Segundo almacén de donación

- **WHEN** se marca `is_donation_warehouse` en un almacén y ya existe otro almacén con ese campo activo
- **THEN** se lanza un error de validación indicando que solo puede haber un almacén de donación

### Requirement: Tipo de operación de donación solo de salida

El sistema DEBE (MUST) impedir, vía constraint sobre `is_donation_picking_type` y `code` de `stock.picking.type`, que un tipo de operación marcado como de donación tenga un código distinto de `outgoing`.

#### Scenario: Tipo de operación de entrada marcado como donación

- **WHEN** se marca `is_donation_picking_type` en un tipo de operación cuyo `code` no es `outgoing`
- **THEN** se lanza un error de validación indicando que el tipo de operación de donación debe ser de salida

### Requirement: Partner de la compañía obligatorio en asientos de donación

El sistema DEBE (MUST) validar, vía constraint sobre `is_donation`, `line_ids` y `line_ids.partner_id` de `account.move`, que tanto el contacto del asiento (si está establecido) como el contacto de cada apunte que tenga contacto establecido de un movimiento marcado como donación sean el partner de la compañía (`company_id.partner_id`); los apuntes sin contacto no se validan.

#### Scenario: Contacto distinto al de la compañía

- **WHEN** un asiento con `is_donation` activo tiene como contacto (en el movimiento o en algún apunte) un partner distinto al partner de la compañía
- **THEN** se lanza un error de validación indicando el contacto esperado y el encontrado

### Requirement: Nota de crédito automática al publicar una factura de donación

Al publicar (`action_post`) una factura de cliente (`move_type = out_invoice`) con `is_donation` activo, el sistema DEBE (MUST) crear automáticamente su reversión mediante el asistente `account.move.reversal` con la fecha del día y el mismo diario, y publicar la nota de crédito resultante.

#### Scenario: Publicación de factura de donación

- **WHEN** se publica una factura de cliente marcada como donación
- **THEN** se crea y publica automáticamente una nota de crédito que revierte la factura, con fecha del día y el diario de la factura

### Requirement: Asignación del partner de la compañía en asientos manuales de donación

Al publicar (`action_post`) un asiento manual (`move_type = entry`) con `is_donation` activo, el sistema DEBE (MUST) escribir el partner de la compañía (`company_id.partner_id`) en todos sus apuntes (`line_ids`).

#### Scenario: Publicación de asiento de donación

- **WHEN** se publica un asiento manual marcado como donación
- **THEN** todos sus apuntes quedan con el partner de la compañía como contacto

### Requirement: Reversión de facturas de donación con el producto de donación agrupado por impuestos

La reversión (`_reverse_moves`) de un movimiento con `is_donation` activo y `move_type` distinto de `entry` DEBE (MUST) crear una nota de crédito (`out_refund`, también marcada `is_donation`) cuyas líneas usan el producto marcado `is_donation_product` y la cuenta `donation_account_id` de la compañía: una línea por cada combinación de impuestos de las líneas originales, con `price_unit` igual a la suma de las bases (`price_subtotal`) de ese grupo y los mismos impuestos. Si no existe producto de donación configurado o la compañía no tiene `donation_account_id`, DEBE (MUST) lanzar un error.

#### Scenario: Factura con dos grupos de impuestos

- **WHEN** se revierte una factura de donación cuyas líneas tienen dos combinaciones distintas de impuestos
- **THEN** la nota de crédito creada tiene dos líneas con el producto de donación, cada una con la suma de bases y los impuestos de su grupo, imputadas a la cuenta de donación

#### Scenario: Sin producto de donación configurado

- **WHEN** se revierte una factura de donación y no existe ningún producto con `is_donation_product` activo
- **THEN** se lanza un error pidiendo configurar el producto de donación

#### Scenario: Sin cuenta de donación configurada

- **WHEN** se revierte una factura de donación y la compañía no tiene `donation_account_id` establecida
- **THEN** se lanza un error pidiendo configurar la cuenta de donación

### Requirement: Excepción de cuenta por cobrar para la cuenta de donación

La validación de cuentas por cobrar/pagar de `account.move.line` (`_check_payable_receivable`) DEBE (MUST) aceptar, en documentos de venta marcados `is_donation`, que la línea de `display_type = payment_term` use la cuenta de donación de la compañía (`donation_account_id`) en lugar de una cuenta de tipo `asset_receivable`; el resto de las validaciones estándar (cuenta payable en ventas, cuenta receivable en compras, correspondencia entre `payment_term` y el tipo de cuenta) se mantienen.

#### Scenario: Línea de vencimiento con la cuenta de donación

- **WHEN** un documento de venta de donación tiene una línea `payment_term` con la cuenta `donation_account_id` de la compañía
- **THEN** la validación pasa sin error

#### Scenario: Cuenta de gasto arbitraria en línea de vencimiento

- **WHEN** un documento de venta (donación o no) tiene una línea `payment_term` con una cuenta que no es receivable ni la cuenta de donación
- **THEN** se lanza un error indicando que los apuntes en cuentas por cobrar deben tener fecha de vencimiento y viceversa

### Requirement: Pedido de venta de donación usa el partner de la compañía

Al marcar `is_donation` en un pedido de venta (`sale.order`), el sistema DEBE (MUST) establecer como cliente el partner de la compañía y el campo `document` en `invoice`, e impedir (onchange de `partner_id`) que se cambie el cliente a un partner distinto al de la compañía mientras el pedido sea una donación.

#### Scenario: Marcar pedido como donación

- **WHEN** un usuario activa `is_donation` en un pedido de venta
- **THEN** el cliente del pedido pasa a ser el partner de la compañía y el tipo de documento queda en `invoice`

#### Scenario: Cambio de cliente en un pedido de donación

- **WHEN** un usuario intenta cambiar el cliente de un pedido con `is_donation` activo a un partner distinto al de la compañía
- **THEN** se lanza un error indicando que el contacto/cliente no puede cambiarse en una donación

### Requirement: Inmutabilidad de la marca de donación en pedidos confirmados

El sistema DEBE (MUST) impedir, vía constraint sobre `is_donation` y `state` de `sale.order`, modificar el valor de `is_donation` en pedidos en estado `sale` o `done`.

#### Scenario: Cambio en pedido confirmado

- **WHEN** se intenta cambiar `is_donation` en un pedido ya confirmado
- **THEN** se lanza un error de validación indicando que el campo no puede modificarse en un pedido confirmado o completado

### Requirement: Propagación de la marca de donación a la factura

Las facturas generadas desde un pedido de venta (`_prepare_invoice`) DEBEN (MUST) heredar el valor de `is_donation` del pedido.

#### Scenario: Facturación de un pedido de donación

- **WHEN** se genera la factura de un pedido con `is_donation` activo
- **THEN** la factura se crea con `is_donation` activo

### Requirement: Ubicación de destino de las salidas por donación

En un `stock.scrap` con `is_donation` activo, el sistema DEBE (MUST) restringir la ubicación de destino (`scrap_location_id`) a ubicaciones de almacén de donación (dominio `is_donation_warehouse = True`, calculado en `scrap_location_domain`) y proponer por defecto la ubicación del almacén de donación de la compañía; las ubicaciones exponen el campo almacenado `is_donation_warehouse` calculado a partir de su almacén (`stock.warehouse`). Para scraps normales se mantiene el dominio nativo (`usage = inventory`).

#### Scenario: Scrap de donación

- **WHEN** se crea un scrap con `is_donation` activo en una compañía que tiene almacén de donación
- **THEN** la ubicación de destino se limita a ubicaciones del almacén de donación y se propone la de ese almacén por defecto

### Requirement: Procesamiento de salidas por donación sin reposición

Al validar (`do_scrap`) un `stock.scrap` con `is_donation` activo, el sistema DEBE (MUST) asignarle un nombre de la secuencia con código `stock.donation`, crear y ejecutar el movimiento de stock, marcar el scrap como `done` con la fecha actual, y omitir la reposición (`do_replenish`) aunque `should_replenish` esté activo. Los scraps sin la marca de donación siguen el flujo estándar.

#### Scenario: Validación de una donación de inventario

- **WHEN** se valida un scrap de donación
- **THEN** el scrap queda en estado `done`, con nombre tomado de la secuencia `stock.donation` y sin generar reposición

### Requirement: Asiento contable de donación por salida de inventario

El asiento contable generado (`_create_account_move` de `stock.move`) por movimientos ligados a un scrap con `is_donation` activo DEBE (MUST) crearse marcado con `is_donation = True`, con el partner de la compañía en el asiento y en cada apunte, en el diario de inventario de la compañía (`account_stock_journal_id`), con la referencia formada por los nombres de las etiquetas de motivo del scrap (`scrap_reason_tag_ids`), y publicarse automáticamente.

#### Scenario: Contabilización de una donación de inventario

- **WHEN** se valida un scrap de donación cuyo movimiento requiere asiento contable
- **THEN** se crea y publica un asiento con `is_donation` activo, partner de la compañía en todos los apuntes y referencia con los motivos de la donación

### Requirement: Reversión de asientos de donación restringida al grupo Donation Manager

El campo computado `can_reverse_donation_move` de `account.move` DEBE (MUST) ser verdadero solo cuando el usuario pertenece al grupo `l10n_ve_donation.group_donation_manager`; la vista de formulario oculta el botón de reversión de los asientos de donación a los usuarios sin ese grupo.

#### Scenario: Usuario sin el grupo

- **WHEN** un usuario que no pertenece a `l10n_ve_donation.group_donation_manager` abre un asiento de donación publicado
- **THEN** `can_reverse_donation_move` es falso y el botón de reversión no está disponible

### Requirement: Restablecer a borrador oculto en asientos de donación

La vista de formulario de `account.move` DEBE (MUST) ocultar el botón "Restablecer a borrador" (`button_draft`) cuando el movimiento está marcado `is_donation`, cuando es una factura o nota de crédito de cliente (`move_type` en `out_invoice` / `out_refund`) o cuando ya está en borrador; el campo `is_donation` solo es editable en asientos manuales (`move_type = entry`) en estado borrador.

#### Scenario: Asiento de donación publicado

- **WHEN** un usuario abre un asiento de donación publicado
- **THEN** el botón "Restablecer a borrador" no está disponible y el campo `is_donation` es de solo lectura

### Requirement: Certificado de donación en PDF

El sistema DEBE (MUST) permitir generar el reporte qweb-pdf "Donation Certificate" (`l10n_ve_donation.action_donation_certificate_account_move`) desde el botón `print_donation_certificate` de `account.move`, disponible únicamente en asientos manuales (`move_type = entry`) publicados y marcados `is_donation`.

#### Scenario: Impresión del certificado

- **WHEN** un usuario pulsa "Generar Certificado de Donación" en un asiento de donación publicado
- **THEN** se genera el PDF del certificado de donación de ese asiento
