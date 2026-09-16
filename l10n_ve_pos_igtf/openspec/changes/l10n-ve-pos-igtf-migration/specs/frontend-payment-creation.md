# Frontend Payment Creation Specification

> **Rediseñado 2026-07-09 (2ª iteración, pedido explícito de Jesús):** la
> línea de pago se precarga SOLO con el restante actual (`remainingDue`);
> el IGTF que genere esa línea nace DESPUÉS, como nuevo restante. Esto
> reemplaza el diseño anterior de "cierre en una línea" (base + deuda +
> IGTF nuevo), que estuvo vigente unas horas ese mismo día. No restaurarlo.

## Purpose

Define cómo se crean y precargan las líneas de pago en Odoo 19 cuando hay
métodos `apply_igtf`, y cómo interactúan con los montos foráneos.

## Regla central: precarga = remainingDue, sin caso especial

No existe ninguna rama especial por método. `addPaymentline` delega SIEMPRE
en el core y luego llama `update_igtf()`:

- El core precarga la línea vía `getDefaultAmountDueToPayIn` →
  `this.remainingDue` (`pos_order_accounting.js`), y `remainingDue` es
  NUESTRO getter: deuda de factura + deuda IGTF acumulada.
- La línea **nunca incluye el IGTF que ella misma va a generar**: ese lo
  calcula `update_igtf()` después (3% de la porción de BASE que cubre, ver
  `_igtfBaseState` en frontend-igtf-calculation.md) y aparece como nuevo
  restante, pagable con cualquier método.
- Consecuencia asumida: pagar una factura completa con un método
  `apply_igtf` son SIEMPRE dos líneas (y un parcial, tres).

#### Scenario A: pago completo con Zelle (factura 11.600 Bs = $17,19, 3%)

- Selecciono Zelle → línea precargada con 11.600 Bs ($17,19).
- Al asociarse, `update_igtf` genera 348 Bs → restante 348 ($0,52).
- Selecciono cualquier método → precarga 348; base restante = 0 → NO genera
  IGTF nuevo. Orden en 0; `amount_paid` = 11.948 = `amount_total + igtf`.

#### Scenario B: parcial de $10

- Zelle, tecleo $10 (6.750 Bs) → IGTF 202,50 → restante 5.052,50 ($7,49 =
  7,19 base + 0,30 deuda).
- Zelle de nuevo → precarga 5.052,50 completo; solo los 4.850 de base
  generan 145,50 **después** → restante 145,50 ($0,22).
- Cualquier método → 145,50, sin IGTF nuevo. IGTF total 348 exacto.

#### Scenario: sobrepago tecleado

- Primera línea Zelle, tecleo $20 → clamp fija 11.600 + sobrepago convertido;
  el excedente salda la deuda IGTF (348) y el resto es vuelto. IGTF sigue
  siendo 348 (tope: 3% de la factura).

## Requirement: sin bypass en PaymentScreen

`l10n_ve_pos_igtf/payment_screen.js::addNewPaymentLine` solo hace
`super(...)` + `update_igtf()` + `render()`. La precarga (incluido el
numberBuffer con formato locale y la conversión foránea) la maneja
`l10n_ve_pos/payment_screen.js`, porque la precarga deseada ES
`remainingDue`. El bypass anterior existía solo para el cierre en una línea.

## Requirement: IGTF-aware set_foreign_amount (clamp al restante)

`l10n_ve_pos_igtf/payment_model.js` parchea `set_foreign_amount`. Se activa
cuando hay contexto IGTF: método `apply_igtf` **o** deuda IGTF acumulada en
la orden (`_igtfRoundLocal(order.igtf_amount) !== 0`) — este segundo caso
cubre pagar la deuda IGTF con un método foráneo sin `apply_igtf`, donde el
clamp de l10n_ve_pos calcula el due desde `totalDue` (sin deuda) y la
conversión estricta produce drift (351 vs 348 Bs).

- Due de referencia: `sign * (remainingBase + unpaidIgtf)` de
  `_igtfBaseState(this)` — el restante actual, SIN el IGTF futuro de la línea.
- Si el foráneo tecleado lo cubre (`roundForeignMoney(requestedN - dueN) >= 0`
  en espacio normalizado por signo): fijar `amount` local EXACTO
  (+ sobrepago convertido), sin ida y vuelta.
- Parcial → delegar en super (l10n_ve_pos, conversión estricta).

#### Scenario: usuario teclea el restante foráneo mostrado

- GIVEN deuda IGTF 348 Bs ($0,52) y un método foráneo sin apply_igtf
- WHEN el usuario teclea 0,52
- THEN amount = 348 exacto (no 351 por reconversión), restante 0

## Requirement: creación vía API de modelos O19

Las líneas se crean por el flujo del core (`models["pos.payment"].create`
dentro de `addPaymentline` nativo). No queda creación manual en el módulo
(`add_paymentline_without_igtf` fue eliminado en este rediseño).
