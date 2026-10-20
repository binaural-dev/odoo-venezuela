## Why

Desde la vista de pagos (`account.payment`) era posible confirmar un pago con importe 0.0, generando un asiento contable vacío sin sentido fiscal. (Ticket #15703.)

## What Changes

- `l10n_ve_accountant`: `account.payment.action_post()` lanza `UserError` si algún pago del conjunto tiene importe cero (comparado con la precisión de la moneda del pago, `currency_id.is_zero`). La validación corre antes de `super()`, así que el pago queda en borrador.
- Traducción es_VE del mensaje.
- Bump de manifest `l10n_ve_accountant` 19.0.1.0.33 → 19.0.1.0.34.

## Impact

- Specs afectadas: `l10n_ve_accountant` (nueva requirement).
- Código: `l10n_ve_accountant/models/account_payment.py`, `l10n_ve_accountant/i18n/es_VE.po`.
- Aplica a toda confirmación vía `action_post` (vista de pagos y wizard de registrar pago).
