## Why

Una factura consolidada en una retención y presente a la vez en su retención individual en borrador podía emitirse dos veces (ticket #16055, reincidencia de #15531): una línea de IVA con alícuota 0 (p. ej. agregada con "Agregar una línea") se omitía de los chequeos de duplicados. Además, los botones de retenciones de la factura podían abrir el formulario de otro tipo de retención.

## What Changes

- `l10n_ve_payment_extension`: se mantiene la regla ya documentada de `_check_duplicate_invoices_all_states` (bloquea solo con misma factura, tipo, partner y diferenciador). Un diferenciador vacío es un valor más y no actúa como comodín.
- `account.retention.line`: las líneas de IVA con alícuota 0 no se crean desde el formulario (no existe retención de IVA con alícuota 0, no hay IVA que retener). `_onchange_move_id` limpia la factura sin IVA y `_onchange_aliquot` vuelve a la alícuota de la factura si el usuario escribe 0.
- `account.move.action_view_retention`: pasa las vistas explícitas del tipo (formulario y lista) y un tipo desconocido no devuelve acción.
- Specs: escenarios «Diferenciador vacío no actúa como comodín» y «Línea de IVA con alícuota 0», y requisito de los botones de retenciones de la factura.

## Impact

- Specs afectadas: `l10n_ve_payment_extension`.
- Código: `l10n_ve_payment_extension/models/account_retention_line.py`, `l10n_ve_payment_extension/models/account_move.py`, vista ISLR, tests de duplicados y de `action_view_retention`.
