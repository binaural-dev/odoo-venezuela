## 0. Preparación

- [x] 0.1 Prueba del usuario con la HKA80 (2026-11-13): Z 0147 impresa, sesión
      con `report_z = 148`; causa: S1 leído después de la Z más el +1 del servidor
- [x] 0.2 Decisiones del usuario (2026-11-13): S1 antes de la Z como el IoT; sin
      S1 no se imprime; sin ceros a la izquierda; tras cerrar, al menú de cajas

## 1. Implementación

- [x] 1.1 `printKioskReportZ`: S1 antes de la Z, sin `printed`
- [x] 1.2 Panel de Debug: título de error único cuando la Z no sale; `redirect`
      al menú de cajas tras cerrar
- [x] 1.3 `i18n/es_VE.po`: aviso de S1 ilegible
- [x] 1.4 Prueba Python sin `base.res_partner_1` (CI sin demo)

## 2. Pruebas

- [x] 2.1 Hoot `kiosk_close_session_z.test.js`: orden S1 → Z, sin S1 o sin
      contador no imprime, Z fallida libera el puerto, el cierre va al menú de
      cajas y sin cierre no sale del Kiosko (16/16; módulo 28/28)
- [x] 2.2 Python en base nueva sin demo, como el CI: 26/26
- [x] 2.3 E2E en `monfarmacia_t16406_real` (caja 14, sesión 87, máquina
      simulada con S1 = 41): llamadas `connect → S1 → Z → disconnect`, sesión
      cerrada con Reporte Z 42 y serial, y el Kiosko pasó a
      `/odoo/action-point_of_sale.action_client_pos_menu`
- [x] 2.4 Con la HKA80 (2026-11-13, prueba del usuario, base
      `monfarmacia_t16406_real`): sesión 89 con Reporte Z 151, el mismo que
      imprimió la máquina. La sesión 88 guardó 148 pero salió la 0149: la
      máquina se quedó sin papel y el driver reenvió el I0Z; se corrige en
      `ti-16406-z-sin-papel`

## 3. Cierre

- [x] 3.1 OpenSpec validado (`--strict`) y archivado en el mismo PR
