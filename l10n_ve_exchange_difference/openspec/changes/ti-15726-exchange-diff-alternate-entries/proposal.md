# Fix: ND/NC de diferencial cambiario sin montos alternos

## Why

Ticket #15726 (ver el change homónimo en `l10n_ve_accountant`), escenario 1.
El asiento de diferencial nativo de Odoo no lleva montos alternos; las ND/NC de
diferencial sí los llevaban (`foreign_debit/credit/balance` distintos de 0). El
diferencial alterno, si existe, vive en su propio asiento: la nota no debe
duplicarlo.

## What Changes

- `account.move.line`: `_skip_foreign_compute` devuelve True en líneas de ND/NC de diferencial; `_zero_foreign_amounts_on_exchange_notes` (en `create`/`write`) fuerza a 0.0 `foreign_debit/credit/balance`, incluso si otros flujos escriben `foreign_balance` directo.
- `account.move._check_draftable`: las ND/NC de diferencial (y sus reversos) no vuelven a borrador. **Extra no pedido en el ticket, detectado al probar:** se generan por la conciliación, no por el usuario; romperla las revierte, y esa es la vía legítima de corrección. Este bloqueo faltó en la implementación original.
- **Sin migración, a propósito:** es un fix para garantizar que las notas nuevas queden bien y balanceadas. Las ND/NC ya emitidas no se tocan (son documentos publicados, posiblemente de períodos cerrados); si alguna se reporta, se corrige manualmente.
- Bump `19.0.0.0.5` -> `19.0.0.0.6`.

## Nota

Las ND/NC de diferencial son siempre exentas (sin impuesto), por lo que no hay montos de impuesto alternos que cuadrar en ellas.
