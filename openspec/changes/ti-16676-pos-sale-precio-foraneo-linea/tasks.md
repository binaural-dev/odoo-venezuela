## 0. Decisiones

- [x] 0.1 Rama destino `19.0`, apilada sobre la del PR #1662 (ticket 16547, descuento global) porque este cambio
      extiende su código (design.md, D7). Ticket: 16676
- [x] 0.2 Confirmar la regla B: recalcular cuando cambia el precio sin un precio alterno nuevo (design.md, D4).
      Si se descarta, se quitan su requirement, el paso de `write` que la aplica y las pruebas 1.5 g
- [x] 0.3 Confirmar que el reembolso de una venta guardada sin alterno se calcula a la tasa de la venta original
      y no queda en 0 (design.md, D3)

## 1. l10n_ve_pos: el servidor completa el precio alterno (`models/pos_order_line.py`)

- [x] 1.1 Helper `_get_foreign_price_from_price_unit()` (design.md, D2):
      - caja en la moneda alterna: el precio unitario;
      - si no: `price_unit × order._get_payment_foreign_rate()`;
      - precisión "Foreign Product Price", HALF-UP, con signo;
      - sin tasa: `None`.
      Se verifica con las pruebas 1.5 a–d
- [x] 1.2 Helper `_fill_missing_foreign_price()` (D3): para las líneas con `foreign_price` en 0 y precio distinto de
      cero, copia primero el alterno de `refunded_orderline_id` y, si sigue en 0, aplica 1.1. `create` lo llama al
      final, en lugar del bucle actual del #15106. Se verifica con las pruebas del #15106 que no cambian
      (`test_refund_line_backfills_foreign_price_from_original`, `test_refund_line_keeps_existing_foreign_price`) y
      con 1.5 a, b, e y f
- [x] 1.3 `write` (D4):
      - regla A: `_fill_missing_foreign_price()` si `price_unit` o `foreign_price` vienen en `vals`;
      - regla B: antes de `super`, las líneas cuyo precio cambia (precisión "Product Price") y cuyo
        `foreign_price` no cambia; después, se recalculan con 1.1;
      - escrituras agrupadas por valor.
      Se verifica con 1.5 g
- [x] 1.4 Como la rama está sobre la del #1662: `_sync_global_discount_foreign_price` llama a 1.1 en vez de
      repetir la fórmula. Se verifica con `tests/test_pos_global_discount_foreign_price.py` en verde
- [x] 1.5 Pruebas nuevas en `tests/test_pos_line_foreign_price_backfill.py` (registrarlo en `tests/__init__.py`;
      base `TestPosSessionAccountingBase`, tasa 36,5):
      - a. línea de venta con precio 100 y `foreign_price` 0 → 3.650,0;
      - b. precio -15 → -547,5;
      - c. precisión "Foreign Product Price" fijada en 2 dentro de la prueba y precio 1,2345 → 45,06
        (1,2345 × 36,5 = 45,05925);
      - d. caja en la moneda alterna → el precio unitario (caja con diario en VEF; si la base no lo permite,
        el helper sobre una orden de esa caja);
      - e. un alterno presente (3.600) se conserva; con precio 0 o con la orden sin tasa queda en 0;
      - f. reembolso: una original con 3,45 da 3,45 aunque precio × tasa dé otro valor; una original en 0
        (forzado por SQL) con el reembolso a tasa 40 da precio × 36,5;
      - g. `sync_from_ui` dos veces con el mismo uuid (patrón de `test_pos_serialization.py:248`); el segundo
        sync manda la línea como `[1, id, vals]`:
        - con `foreign_price` 0 → sigue en 3.650;
        - con precio 120 y el alterno viejo 3.650 → 4.380;
        - con precio 120 y alterno 4.400 enviado → 4.400;
      - h. alterno que redondea a 0 (precisión 2, tasa 1/600, precio 2) → 0,00 sin error ni recursión; con
        `write` a 600 → 1,00 y de vuelta a 2 → 0,00; también por `sync_from_ui`;
      - ve. configuración de Venezuela (tasa 1/600, precisión 2): casos a, b, g y h;
      - kiosko: `recompute_prices` con un alterno que redondea a 0 no recursa;
      - línea nueva en una orden de reembolso usa la tasa de su orden.
      Se verifica con la suite del archivo en verde
- [x] 1.6 `tests/test_pos_refund_foreign_price.py`:
      - `test_non_refund_line_foreign_price_untouched` pasa a "una línea de venta sin alterno se completa"
        (o se borra, porque queda cubierta en 1.5 a);
      - `test_refund_line_no_backfill_when_original_has_no_foreign_price` fuerza el 0 de la original por SQL
        y espera precio × tasa original.
      Se actualiza el docstring del módulo. Se verifica con el archivo en verde
- [x] 1.7 `l10n_ve_pos_self_order/tests/test_kiosk_invoice_foreign_debit_credit.py`: en
      `test_kiosk_order_line_foreign_price_filled_by_recompute`, la precondición `foreign_price == 0.0` ya no se
      cumple al crear la orden. Forzar el 0 por SQL (para seguir probando `recompute_prices`) o quitarla. Se
      verifica con la suite de `l10n_ve_pos_self_order` en verde

- [x] 1.8 Pruebas de escenarios `pos_sale` en `tests/test_pos_sale_foreign_price_scenarios.py` (simulan el payload
      del PdV con `foreign_price` 0; no ejecutan el JS; `skipTest` si falta `sale_order_line_id`). Se verifican
      con el archivo en verde:
      - `test_downpayment_payment_line_is_filled`: pago de un anticipo, línea positiva → tasa del PdV, también en
        la factura;
      - `test_settle_remainder_with_negative_downpayment_line`: producto + anticipo descontado (negativo) → todas a
        la tasa del PdV con signo, y la factura las lleva;
      - `test_split_lines_with_same_sale_order_line`: dos líneas con el mismo `sale_order_line_id` (partidas por
        lote o UoM) → ambas completas y la factura con las dos;
      - `test_combo_children_are_filled_and_parent_stays_zero`: padre de combo en 0 queda en 0, hija con precio se
        completa, y en la factura no hay líneas de producto en 0 con precio ≠ 0;
      - `test_refund_of_settled_order_reverses_original_foreign_price`: orden liquidada a tasa 36,5, reembolso a
        tasa 40 con alterno 0 → copia el de la original, y la NC lleva el alterno de la factura de origen
- [x] 1.9 `TestPosSaleForeignPriceVesCompany` (mismo archivo): compañía en VES con alterna USD, caja y diario de
      factura en VES, tasa 1/600 y precisión 2. El fixture `TestPosSessionAccountingBase` se parametrizó
      (19.0 ya traía `company_currency_name` y `foreign_currency_name`; se agregó `sales_in_foreign`, cuyo valor por
      defecto no cambia nada).
      `test_settled_sale_order_invoice_foreign_amounts` sincroniza con `sync_from_ui` una orden `pos_sale` de dos
      líneas (600 Bs con IVA 8 % y 1.234,56 Bs con IVA 22 %) y asevera `foreign_price`, `foreign_subtotal` y
      `foreign_credit` (1,00 y 2,06), el IVA alterno (0,53), la CxC alterna = `foreign_amount_total` (3,59, ±0,01) y
      la suma de `foreign_balance` = 0

## 2. l10n_ve_pos: red de seguridad en la factura (`models/pos_order.py`)

- [x] 2.1 En `_get_invoice_lines_values` (D5), después de la regla de reembolso que ya existe: si `foreign_price`
      sigue en 0, el precio no es cero y el valor devuelto es una línea de producto, usar 1.1. No se escribe en la
      línea de orden. Se verifica con 2.2
- [x] 2.2 Pruebas de factura en el archivo de 1.5, con `_create_rate_of_day(40.0)` para que la tasa del día
      difiera de la del PoS, y `order._create_invoice(order._prepare_invoice_vals())`. Lo que se asevera:
      - con líneas creadas sin alterno y con la línea de orden en 0 forzado por SQL (la línea de orden sigue en
        0): `foreign_price` 3.650 y `foreign_subtotal` 3.650 en cada línea de producto de la factura, y el IVA
        alterno 584 (solo en el primer caso).
      No se asevera `foreign_credit`, la CxC ni la suma de `foreign_balance`: en el fixture el diario de la
      factura está en la moneda alterna y `l10n_ve_accountant` deriva débito/crédito alterno del importe en
      moneda de la factura. Esa parte la cubre 1.9 (compañía VES) y la verificación de punta a punta (4.2)
- [x] 2.3 Caso `pos_sale` en el mismo archivo, con `skipTest` si `sale_order_line_id` no está en
      `pos.order.line` (D8). Se crea una orden de venta de dos líneas (marcada `sale` por `write`, porque
      confirmar falla en el fixture por rutas de stock) y una orden del PdV con dos líneas con
      `sale_order_origin_id`, `sale_order_line_id` y `foreign_price` 0. Se asevera que las líneas y las líneas
      de producto de la factura quedan con `foreign_price` 100 × 36,5, con la tasa del día distinta (40)

## 3. Manifest y documentación

- [x] 3.1 Subir `l10n_ve_pos/__manifest__.py` de 19.0.1.30.1 (versión del #1662) a 19.0.1.30.2 (D9). Se verifica con `-u l10n_ve_pos` sin errores en una base de prueba
- [x] 3.2 Docstrings de `create`, `write`, los helpers y `_get_invoice_lines_values`: causa (`534aaac9114d`,
      `pos_sale` sin `super`), regla y ticket. El docstring actual de `create` habla solo de reembolsos. Se
      verifica con pre-commit verde sobre los archivos tocados

## 4. Verificación integrada

- [x] 4.1 Suites completas en una base nueva sobre la rama, sin tocar las instancias (worktree con puertos
      propios): `odoo -d <base nueva> -i l10n_ve_pos,l10n_ve_pos_self_order,pos_sale,pos_discount
      --test-tags /l10n_ve_pos,/l10n_ve_pos_self_order --stop-after-init`. `l10n_ve_pos_igtf` y `l10n_ve_pos_mf`
      van en otra base si el CI las separa. Sin fallos nuevos
- [x] 4.2 PdV en una base con `pos_sale` (copia de `posconsultoria_ti16585`, con la rama aplicada): liquidar una
      orden de venta de dos líneas y cobrar. En Contabilidad > Apuntes, las líneas de producto llevan alterno, la
      CxC es igual al `foreign_amount_total` de la orden (2,30 USD en el ejemplo del ticket) y el asiento cuadra
      en alterno
      Verificado con script `sync_from_ui` simulado sobre copia de `posconsultoria_ti16585`: sin fix, CxC 0,55
      vs 3,86; con fix, 3,86 = 3,86; caso borrador con precio editado 750 → 900 → 1,50 y CxC 4,13 = 4,13; tasa
      de caja 650 ≠ día 600 ≠ orden de venta 500 → usa 650; red de seguridad de factura OK. Falta el PdV real en
      navegador
- [x] 4.3 Ruta `write`: liquidar una orden de venta, abrir la pantalla de órdenes (sincroniza el borrador), volver,
      cambiar el precio de una línea de la orden de venta y cobrar. El alterno de la línea y de la factura
      corresponde al precio nuevo
      Verificado con script `sync_from_ui` simulado sobre copia de `posconsultoria_ti16585`: sin fix, CxC 0,55
      vs 3,86; con fix, 3,86 = 3,86; caso borrador con precio editado 750 → 900 → 1,50 y CxC 4,13 = 4,13; tasa
      de caja 650 ≠ día 600 ≠ orden de venta 500 → usa 650; red de seguridad de factura OK. Falta el PdV real en
      navegador
- [ ] 4.4 Anticipo (porcentaje y monto fijo), liquidación de una orden con anticipo ya pagado y producto con UoM no
      agrupable o con lotes (líneas partidas): la consulta de líneas del PdV de design.md no devuelve nada para
      esas órdenes
      Cubierto en el servidor por `test_downpayment_payment_line_is_filled`,
      `test_settle_remainder_with_negative_downpayment_line` y `test_split_lines_with_same_sale_order_line` (payload
      simulado). Falta el PdV real en navegador (el payload real y la consulta de líneas en 0)
- [ ] 4.5 Combo: vender un combo y revisar el `foreign_price` de las hijas en la base y en la factura. Confirma o
      descarta la hipótesis de design.md (Context y Risks)
      Cubierto en el servidor por `test_combo_children_are_filled_and_parent_stays_zero` (payload simulado). La
      hipótesis de que el core manda las hijas en 0 sigue sin confirmar: falta el navegador
- [ ] 4.6 Reembolso desde el PdV de una orden liquidada: la NC revierte el alterno de la factura a la tasa de la
      venta
      Cubierto en el servidor por `test_refund_of_settled_order_reverses_original_foreign_price` (payload simulado).
      Falta el reembolso real desde el PdV
- [ ] 4.7 Regresión: venta normal, descuento global (#16547), reembolso (#15106) e impresión fiscal con
      `l10n_ve_pos_mf`, sin cambios

## Workflow follow-up

- Decidir con cada cliente la reparación de los datos ya registrados (design.md, "Datos ya afectados").
- PR con "Ticket: https://binaural.odoo.com/odoo/all-tickets/<id>". Nota en el chatter solo después de que se
  pruebe la rama en la instancia.
- Archivar el change después de la revisión. `reembolso-precio-foraneo-linea` se archiva aparte, cuando se
  cierren sus pruebas de navegador (2.1 a 2.5); su texto ya quedó conciliado con este change.
