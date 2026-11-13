## 0. Preparación

- [x] 0.1 Prueba del usuario con la HKA80 (2026-11-13): Z 0147 impresa, sesión 86
      con `report_z = 148`
- [x] 0.2 Causa: S1 leído después de la Z más el +1 del servidor; el IoT lee S1
      antes de la Z
- [x] 0.3 Decisiones del usuario (2026-11-13): solo caja y Kiosko; sin ceros a la
      izquierda en ningún lado; si S1 falla antes de la Z, no imprimir

## 1. Implementación

- [x] 1.1 `ClosePosPopup._printFiscalReportZ`: S1 antes de `printReportZ()`; sin
      S1 legible, aviso y sin Z
- [x] 1.2 `pos.session.set_report_z`: documentar que el contador es el de la
      última Z

## 2. Pruebas

- [x] 2.1 Hoot `close_pos_popup_report_z.test.js`: orden S1 → Z, valor
      sincronizado, sin S1 no imprime, Z fallida no sincroniza, sin confirmar no
      toca la máquina (5/5)
- [x] 2.2 Python de `l10n_ve_pos_mf` y `l10n_ve_pos_mf_self_order` en base nueva
      sin demo, como el CI: 26/26
- [x] 2.3 Con la HKA80 (2026-11-13, prueba del usuario, base
      `monfarmacia_t16406_real`): sesión 89 con Reporte Z 151, el mismo que
      imprimió la máquina. La sesión 88 guardó 148 pero salió la 0149: la
      máquina se quedó sin papel y el driver reenvió el I0Z; se corrige en
      `ti-16406-z-sin-papel`

## 3. Cierre

- [x] 3.1 OpenSpec validado (`--strict`) y archivado en el mismo PR
