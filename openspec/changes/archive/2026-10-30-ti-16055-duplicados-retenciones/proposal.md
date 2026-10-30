## Why

Una factura consolidada en una retención y presente a la vez en su retención individual en borrador podía emitirse dos veces (ticket #16055, reincidencia de #15531), y los botones de retenciones de la factura podían abrir el formulario de otro tipo de retención.

## What Changes

- `l10n_ve_payment_extension`: se mantiene la regla ya documentada de `_check_duplicate_invoices_all_states` (bloquea solo con misma factura, tipo, partner y diferenciador). Un diferenciador vacío (alícuota 0, sin concepto o sin actividad) es un valor más y no actúa como comodín: una retención de IVA con alícuota 0 no existe, porque no hay IVA que retener.
- `account.move.action_view_retention`: pasa las vistas explícitas del tipo (formulario y lista) y un tipo desconocido no devuelve acción.
- Specs: escenario «Diferenciador vacío no actúa como comodín» y requisito de los botones de retenciones de la factura.

## Impact

- Specs afectadas: `l10n_ve_payment_extension`.
- Código: `l10n_ve_payment_extension/models/account_move.py`, tests de duplicados y de `action_view_retention`.
