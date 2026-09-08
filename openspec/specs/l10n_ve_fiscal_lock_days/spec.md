# l10n_ve_fiscal_lock_days

## Purpose

Restringe la creación y publicación de facturas de cliente cuando el período fiscal anterior (quincena o mes) no ha sido bloqueado con la fecha de bloqueo de impuestos, y valida el asistente de cambio de fecha de bloqueo contra pedidos pendientes de facturar. Extiende `account.move`, `account.change.lock.date`, `res.company` y `res.config.settings`. Depende de `base`, `account_accountant` y `l10n_ve_accountant`; agrega su configuración al bloque "Fiscal Configuration" de la vista de ajustes de `l10n_ve_base`.

## Requirements

### Requirement: Configuración del período fiscal y de la validación de bloqueo

Cada compañía (`res.company`) DEBE (MUST) poder configurar el período fiscal `tax_period` (selección `fortnightly` / `monthly`) y activar la validación `lock_date_tax_validation` desde los ajustes generales (campos related en `res.config.settings` con `readonly=False`).

#### Scenario: Activación desde ajustes

- **WHEN** un administrador selecciona un período fiscal y activa "Validation to Block Invoice Creation" en ajustes y guarda
- **THEN** los campos `tax_period` y `lock_date_tax_validation` de la compañía activa quedan establecidos

### Requirement: Bloqueo de facturas de venta con período fiscal anterior sin cerrar

Con `lock_date_tax_validation` activo, el sistema DEBE (MUST) impedir crear y publicar (`create` y `action_post` de `account.move`) facturas y notas de crédito de cliente (`move_type` en `out_invoice` / `out_refund`) cuando la fecha de bloqueo de impuestos de la compañía (`tax_lock_date`) está establecida y no coincide con el último día del período anterior según `tax_period`: para `fortnightly`, el día 15 del mes en curso si hoy es posterior al 15, o el último día del mes anterior en caso contrario; para `monthly`, el último día del mes anterior. Si `tax_lock_date` no está establecida, la validación no bloquea.

#### Scenario: Creación con período anterior sin bloquear

- **WHEN** con la validación activa se intenta crear una factura de cliente y `tax_lock_date` está establecida pero no es el último día del período fiscal anterior
- **THEN** se lanza un error indicando que debe bloquearse la quincena o mes anterior antes de crear o publicar facturas en un nuevo período fiscal

#### Scenario: Publicación con el período anterior bloqueado

- **WHEN** con la validación activa se publica una factura de cliente y `tax_lock_date` es exactamente el último día del período fiscal anterior
- **THEN** la factura se publica normalmente

#### Scenario: Documentos que no son de venta

- **WHEN** con la validación activa se crea un asiento cuyo `move_type` no es `out_invoice` ni `out_refund`
- **THEN** la validación no se aplica y el asiento se crea normalmente

### Requirement: Bloqueo de la fecha de impuestos con pedidos pendientes de facturar

El asistente `account.change.lock.date` DEBE (MUST) impedir establecer la fecha de bloqueo de impuestos (`tax_lock_date`) cuando existen pedidos de venta (`sale.order`) con `invoice_status = "to invoice"` cuya fecha de pedido (`date_order`) es anterior o igual a esa fecha.

#### Scenario: Pedidos por facturar anteriores a la fecha

- **WHEN** se cambia la fecha de bloqueo de impuestos y existe al menos un pedido por facturar con fecha de pedido anterior o igual a la fecha elegida
- **THEN** se lanza un error de validación indicando que no puede establecerse la fecha de bloqueo por existir pedidos en estado "Para facturar" anteriores

#### Scenario: Sin pedidos pendientes

- **WHEN** se cambia la fecha de bloqueo de impuestos y no existen pedidos por facturar anteriores o iguales a esa fecha
- **THEN** el cambio de fecha de bloqueo se aplica normalmente
