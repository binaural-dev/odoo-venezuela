## Why

`res.currency.rate.compute_rate` devolvía un diccionario vacío cuando no encontraba tasa, y los llamadores lo convertían en una tasa `0` silenciosa. Se pidió que toda búsqueda sin resultado detenga la operación con un error claro de que no hay tasa asignada. (Ticket #15923.)

## What Changes

- `l10n_ve_rate`: `compute_rate` usa `raise_if_not_found=True` por defecto y lanza `UserError` con la moneda y la fecha («No hay una tasa asignada para USD al ...»). `raise_if_not_found=False` conserva el comportamiento silencioso.
- Excepciones que no son una tasa faltante: la moneda principal de la compañía sin registro de tasa devuelve `1.0/1.0` (su tasa contra sí misma), y sin moneda alterna (`foreign_currency_id` vacío) devuelve `{}` porque no hay moneda que buscar.
- `compute_inverse_rate` lanza `UserError` si la tasa es `0`, `None` o `False`.
- Traducción es_VE de los mensajes y bump de manifest `l10n_ve_rate` 1.3 → 1.4.
- Tests de `l10n_ve_accountant` que dependían de la tasa silenciosa (`test_indexed_payments`, `test_account_journal_bank_account`) ahora cargan la tasa de USD que necesitan.

## Impact

- Specs afectadas: `l10n_ve_rate` (cálculo de tasa, sucursales, inversión de tasa) y `l10n_ve_sale` (defaults de la orden y confirmación).
- Riesgo funcional: con el error activo, crear una orden de venta, preparar una factura o registrar un pago un día sin tasa cargada falla. Es la decisión pedida; antes se había revertido (commits `ddc4438ec`, `e9b8ffdf8`, tarea 80063) por bloquear esas operaciones.
- Código: `l10n_ve_rate/models/res_currency_rate.py`, `l10n_ve_rate/i18n/es_VE.po`, `l10n_ve_rate/__manifest__.py`.
