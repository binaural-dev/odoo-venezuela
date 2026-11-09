## 1. Implementación

- [x] 1.1 `l10n_ve_reconcile_assistant`: clasificador `_l10n_ve_reconcile_classify`, campo `l10n_ve_open_amount` y ganchos `_l10n_ve_reconcile_is_special_note` y `_l10n_ve_reconcile_apply_context`
- [x] 1.2 Wizard `l10n_ve.reconcile.assistant` y líneas `l10n_ve.reconcile.assistant.item`: vista previa sin escritura, orden por `sequence` con widget `handle`, `_onchange_item_ids` y `action_confirm` par por par en una transacción
- [x] 1.3 La vista previa de un anticipo imita `_create_advance_payment_move` (saldo × base ÷ monto del widget redondeado) y la de un pago usa la tasa del widget
- [x] 1.4 `ir.model.access.csv` de los dos modelos transitorios para `account.group_account_user`
- [x] 1.5 `l10n_ve_reconcile_assistant_accountant`: `action_reconcile` abre el asistente cuando la selección es suya
- [x] 1.6 Traducciones `i18n/es_VE.po` por exportación con la CLI
- [x] 1.7 Archivar el change y volcarlo en `openspec/specs/l10n_ve_reconcile_assistant/spec.md` y `openspec/specs/l10n_ve_reconcile_assistant_accountant/spec.md`

## 2. Tests

- [x] 2.1 `l10n_ve_reconcile_assistant/tests/test_classifier.py`: casos permitidos y bloqueados, un origen contra cinco facturas y varios orígenes bloqueados
- [x] 2.2 `l10n_ve_reconcile_assistant/tests/test_wizard.py` (flujo de usuario con `Form`): pago contra dos y tres facturas, anticipo con y sin IGTF, anticipo parcial en USD y en bolívares con tasas distintas, "mantener valor", reordenar arrastrando, bloqueos, reversión si falla la segunda factura, compañía activa distinta, usuario contable y usuario sin acceso, y cada fila comparada con el widget real de su factura (bolívares con fechas distintas en ambos órdenes, USD contra facturas en bolívares, valor en divisa y EUR)
- [x] 2.3 `l10n_ve_reconcile_assistant_accountant/tests/test_action_reconcile.py`: abre el asistente en lo suyo y deja pasar el resto a la conciliación nativa
- [x] 2.4 Base nueva `--without-demo=all` con los repos en `maintenance-19.0`:
      `odoo -d <base> -i binaural_subsidiary_reconcile_assistant,l10n_ve_reconcile_assistant_accountant,l10n_ve --without-demo=all --test-enable --test-tags=/l10n_ve_reconcile_assistant,/l10n_ve_reconcile_assistant_accountant,/binaural_subsidiary_reconcile_assistant`:
      56 tests, 0 fallos, 100 % de líneas y ramas de los tres módulos
