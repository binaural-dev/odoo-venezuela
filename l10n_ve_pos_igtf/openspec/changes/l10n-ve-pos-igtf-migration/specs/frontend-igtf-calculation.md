# Frontend IGTF Calculation Specification

> **Rediseñado 2026-07-09.** El algoritmo O17 heredado (3% del monto de cada
> línea, con topes y un cálculo paralelo en moneda foránea) fue reemplazado
> por `_igtfBaseState` en `order_model.js`. Este documento es la fuente de
> verdad del comportamiento actual.

## Purpose

Define how IGTF is computed on the Odoo 19 POS order when payment methods
with `apply_igtf` are used.

## Business rules (confirmadas por Jesús, 2026-07)

1. **IGTF = `config.igtf_percentage`% solo de la BASE de factura cubierta**
   por líneas con `apply_igtf`. Tope: nunca más del 3% del total de la
   factura, aunque el cliente sobrepague (el exceso es vuelto).
2. **La porción de un pago que salda deuda IGTF NUNCA genera IGTF**, aunque
   se pague con un método `apply_igtf` (anti-loop del 3% infinito).
3. **El cálculo se hace SIEMPRE sobre la moneda principal de la DB**
   (`line.amount`; en esta DB Bs). El lado foráneo (`foreign_igtf_amount`,
   totales foráneos) es solo display y se deriva con **UNA** conversión
   `localToForeign`, nunca con un cálculo paralelo en foráneo.
   - Cálculo paralelo en USD producía 341 vs 348 Bs (doble resta del IGTF
     acumulado + redondeos independientes).
4. **Regla de redondeo (engram l10n_ve_pos):** cada total foráneo es UNA
   conversión de su contraparte local. `round(a) + round(b) != round(a+b)`
   → sumar conversiones redondeadas descuadra $0,01 entre el total, la
   línea y el restante (bug 17,71 vs 17,70).
5. **Prohibido `Math.abs` y comparaciones float crudas** en montos:
   usar `roundLocalMoney` / `roundForeignMoney` (res.currency.round) o
   `floatIsZero(v, currency.decimal_places)`. El signo se maneja
   normalizando: `amt = sign * amount` con `sign = total < 0 ? -1 : 1`
   (reembolsos = espejo exacto de ventas).
6. IGTF solo aplica cuando `order.to_invoice` es true.

## Algorithm: `_igtfBaseState(excludeLine = null)`

Recorre `payment_ids` en orden rastreando, en moneda principal:

```
remainingBase = |total factura|      (sin IGTF)
unpaidIgtf    = 0                    (IGTF generado aún no cobrado)
por cada línea (excluyendo excludeLine):
  amt = sign * amount                (líneas de cambio: amt < 0 → skip)
  base = min(amt, remainingBase)     (porción que cubre factura)
  remainingBase -= base
  si apply_igtf: newIgtf = compute_igtf_amount(base); unpaidIgtf += newIgtf
  excess = amt - base                (porción que paga deuda IGTF)
  unpaidIgtf = max(0, unpaidIgtf - excess)   (también líneas sin apply_igtf)
```

Devuelve `{ sign, remainingBase, unpaidIgtf, lines[{payment, base, newIgtf,
isChange, isIgtf}] }`. Todos los pasos redondean con `_igtfRoundLocal`
(→ `roundLocalMoney`).

Consumidores:
- `update_igtf()`: per-line `igtf_amount = sign * newIgtf` (el IGTF que la
  base de ESA línea genera — semántica que espera el split contable de
  `_create_payment_moves`), `include_igtf = true` en líneas apply_igtf no-cambio.
  Orden: `igtf_amount = Σ newIgtf`, `bi_igtf = Σ base` (solo líneas apply_igtf),
  foráneos = `localToForeign(local)`.
- `PosPayment.set_foreign_amount` (patch IGTF): clamp exacto al restante
  (`sign * (remainingBase + unpaidIgtf)`), ver frontend-payment-creation.md.

## Requirements

### Requirement: la precarga nunca incluye el IGTF de la propia línea

> Rediseño 2026-07-09 (2ª iteración): reemplaza al requirement "Closing
> amount in a single line". La precarga es SIEMPRE `remainingDue` (deuda de
> factura + deuda IGTF acumulada); el IGTF de la base que cubre la línea se
> genera DESPUÉS en `update_igtf()` y queda como nuevo restante. Detalle y
> escenarios A/B en frontend-payment-creation.md.

#### Scenario: pago completo (números reales de la DB pos, tasa 675)

- GIVEN factura 11.600 Bs (= $17,19), IGTF 3%, Zelle apply_igtf + foránea
- WHEN se selecciona Zelle sin pagos previos
- THEN la línea queda en 11.600 Bs = $17,19 (sin su IGTF)
- AND tras asociarse, `remainingDue` = 348 ($0,52), IGTF total 348, BI 11.600
- AND una segunda línea (cualquier método) precarga 348 y NO genera IGTF

#### Scenario: pago parcial $10 + restante completo

- GIVEN la misma factura, línea 1 Zelle $10 (6.750 Bs, todo base, genera
  202,50 Bs de deuda IGTF)
- WHEN se selecciona Zelle de nuevo
- THEN la línea 2 precarga el restante completo: 4.850 + 202,50 = 5.052,50 Bs
  ($7,49); solo la porción de base (4.850) genera 145,50 después
- AND `remainingDue` queda en 145,50 ($0,22); una tercera línea lo salda
- AND IGTF total 348 exacto

#### Scenario: pagar solo deuda IGTF con método apply_igtf

- GIVEN base de factura ya cubierta y deuda IGTF de 348 Bs
- WHEN se paga 348 con Zelle
- THEN base = min(348, remainingBase=0) = 0 → NO genera IGTF nuevo

#### Scenario: método sin apply_igtf

- GIVEN deuda IGTF pendiente
- WHEN se selecciona un método sin apply_igtf
- THEN precarga `remainingDue` (incluye la deuda IGTF); la línea no genera
  IGTF y su excedente sobre la base salda la deuda

### Requirement: Foreign totals are single conversions

- `get_foreign_total_with_tax()` = `localToForeign(get_total_with_tax())`
  (17,70), NUNCA `localToForeign(total) + foreign_igtf` (17,71).
- `l10n_ve_pos/payment_status.js::_getForeignTotalDueAmount` NO debe volver
  a sumar `get_foreign_igtf_amount` (producía $18,23 = 17,71 + 0,52).
- `get_foreign_due` (l10n_ve_pos) cuadra a 0 porque total y líneas usan la
  misma conversión.

### Requirement: remainingDue / change incluyen IGTF (fórmula DIRECTA)

- Con IGTF: `remainingDue = roundLocal(totalDue + igtf_amount - amountPaid)`,
  clampeado a 0 con normalización de signo (`sign * remaining <= 0`), con la
  tolerancia de cash rounding del core. Sin IGTF: delega en el core intacto.
- **PROHIBIDO componer sobre el `remainingDue` del core** (`core + igtf`):
  el core clampa a 0 en cuanto `amountPaid >= totalDue`, y cuando una línea
  absorbe deuda IGTF ese exceso se pierde → devolvía la deuda IGTF COMPLETA.
  Caso real (factura 14.220, Zelle 13.498,61 con IGTF 404,96 + Zelle 1.126,35
  que absorbe la deuda y genera 21,64): la fórmula compuesta daba 426,60
  (IGTF total) en vez de los 21,64 pendientes, y esa cifra se precargaba en
  la siguiente línea. La fórmula directa descuenta TODO lo pagado.
- `change` solo existe cuando se paga más que `totalDue + igtf_amount`
  (también con fórmula directa; nunca dependió del clamp del core).
- Las simulaciones de verificación DEBEN modelar el clamp real del core; una
  simulación con `total - paid` sin clamp dio por buena la versión rota.

### Requirement: compute_igtf_amount rounds with main currency

`compute_igtf_amount(v) = roundLocalMoney(v * igtf_percentage / 100)`.

## Backend contract (`_create_payment_moves`)

Para líneas `include_igtf`: acredita `amount - igtf_amount` al receivable y
`igtf_amount` a `company.customer_account_igtf_id` (lados foráneos con
`foreign_amount - foreign_igtf_amount` / `foreign_igtf_amount`). La suma por
orden cuadra: Σ(amount - igtf) = total factura, Σ igtf = IGTF total,
independientemente de qué línea "pagó" la deuda.

## Eliminado en el rediseño

- Guard `last_igtf_amount == payment.amount` (hack O17 para "línea que paga
  exactamente el IGTF"; ahora sale natural: base restante = 0 → IGTF 0).
- `get_max_total_with_igtf()`: sin consumidores y calculaba 3% sobre el
  foráneo (contra la regla 3).
- Cálculo paralelo foráneo completo dentro de `update_igtf`.
