# Unificar el cálculo de montos en moneda alterna en una sola vía (`_convert`)

Tarea: [TA-74966](https://binaural.odoo.com/odoo/action-341/74966)

## Why

El requerimiento original era de compras: al cambiar la moneda de una factura
de proveedor generada desde una orden, recalcular los precios a la tasa de la
factura. Al implementarlo apareció un desfase — 300 USD volvían como 300,57 —
que no venía del código de compras sino de la localización.

### Causa raíz

Existían **dos formas distintas de llegar al mismo monto alterno**:

1. Multiplicar por `foreign_inverse_rate`, un valor almacenado en el
   documento.
2. Convertir con `currency._convert()`, que lee `res.currency.rate` por fecha.

Con la misma tasa nominal ambas pueden no coincidir, y el resultado dependía
de por cuál de las dos hubiera pasado el cálculo.

Peor: la migración de v17 a v19 **cambió la moneda base de la compañía de USD
a VEF**, y con ello se intercambió el significado de los dos campos de tasa
que devuelve `l10n_ve_rate/models/res_currency_rate.py::compute_rate`:

| | v17 (base USD, alterna VEF) | v19 (base VEF, alterna USD) |
|---|---|---|
| `foreign_rate` | 0,02 (USD por VEF) | **50** (VEF por USD) |
| `foreign_inverse_rate` | **50** (VEF por USD) | 0,02 (USD por VEF) |

Todo el código escrito en v17 que multiplicaba a mano quedó expuesto a aplicar
el factor invertido. La variable se sigue llamando `vef_id` para lo que en
realidad es "moneda de la compañía", y `compute_inverse_rate` todavía
hardcodea `if the foreign currency is USD`.

### Segundo hallazgo: el redondeo

`_convert()` redondea por defecto a los decimales de la **moneda destino**
(USD = 2), pero `foreign_price` declara `digits="Foreign Product Price"`, una
`decimal.precision` configurable desde la interfaz y normalmente mayor que 2.
Migrar a `_convert()` sin más habría *perdido* precisión en lugar de ganarla:
con la precisión por defecto de la instalación, un precio unitario de 0,0567
VEF a tasa 50 se guardaba como `0,00` en vez de `0,001134`, y
`foreign_subtotal` (= `foreign_price` × cantidad) arrastraba ese cero
multiplicado por la cantidad.

Medido en instancia: con `round=False` + redondeo a la precisión del campo, la
conversión de ida y vuelta es **exacta** (error 0,00000000 en 15 combinaciones
de tasa y precio). Es lo que hace innecesario forzar valores a mano entre
documentos.

### Tercer hallazgo: subtotales sin `compute_all`

`sale.order.line` y `purchase.order.line` calculaban `foreign_subtotal` como
`foreign_price × cantidad`, mientras `account.move.line` pasaba por
`compute_all`. Medido: con IVA **no** incluido difieren solo por redondeo
(hasta 0,005 por línea, acumulativo); con impuesto **incluido en precio** la
diferencia es del 13,79% — la multiplicación directa reporta como "subtotal
sin impuestos" un monto que lleva el impuesto dentro.

No se estaba materializando porque la localización venezolana no define
ningún impuesto con precio incluido, pero cualquier cliente puede crear uno
desde la interfaz.

## What Changes

- **Una sola vía de conversión.** Se elimina toda multiplicación o división
  manual por una tasa en `l10n_ve_accountant` y `l10n_ve_sale`. Todo pasa por
  `_convert()`.
- **La precisión la manda el campo, no la moneda**: `_convert(round=False)` +
  `float_round` a la precisión declarada.
- **Una sola fuente de fecha por línea**, vía `_get_foreign_rate_date()`.
- **Los subtotales alternos pasan por `compute_all`** cuando hay impuestos.
- **Los totales del documento se leen de `tax_totals`**, que ya los calcula,
  en lugar de convertirlos por segunda vez.
- **La tasa almacenada en el documento pasa a ser informativa** para el
  cálculo de montos: manda la tabla de tasas a la fecha correspondiente.
- **`sale.order.foreign_rate_date`** (campo nuevo, oculto): guarda la fecha de
  la que salió la tasa de la orden y sobrevive a que el core reescriba
  `date_order` al confirmar.

## Non-goals

- **No se toca `legacy_compute_line_ids_foreign_debit_and_credit`.** Es código
  muerto: sin invocadores, su acción de servidor no tiene `binding_model_id`
  y revienta con `TypeError` en `account_move.py:772` para cualquier factura
  con impuestos.
- **No se corrigen los módulos con la dirección de conversión invertida**
  heredada de v17 (`binaural_hr_payroll`, `binaural_advance_payment_igtf`,
  `l10n_ve_account_mf`, `binaural_ft`, `binaural_club_socios_mf`). Están
  inventariados aparte; son bugs funcionales con impacto fiscal y de nómina
  que necesitan su propio ticket y validación.
- **No se migran los montos alternos de retención**: todos sus consumidores
  están tras un `if compañía == USD` que en v19 nunca se cumple.
- **No se unifica `compute_all` al motor nuevo de impuestos.** El core de v19
  hace la misma separación: motor nuevo para el flujo de asiento y totales,
  `compute_all` para cálculos de línea aislada
  (`sale/models/sale_order_line.py:1176`).

## Impact

- Módulos: `l10n_ve_accountant`, `l10n_ve_sale` (y `binaural_purchase` en
  `integra-addons`, que no usa openspec).
- **Documentos existentes no se recalculan**: `foreign_price`,
  `foreign_debit` y `foreign_credit` son `store=True`; su valor solo cambia
  si se toca una dependencia.
- **Sí cambian de valor**, en el orden de céntimos, los subtotales alternos de
  órdenes de venta y compra al recalcularse, por el redondeo a la moneda que
  antes no se aplicaba.
- **Flujos que heredaban la tasa** (POS, cierre de ejercicio y
  `use_invoice_rate_from_sale_order`) muestran su tasa pero los montos salen
  de la tabla. En ventas se preserva la equivalencia heredando la *fecha* de
  la tasa en lugar del *valor*.
- Migración: `l10n_ve_sale/migrations/19.0.1.0.6/post-set_foreign_rate_date.py`
  rellena el campo nuevo en las órdenes aún no facturadas.
