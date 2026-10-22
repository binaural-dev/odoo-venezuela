# Chore: remover los campos `foreign_*` de retenciones, código muerto heredado de v17

> **Estado:** propuesta. Pendiente de crear el ticket que la implemente (sin id
> todavía). Este documento existe para que ese ticket se cree con el alcance
> ya investigado.

## Why

En v17 la base del sistema era USD y el bolívar la moneda secundaria, así que
las retenciones guardaban su valor en "moneda foreign" y las vistas y reportes
lo mostraban. En v19 la base es **siempre VEF**: las columnas foreign de las
retenciones nunca se ven y ningún cálculo contable las lee. Se arrastran solo
por herencia.

Evidencia (investigada sobre la rama `maintenance-19.0`):

- **Vistas:** todas las columnas y totales foreign de los comprobantes IVA,
  ISLR y municipal, y de las pestañas de retención de la factura, llevan
  `column_invisible="parent.base_currency_is_vef"` o
  `invisible="base_currency_is_vef"`. Con base VEF nunca se muestran.
- **Reportes:** todas las ramas que leen estos campos dependen de que la moneda
  de la compañía no sea VEF o de que la moneda foreign sea VEF
  (`retention_voucher_templates.xml`, `municipal_retention_xlsx.py`,
  `retention_line_report.py`, `wizard/accounting_reports.py`,
  `wizard/wizard_retention_iva.py`, `l10n_ve_pos_mf/wizard/wizard_sales_book.py`).
  Con base VEF no corren. La rama foreign del ARC-V ya se retiró.
- **Contabilidad:** el USD del asiento del pago de la retención NO sale de estos
  campos. Lo calcula `account.move.line._compute_foreign_debit_credit` →
  `_get_foreign_value` → `_get_non_invoice_foreign_value`, con la tasa de la
  fecha (`_get_foreign_rate_date`, que para retenciones devuelve la fecha de la
  factura). El único lugar que leía `payment.retention_foreign_amount` es
  `legacy_compute_line_ids_foreign_debit_and_credit`
  (`l10n_ve_accountant/models/account_move.py`), un método **sin ningún
  llamador**.
- **Tasa:** `foreign_rate` del documento y `foreign_currency_rate` de la línea
  son referenciales (menos dígitos que la tasa real). Las conversiones deben
  salir de la tasa de la fecha, nunca de ese valor.

## What Changes (para el ticket)

Criterio: **se reutilizan los campos que la modalidad de retención indexada
necesite y se eliminan los que sobren.** No se crean campos paralelos
(`document_*`) para lo que un `foreign_*` ya cubre.

### Se conservan y se reutilizan (cambian de significado)

Pasan a expresar la **moneda del documento** (la de la factura) y solo existen en
retenciones indexadas, que solo aceptan facturas en moneda extranjera. Ya
aplicado en la rama de trabajo junto con la modalidad indexada:

- `account.retention.line.foreign_currency_id`: `related` a
  `move_id.currency_id`. Siempre es la moneda del documento; nunca la alterna.
- `account.retention.line.foreign_retention_amount`: retención valorada en la
  moneda del documento con la tasa de la fecha del comprobante.
- `account.retention.line.foreign_currency_rate`: tasa usada, solo lectura y
  referencial.

Una línea que no es indexada no tiene valoración foreign: esos campos quedan en
0 o vacíos. Las vistas los muestran únicamente cuando la retención es indexada.

### Se eliminan (sobrantes)

Con sus vistas, cálculos, traducciones y pruebas:

- `account.retention.line`: `foreign_invoice_amount`, `foreign_iva_amount`,
  `foreign_invoice_total`.
- `account.retention`: `foreign_total_invoice_amount`,
  `foreign_total_iva_amount`, `foreign_total_retention_amount`,
  `foreign_currency_id` (y su cálculo en `_compute_totals`).
- `account.payment`: `retention_foreign_amount` y
  `_compute_retention_foreign_amount`.
- Código que solo existía para esos campos:
  - ramas `not base_currency_is_vef` y de moneda USD en
    `_compute_retention_amount`, `_compute_amounts`, `_compute_related_fields`
    y `onchange_retention_amount` (`account_retention_line.py`); el monto
    foreign de ISLR y municipal deja de depender de `foreign_invoice_amount` y
    pasa a salir del Bs retenido convertido con la tasa de la fecha;
  - la rama de `_get_foreign_rate_date` que forzaba la tasa de la factura en el
    asiento y la copia de `foreign_rate` en `_synchronize_to_moves`
    (`account_payment.py`) **solo si se confirma** que el cálculo por fecha de
    `_get_foreign_value` cubre el caso (ver Impact);
  - el campo `base_currency_is_vef` y las condiciones de vistas que dependen
    de él;
  - columnas foreign del asistente de registro de pago
    (`wizard/account_payment_register.xml`).

### Consumidor externo que también debe dejar de usarlos

`binaural_mobile` (repo `integra-addons`) lee y escribe estos campos y **no
debería hacerlo**: son código muerto y su portal no tendría por qué mostrar ni
calcular montos foreign de retenciones. Debe limpiarse en el mismo ticket:

- `views/portal_retention.xml`: `retention.foreign_total_*`
  (líneas ~205, 344-356) y `line.foreign_iva_amount` /
  `line.foreign_retention_amount` (~272-311).
- `controllers/account_retention_payments.py` (~290-316): calcula y escribe
  `foreign_iva_amount` y `foreign_retention_amount`.
- `controllers/account_payment_payments.py` (~534): escribe
  `foreign_currency_rate`.
- `static/src/js/portal_retention.js` (~504): envía `foreign_retention_amount`.
- `tests/test_retention_monetary.py` (~161-195): afirma `foreign_total_*`.

## Impact

- **Capability:** `l10n_ve_payment_extension` (retenciones).
- **Dependencia con retenciones indexadas:** la tarea de retenciones
  indexadas reutiliza `foreign_currency_id`, `foreign_retention_amount` y
  `foreign_currency_rate` con el significado de "moneda del documento". Este
  ticket NO debe eliminar esos tres; elimina el resto. Si el ticket se hace
  antes que la tarea, esos tres se dejan intactos; si se hace después, parte
  de ya haberlos reinterpretado.
- **Riesgo:** medio. Es un cambio de esquema (se eliminan columnas) y toca
  vistas, reportes y otro repositorio. Antes de borrar la rama que fuerza la
  tasa de la factura en el asiento hay que comprobar con pruebas que el valor
  alterno del asiento (`foreign_debit/credit`) no cambia.
- **Datos:** las columnas eliminadas no tienen consumidores contables, pero
  `foreign_*` de retenciones sí aparecen en el portal de `binaural_mobile`
  mientras no se limpie allí.
- **Pruebas afectadas** (afirman estos campos y deben ajustarse o eliminarse):
  `test_withholdings_islr.py`, `test_withholdings_manual_flows.py`,
  `test_withholdings_iva_partner.py`, `test_payment_concept_setup.py`
  (`test_05_sum_retention_total_foreign`),
  `test_retention_foreign_rate_ticket_15154.py`,
  `test_retention_islr_foreign_amount.py`.

## Ya aplicado en la rama de trabajo (fuera de este change)

- Eliminados los campos sin ningún uso `amount_tax_ret`, `base_ret`, `imp_ret`,
  `retention_rate` y `display_invoice_number` de `account.retention.line`. Este
  último declaraba `compute="_compute_display_invoice_number"` pero ese método
  nunca existió en la rama, así que el campo siempre quedaba vacío.
- Eliminado `legacy_compute_line_ids_foreign_debit_and_credit`
  (`l10n_ve_accountant`), que era el único lector de
  `payment.retention_foreign_amount`. No tenía llamadores en Python; su única
  referencia era la acción de servidor
  `recompute_foreign_debit_and_credit_of_journal_entries`, sin
  `binding_model_id` (no accesible desde el menú), que además fallaba con
  `TypeError` en facturas con impuestos (ya lo documentaba el change
  `l10n-ve-currency-conversion-unification`). Se eliminaron junto con ella su
  ayudante `get_invoice_line_ids_subtotals_by_name` y la traducción de la
  acción.
- `_compute_retention_amount` (ISLR) quedó solo con la ruta VEF: se eliminaron
  las ramas `not base_currency_is_vef` (base USD de v17). El monto retenido
  sale siempre de `invoice_amount`. Queda pendiente `_compute_amounts`, que solo
  actúa si la base no es VEF y está atado al campo `foreign_invoice_amount`
  que se elimina en este ticket.
- ISLR: el monto foreign dejó de convertirse dos veces; ahora sale del Bs
  retenido convertido con la tasa de la fecha de la factura. Es una corrección
  mínima mientras estos campos existan; este change la vuelve irrelevante.
