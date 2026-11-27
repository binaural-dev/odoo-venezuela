## 1. l10n_ve_accountant — números duplicados sin renombrar

- [x] 1.1 `models/account_move.py`: redeclarar `_unique_name` con partner y compañía
- [x] 1.2 `models/account_move.py`: `_auto_init` verifica duplicados mientras el índice no sea el ampliado, sin renombrar; borra el índice estrecho y el marcador `_ve`
- [x] 1.3 `i18n/es_VE.po`: mensaje y líneas de detalle traducibles
- [x] 1.4 `tests/test_account_move_unique_name_index.py`: duplicados bloquean, índice ampliado creado, índice del core con y sin comentario reemplazado, base actualizada sin verificación, asientos sin proveedor

## 2. Verificación

- [x] 2.1 Suite de `l10n_ve_accountant` en base limpia
- [ ] 2.2 Actualizar una base 19 que ya tenga `account_move_unique_name_ve` y comprobar que el índice queda ampliado
