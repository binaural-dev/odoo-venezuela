# Tasks

## 1. Tests

- [x] 1.1 `static/tests/unit/payment_lines_layout.test.js`: monta
      `PaymentScreenPaymentLines` (App de Owl con env mínimo: el entorno
      simulado de web arranca los servicios del bundle, que piden datos al mock
      server) en 427 px, el ancho de la columna medido en posv19, y mide la
      geometría real (el bundle de tests carga Bootstrap): la línea foránea
      muestra sus dos montos enteros en una segunda fila, la línea corta sigue
      en una fila y un par extremo se parte por el " / " sin recortarse. Rojo
      con la plantilla anterior (contenido de 497 px en 362 px)

## 2. Corrección

- [x] 2.1 `payment_line.xml`: `.payment-infos` con `flex-wrap`, nombre en
      `span.payment-name.text-truncate`, `.payment-amount` con `text-end`, cada
      monto sin cortes y el segundo en `inline-block`, en los dos bloques
- [x] 2.2 Code review: un par demasiado largo se recortaba sin "…" con
      `.payment-amount` en `text-nowrap`; ahora se parte por el " / "; test con
      geometría en vez de clases; comentario de cabecera corregido. Segunda
      pasada: el espacio antes del "/" se perdía dentro del `inline-block` → margen
      `ms-1`; el test afirma la separación entre los dos montos

## 3. Verificación

- [x] 3.1 Hoot `payment_lines_layout` 2/2 en verde (posv19, 07-oct); `@l10n_ve_pos/` 89/106
      (los 17 de `pos_order_line_discount`, previos); `@binaural_pos_multicurrency/`
      12/12 y sus tours 3/3 (integra, PR #2896). Sin cambios de Python: los tests
      Python de `l10n_ve_pos` no aplican
- [x] 3.2 Navegador (posv19, 07-oct, con la plantilla final): Caja VES con
      Efectivo USD 70 $ → "$ 70,00 / 56.233,80 Bs.F" entero en una segunda fila
      (antes "$ 70,00 / 56.2…"); Caja USD con Banco Bs → "54.627,12 Bs.F /
      $ 68,00"; Caja EUR con Efectivo EUR → "58,10 € / 54.628,53 Bs.F"; en las
      tres sin recorte y con 4 px entre los montos
