# Tasks

## 1. Frontend (PdV)

- [x] 1.1 `static/src/overrides/models/pos_order_line.js`: en `setUnitPrice`,
      tras `super.setUnitPrice(...)` y antes de derivar `foreign_price`,
      redondear `this.price_unit` con `order.roundLocalMoney()` (orden en
      moneda principal) u `order.roundForeignMoney()` (rama
      `_is_order_in_foreign_currency()`)
- [x] 1.2 Guardar con `typeof order.roundLocalMoney === "function"` para no
      romper si `setUnitPrice` corre antes de que la orden esté lista
- [x] 1.3 Comentario que explica el porqué (paridad con la MF, Flag 21=00),
      que es aguas arriba de foránea/IGTF y que rompe a propósito la
      convención "unit prices NO se redondean a moneda"

## 2. Manifest

- [x] 2.1 `__manifest__.py`: bump de versión `1.10 → 1.11`

## 3. Prerequisito de configuración (no es código de este módulo)

- [x] 3.0 Impuesto `16% Ventas` → **`price_include = tax_excluded`** (No
      incluido), porque la MF está fiscalizada en modo "suma IVA" y su tipo de
      tasa está bloqueado (no reprogramable por comando). Sin esto, el doble
      IVA del 16% domina y este redondeo no basta.

## 4. Verificación manual en navegador (hecha — confirmada por el usuario)

- [x] 4.1 Con el impuesto en `tax_excluded` **y** este redondeo, y la sesión del
      PdV recargada: 4 uds del producto (unitario `5.068,87` neto), pago en
      divisa → la MF calcula base `20.275,48` + IVA `3.244,08` = `23.519,56`
      + IGTF `705,58` = **`24.225,14`**, el `199` cierra **ACK** y la factura
      imprime completa
- [x] 4.2 A/B: con el redondeo en stash (solo el fix de impuesto) el `199`
      seguía dando NAK por ~2 cts (Odoo `24.225,12` vs MF `24.225,14`) →
      confirma que el redondeo hace falta por debajo
- [ ] 4.3 Caso **con descuento** en una línea con unitario de >2 decimales,
      pago en divisa → confirmar que el `199` también cuadra (o anotar si
      reaparecen céntimos por el redondeo del descuento)
- [ ] 4.4 Regresión moneda foránea: precio/subtotal/total en $ por línea y su
      suma vs el total de la orden siguen coherentes
- [ ] 4.5 Regresión IGTF: `TOTAL a Pagar con IGTF` y el IGTF por línea siguen
      correctos; venta mixta (divisa + Bs) reparte IGTF sólo sobre la parte en
      divisa

## 5. OpenSpec

- [x] 5.1 `proposal.md`, `design.md`, `tasks.md`
- [x] 5.2 `specs/pos-unit-price-currency-rounding/spec.md` (delta ADDED)
- [ ] 5.3 `openspec validate --changes` (correr al cerrar)

## 6. Cierre (pendiente — requiere confirmación del usuario)

- [ ] 6.1 Commit en el submódulo `odoo-venezuela`
      (rama `19.0_fix-ta_78328_mf_port_handoff`) y actualización del puntero
      del padre
