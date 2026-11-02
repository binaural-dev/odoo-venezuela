# Tasks

## 1. Tests

- [x] 1.1 `static/tests/unit/payment_model.test.js`: el test del #15114 ("snap
      solo dentro de un paso foráneo", rojo en origin/19.0: −3.600,4) y casos
      nuevos (89,99 / 89,98, deuda fuera del céntimo, tasa 36,5, moneda sin
      resolver)

## 2. Corrección

- [x] 2.1 `payment_model.js`: decisión en divisa con `currency.comp` sobre la
      deuda mostrada; respaldo con `roundPrecision`

## 3. Verificación

- [x] 3.1 Hoot (`/web/tests?debug=assets&filter=payment_model`, posv19, 06-oct): toda la suite
      `payment_model` en verde, incluido el test del #15114; los 3 fallos del filtro son
      ajenos (`pos_enterprise` preparation_display ×2, `pos_online_payment_self_order`)
