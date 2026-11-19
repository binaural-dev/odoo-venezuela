## Why

`compute_rate` busca la tasa SOLO en la fecha exacta del documento y, si no la encuentra, lanza un `UserError` (ticket 15923). Esa regla es correcta para facturas y pagos, pero bloquea operaciones que no son documentos fiscales cuando su fecha cae en un día sin tasa cargada (fin de semana, feriado o fecha futura): asientos de valoración de inventario, extractos bancarios, depreciaciones de activos y cualquier asiento manual (ticket #16384).

Para esos asientos basta con usar la última tasa publicada antes de su fecha; para facturas, notas y pagos se mantiene la tasa exacta, que tiene efecto fiscal.

## What Changes

- `l10n_ve_rate`: `res.currency.rate.compute_rate` recibe el parámetro `use_last_rate` (por defecto `False`, comportamiento exacto sin cambios). Con `True`, si no hay tasa de la fecha exacta usa la de mayor `name <= rate_date` de la moneda, recorriendo las compañías en el mismo orden (activa y luego raíz). Nunca usa una tasa posterior; sin ninguna tasa anterior mantiene el `UserError` (o `{}` con `raise_if_not_found=False`). Versión 19.0.1.3.0 -> 19.0.1.4.0.
- `l10n_ve_accountant`: nuevo hook `account.move._is_exact_rate_required()`. Es `True` para facturas, notas de crédito/débito y recibos (`is_invoice(include_receipts=True)`) y para asientos con `origin_payment_id`; `False` para el resto de asientos `entry`, incluidos los de diferencia cambiaria (`l10n_ve_exchange_foreign_diff_entry`), cuyas líneas no usan la tasa de cabecera (`_skip_foreign_compute`), así que un reverso o una conciliación en un día sin tasa no debe fallar.
- `_compute_rate_for_documents` llama a `compute_rate` con la compañía del movimiento (`with_company(move.company_id)`) y `use_last_rate=not move._is_exact_rate_required()`. La tasa resultante queda fija desde que se guarda el asiento: no se recalcula si luego se carga la tasa del día.
- `account.move.create()` solo consulta la tasa del día cuando el movimiento tiene tasa manual (`manually_set_rate`), y solo para decidir si publica el mensaje de chatter de tasa distinta. La consulta ya no lanza: si no hay tasa de referencia, no publica el mensaje.
- Versión `l10n_ve_accountant` 19.0.1.0.44 -> 19.0.1.0.45.

## Impact

- Specs afectadas: `l10n_ve_rate` (se MODIFICA «Cálculo de tasa y tasa inversa por fecha») y `l10n_ve_accountant` (se MODIFICA «Cálculo automático de la tasa según la fecha del documento»).
- Código: `l10n_ve_rate/models/res_currency_rate.py`, `l10n_ve_accountant/models/account_move.py` (`create`, `_is_exact_rate_required`, `_compute_rate_for_documents`) y los manifiestos de ambos módulos.
- Los asientos de stock/valoración y los asientos de extractos bancarios dejan de bloquearse por falta de tasa en la fecha: usan la última tasa anterior. (Se verificó con asientos `entry` genéricos; no se probó el flujo de stock ni el de extractos de punta a punta.)
- Cambio de comportamiento: una factura o un asiento con tasa manual en una fecha sin tasa YA NO lanza `UserError` al crearse (antes lanzaba aunque la tasa del día no se usara, `create` la consultaba siempre). Esto afecta al cierre de ejercicio, al PdV y a las facturas con tasa manual. Las facturas sin tasa manual siguen exigiendo la tasa exacta de su fecha.
- Tasa fija al guardar: la tasa de un asiento con fecha futura o de fin de semana queda fija con la última tasa anterior; no se actualiza al cargarse después la tasa de su fecha.
- Diferencia cambiaria no exacta por diseño: sus asientos usan la última tasa anterior aunque no exista la de su fecha.
- Pagos fuera de alcance: los asientos de pago (`origin_payment_id`) siguen exigiendo la tasa exacta.
- Multicompañía: la tasa se busca en la compañía del movimiento (`move.company_id`) y su raíz, no en la compañía activa de la sesión.
- Sin ninguna tasa anterior a la fecha el comportamiento no cambia: `UserError` «There is no rate assigned».
- `compute_rate` conserva su firma compatible: los llamadores existentes no cambian.
