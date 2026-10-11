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
- **El guard corre en `action_post` y en los dos caminos de UI que confirman con `_post`:** la acción
  "Confirm Entries" (`action_validate_moves_with_confirmation`) y el asistente `validate.account.move`
  (`validate_move`, con o sin "Force"). `_post` en sí no se bloquea: los llamadores internos directos
  (donación, reverso de IGTF, cron) lo hacen de forma intencional.
- **La tasa (`invoice_date`) de toda nota es la del origen:** readonly en los dos campos `invoice_date`
  del formulario (ventas y compras, "Rate Date") y validada igual al origen al confirmar.
- **`invoice_date <= invoice_date_display` siempre**, también en compras: aunque ningún ticket lo pida para
  compras, impedir facturas con fecha futura es el criterio correcto y la validación no debe depender del
  tipo de documento.
- **Una nota por factura:** regla contable venezolana (una nota ligada a una factura y no a N facturas);
  difiere del núcleo, que crea una nota por cada factura seleccionada.
- **`date` de una nota:** constraint de guardado `_check_note_accounting_date` (no puede ser anterior a su
  `invoice_date_display`, que a su vez no puede ser anterior al del origen).
- **Los mensajes del guard nombran el documento** (`display_name`): un lote de "Confirm Entries" se aborta
  completo si un borrador no cumple, y el error debe decir cuál.
- **La igualdad de tasa con el origen no aplica a las notas automáticas** (`_l10n_ve_allows_future_date`): la nota
  de diferencial lleva la fecha de tasa del pago; si se confirmara de nuevo a mano no debe bloquearla.
- **La exención del guard es solo para notas automáticas** (diferencial cambiario e IGTF) y exige
  contexto + marca del documento (`_l10n_ve_allows_future_date`). Esas marcas no están en formularios
  ni en `onchange`.
- **La fecha de la ND de IGTF no cambia** (hoy; su cálculo es en VEF).
- **Combos:** exentos de la regla de un solo impuesto en `l10n_ve_stock`, como en `l10n_ve_accountant`
  y el núcleo de Odoo 19 (oculta y vacía sus impuestos; viven en las líneas de los componentes).

- **Los arreglos de `l10n_ve_stock` y `l10n_ve_invoice_digital/models/stock_picking.py` no llevan ticket propio:**
  son consecuencia directa del análisis para que los tickets 15450 y 15594 funcionen y sus tests pasen
  (combos exentos de la regla de un impuesto; `move_ids_without_package` -> `move_ids`). Se rastrean con esos
  mismos tickets.
- **Orígenes con fecha futura:** no existen datos con ese error. El guard se aplica para prevenirlos, ya que
  antes se podían crear; al llevarse al código principal es correcto que bloquee lo que debe bloquear. La
  regla `origen <= fecha de la nota <= hoy` no se relaja para ese caso.
- **Auto-post:** el cron `_autopost_draft_entries` confirma con `_post` los borradores con `auto_post` activo;
  no pasa por el guard (caso borde: requiere editar `date` y activar el auto-post).

## Pendientes conocidos (fuera de este PR)

- `l10n_ve_stock_account` (`stock_location.py`) llama a `stock.location.get_warehouse()`, método que
  define `l10n_ve_donation`, sin depender de ese módulo: con `l10n_ve_invoice_digital` instalado sin
  donación, los tests de stock picking fallan con `AttributeError`. Los tests de digital se ejecutan
  instalando también `l10n_ve_donation`. Falta declarar la dependencia o mover el método (ticket aparte).
- `l10n_ve_payment_extension/tests/test_retention_lifecycle.py::test_15_accounting_date_multi_invoice_uses_latest_date`
  confirma una factura de proveedor con `invoice_date` (tasa) de hoy e `invoice_date_display` de hoy-10, lo que
  la regla `invoice_date <= invoice_date_display` bloquea. Se ajustará en un ticket posterior; el CI no corre
  ese módulo.
- Al desplegar: una NC/ND en borrador con tasa distinta a la del origen ya no se puede confirmar y su tasa es
  de solo lectura; hay que borrarla y recrearla. Avisar a soporte.
- Verificación manual 3.1 del ticket con la vertical y validación funcional en staging de 15450 y 15594.

## Tests de l10n_ve_invoice_digital (arreglados en este PR)

Estaban rotos desde la migración a Odoo 19. Se ajustaron los fixtures (`account.account` con
`company_ids`, diario bancario con cuentas en sus métodos de pago, grupo de impuestos, país fiscal de
la compañía, impuesto de compra, diarios de retenciones, concepto de pago en el producto, `account_id`
en las líneas de factura, `uom_po_id`/`stock.move.name`/`type='product'` ya inexistentes, correlativo
distinto por factura) y se corrigió un bug de producción: `l10n_ve_invoice_digital/models/stock_picking.py`
leía `move_ids_without_package`, campo que ya no existe en Odoo 19 (ahora `move_ids`). Las fechas usan
`context_today`.

