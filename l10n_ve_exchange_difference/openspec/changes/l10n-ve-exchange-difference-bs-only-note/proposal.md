# Fix: cruce de la nota de diferencial solo en Bs + presentación en el widget de pagos

## Why

La ND/NC de diferencial es un documento en moneda de la compañía (Bs) que se
cierra con `reconciled_lines_ids`. Cuando la línea contra la que se cierra
todavía tiene saldo en divisa (liquidación parcial), el núcleo
(`_prepare_move_line_residual_amounts`, rama `currency == company_currency and
counterpart_currency != company_currency`) le inventa a la nota un equivalente
en USD y concilia en USD: el cruce de la nota consume USD (p. ej. 0,46/0,91) y
"Cantidad por pagar" baja de más; a veces la nota queda con dos cruces. Tras
una aplicación completa la línea ya no tiene USD, el núcleo concilia en Bs y el
cruce lleva 0 USD (correcto, igual que el asiento nativo EXCH).

Además, el widget "Pagado/Revertido" pinta el EXCH nativo en gris/cursiva/Bs
("Exchange Difference") por `is_exchange`, pero las notas salen como una fila
de pago normal con USD.

## What Changes

**Cruce solo en Bs (totales):**
- `_create_exchange_difference_note` cierra la nota con una clave de contexto
  propia (`l10n_ve_exchange_closing_note_line_id` = id de la línea de la nota),
  misma idea que `l10n_ve_exchange_is_retention_reconcile`: clave explícita,
  no heurística.
- El override de `_prepare_reconciliation_single_partial` entrega al núcleo una
  copia (sandbox) del dict de la contraparte con
  `amount_residual_currency = 0.0` cuando `_l10n_ve_note_foreign_values` lo
  indica, y al volver copia los resultados al dict original (salvo el residual
  en divisa) y restituye su identidad en `res`. Una sola llamada a `super()`.

**Presentación (widget de la factura):**
- `_get_all_reconciled_invoice_partials` quita las filas de nuestras notas y
  agrega UNA fila `is_exchange=True` por nota viva (Bs, `partial_id` real).
- `_compute_payments_widget_reconciled_info` marca `is_exchange_note` y
  `exchange_note_name` en cada fila de nota.
- Herencia OWL de `account.AccountPaymentField` que muestra
  "Exchange Difference Note <número>" (es_VE: "Nota por Diferencial").

Versión del módulo 19.0.0.0.7. Sin migración: las notas históricas conciliadas
con USD no se migran.

## Impact

- **Capability**: `exchange-difference-note` (extendida).
- **Sin overrides de `create`/`write`/`unlink`, sin `store=True` nuevos, sin
  recordsets `new()`.**
- **Límites documentados** (README): PDF de la factura deja de listar la nota
  como "Pagado el"; los módulos de máquina fiscal (`l10n_ve_account_mf` /
  `l10n_ve_iot_mf`) recorren `content` sin filtrar `is_exchange` y recibirán la
  nota en Bs sin convertir -- pendiente de decisión funcional (la bandera
  `is_exchange_note` permite filtrarla).
- **Fuera de alcance**: la restricción "una nota por pareja factura-pago"
  (guarda `existing_note`) no se toca (cambio separado).
- **Tests**: `tests/test_exchange_note_bs_only.py`.
