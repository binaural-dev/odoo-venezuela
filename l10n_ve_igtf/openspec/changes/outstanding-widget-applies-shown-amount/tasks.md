## 1. Implementación

- [x] 1.1 `rate` sin redondear en el contenido del widget.
- [x] 1.2 `js_assign_outstanding_line` fija `l10n_ve_widget_rates`; excluye retenciones y la ND de IGTF.
- [x] 1.3 `_prepare_move_line_residual_amounts` y `_prepare_reconciliation_single_partial` (VEF<->divisa y tercera moneda).
- [x] 1.4 `compute_bi_igtf` (igtf e igtf_note_debit) con varias cuotas por cobrar.
- [x] 1.5 `remove_igtf_from_account_move`: salida anticipada sin línea de IGTF (no pasa el asiento a borrador).
- [x] 1.6 `advanced_move_ids`: dominio como lista (solo cruces publicados).
- [x] 1.7 El cruce de anticipo solo se deshace por sus caminos gestionados (guardas en `button_draft`, `button_cancel` y `_post`; cancelación de borradores residuales con el pago origen; log del error tragado en `remove_igtf_from_account_move`).
- [x] 1.7b Cruce huérfano (publicado y sin pago origen): `remove_igtf_from_account_move` decide por `_is_advance_cross()` y no por el pago origen, así que lo cancela al desconciliarlo desde la factura en vez de intentar republicarlo (la guarda de `_post` lo rechazaba y el `super()` terminaba en `MissingError`). Las salidas anticipadas también lo dejan pasar.
- [x] 1.7c `_cancel_draft_advance_crosses` solo cancela borradores con `is_advance_move` (otros módulos, como las integraciones, también llenan `origin_payment_advanced_payment_id`).
- [x] 1.7d `l10n_ve_igtf_note_debit`: en modo `debit_note`, un cruce VEF sin pago origen no cuenta como pago directo, para que se reverse la ND de IGTF igual que con un cruce que conserva su pago origen.
- [x] 1.7e Traducción es_VE del mensaje de la guarda en tuteo.
- [x] 1.8 Bump de versión de `l10n_ve_igtf` y `l10n_ve_igtf_note_debit`.

## 2. Tests

- [x] 2.1 `l10n_ve_igtf/tests/test_outstanding_widget_amount.py` (fixture común `common_currency.py`, solo requiere `l10n_ve_igtf`; moneda base VEF), incluida la factura en VEF pagada con JPY (0 decimales) y KWD (3 decimales).
- [x] 2.2 `l10n_ve_igtf/tests/test_remove_igtf_without_igtf_line.py` (pago USD y VEF sin línea de IGTF no se tocan; desconciliar un parcial deja pagada la otra factura).
- [x] 2.3 `l10n_ve_igtf/tests/test_unreconcile_advance_cross.py` (cruce sin publicar, publicado, y parcial del propio cruce: el asiento origen nunca se cancela).
- [x] 2.3b `test_unreconcile_advance_cross.py`: botones propios bloqueados, cruce cancelado no vuelve a publicarse, `remove_igtf_from_account_move` completa el camino gestionado, y cancelar el pago cancela sus cruces en borrador.
- [x] 2.3c `test_unreconcile_advance_cross.py`: cruce huérfano (con y sin línea de IGTF) se cancela al desconciliar; cancelarlo desconcilia también sus otras facturas; los borradores que no son cruces no se cancelan con el pago.
- [x] 2.4b `l10n_ve_igtf_note_debit/tests/test_igtf_note_debit_unit.py`: cruce VEF huérfano en modo `debit_note` se trata como cruce (se llama a `create_note_credit_igtf`) y la ND de IGTF queda reversada con una NC publicada.
- [x] 2.4 `l10n_ve_igtf_note_debit/tests`: la ND de IGTF (pago en USD) conserva la tasa del pago, con control; y `compute_bi_igtf` con dos cuotas.

## 3. Verificación manual (fuera del alcance de la implementación: se hace en la instancia de pruebas)

- [ ] 3.1 Cruce desde el widget con pagos en VEF, USD y una tercera moneda: lo aplicado coincide con lo mostrado.
- [ ] 3.2 Pago USD aplicado a dos facturas: desconciliar una desde el widget deja la otra pagada y el pago publicado.
- [ ] 3.3 Con tasas que suben (pago en Bs anterior a la factura en USD): confirmar que el widget muestra y aplica el monto a la tasa de la fecha de la factura (puede dejar la factura parcial) y que la conciliación manual conserva la valoración nativa (decisión funcional documentada en `proposal.md`).
