## 1. Modelo

- [x] 1.1 `order_model.js`: `get_total_paid_with_igtf()` = `get_total_without_igtf() + igtf_amount`, redondeado con `_igtfRoundLocal` (espejo del backend `_get_total_with_igtf()`)
- [x] 1.2 `order_model.js`: `get_foreign_total_paid_with_igtf()` = `get_foreign_total_with_tax() + foreign_igtf_amount`, redondeado con `roundForeignMoney`
- [x] 1.3 Comentario que distingue estos getters de `get_total_with_igtf()` (3% fijo de la factura completa, solo para el panel de estado de pago)

## 2. Pantalla de recibo

- [x] 2.1 `receipt_screen.js` (nuevo): parche de `ReceiptScreen.prototype` con `igtfAmount`, `igtfAmountLabel`, `foreignIgtfAmountLabel`
- [x] 2.2 `receipt_screen.js`: `orderAmountPlusTip` — copia del core con `+ igtf`, delegando en `super()` cuando no hay IGTF; marcado REVISAR EN CADA UPGRADE
- [x] 2.3 `receipt_screen.js`: `foreignOrderAmountWithIgtf`, con fallback a `get_foreign_total_with_tax()` sin IGTF
- [x] 2.4 `receipt_screen.xml` (nuevo): reemplaza por expresión (`contains(@t-out, 'get_foreign_total_with_tax')`) el total foráneo que inserta `l10n_ve_pos`
- [x] 2.5 `receipt_screen.xml`: renglón "IGTF: … / …" bajo el total, con `t-if="igtfAmount"`

## 3. Verificación

- [x] 3.1 Comprobada la cadena de herencia `point_of_sale` → `l10n_ve_pos` → `l10n_ve_pos_igtf` fuera de Odoo (lxml + `hasclass`): ambos xpath casan con un único nodo y el badge "Edit Payment" sigue siendo hermano de los montos
- [ ] 3.2 Probar en POS real el repro de Jesús: factura 12.806,40 Bs / $17,37, pago de 7.372,30 con método `apply_igtf` (IGTF 221,17 / $0,30) + 5.655,27 en Bs → el recuadro debe mostrar **13.027,57 Bs / $ 17,67** y el renglón "IGTF: 221,17 Bs.F / $ 0,30"
- [ ] 3.3 Regresión: orden SIN método `apply_igtf` → el recuadro debe mostrar exactamente lo de siempre (total de factura en ambas monedas, sin renglón IGTF)
- [ ] 3.4 Regresión: el subtítulo foráneo del panel de estado de pago y el voucher impreso siguen mostrando el total de factura SIN IGTF (no se rompió el fix de 2026-07-14)

## 4. Pendiente / fuera de alcance

- [ ] 4.1 Decidir si el voucher impreso (`OrderReceipt`) debe llevar también la línea de IGTF y el total cobrado
- [ ] 4.2 Reimpresión desde la lista de órdenes de una sesión cerrada: cae al comportamiento nativo porque `igtf_amount` es prop JS plana y no se recarga del backend (no puede ir en `_load_pos_data_fields`)
