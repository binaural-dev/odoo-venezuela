# Fix: pos.payment.foreign_amount se computa para TODO método de pago, no solo is_foreign_currency (l10n_ve_pos)

## Why

Rastreando el bug de asientos con `foreign_debit`/`foreign_credit` en 0
encontrado en las sesiones Binaural C.A/00043 y /00044 (ver
`openspec/changes/l10n-ve-pos-session-close-cash-foreign-amount-fix`, que
arregló un bug de escritura distinto en `set_foreign_amount_in_line`), se
llegó a la causa de fondo en la sesión 00044: el pago "Efectivo Bs" que
salda el recargo IGTF de una factura tenía `foreign_amount = 0.00` en el
propio `pos.payment`, mientras que su equivalente correcto (0.64) ya
existía en un campo hermano (`foreign_igtf_amount` del pago que generó el
IGTF) — el valor nunca se copiaba porque **nunca se calculaba** para ese
pago.

Esto ya estaba documentado como pendiente desde el 2026-07-10 en
`openspec/migration-lessons.md` ("Pendientes por tratar"): Jesús había
notado que `_recomputeForeignFromLocal`
(`static/src/overrides/models/payment_model.js`) fija `foreign_amount = 0`
para cualquier pago cuyo método NO sea `is_foreign_currency` — es decir,
para todo pago en Bs, sea "Efectivo Bs" o cualquier otro método local. La
nota advertía que esto no es solo visual: se propaga a todos los
consumidores de `pos.payment.foreign_amount`.

Un agente de exploración (2026-07-21) mapeó exhaustivamente esos
consumidores y encontró uno grande que la nota original no listaba:
**`models/pos_session.py`**, el cierre de sesión completo
(`_accumulate_amounts`, `_create_bank_payment_moves`,
`_create_split_account_payment`, `_create_combine_account_payment`,
`_create_invoice_receivable_lines`,
`_create_cash_statement_lines_and_cash_move_lines`) — ninguno de estos
métodos filtra por `is_foreign_currency`, así que con `foreign_amount = 0`
en el pago, TODAS las líneas de recibo de cierre de sesión para métodos
locales quedaban en `foreign_debit`/`foreign_credit = 0`. Este es el
mecanismo real detrás de los casos observados, no solo el bug puntual de
`set_foreign_amount_in_line` ya corregido.

## What Changes

- `static/src/overrides/models/payment_model.js`, método
  `_recomputeForeignFromLocal`: ya no filtra por `is_foreign_currency`.
  Siempre calcula `order.localToForeign(this.amount || 0)` — un pago en
  Bs pasa a llevar su equivalente en USD igual que cualquier otra línea
  contable (producto, impuesto), en vez de un 0 forzado.
- Se elimina `_isForeignMethod()` (quedó sin uso; era el único punto que
  la llamaba).
- `static/tests/unit/payment_model.test.js`: nuevo `describe` para
  `_recomputeForeignFromLocal`, cubriendo método local (antes 0, ahora
  calculado), método foráneo (sin cambio de comportamiento) y el caso sin
  orden/sin helper de conversión (sigue cayendo a 0).

## Impact

- **Capability**: `pos-payment-foreign-amount` (nueva).
- **Módulo**: `l10n_ve_pos`, frontend
  (`static/src/overrides/models/payment_model.js`). Requiere regenerar
  assets del PdV (JS), no requiere `-u` del módulo.
- **Auditoría de consumidores** (agente Explore, sin cambios de código en
  ellos — todos empiezan a recibir el valor correcto automáticamente):
  - `models/pos_payment.py::_create_payment_moves` y el equivalente de
    `l10n_ve_pos_igtf` — asignación directa a `foreign_debit`/
    `foreign_credit`, sin resta/división que asuma 0.
  - `models/pos_session.py` (el consumidor grande, ver arriba) — mismo
    patrón, asignación directa por línea ya identificada por importe.
  - `report/report_saledetails.py` y `report/payment_report_pos.py` —
    `sum(foreign_amount)` simple, sin doble conteo.
  - Frontend `pos_order.js::get_foreign_total_paid()` y
    `get_foreign_amount()` (usado en `payment_line.xml`) — ya desacoplados
    de `remainingDue`/change desde el 2026-07-09, solo mejoran la cifra
    mostrada.
  - **Bug latente que este cambio arregla de paso**: en
    `l10n_ve_pos_igtf/pos_payment.py::_create_payment_moves`, un método
    local con `apply_igtf=True` calculaba mal `amount_without_igtf`
    (`payment.foreign_amount - payment.foreign_igtf_amount`) porque el
    primer término era 0 y el segundo no — ambos campos son
    independientes. Con el fix, la resta da el resultado correcto.
- **Tests**: ningún test existente (Python ni JS) depende de la
  invariante "método local → `foreign_amount == 0`" — confirmado por el
  agente de exploración leyendo `test_pos_session_accounting_common.py`
  (los fixtures de test fijan `foreign_amount` directamente, sin pasar
  por esta lógica JS) y ambos `static/tests/unit/*.test.js`. No se espera
  ninguna regresión de test por este cambio.
- **Riesgo de despliegue**: bajo-medio — a diferencia del fix anterior
  (acotado a una función backend), este toca el modelo de pago que usan
  TODOS los métodos de pago del PdV. Mitigado por: (a) la auditoría
  exhaustiva de consumidores de arriba, (b) ningún consumidor hace
  aritmética que dependa de 0, (c) test nuevo de regresión.
- **Fuera de alcance (pendiente, no corregido en este change)**:
  - Data-fix de los asientos YA generados con `foreign_debit`/
    `foreign_credit = 0` en las sesiones 00043 y 00044 (y cualquier otra
    sesión cerrada antes de este fix con pagos en métodos locales).
  - El test `test_create_cash_statement_lines_writes_foreign_fields_on_cash_receivable`
    (Slice C2.3) seguía skippeado antes de este change y sigue igual.
