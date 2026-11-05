## 0. Preparación y decisiones

- [x] 0.1 2026-11-04: el usuario aprueba el plan de la fase 2 con las opciones recomendadas, salvo la rama:
      commits en la misma rama (`19.0_feat-ta_86066_pos_third_currency_cash`) y los mismos PRs
      (odoo-venezuela#1569, integra-addons#3173). Change nuevo: el de la fase 1 ya está archivado.
- [x] 0.2 Evidencia: en una caja en otra moneda `binaural_pos_multicurrency` desvía toda conversión a la
      tasa nativa (`pos_config.py:42-49`, `pos_order.js:38-50`), que ya pasa por la moneda de la compañía
      sin redondear (`res.currency._compute_current_rate`).

## 1. Validaciones por caja

- [x] 1.1 `pos.config._get_tender_currency_error` / `_check_tender_currency_methods` (gancho por caja)
- [x] 1.2 `pos.payment.method._check_tender_currency`: lo propio del método y la validación de cada caja;
      `_tender_currency_not_third_message` (mismo msgid de antes)

## 2. Cruce

- [x] 2.1 `_get_cross_real_amount_currency`: fallback desde la moneda de la compañía
- [x] 2.2 `transitory_amount_currency` en `_create_cross_move_for`, `_get_cross_move_line_vals`, los
      constructores de líneas, `_get_combined_cross_legs` (`transitory_amount_of`),
      `_create_combined_cross_move` y `_cross_legs_net_is_zero`; `_get_cross_transitory_currency_amount`

## 3. Pruebas

- [x] 3.1 `test_pos_tender_currency.py`: la alterna en una caja en la moneda de la compañía, la línea
      transitoria en la moneda del diario (con y sin el parámetro), el cruce combinado con
      `transitory_amount_of` (en las dos compañías de prueba)
- [x] 3.2 Python (`odoo -c <conf> -d <base> -u <módulos> --test-tags /<módulo> --stop-after-init --no-http`):
      `l10n_ve_pos` 252/252 (`pos_t86066_ve`), `l10n_ve_pos_igtf` 13/13 (`pos_t86066_igtf`),
      `l10n_ve_pos_self_order` 95/95 (`pos_t86066_so`), `l10n_ve_pos_mf` 5/5 (`pos_t86066_mf`)
- [ ] 3.3 Hoot de `l10n_ve_pos`, `l10n_ve_pos_igtf` y `l10n_ve_pos_self_order` (JS sin cambios en este change)
- [x] 3.4 E2E en `pos_test_86066` por JSON-RPC y con el PdV en las cajas USD y EUR: ver el change de
      `binaural_pos_multicurrency` en integra-addons
- [x] 3.5 Precommit (`scripts/precommit pos -m l10n_ve_pos,...`): pasa

## 4. Cierre

- [x] 4.1 Versión 19.0.1.29.1 → 19.0.1.30.0
- [x] 4.2 `openspec validate ta-86066-tercera-moneda-caja-otra-moneda --strict`
- [ ] 4.3 Revisión de Binaural y decisión del usuario
- [ ] 4.4 Archivar en el mismo PR
