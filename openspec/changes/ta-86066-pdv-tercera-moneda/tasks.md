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

## 5. Revisión del `code-reviewer` (2026-11-03, cambios pedidos)

- [x] 5.1 Hallazgo 1 (orden de despliegue): `payment_line.xml` conserva
      `t-if="line.payment_method_id?.is_foreign_currency"`; la rama de la moneda de cobro va por fuera
      (`t-if getTenderCurrency()` / `t-else` con el bloque de siempre), en la línea seleccionada y en la
      no seleccionada. Probado con el `binaural_pos_multicurrency` de `origin/19.0` (checkout temporal de
      integra-addons en `origin/19.0`, base `pos_t86066_old` = copia de `pos_consultor` con
      `-u l10n_ve_pos`): el PdV carga, la Caja 1 muestra "Efectivo USD $9,88 / 8.500,00 Bs" y la Caja EUR
      las dos ramas de multicurrency ("Pago movil Bs / €", "Efectivo CajaEUR € / Bs"), sin errores en la
      página. En ese intermedio la lista y el formulario de `pos.payment` muestran `tender_amount` dos
      veces (la vista vieja de multicurrency), hasta actualizar integra-addons.
- [x] 5.2 Hallazgo 4 (cobro desde el backend): `_set_payment_tender_values` en `_process_saved_order`, que
      usan la sincronización y `pos.make.payment`, antes de `_align_foreign_signs`; sin `tender_amount`,
      un reembolso toma la tasa de los cobros originales (`_get_payment_tender_amount`).
- [x] 5.3 Hallazgo 5 (caja en otra moneda): restricción en `pos.config`
      (`_check_tender_currency_methods_currency`) y en el método (`_check_tender_currency`, con
      `config_ids`); `_compute_tender_currency_rates` con `with_company(config.company_id)`; el fixture de
      la prueba ya no fuerza `allowed_company_ids`.
- [x] 5.4 Hallazgo 6 (cruce combinado): `_get_combined_cross_legs` + `_create_combined_cross_move`: un
      asiento por método y sesión con la pata de entradas y la de salidas, cada una construida como el
      cruce de un pago (`_get_cross_move_line_vals`, con la inversión de `use_suspense`); nada solo si los
      netos en la caja, la alterna y la moneda de cobro son cero. `binaural_pos_multicurrency` lo usa
      igual en `_validate_cross_move_in_session_currency`.
- [x] 5.5 Sugerencias: `_get_cross_real_amount_currency` convierte con `config._convert` si no llega
      `currency_amount`; `split_transactions` fuera del `@api.constrains`; `tender_currency_id` /
      `tender_amount` en la lista y el formulario de `pos.payment`; conflicto posible con
      odoo-venezuela#1529 anotado en `proposal.md`.
- [x] 5.6 Traducciones es_VE agregadas al final del `.po` (`msgfmt -c` sin errores); versiones
      `l10n_ve_pos` 19.0.1.29.1 y `l10n_ve_pos_igtf` 19.0.1.5.2.
- [x] 5.7 Pruebas Python (base nueva solo con `l10n_ve_pos`, como el CI):
      `odoo -c <conf> -d pos_t86066_ve -u l10n_ve_pos --test-tags /l10n_ve_pos --stop-after-init --no-http`
      → 236 tests, 0 fallos. Cambian de comportamiento y se actualizaron
      `test_combine_net_negative_uses_outgoing_branch` y `test_cash_sale_net_negative_mirrors_the_entry`
      (el neto sigue igual, ahora en dos patas); nuevas `test_combine_opposite_sign_nets_cross_each_leg_on_its_own`
      y `test_combine_zero_net_in_the_pos_currency_still_crosses_the_foreign_amount`.
      `test_pos_tender_currency.py` corre dos veces: compañía USD/VEF y compañía en Bs con alterna USD
      (`TestPosTenderCurrencyBsCompany`, `allow_inherited_tests_method`); nuevas: `sync_from_ui` sin llamar
      a mano a `_set_payment_tender_values`, cobro y reembolso desde `pos.make.payment`, tasas de la
      compañía de la caja, restricción en caja en otra moneda, cruce sin `currency_amount` y los tres
      casos del combinado en euros.
- [x] 5.8 `l10n_ve_pos_igtf`: base nueva `pos_t86066_igtf`
      (`-i l10n_ve_pos_igtf --test-tags /l10n_ve_pos_igtf`) → 12 tests Python en verde; bundle
      `web.assets_unit_tests` nuevo y Hoot `payment_tender_igtf.test.js` (4 tests de
      `_getLocalDueBefore`) en verde (`@l10n_ve_pos_igtf/`: 15 pasan). El parche importa el de
      `l10n_ve_pos` para aplicarse después también en Hoot.
- [x] 5.9 Hoot `@l10n_ve_pos/` en `pos_test_86066`: 135 pasan y los mismos 18 fallos previos
      (`partner_list_searched_vat`, `pos_order_line_discount`). Precommit de los cinco módulos en verde.

- [x] 5.10 De punta a punta: Caja 78 de `pos_test_86066` desde el PdV (Chrome headless), después de
      `-u l10n_ve_pos,l10n_ve_pos_igtf,binaural_pos_multicurrency,binaural_pos_close,binaural_pos_close_multicurrency`.
      Sesión 00122: venta exacta 8,47 € = 8.500 Bs; de más, 10 € = 10.035,93 Bs con vuelto de 1.535,93 Bs;
      parcial, 5 € (5.019,38 Bs) + 11.980,62 Bs; 25,40 € = 25.500 Bs; entrada de 10 € (10.038,77 Bs, cruce
      con −10 €); reembolso de la primera con −8,47 € (tasa original). Pagos con moneda EUR y sus euros;
      asientos de pago en Bs con su USD. Cierre: esperado 140,40 €, contados 139,40 € → pérdida de 1 €
      (1.003,88 Bs, $1,17) con su cruce; cruce de las ventas en dos patas (49.055,31 Bs / $57,01 / 48,87 € y
      8.500 Bs / $9,88 / 8,47 €); asiento de la sesión cuadrado en Bs y USD. Sesión 00123: apertura con
      141,40 € contra 139,40 € → ganancia de 2 € (2.007,75 Bs, $2,33) con su cruce y la `ref` de la sesión;
      con el € a 1.400 Bs, venta de 24,29 € = 34.000 Bs y reembolso de la venta de 25,40 € a su tasa
      (−25.500 Bs; a la del día habrían sido 18,21 €); cierre sin diferencia (140,29 €) con el cruce en dos
      patas (34.000 Bs / $39,52 / −24,29 € y 25.500 Bs / $29,64 / +25,40 €). Con un solo neto, la línea de
      la caja real en EUR habría sido −8.500 Bs contra +1,11 € y el cierre chocaba con
      `account_move_line_check_amount_currency_balance_sign`. La tasa del € del 03-nov se devolvió a
      1.003,8765.

## 6. Cierre

- [ ] 6.1 Segunda revisión con `code-reviewer` de Binaural antes de los PRs
- [ ] 6.2 Archivar el change y volcarlo en `openspec/specs/l10n_ve_pos/spec.md` y
      `openspec/specs/l10n_ve_pos_igtf/spec.md`
