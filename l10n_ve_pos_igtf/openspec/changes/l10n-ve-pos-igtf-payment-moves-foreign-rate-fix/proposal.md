## Why

`pos_payment.py::_create_payment_moves` en `l10n_ve_pos_igtf` reimplementa el
método completo sin llamar a `super()`, así que nunca pasa por
`l10n_ve_pos/models/pos_payment.py::_create_payment_moves`, que es quien
escribe `foreign_rate`, `foreign_inverse_rate` y `manually_set_rate=True` en
el asiento de pago (usando `payment.foreign_rate`, la tasa capturada en el
frontend al momento del pago).

Como `manually_set_rate` queda en `False`, el `create()` de
`l10n_ve_accountant/models/account_move.py` dispara automáticamente
`_compute_rate()` → `_compute_rate_for_documents()`, que al ver
`manually_set_rate=False` sobreescribe `foreign_rate`/`foreign_inverse_rate`
con la tasa del día de creación del asiento, en vez de la tasa realmente
pactada en el pago. En un país con tasa de cambio volátil, esto descuadra la
tasa registrada en los asientos de pago de pedidos POS con IGTF.

Detectado durante una revisión de código de la rama
`19.0_mig-ta_76667_full_refund_v17_to_v19` (2026-07-29).

## What Changes

- `pos_payment.py::_create_payment_moves`: tras crear y postear
  `payment_move` para cada pago, se añade el mismo `write()` que hace
  `l10n_ve_pos` (`foreign_rate`, `foreign_inverse_rate` = `payment.foreign_rate`,
  `manually_set_rate = True`). No se toca el resto del método — la creación
  de líneas específicas de IGTF (split hacia `customer_account_igtf_id`,
  `foreign_debit`/`foreign_credit` con `not_foreign_recalculate: True`) se
  mantiene igual, ya era correcta.
- No se cambia a llamar `super()` porque la estructura de líneas de IGTF
  (línea de crédito adicional para el split, montos calculados aparte) es
  incompatible con la de `l10n_ve_pos`/core sin una reescritura mayor; el fix
  puntual cierra el hueco real (header del asiento) sin ese riesgo.

## Capabilities

### Modified Capabilities

- `backend-payment-moves`: `_create_payment_moves` ahora preserva la tasa
  pactada en el pago (`foreign_rate`/`foreign_inverse_rate`/`manually_set_rate`)
  en vez de dejar que se sobreescriba con la tasa del día.

## Impact

- Módulo: `l10n_ve_pos_igtf` (backend).
- Archivo: `models/pos_payment.py`.
- Sin cambios de frontend ni de otros módulos.
