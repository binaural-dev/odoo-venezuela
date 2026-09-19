## 1. l10n_ve_pos — precio unitario foráneo a plena precisión

- [x] 1.1 En `pos.order.line._foreignUnitPriceDp()` (JS), leer la dp "Foreign Product Price" desde `this.models["decimal.precision"].find((dp) => dp.name === "Foreign Product Price")` (Odoo 19), reemplazando el inexistente `this.pos.dp["Foreign Product Price"]`. Mantener el fallback a los decimales de la moneda foránea
- [x] 1.2 Bump de manifest `l10n_ve_pos` 1.13 → 1.14
- [x] 1.3 Unit tests JS (`static/tests/unit/pos_order_line_foreign_dp.test.js`): `_foreignUnitPriceDp` devuelve la dp de catálogo cuando está cargada; cae a los decimales de la moneda si no; `get_foreign_unit_price` conserva la precisión de catálogo (no trunca a 2)

## 2. Verificación

- [ ] 2.1 Probar en navegador: vender con cantidad > 1 (p. ej. 4) y facturar. En Contabilidad → Apuntes contables, el asiento de la factura cuadra en USD contra lo cobrado, y cada línea es consistente (precio unitario × cantidad = subtotal)
- [ ] 2.2 Regresión IGTF: venta con pago en divisa (IGTF) → la venta cuadra y el IGTF queda igual (sus líneas viven en el asiento del pago)
- [ ] 2.3 Regresión IVA incluido: una venta con impuesto incluido sigue cuadrando (sin cambios)
- [ ] 2.4 Regresión reembolso: la NC sigue revirtiendo el alterno a la tasa de la venta original (backfill del #15106 intacto)
