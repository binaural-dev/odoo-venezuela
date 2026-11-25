# Tasks

## 0. Preparación

- [x] 0.1 Ticket 16406 (ref. #16444) creado el 2026-11-12 en el equipo
      Producto, etiqueta POSV19
- [x] 0.2 Decisiones del usuario (2026-11-12): con órdenes sin número fiscal se
      bloquea como en la caja; Z primero y cierre después, igual que
      `l10n_ve_pos_mf` (sin lógica extra de reintento); acceso igual que el
      resto del panel de Debug (`?debug=1` + token) más la confirmación
- [x] 0.3 Decisión del usuario (2026-11-12): aplicar todo el code review
      (bloqueante, "a corregir" y sugerencias) y guardar en la sesión el serial
      y la fecha de la Z en este mismo PR (change de raíz
      `ti-16406-sesion-serial-y-fecha-z`, módulo `l10n_ve_pos_mf`)

## 1. Implementación

- [x] 1.1 `controllers/main.py`: rutas `close_session/check`, `report_z` y
      `close_session`
- [x] 1.2 `static/src/overrides/self_order_fiscal.js`: impresión de la Z con
      lectura de S1 y llamadas a las rutas
- [x] 1.3 `static/src/app/debug/kiosk_debug_dialog_fiscal.{js,xml}`: botón y
      flujo del panel
- [x] 1.4 `i18n/es_VE.po`: textos nuevos
- [x] 1.5 `__manifest__.py`: `19.0.1.1.0`

## 2. Correcciones del code review (2026-11-12)

- [x] 2.1 Bloqueante: las rutas solo aceptan cajas en modo kiosko
      (`_l10n_ve_verify_kiosk_config`); el core también acepta el token del QR
      de mesa
- [x] 2.2 Los borradores con pago bloquean (cobro con la finalización a
      medias); el aviso los manda al backend
- [x] 2.3 El chequeo devuelve las pendientes en formato `connectNewData` y el
      aviso abre el panel de Órdenes con ellas cargadas (el panel solo trae las
      últimas 50)
- [x] 2.4 No empieza si hay una factura fiscal imprimiéndose ni si la sesión
      ya tiene su Z
- [x] 2.5 Botón visible solo con `access_button_mf`; comentario del `sudo` en
      el cierre; `report_z` no devuelve errores internos a la ruta pública
- [x] 2.6 Pendiente aparte (fuera de alcance): las rutas que ya existían en el
      Kiosko también aceptan el token del QR

## 3. Pruebas

- [x] 3.1 `tests/test_kiosk_close_session_z.py` (usuario de Kiosko sin
      permisos contables): pendientes de la sesión, borrador con pago,
      datos para el panel, Z ya registrada, rechazo del modo `mobile` en las
      tres rutas, bloqueo del cierre (pendientes y borrador con pago), cierre
      que borra carritos, fallo y cierre sin terminar que dejan la sesión
      abierta, datos de Z inválidos, sincronización de la Z (órdenes, factura,
      serial y fecha en la sesión) y serial de otra máquina. Más
      `TestKioskCloseSessionZHttp` por JSON-RPC real: token del Kiosko, token
      inválido y token del QR
- [x] 3.2 `tests/test_mf_self_order.py`: producto con `with_company` (el
      `setUpClass` fallaba en `origin/19.0` con AccessError de `l10n_ve_stock`)
- [x] 3.3 Suites en base nueva (2026-11-12, instancia `monfarmacia`, código de
      la rama, `--workers=0` y `--db-filter` para el `HttpCase`):
      `odoo -u l10n_ve_pos_mf,l10n_ve_pos_mf_self_order --test-tags
      /l10n_ve_pos_mf,/l10n_ve_pos_mf_self_order` → 27 tests, 0 fallos (19 de
      este módulo: 17 nuevos y los 2 que antes no corrían). Mutaciones: sin el
      filtro de modo kiosko fallan `test_routes_reject_mobile_box` y
      `test_mobile_token_rejected`; sin el bloqueo de borradores con pago,
      `test_check_counts_draft_with_payment` y
      `test_close_refused_with_draft_with_payment`; sin la protección del
      serial, `test_report_z_does_not_touch_other_machines`; sin la revisión de
      pendientes en el cierre, `test_close_refused_with_pending_orders`
- [x] 3.4 Hoot `static/tests/unit/kiosk_close_session_z.test.js`: impresión de
      la Z (puerto liberado siempre), impresión en curso, y orden de los pasos
      del panel con sus cortes (Z ya registrada, borrador con pago, "Abrir
      Órdenes"). `/web/tests?filter=@l10n_ve_pos_mf_self_order` → 28 pasan
      (16 nuevos)
- [x] 3.5 Prueba en el Kiosko real (headless, base `monfarmacia_t16406`,
      máquina fiscal simulada en el navegador, 2026-11-12):
      - caja sin `access_button_mf`: el botón no aparece
      - una orden pagada y un borrador con pago sin número fiscal: aviso con
        las dos (el borrador marcado para el backend), "Abrir Órdenes" muestra
        la pagada como pendiente de factura, sin llamadas a la máquina
      - con las órdenes resueltas: confirmación → Z → S1 → puerto liberado →
        sincronización → cierre; sesión `closed` con Reporte Z 42, serial
        `Z7CE2E0001`, fecha y hora, asiento de cierre publicado, carrito borrado y el Kiosko deja de recibir pedidos
      - asiento de cierre descuadrado: el cierre nativo revierte y devuelve el
        asistente; la ruta responde con error y la sesión queda abierta (la Z
        ya sincronizada se mantiene, como en la caja)
      - las líneas cuyo producto no carga el Kiosko no llegan al cliente (pasa
        igual con `session_orders`); en el Kiosko real las órdenes son de
        productos que el Kiosko vende
- [ ] 3.6 Prueba con la máquina fiscal de pruebas (HKA80) en el Kiosko de
      Monfarmacia, antes del merge

## 4. Cierre

- [x] 4.1 Archivar el change y volcarlo en
      `openspec/specs/pos-mf-self-order-kiosk-close-z/spec.md`
