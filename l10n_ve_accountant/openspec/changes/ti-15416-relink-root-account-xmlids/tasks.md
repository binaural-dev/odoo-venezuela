## 1. Implementación

- [x] 1.1 `_pre_load_data` + `_l10n_ve_relink_root_xmlids` en `account_chart_template.py`.
- [x] 1.2 Warning si la cuenta re-vinculada está archivada.

## 2. Tests

- [x] 2.1 `l10n_ve_accountant/tests/test_chart_template_relink.py` (faltante, huérfano, archivada, sin cuenta, varias coincidencias, multinivel, idempotencia, `res.company`, contrato del core).

## 3. Verificación manual

- [ ] 3.1 Instancia del ticket: crear la sucursal con la raíz sin xmlids y verificar que carga.
