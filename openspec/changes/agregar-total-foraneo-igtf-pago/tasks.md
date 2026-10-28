## 1. l10n_ve_pos — total foráneo bajo el monto más grande

- [x] 1.1 Subir el tamaño del total foráneo en `payment_screen_top.xml` (`fs-3` → `fs-2`)

## 2. l10n_ve_pos_igtf — total foráneo con IGTF

- [x] 2.1 Getter de orden `get_foreign_total_with_igtf()` en `order_model.js` (espejo foráneo de `get_total_with_igtf`)
- [x] 2.2 Getter de pantalla `foreignTotalWithIgtfAmount` en `payment_status.js`
- [x] 2.3 Mostrar el equivalente foráneo bajo "TOTAL a Pagar con IGTF" en `payment_status.xml`

## 3. Verificación

- [ ] 3.1 Probar en navegador: cobro con método `apply_igtf` muestra el total foráneo bajo "TOTAL a Pagar con IGTF" y coincide con la conversión del total con IGTF
- [ ] 3.2 Verificar que órdenes sin IGTF no ven el bloque (sin regresión)
