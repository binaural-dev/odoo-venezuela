## 1. Diagnóstico

- [x] 1.1 CI del PR #1252: 34 errores, 0 fallos → error de setUpClass en
      cascada (log en S3, no en el job de GitHub)
- [x] 1.2 Causa B (37 hits): `action_pos_session_open` exige la cuenta IGTF sin
      chequear si IGTF está en uso; al co-instalarse con `l10n_ve_pos` rompe la
      creación de `pos.session` en sus tests
- [x] 1.3 Causa A (1 hit): `test_pos_igtf_migration.py` busca `account.account`
      por `company_id`, campo eliminado en Odoo 19 (`company_ids`)
- [x] 1.4 Confirmado que los archivos afectados son idénticos a `origin/19.0`:
      fallo preexistente destapado por el scope del CI, no una regresión

## 2. Implementación

- [x] 2.1 `models/pos_session.py`: guardar la validación con
      `igtf_in_use = any(config_id.payment_method_ids.mapped("apply_igtf"))`
- [x] 2.2 `tests/test_pos_igtf_migration.py`: `("company_ids", "in", …)` en el
      search de `account.account`
- [x] 2.3 Bump de versión del manifest (`1.3` → `1.4`)

## 3. Verificación (CI)

- [ ] 3.1 El run-cli-command del PR #1252 pasa a verde (0 errores) tras el push
- [ ] 3.2 (Opcional) Correr localmente `/l10n_ve_pos,/l10n_ve_pos_igtf,/l10n_ve_pos_mf`
      si se quiere confirmar antes del push
