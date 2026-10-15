# Design

## Detección del cierre de la nota

`_create_exchange_difference_note` cierra la línea por cobrar de la nota con
`note_line.with_context(no_exchange_difference=True,
l10n_ve_exchange_closing_note_line_id=note_line.id).write({'reconciled_lines_ids': ...})`.
El inverse corre `_reconcile_plan` con el env de `note_line`, que conserva el
contexto, hasta `_prepare_reconciliation_single_partial`.

`_l10n_ve_note_foreign_values(debit_values, credit_values)` devuelve el dict de
la contraparte, o `None`, y solo devuelve algo si:

1. la clave de contexto coincide con el `aml.id` de una de las dos líneas;
2. exactamente una de las dos es una nota nuestra (excluye nota-vs-nota y
   reversiones) y es la de la clave;
3. la contraparte está en divisa y conserva saldo en ella;
4. la contraparte conserva saldo en Bs tras el cruce
   (`|residual_contraparte| > |residual_nota|`): el núcleo no puede darla por
   cerrada.

`shadowed_aml_values is not None` (previews) nunca activa el sandbox.

## Sandbox

El núcleo solo LEE los saldos de los dicts que recibe y los reescribe al final
(`debit_values['amount_residual'] = ...`), y su llamador
(`_prepare_reconciliation_amls`) conserva sus propios dicts y solo lee `None`
de `res['debit_values'|'credit_values']`. Por eso se le pasa
`dict(foreign, amount_residual_currency=0.0)`, con lo que el núcleo ve la línea
sin saldo en divisa y concilia en Bs con 0 USD (`exchange_line_mode`/tasa
`None` para esa línea). Tras `super()` se copian al dict original todas las
claves del sandbox menos `amount_residual_currency` (no se pierden claves de
otros overrides) y, si `res[...]` es el sandbox, se reemplaza por el original.
Un único `super()`; el `try/finally` del stash en el cursor no cambia.

## Widget

Una fila por NOTA y no por cruce: evita duplicar importes si la nota tiene dos
cruces (históricas) y cubre las ND que se cierran contra la línea del pago (no
aparecen entre los partials de la factura). Se conserva un `partial_id` real:
el JS de `l10n_ve_accountant` solo toca filas con `partial_id === false`
(asientos "alt-diff" standalone). Las reversiones (`l10n_ve_exchange_original_id`)
y las notas revertidas no se listan. Ambas variantes del compute (núcleo e
`l10n_ve_igtf`) llaman a `_get_all_reconciled_invoice_partials`.

El override de `_compute_payments_widget_reconciled_info` post-procesa tras
`super()` y reasigna el Json completo. El xpath de la plantilla se ancla en
`td[@t-if='line.is_exchange']` (estructura, no texto).

## Alternativas descartadas

- Excluir por heurística de montos: frágil; se usa clave de contexto propia.
- Reescribir el partial después de creado: implicaría tocar
  `account.partial.reconcile`; se corrige antes de que se cree.
