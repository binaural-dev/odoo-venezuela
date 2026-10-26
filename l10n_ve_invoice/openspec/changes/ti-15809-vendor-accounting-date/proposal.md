# Fix: fecha contable de facturas de proveedor no menor a la fecha de la factura

## Why

Ticket Helpdesk #15809 (https://binaural.odoo.com/odoo/helpdesk/action-389/15809).
Era posible guardar una factura de proveedor con fecha contable anterior a la fecha de la factura.

## What Changes

- La constraint `_check_invoice_date_display_purchases` ya existía, pero dependía de
  `res.company.block_invoice_display_date_upper_than_date`, que venía apagada (sin `default`).
- La configuración ahora es `default=True` y la migración `19.0.1.0.25` la enciende en las
  compañías existentes.
- Se elimina el `_logger.warning` que la constraint emitía en cada validación.

## Decisiones

- **La configuración se conserva y debe estar siempre encendida.** Apagarla queda a criterio del
  consultor para ajustes o casos puntuales; no es un modo de operación normal.
- Aplica a todo documento de compra (facturas, notas y recibos); las ventas no se tocan.

## Tests

`l10n_ve_invoice/tests/test_vendor_accounting_date.py` y `test_account_move_extended.py`
(`_check_invoice_date_display_purchases`).
