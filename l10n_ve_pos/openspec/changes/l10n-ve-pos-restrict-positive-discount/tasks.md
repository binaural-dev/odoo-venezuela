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

- [ ] 4.1 Test unitario (hoot) `setUnitPrice` sobre línea de descuento:
      monto entero (`"500"`), monto con coma decimal (`"500,50"`), número ya
      parseado (`+/-`), línea exenta por `order_id.isRefund`, línea que no es
      de descuento
- [ ] 4.2 Navegador: "+/-" y tecleo de monto con decimales sobre la línea de
      descuento en locale `es_VE` → la línea permanece negativa
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
