# Tasks

## 1. Monto en divisa de los combos

- [x] 1.1 `pos_order_line.js`: `get_foreign_display_price()` = `displayPrice`
      del core convertido una vez (en el padre del combo, suma de las hijas)
- [x] 1.2 `orderline.xml`: usar `get_foreign_display_price()` y pintarlo solo
      con `vals.price`
- [x] 1.3 Test hoot `pos_order_line_combo_foreign.test.js` (incluido,
      excluido, línea normal, reembolso a tasa original, tasa congelada,
      conversión única sin acumular redondeos)
- [x] 1.4 Versión 19.0.1.21.0
- [x] 1.5 `components/orderline/orderline.js`: las hijas del combo muestran su
      parte del precio en las dos monedas (antes del fix tenían el "/ $"
      suelto; con el `t-if` se quedaron sin precio), con su test hoot
      `orderline_combo_child_price.test.js`

## 2. Verificación

- [x] 2.1 Correr los tests hoot de `l10n_ve_pos`: 18/18 en verde en una BD nueva
      (20-oct, estado final de este PR y de integra-addons#2996):
      `odoo -d <bd_nueva> -i binaural_pos_multicurrency --test-tags "/web:WebSuite.test_unit_desktop[@l10n_ve_pos/unit/pos_order_line_combo_foreign,@l10n_ve_pos/unit/orderline_combo_child_price,@binaural_pos_multicurrency/unit/pos_order_line_company_price]"`.
      El test de las hijas (1.5) no se había corrido: fallaba porque
      `lineScreenValues` formatea y traduce sin localización ni traducciones
      cargadas; corregido en el propio test.
- [x] 2.2 Navegador, caja en moneda principal: combo con impuestos incluidos y
      separados (posv19, caja 81: $ 17,00 / $ 15,00)
- [x] 2.3 Navegador: reembolso de un combo con la tasa del día cambiada (900
      en el cliente): el padre muestra $ 17,00 a la tasa original
- [x] 2.4 Navegador: ticket screen (orden sincronizada a tasa congelada) y
      pantalla de pago
- [x] 2.6 Navegador (posv19, 14-oct): hijas en caja VES (Bs 8.033,40 / $ 10,00
      y Bs 4.016,70 / $ 5,00) y en caja USD ($ 8,62 / Bs 6.925,34 y $ 4,63 /
      Bs 3.719,17)
- [x] 2.5 Navegador, todas las cajas de posv19 (1, 4, Kiosko, VES, USD x2,
      EUR): cada monto cuadra con su conversión multiplicando

## 3. OpenSpec

- [x] 3.1 `openspec validate`
- [x] 3.2 El delta va en su propia capability, `pos-orderline-foreign-display`,
      no en `pos-refund-original-rate` (code review)
