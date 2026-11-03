## 0. Preparación y decisiones

- [x] 0.1 2026-11-02: el usuario aprueba las opciones recomendadas del plan: la moneda de cobro vive en
      `l10n_ve_pos`; se declara con un campo explícito en el método; el cajón en esa moneda es un modelo
      nuevo en `binaural_pos_close`; el reembolso devuelve esa moneda a la tasa con la que se cobró; el
      vuelto sigue en la moneda de la caja. Primero la caja en la moneda de la compañía.
- [x] 0.2 Rama `19.0_feat-ta_86066_pos_third_currency_cash` desde `origin/19.0` en odoo-venezuela y en
      integra-addons.
- [x] 0.3 Base de prueba `pos_test_86066` (copia de `pos_consultor`, módulos al día), tasas del 02 y 03-nov
      (1 $ = 860,4321 Bs, 1 € = 1.003,8765 Bs) y "Caja Bs EUR 86066" con efectivo Bs, efectivo USD
      (alterna, con cruce), efectivo EUR (moneda de cobro, con cruce) y Tarjeta.

## 1. Método y motor de conversión

- [x] 1.1 `pos.payment.method.tender_currency_id` con sus validaciones, en la vista y en la carga al PdV
- [x] 1.2 `pos.config.tender_currency_rates` (Json, `compute_rate` a la fecha del usuario)
- [x] 1.3 `_get_pos_conversion_rate` / `_getPosConversionRate` con la moneda de cobro; los pares de siempre
      sin cambios
- [x] 1.4 Loader de `res.currency` con las monedas de cobro; `res.currency` siempre completo
- [x] 1.5 `pos.config._check_tender_cash_methods_order` en la apertura

## 2. Pago

- [x] 2.1 `pos.payment.tender_currency_id` / `tender_amount`
- [x] 2.2 `PosPayment`: `getTenderCurrency`, `setTenderAmount`, `_getTenderRates`, `_getLocalDueBefore`,
      `_getTenderDue`, `_getPartialTenderLocalAmount`, `_recomputeTenderFromLocal`
- [x] 2.3 Pantalla de pago: precarga y teclado en la moneda de cobro, aviso sin tasa del día, línea
      "€ X / Bs Y", restante en esa moneda en el panel de estado, monto en el recibo
- [x] 2.4 Servidor: `_set_payment_tender_values`, signo en `_align_foreign_signs`,
      `get_refund_tender_rates` y su precarga en el reembolso
- [x] 2.5 `l10n_ve_pos_igtf`: `_getLocalDueBefore` con la deuda IGTF

## 3. Cruce

- [x] 3.1 `_is_cross_move_eligible` con la moneda de cobro
- [x] 3.2 `currency_amount` en `_create_cross_move_for` y en los constructores de líneas; solo se pasa para
      métodos con moneda de cobro (`_get_cross_currency_amount_kwargs`)

## 4. Pruebas

- [x] 4.1 Python `tests/test_pos_tender_currency.py`: motor, validaciones, valores del pago, tasa del
      reembolso, carga al PdV y cruces en efectivo, por pago y en banco. Suite completa de `l10n_ve_pos`
      en una base nueva con solo ese módulo, como el CI: 194 tests, solo fallaban los nuevos antes de
      ajustar su fixture; después, 22/22 de la clase
      (`odoo -c <conf> -d pos_t86066_ve -i l10n_ve_pos --test-tags /l10n_ve_pos --stop-after-init --no-http`)
- [x] 4.2 Hoot `static/tests/unit/payment_tender.test.js`: 15 tests en verde. La suite `@l10n_ve_pos`
      tiene los mismos 18 fallos con y sin el cambio (`partner_list_searched_vat`, `pos_order_line_discount`)
- [x] 4.3 PdV de punta a punta en `pos_test_86066` (Chrome headless): apertura con el cajón en €, conteo de
      billetes en €, venta exacta en € (8.500 Bs = 8,47 €), de más (10 € → vuelto 1.535,93 Bs), parcial
      (5 € + 11.980,62 Bs), entrada de 10 € con el botón de moneda, bloque del cierre (esperado 84,27 €).
      Pagos, facturas y asientos de pago revisados en la base
- [x] 4.4 Cierre de la sesión desde el PdV (83,27 € contados, pérdida de 1 € con su cruce; cruce de las
      ventas 74.555,31 Bs / 74,27 € / $86,65) y apertura siguiente con el contado anterior y 90 € contados
      (ganancia de 6,73 € = 6.756,09 Bs con su cruce, `ref` con el nombre de la sesión)

## 5. Cierre

- [ ] 5.1 Revisión con `code-reviewer` de Binaural antes de los PRs
- [ ] 5.2 Archivar el change y volcarlo en `openspec/specs/l10n_ve_pos/spec.md` y
      `openspec/specs/l10n_ve_pos_igtf/spec.md`
