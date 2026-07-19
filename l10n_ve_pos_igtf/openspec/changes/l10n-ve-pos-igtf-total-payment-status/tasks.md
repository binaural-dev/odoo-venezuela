## 1. Modelo

- [x] 1.1 `order_model.js`: nuevo `get_total_with_igtf()` = `get_total_without_igtf() + igtf_amount`, redondeado con `_igtfRoundLocal`, sin tocar `get_total_with_tax()`/`get_foreign_total_with_tax()`

## 2. Panel de estado de pago

- [x] 2.1 `payment_status.js`: nuevo getter `totalWithIgtfAmount` (formatCurrency sobre `get_total_with_igtf()`)
- [x] 2.2 `payment_status.xml`: renglón "TOTAL a Pagar con IGTF:" bajo el desglose BI IGTF/IGTF/Foreign IGTF existente, separado con `border-top`, tipografía grande, monto al borde derecho
- [x] 2.3 `payment_status.xml`: `text-dark` en el div del bloque IGTF para que no herede el `text-danger`/`text-success` del `.paymentlines-container` nativo

## 3. Verificación funcional

- [ ] 3.1 Probar en POS real: factura con método `apply_igtf`, confirmar que el renglón nuevo muestra total factura + 3% y que el subtítulo foráneo bajo el total nativo sigue SIN IGTF (no se rompió el fix de 2026-07-14)
