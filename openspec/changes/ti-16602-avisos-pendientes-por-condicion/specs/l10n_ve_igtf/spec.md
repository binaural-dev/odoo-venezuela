## ADDED Requirements

### Requirement: Un aviso de pendientes por tipo de documento

El formulario de `account.move` DEBE (MUST) mostrar, en la parte superior de un documento publicado con estado de pago `not_paid` o `partial` e `invoice_has_outstanding`, un único aviso de pendientes. Ese aviso es el de IGTF: enlaza a créditos o débitos pendientes, a anticipos, o a ambos, según qué widget tenga contenido (`invoice_outstanding_credits_debits_widget` / `invoice_outstanding_credits_debits_widget_advance_payment`). Aplica a `out_invoice`/`out_receipt` (créditos, cliente), `in_invoice`/`in_receipt` (débitos, proveedor), `out_refund` (débitos, cliente) e `in_refund` (créditos, proveedor). El aviso estándar de Odoo NO DEBE (MUST NOT) mostrarse junto al de IGTF.

#### Scenario: Factura de proveedor con débitos pendientes

- **WHEN** se abre una factura de proveedor publicada, no pagada, cuyo proveedor tiene débitos pendientes
- **THEN** se ve un solo aviso "outstanding debits … for this vendor", con el enlace a los pendientes

#### Scenario: Nota de crédito de cliente con anticipos

- **WHEN** se abre una nota de crédito de cliente publicada, no pagada, con anticipos del cliente disponibles
- **THEN** se ve el aviso de IGTF con el enlace a anticipos, no el estándar

#### Scenario: Nota de crédito de proveedor con créditos pendientes

- **WHEN** se abre una nota de crédito de proveedor publicada, no pagada, con créditos pendientes
- **THEN** se ve un solo aviso "outstanding credits … for this vendor"

### Requirement: Los avisos de otros módulos se conservan

Los avisos `alert-info` que otros módulos agregan en la parte superior del formulario de `account.move` (por ejemplo, los de tasa tomada de la orden de `binaural_purchase` y `l10n_ve_sale`) DEBEN (MUST) seguir visibles, y su presencia NO DEBE (MUST NOT) cambiar qué aviso de pendientes reemplaza IGTF, sin importar el orden en que se apliquen las vistas.

#### Scenario: Factura de proveedor creada desde una orden de compra con su tasa

- **WHEN** se abre una factura de proveedor publicada, creada desde una orden de compra que fija la tasa, y el proveedor tiene débitos pendientes
- **THEN** se ven el aviso de tasa de la orden de compra y un único aviso de pendientes

#### Scenario: Módulo que agrega un aviso antes que IGTF

- **WHEN** un módulo agrega un `alert-info` después del encabezado y su vista se aplica antes que la de IGTF
- **THEN** su aviso sigue en el formulario y cada tipo de documento conserva un único aviso de pendientes de IGTF
