# Diferencial cambiario en moneda alterna al conciliar facturas y pagos

## Why

El diferencial cambiario nativo de Odoo (`account.move.line._prepare_exchange_difference_move_vals` /
`_create_exchange_difference_moves`, core) solo mira `amount_residual` — el
residual en **moneda de la compañía** (VEF). Cuando se concilia una factura
contra un pago, Odoo corrige lo que haga falta en VEF, pero nunca genera
ningún asiento para la deuda equivalente en la **moneda alterna** (`company.
foreign_currency_id`, normalmente USD) que esta localización lleva en
paralelo (`foreign_debit`/`foreign_credit`, `l10n_ve_rate`).

Esto deja dos huecos reales:

1. **Factura en VEF pagada en VEF exacto** (o en cualquier combinación que
   cuadre la moneda de compañía): Odoo no dispara ningún ajuste — pero el
   valor en USD de esa factura, calculado a la tasa de reserva, casi nunca
   coincide con su valor en USD a la tasa de pago. Esa diferencia queda sin
   registrar en ningún lado.
2. **Factura en VEF pagada con un residual en VEF que Odoo sí corrige**: el
   asiento nativo corrige el VEF, pero el monto alterno de esas mismas dos
   líneas nunca se toca — queda desactualizado indefinidamente.

### Decisión de diseño: no depender de `foreign_amount_residual`

Se evaluó enganchar esto al campo `foreign_amount_residual`
(`integra-addons/binaural_account_reports`, `compute`+`store` sobre
`matched_debit_ids`/`matched_credit_ids`). Se descartó por dos motivos:

1. **Dependencia circular real**: `binaural_account_reports` ya depende de
   `l10n_ve_accountant` (dueño de `foreign_currency_id`/`foreign_rate`).
   Enganchar el cálculo a ese campo habría acoplado `l10n_ve_accountant` a un
   módulo de reportes que depende de él.
2. **No cubre el caso "solo hay diferencia en alterno"**: su avance depende
   de que haya conciliación de residual en moneda de compañía en el mismo
   partial (ratio `consumed_company / initial_company`) — da `0` quien
   la compañía ya cuadra exacto, exactamente el caso 1 de arriba.

En su lugar, el cálculo se reimplementa de forma independiente, reutilizando
el **mismo código nativo** que Odoo ya usa para el diferencial en VEF —
enganchado en `_prepare_reconciliation_single_partial` (corre en cada
partial, a diferencia de `_prepare_exchange_difference_move_vals`) y en
`_create_exchange_difference_moves` — para que la reversión de Odoo (al
deshacer una conciliación) también revierta el ajuste alterno, sin código de
reversión propio.

## What Changes

- **Toggle de empresa** `l10n_ve_use_foreign_exchange_diff` (Ajustes >
  Contabilidad), con `@api.constrains` que exige las mismas cuentas/diario de
  diferencial cambiario nativo que Odoo ya requiere
  (`income_currency_exchange_account_id`, `expense_currency_exchange_account_id`,
  `currency_exchange_journal_id`) — se reutilizan, no se crean cuentas
  dedicadas para el alterno.
- **Caso combinado**: cuando Odoo SÍ construye su asiento nativo para un
  partial, se le inyecta `foreign_debit`/`foreign_credit` a las MISMAS dos
  líneas que Odoo ya creó, derivando el monto base directamente del
  `debit`/`credit` (o `amount_currency`, rama `amount_residual_currency`) que
  el propio core calculó para esa línea — nunca re-derivado de forma
  independiente, para no misatribuir el ajuste al lado equivocado del
  partial.
- **Caso standalone**: cuando Odoo no construye ningún asiento (la moneda de
  compañía ya cuadra exacto) pero sí hay diferencia en alterno, se crea un
  asiento con la MISMA forma (mismas cuentas/diario) con montos en VEF en
  cero y solo `foreign_debit`/`foreign_credit` distintos de cero.
- **Idempotencia y reversión 100% nativas**: ambos casos reutilizan
  `account.partial.reconcile.exchange_move_id` — el mismo campo que Odoo usa
  para sus propios asientos genéricos. Si el partial ya tiene
  `exchange_move_id`, se reutiliza (no se duplica); al deshacer la
  conciliación, Odoo revierte ese asiento automáticamente
  (`account.partial.reconcile.unlink()`, core) sin código propio de
  reversión.
- **Regla de exclusión (el hallazgo que motivó esta ronda de pruebas)**:
  cuando la propia factura está denominada EN la moneda alterna (ej. factura
  en USD), su exposición en USD ya es fija y exacta desde el origen — no
  puede haber diferencial alterno, sin importar cuánto diferencial nativo en
  VEF se genere ni en qué moneda se pague. El cálculo lo detecta comparando
  la moneda de la línea que fija la tasa (el lado factura del partial)
  contra `company.foreign_currency_id`, y retorna `0` si coinciden.

## Non-goals

- **No se toca `l10n_ve_exchange_difference`** (reemplaza el asiento nativo
  de Odoo con notas de débito/crédito fiscales para facturas de cliente). Se
  verificó que ambos conviven sin conflicto: core zeroa `remaining_debit_amount`/
  `remaining_credit_amount` antes de decidir qué módulo construye el
  documento final, así que esta feature ve el residual ya cerrado
  independientemente de cuál de los dos termine emitiendo el documento.
- **No se depende de `binaural_account_reports`** ni de su campo
  `foreign_amount_residual`, por las razones de la sección "Why".
- **No se crean cuentas de ganancia/pérdida cambiaria dedicadas para el
  alterno** — se reutilizan las nativas de VEF.
- **No se cubre el caso `l10n_ve_igtf_note_debit`**: esa nota no debe generar
  ningún diferencial cambiario en el momento de su emisión, por diseño.

## Impact

- Módulo: `l10n_ve_accountant` únicamente (`odoo-venezuela`), sin módulo
  nuevo ni dependencias nuevas.
- Archivos: `models/account_move_line.py` (hooks + cálculo),
  `models/account_move.py` (campos de trazabilidad
  `l10n_ve_exchange_foreign_diff_entry`,
  `l10n_ve_exchange_foreign_source_move_id`,
  `l10n_ve_exchange_foreign_payment_move_id`), `models/res_company.py`
  (toggle + constraint), `models/res_config_settings.py` +
  `views/res_config_settings_views.xml` (UI del toggle).
- Tests: `tests/test_foreign_exchange_diff.py`, 16 casos — cálculo puro,
  standalone, múltiples cuotas parciales en distintas monedas y fechas,
  factura en moneda extranjera con residual mixto, reversión automática vía
  `exchange_move_id`, y la exclusión cuando la factura ya está en la moneda
  alterna.
- **Efecto en asientos existentes**: ninguno — el toggle nace desactivado;
  solo aplica a conciliaciones nuevas hechas con el toggle activo.

## Ronda 2: visibilidad, redondeo y reversión (ver `design-notes.md`)

Encontrado y corregido probando en vivo con el usuario, después de la
primera entrega:

- **Redondeo**: el cálculo original re-derivaba el monto alterno por tasa
  (`base_amount × delta_tasa`), lo que podía desfasarse por 1 centavo del
  monto real (`factura.foreign_debit − pago.foreign_credit`). Reemplazado
  por `_foreign_exposure_at_residual` — función pura que telescopía exacto
  incluso con múltiples parciales, sin ninguna tasa de por medio.
- **Visibilidad**: el standalone no aparecía ni en el widget "Pagos" de la
  factura ni en "Reconciled Items" — se agregó `_get_all_reconciled_invoice_partials`
  (widget) y se extendió `open_reconcile_view` (dominio ampliado, reutiliza
  la acción nativa) para surfacear la línea de cierre del standalone.
- **`is_exchange=True`**: decisión final para la fila sintética del widget —
  oculta el botón "Unreconcile" (que sería inútil, no hay partial real),
  a costa de que el renderer nativo (compartido con `l10n_ve_igtf`) etiquete
  el monto con la moneda de compañía en vez de la alterna.
- **Reversión rota**: `_reverse_moves` (core) nunca tocaba
  `foreign_debit`/`foreign_credit` al revertir — la reversión duplicaba o
  anulaba el monto alterno en vez de invertirlo. Corregido con un override
  que invierte esos campos explícitamente, más una red de seguridad en
  `account_partial_reconcile.unlink()` para cuando un módulo de terceros
  (`l10n_ve_igtf`) rompe la conciliación por un camino no estándar.
- **Filtro de estado**: ambas vías de visibilidad ahora excluyen entradas
  con `reversal_move_ids` seteado — antes, un asiento ya revertido seguía
  apareciendo en la factura.
- Tests: 16 → 34 en este archivo (244 en la suite completa del módulo).

## Ronda 3: símbolo de moneda en el widget de Pagos (ver `design-notes.md`)

La fila sintética del standalone (Ronda 2) mostraba el monto correcto pero
con el símbolo de moneda equivocado ("Bs.F" en vez de "$"), porque
`is_exchange=True` hace que el renderer del widget (compartido con
`l10n_ve_igtf`, no tocable desde Python) etiquete cualquier fila `is_exchange`
con la moneda de compañía sin importar cuál le pasemos.

Resuelto con un parche de frontend (`static/src/components/payment_field/payment_field.js`,
`patch()` sobre `AccountPaymentField`, mismo patrón que ya usa este módulo en
`tax_totals.js`) — sin tocar ningún archivo de core y sin campos nuevos en el
modelo (`foreign_debit`/`foreign_credit`/`foreign_currency_id` ya existían en
`account.move.line`). Verificado con datos reales en una DB temporal
(sin necesitar navegador): mismo monto, moneda corregida de VEF a USD.
