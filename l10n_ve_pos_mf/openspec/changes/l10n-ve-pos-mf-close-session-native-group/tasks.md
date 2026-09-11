## 1. Grupo de permisos y exposición al frontend

- [x] 1.1 `security/res_group.xml`: nuevo `res.groups`
      `group_pos_close_native`, sin `privilege_id`
- [x] 1.2 Registrar `security/res_group.xml` en `__manifest__.py` (`data`)
- [x] 1.3 `models/res_users.py`: override `_load_pos_data_read` exponiendo
      `_can_close_session_native`
- [x] 1.4 Registrar `res_users` en `models/__init__.py`
- [x] 1.5 Traducción es_VE del nombre del grupo en `i18n/es_VE.po`

## 2. Frontend: tercer botón de cierre nativo

- [x] 2.1 `ClosePosPopup.js`: `this.canCloseNative` en `setup()`
- [x] 2.2 `ClosePosPopup.xml`: nuevo xpath `position="after"` sobre el botón
      de Reporte Z, botón "Cerrar sesión" con `t-if="canCloseNative"`
      llamando a `confirm()` nativo

## 3. Verificación funcional (manual, en navegador)

- [ ] 3.1 Actualizar el módulo `l10n_ve_pos_mf`
- [ ] 3.2 Asignar el grupo "Close POS session natively (skip mandatory Z
      report)" a un usuario de prueba en Ajustes > Usuarios (Extra Rights)
- [ ] 3.3 Abrir el PDV con ese usuario, cerrar sesión: deben verse los tres
      botones (Reporte X, Cerrar sesion e imprimir Z, Cerrar sesión). Probar
      el tercero: debe cerrar sin exigir Reporte Z ni pedidos facturados
- [ ] 3.4 Abrir el PDV con un usuario SIN el grupo: debe verse solo el flujo
      dual de siempre, sin el tercer botón
- [ ] 3.5 Confirmar que ningún usuario existente quedó con el grupo asignado
      por accidente tras actualizar el módulo
