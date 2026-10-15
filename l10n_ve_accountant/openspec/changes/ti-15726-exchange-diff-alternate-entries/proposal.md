# Fix: diferencial cambiario alterno (asientos, ND/NC y montos alternos)

## Why

Ticket #15726 (https://binaural.odoo.com/odoo/my-tickets/15726). Al probar el
diferencial cambiario alterno (`l10n_ve_use_foreign_exchange_diff`) en staging
aparecieron 5 escenarios con montos alternos incorrectos o confusos. Este change
documenta cada escenario, el porqué de la solución y los **extras** que no
estaban en el ticket pero se detectaron al probar.

## Escenarios del ticket

1. **ND/NC de diferencial con montos alternos.** Las notas por diferencial
   cambiario llevaban `foreign_debit/credit/balance` distintos de 0. El asiento
   de diferencial nativo de Odoo no los lleva: el diferencial alterno, si existe,
   vive en su propio asiento. Las notas pasan a 0.0 en esos tres campos
   (`_skip_foreign_compute` + `_zero_foreign_amounts_on_exchange_notes`). Sin
   migración: es un fix hacia adelante y las notas ya emitidas se corrigen
   manualmente si se reportan.
2. **Apuntes conciliados incompletos.** El asiento de diferencial alterno solo
   aparecía en los apuntes conciliados del pago que lo originó. Ahora aparece en
   los de todos los documentos de la cadena de liquidación (factura, pago,
   asiento nativo), porque es parte económica de la misma liquidación
   (`open_reconcile_view` recorre `_all_reconciled_lines`).
3. **Wizard de pagos.** (a) El check "Pago indexado" solo tiene sentido con el
   modo de indexación "A convenir": en los otros modos el modo ya define la tasa.
   (b) El wizard rechaza importe 0.0 (`float_compare` con el redondeo de la
   moneda del wizard).
4. **Configuración.** `l10n_ve_use_foreign_exchange_diff` pasa a `True` por
   defecto, con posibilidad de desactivarse. Solo cambia el default: las
   compañías existentes conservan su valor (no hay migración que lo encienda,
   porque cambiaría la contabilidad de los clientes en el próximo `-u`).
5. **`foreign_balance` desfasado** (p. ej. 25,89 contra 25,90 de débito/crédito)
   tras la redistribución del residuo alterno en facturas: se recalcula al
   redistribuir. Sin migración: es un fix hacia adelante y los datos existentes se corrigen
   manualmente si se reportan.

## Extras detectados al probar (no pedidos en el ticket)

Se dejan documentados a propósito: son consecuencia directa de la naturaleza de
estos asientos y se detectaron al ejecutar la prueba, aunque nadie los solicitó.

- **Las ND/NC de diferencial y el asiento de diferencial alterno no pueden volver
  a borrador.** *Por qué:* son documentos generados automáticamente por la
  conciliación, no capturados por el usuario. El asiento de diferencial nativo de
  Odoo tampoco puede volver a borrador (`partial.exchange_move_id`), y mientras
  la conciliación existe el core ya lo bloquea; el hueco estaba *después* de
  revertir. Volver a borrador un documento cuyo ciclo de vida lo gobierna la
  conciliación deja un asiento sin respaldo en una liquidación que ya no existe.
  *Salida legítima:* romper la conciliación revierte el asiento/la nota
  automáticamente. Este bloqueo faltó en la implementación original.
- **El constraint de configuración se omite al crear la compañía y durante la
  carga del plan de cuentas.** *Por qué:* con el default en `True`, una compañía
  recién creada (o a mitad de la carga del plan, donde diario y cuentas se
  escriben en pasos separados) todavía no puede tener la configuración. Solo se
  valida una activación explícita. Al terminar `account.chart.template._load` se
  revalida: si el plan no dejó diario y cuentas, el toggle se apaga con un warning.

## What Changes

- `l10n_ve_accountant`: `res.company` (default, `create`, constraint),
  `account.chart.template._load`, `account.move._check_draftable`,
  `account.move.line` (`_set_foreign_value`, `open_reconcile_view`),
  `account.move._distribute_foreign_pt_residual` (`foreign_balance`), wizard de pagos
  (importe 0.0 y visibilidad del check). Bump `19.0.1.0.30` -> `19.0.1.0.32`.
- `l10n_ve_exchange_difference`: ver el change homónimo. Bump `19.0.0.0.5` -> `19.0.0.0.6`.

## Decisiones

- **Sin migraciones.** Es un fix para que los documentos nuevos queden bien y
  balanceados (`foreign_balance` alineado, ND/NC sin alternos). Los datos ya
  existentes no se tocan; si se reporta alguno, se corrige manualmente.
- **Asiento alterno de $0,01 por redondeo en pagos parciales del mismo día:** se
  mantiene, sin umbral; esos asientos se balancean automáticamente con los
  alternos. Los tests de IGTF solo los excluyen al buscar el asiento de cruce.
- **Tests de IGTF con el diferencial alterno encendido** (la configuración por
  defecto): no se apaga el flag en el `setUp`.

## Impacto a revisar

- Verificar en staging con una factura nueva que débito alterno = saldo alterno (la INV/2027/0014 del ticket es histórica y no se migra).
- Coordinar con #1464 (importe 0 en `account.payment.action_post`) para unificar
  el mensaje de importe 0.
- Versión: si #1462/#1464 se mergean antes, ajustar el número de versión del manifest.
