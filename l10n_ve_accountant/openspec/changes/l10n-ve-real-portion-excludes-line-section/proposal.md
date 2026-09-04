# Fix: el residuo de redondeo del real portion puede caer sobre una línea de sección

## Why

Ticket Helpdesk #14978. Reportado en staging de un cliente: una factura en
USD con una sección de producto combo (generada automáticamente al agregar
un combo, o tipeada a mano) no podía confirmarse. Postgres rechazaba el
posteo con:

    psycopg2.errors.CheckViolation: new row for relation "account_move_line"
    violates check constraint "account_move_line_check_non_accountable_fields_null"
    DETAIL: Failing row contains (..., balance=0.01, debit=0.01, ...)

La fila que fallaba era exactamente la línea `line_section` del combo -- un
encabezado visual que nunca debe tener balance ni cuenta contable asignados
(así lo exige el CHECK nativo de `account.move.line`).

## What Changes

`_distribute_invoice_real_portion` arma dos listas de líneas candidatas a
recibir el residuo del redondeo del "real portion" (`non_pt` y
`target_lines`), filtrando solo `('payment_term', 'cogs')`. Como una línea de
sección siempre tiene `balance=0`, `_distribute_to_lines` -- que ordena las
candidatas por `-abs(balance)` y le asigna a la última de la lista lo que
sobra del redondeo -- las manda al final y les asigna el residuo. Una línea
no contable termina con `balance`/`debit` distinto de cero.

Se agrega `('line_section', 'line_subsection', 'line_note')` a los dos
filtros, para que estas líneas nunca sean candidatas.

## Capabilities

### New Capabilities
- `real-portion-rounding-distribution`: el reparto del residuo de redondeo
  del "real portion" en `_distribute_invoice_real_portion` debe excluir
  siempre las líneas no contables (`line_section`, `line_subsection`,
  `line_note`) de sus candidatas, sin importar si hay o no líneas
  `payment_term` en la factura.

## Impact

- Archivo: `l10n_ve_accountant/models/account_move.py`
  (`_distribute_invoice_real_portion`), dos ocurrencias (con y sin líneas
  `payment_term`).
- Módulos afectados: cualquier cliente con `l10n_ve_accountant` que use
  secciones (manuales o generadas por combos) en facturas con moneda
  distinta a la de la compañía.
- Sin migración de datos: el CHECK constraint nativo impidió que se
  persistiera cualquier balance corrupto -- los documentos afectados
  simplemente quedaban trabados en borrador, nunca llegaban a postear con
  data inválida.
- Bump de manifest `19.0.1.0.13` → `19.0.1.0.14`.
