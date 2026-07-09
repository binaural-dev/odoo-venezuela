# Frontend Payment Creation Specification

> **Rediseñado 2026-07-09.** La regla anterior ("el monto de la línea excluye
> el IGTF, la deuda queda en remainingDue") fue reemplazada: la línea de
> cierre INCLUYE base restante + deuda IGTF + IGTF de la nueva base.
> Ver `frontend-igtf-calculation.md` para el algoritmo (`_igtfBaseState`).

## Purpose

Define how `add_paymentline_without_igtf` creates the closing POS payment in
Odoo 19 and how the payment screen / foreign amounts interact with it.

## Requirements

### Requirement: Payment creation uses Odoo 19 model API

The system MUST create the payment via `this.models["pos.payment"].create(...)`
instead of `new Payment(...)` and `paymentlines.add(...)`.

### Requirement: Closing amount includes IGTF

`add_paymentline_without_igtf` sets:

```
amount = sign * (remainingBase + unpaidIgtf + compute_igtf_amount(remainingBase))
```

(estado calculado con `_igtfBaseState(newPaymentline)`, excluyendo la línea
recién creada). Redondeo con `_igtfRoundLocal`.

#### Scenario: cierre con deuda previa

- GIVEN factura 11.600 Bs, línea 1 Zelle 6.750 Bs (deuda IGTF 202,50)
- WHEN se crea la línea de cierre
- THEN amount = 4.850 + 202,50 + 145,50 = 5.198 Bs

### Requirement: branch selection in addPaymentline

`addPaymentline(method)` usa la ruta de cierre IGTF solo si TODAS:
`to_invoice`, `method.apply_igtf`, no es cambio, y queda base por cubrir
(`roundLocal(sign * (get_due() - get_igtf_amount())) > 0`). En cualquier otro
caso delega al core (que llena con `remainingDue`, ya IGTF-inclusive).
Si `add_paymentline_without_igtf` devuelve false (pago electrónico en curso),
addPaymentline devuelve `{ status: false, data: ... }`.

### Requirement: Foreign amount derives from local via setAmount

El monto se fija con `newPaymentline.setAmount(totalPayment)` (moneda local);
para métodos foráneos `_recomputeForeignFromLocal` (l10n_ve_pos) deriva
`foreign_amount = localToForeign(amount)` — una sola conversión. PROHIBIDO
fijar el foráneo con una segunda conversión manual.

### Requirement: PaymentScreen bypass for apply_igtf methods

`l10n_ve_pos_igtf/payment_screen.js::addNewPaymentLine`: si `to_invoice` y
`method.apply_igtf`, llama `order.addPaymentline` directo (bypass de
l10n_ve_pos, cuyo `set_foreign_amount(localToForeign(dueBefore))` pisaría el
cierre con drift ida-vuelta y sin IGTF). El numberBuffer se llena con
`formatForeignCurrency(line.get_foreign_amount(), false)` (o `formatCurrency`
local) — NUNCA `String(amount)`/`toFixed` (es_VE parsea "." como separador
de miles).

### Requirement: IGTF-aware set_foreign_amount

`l10n_ve_pos_igtf/payment_model.js` parchea `set_foreign_amount`: si el monto
foráneo tecleado cubre el cierre (`roundForeignMoney(sign*requested -
sign*closingForeign) >= 0`), fija `amount = closingLocal (+ sobrepago
convertido)` EXACTO en local, sin ida y vuelta. Si es parcial, delega en
l10n_ve_pos (conversión estricta).

#### Scenario: usuario teclea el total foráneo mostrado

- GIVEN cierre local 11.948 Bs, foráneo $17,70 (tasa 675)
- WHEN el usuario teclea 17,70 en la línea Zelle
- THEN amount = 11.948 exacto (no 11.950,9 por reconversión), cambio 0
