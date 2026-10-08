# Tasks

## 1. Monto en divisa de los combos

- [x] 1.1 `pos_order_line.js`: `get_foreign_display_price()` (criterio de
      `displayPrice` del core; en el padre del combo, suma de las hijas)
- [x] 1.2 `orderline.xml`: usar `get_foreign_display_price()` y pintarlo solo
      con `vals.price`
- [x] 1.3 Test hoot `pos_order_line_combo_foreign.test.js` (incluido,
      excluido, línea normal, reembolso a tasa original)

## 2. Verificación

- [ ] 2.1 Correr los tests hoot de `l10n_ve_pos` (no corridos: arreglo puntual, verificado en navegador)
- [x] 2.2 Navegador, caja en moneda principal: combo con impuestos incluidos y
      separados (posv19, caja 81: $ 17,00 / $ 15,00)
- [x] 2.3 Navegador: reembolso de un combo con la tasa del día cambiada (900
      en el cliente): el padre muestra $ 17,00 a la tasa original
- [x] 2.4 Navegador: ticket screen (orden sincronizada a tasa congelada) y
      pantalla de pago
- [x] 2.5 Navegador, todas las cajas de posv19 (1, 4, Kiosko, VES, USD x2,
      EUR): cada monto cuadra con su conversión multiplicando

## 3. OpenSpec

- [x] 3.1 `openspec validate`
