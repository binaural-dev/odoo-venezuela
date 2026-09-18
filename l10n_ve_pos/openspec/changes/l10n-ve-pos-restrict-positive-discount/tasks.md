# Tasks

## 1. Frontend (PdV)

- [x] 1.1 `static/src/overrides/models/pos_order_line.js`: helper
      `_isDiscountProductLine()` (`pos.config.discount_product_id`)
- [x] 1.2 Override de `setUnitPrice()` que coacciona a `-|price|` cuando la
      línea es de descuento, no es de reembolso y el precio resultante sería
      positivo; delega en `super` en el resto de casos
- [x] 1.3 `_isRefundLine()` exime también `order_id.isRefund` (orden marcada
      como reembolso por el core vía Órdenes → Reembolsar), no solo
      `refunded_orderline_id` / `preset_id.is_return`
- [x] 1.4 Parseo del precio sensible al locale: `_quantityAsNumber()` se
      generaliza a `_numberFromInput()` (mismo parser, ahora reusado por
      `setQuantity` y `setUnitPrice`) para no fallar con el separador decimal
      de `es_VE` (coma)
- [x] 1.5 `_numberFromInput()` prueba primero `Number()` nativo (mismo
      criterio que el `setUnitPrice` del core) antes de caer al parser de
      locale — corrige que un string con punto decimal armado por el propio
      core (`String(numero)` en la rama "+/-" con buffer vacío) se
      multiplicara ×100 al reinterpretar el punto como separador de miles
- [x] 1.6 `static/src/overrides/screens/product_screen/order_summary/order_summary.js`:
      override de `updateSelectedOrderline()` — "+/-" con buffer vacío en
      modo precio sobre la línea de descuento es no-op (el core arma ese
      caso desde `prices.total_excluded_currency`, que con un impuesto
      tax-included no es `price_unit`, y encogía el monto del descuento)

## 2. Backend

- [x] 2.1 `models/pos_order_line.py`: `@api.constrains("price_unit",
      "product_id", "order_id")` → `_check_discount_price_not_positive`
- [x] 2.2 Comparación con `float_compare` a la precisión `Product Price`
- [x] 2.3 Exenciones alineadas con el frontend y con la constraint hermana de
      cantidad: `refunded_orderline_id`, `order_id.is_refund`,
      `order_id.preset_id.is_return`
- [x] 2.4 Mensaje en inglés dentro de `_()` con formato
      `_("... %(clave)s", clave=valor)`

## 3. Traducciones

- [x] 3.1 `i18n/es_VE.po`: entrada de la `ValidationError` nueva (odoo-python)
- [x] 3.2 `msgfmt -c` sin errores nuevos

## 4. Verificación

- [x] 4.1 Test unitario (hoot) `setUnitPrice` sobre línea de descuento:
      monto entero (`"500"`), monto con coma decimal (`"500,50"`), número ya
      parseado (`+/-`), string con punto decimal armado por el core
      (`"-4842.69"`, `"4842.69"`), línea exenta por `order_id.isRefund`,
      línea que no es de descuento
- [x] 4.1b Test unitario (hoot) `OrderSummary.updateSelectedOrderline`: no-op
      en la línea de descuento con buffer vacío en modo precio. La condición
      vive aparte en `_shouldSkipDiscountLineSignToggle` (testeada directo,
      sin pasar por `super`) para no depender de que el core reviente sobre
      un stub incompleto como señal de "no se tomó la rama de no-op"
- [x] 4.1c Test unitario (hoot) `setQuantity` sobre línea de descuento con los
      mismos casos de parseo (`_numberFromInput` es compartido): entero,
      coma decimal, string con punto armado por el core
- [ ] 4.2 Navegador: "+/-" y tecleo de monto con decimales sobre la línea de
      descuento en locale `es_VE` → la línea permanece negativa
- [ ] 4.2b Navegador: "+/-" con buffer vacío sobre la línea de descuento con
      un impuesto tax-included → el monto no cambia (antes se encogía por el
      factor del impuesto, y al segundo "+/-" se multiplicaba por 100)
- [ ] 4.3 Navegador: descuento global en una orden reembolsada vía Órdenes →
      Reembolsar (sin preset de devolución) → el precio positivo legítimo no
      se altera
- [ ] 4.4 Backend: escribir `price_unit` positivo por RPC en una línea de
      descuento de una orden que no es de reembolso → `ValidationError`
- [ ] 4.5 `-u l10n_ve_pos` en una BD con órdenes de descuento históricas → la
      actualización no falla (`@api.constrains` no revalida datos existentes)

## 5. OpenSpec

- [x] 5.1 `proposal.md`, `specs/pos-restrict-positive-discount/spec.md`,
      `tasks.md`
- [x] 5.2 Directorio del change con prefijo `l10n-ve-pos-` (convención del
      resto de changes del módulo)
