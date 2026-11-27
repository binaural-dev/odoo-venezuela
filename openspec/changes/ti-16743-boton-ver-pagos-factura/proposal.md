## Why

En el popover de pagos de la factura («Información sobre el asiento contable») solo aparecía «Romper conciliación»; faltaba el botón nativo **Ver**, que abre el pago.

Causa: `l10n_ve_igtf` sobrescribía `_compute_payments_widget_reconciled_info` con una copia completa del diccionario de `account`, sin llamar a `super()`. La copia no traía `can_open_move`, y la plantilla `account.AccountPaymentField` muestra Ver solo con `t-if="props.can_open_move"`. Evidencia: en el staging el JSON de `invoice_payments_widget` traía `is_retention` (de `l10n_ve_payment_extension`) pero no `can_open_move`.

## What Changes

- `_compute_payments_widget_reconciled_info` de `account.move` llama a `super()` y, después, aplica lo único propio del módulo: solo las facturas publicadas muestran pagos conciliados (`invoice_payments_widget = False` en el resto). Se elimina la copia del diccionario; `account` aporta todas las llaves (incluida `can_open_move`) y `l10n_ve_payment_extension` sigue agregando `is_retention`.
- Pruebas: `test_igtf_payments_widget_open_move.py` (el pago conciliado trae `can_open_move`; una factura en borrador no trae widget).
- Versión de `l10n_ve_igtf`: 19.0.1.2.25.

## Impact

- **Specs afectadas**: `l10n_ve_igtf` (widget de pagos conciliados de la factura).
- **Código**: `l10n_ve_igtf/models/account_move.py`. Sin migración, vistas ni textos nuevos.
- **Qué ve el usuario**: el botón Ver vuelve a aparecer junto a «Romper conciliación» y abre el pago.
- **Lo que no cambia**: contenido del widget, `is_retention`, la regla de mostrarlo solo en facturas publicadas.
- **Mantenimiento**: al no copiar el diccionario, las llaves nuevas de `account` llegan sin tocar el módulo.
