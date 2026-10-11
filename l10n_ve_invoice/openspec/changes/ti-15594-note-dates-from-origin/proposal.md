# Fix: NC y ND respetan la fecha de su factura origen

## Why

Ticket Helpdesk #15594 (https://binaural.odoo.com/odoo/helpdesk/action-389/15594).
Era posible confirmar una NC o ND con fecha anterior a la de la factura origen.

## Regla

La nota (NC o ND) es la misma transacción que su origen:

- `invoice_date` (fecha de tasa): siempre igual a la del origen (solo lectura en el formulario de la nota).
- `invoice_date_display` (fecha del documento): editable, por defecto hoy (`context_today`),
  nunca anterior a la fecha del origen ni posterior a hoy.
- Una sola factura por nota.

## What Changes

- `account.debit.note` (`models/account_debit_note.py`): `_prepare_default_values` toma
  `invoice_date_display` del wizard e `invoice_date` del origen; `create_debit` valida
  `_l10n_ve_check_note_date`; `default_get` y `create_debit` rechazan más de un documento.
- `account.move._check_dates_not_in_future` (en `action_post`): una nota con
  `invoice_date_display` anterior al origen no se confirma (cubre ediciones posteriores
  a la creación desde el formulario).
- La fecha del wizard queda editable (sin vista que la bloquee).
- La fecha de la ND de IGTF no cambia (hoy); su exención del guard de fecha futura
  (`l10n_ve_skip_future_date_check` + `_l10n_ve_allows_future_date`) aplica solo a notas automáticas.
- La NC se resuelve en `l10n_ve_accountant` (change homónimo).

## Non-goals

- `l10n_ve_out_of_fiscal_period_warning` se conserva sin cambios.


## Decisiones

- **15594 viaja junto con 15450.** Ambos tickets cambian las mismas fechas de las notas
  (`invoice_date`, `invoice_date_display`) y el mismo guard de `action_post`. Separarlos obliga a
  mergear dos PRs que se pisan y a rehacer a mano las correcciones del otro; por eso se mantienen en
  esta rama.
- **El guard vive solo en `action_post`.** No se limita la creación ni se bloquea `_post`: la UI
  confirma por `action_post` y los llamadores directos a `_post` (asistente "Confirm Entries" con
  `force_post`, procesos internos, cron) lo hacen de forma intencional.
- **`invoice_date <= invoice_date_display` siempre**, también en compras.
- **La exención del guard es solo para notas automáticas** (diferencial cambiario e IGTF) y exige
  contexto + marca del documento (`_l10n_ve_allows_future_date`). Esas marcas no están en formularios
  ni en `onchange`.
- **La fecha de la ND de IGTF no cambia** (hoy; su cálculo es en VEF).
- **Combos:** exentos de la regla de un solo impuesto en `l10n_ve_stock`, como en `l10n_ve_accountant`
  y el núcleo de Odoo 19 (oculta y vacía sus impuestos; viven en las líneas de los componentes).

## Pendientes conocidos (fuera de este PR)

- Los tests de `l10n_ve_invoice_digital` (`TestAccountMoveApiCalls`, `TestAccumulatedRate`,
  `TestStockPickingApiCalls`) fallan en `setUp` desde la migración a Odoo 19, antes de llegar a
  cualquier fecha: `account.account` sin `company_id`/`deprecated`, diario bancario sin cuentas en sus
  métodos de pago, impuestos sin `tax_group_id`/`country_id`, producto sin impuesto de compra, país
  fiscal y `account_move_line_check_accountable_required_fields`. Requieren un ticket propio. En este
  PR solo se cambió `Date.today()` por `context_today` en esos tests.
- `_post(soft=False)` desde "Confirm Entries" (`force_post`) no pasa por el guard (ver Decisiones).
- Verificación manual 3.1 del ticket con la vertical.
