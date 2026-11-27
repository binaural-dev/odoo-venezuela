## ADDED Requirements

### Requirement: Widget de pagos conciliados de la factura

`_compute_payments_widget_reconciled_info` de `account.move` DEBE (MUST) llamar a `super()` para que `account` arme el widget completo (incluida la llave `can_open_move`, que decide si el popover muestra el botón nativo **Ver**) y los módulos encadenados (`l10n_ve_payment_extension`, con `is_retention`) lo sigan extendiendo. Después DEBE (MUST) dejar `invoice_payments_widget` en falso en toda factura que no esté publicada. El módulo NO DEBE (MUST NOT) copiar el diccionario del widget. (Antes: se reescribía el diccionario completo sin `super()` y sin `can_open_move`, por lo que el botón Ver no aparecía.)

#### Scenario: Pago conciliado en factura publicada

- **WHEN** una factura publicada tiene un pago conciliado
- **THEN** cada línea de `invoice_payments_widget['content']` trae `can_open_move` verdadero y el popover muestra Ver junto a «Romper conciliación»

#### Scenario: Factura en borrador

- **WHEN** la factura no está publicada
- **THEN** `invoice_payments_widget` es falso
