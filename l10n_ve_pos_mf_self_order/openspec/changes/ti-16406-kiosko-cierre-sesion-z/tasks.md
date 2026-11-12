# Tasks

## 0. Preparación

- [x] 0.1 Ticket 16406 (ref. #16444) creado el 2026-11-12 en el equipo
      Producto, etiqueta POSV19
- [x] 0.2 Decisiones del usuario (2026-11-12): con órdenes sin número fiscal se
      bloquea como en la caja; Z primero y cierre después, igual que
      `l10n_ve_pos_mf` (sin lógica extra de reintento); acceso igual que el
      resto del panel de Debug (`?debug=1` + token) más la confirmación

## 1. Implementación

- [x] 1.1 `controllers/main.py`: rutas `close_session/check`, `report_z` y
      `close_session`
- [x] 1.2 `static/src/overrides/self_order_fiscal.js`: impresión de la Z con
      lectura de S1 y llamadas a las rutas
- [x] 1.3 `static/src/app/debug/kiosk_debug_dialog_fiscal.{js,xml}`: botón y
      flujo del panel
- [x] 1.4 `i18n/es_VE.po`: textos nuevos
- [x] 1.5 `__manifest__.py`: `19.0.1.1.0`

## 2. Pruebas

- [x] 2.1 `tests/test_kiosk_close_session_z.py` (usuario de Kiosko sin
      permisos contables): pendientes de la sesión, bloqueo del cierre, cierre
      que borra carritos, fallo y cierre sin terminar que dejan la sesión
      abierta, datos de Z inválidos, sincronización de la Z y serial de otra
      máquina
- [x] 2.2 `tests/test_mf_self_order.py`: producto con `with_company` (el
      `setUpClass` fallaba en `origin/19.0` con AccessError de `l10n_ve_stock`)
- [x] 2.3 Suite del módulo en base nueva (2026-11-12, instancia `monfarmacia`,
      código de la rama): `odoo -u l10n_ve_pos_mf_self_order --test-tags
      /l10n_ve_pos_mf_self_order` → 11 tests, 0 fallos (9 nuevos + 2 que antes
      no corrían). Mutaciones: sin la protección del serial falla
      `test_report_z_does_not_touch_other_machines`; sin la revisión de
      pendientes en el cierre falla `test_close_refused_with_pending_orders`
- [x] 2.4 Hoot `static/tests/unit/kiosk_close_session_z.test.js`: impresión de
      la Z (puerto liberado siempre) y orden de los pasos del panel con sus
      cortes. `/web/tests?filter=@l10n_ve_pos_mf_self_order` → 24 pasan (12
      nuevos)
- [x] 2.5 Prueba en el Kiosko real (headless, base `monfarmacia_t16406`,
      máquina fiscal simulada en el navegador, 2026-11-12):
      - con una orden pagada sin número fiscal: aviso con la orden
        (`260-6-000001`), sin llamadas a la máquina
      - con la orden fiscalizada: confirmación → Z → S1 → puerto liberado →
        sincronización → cierre; sesión `closed` con `report_z` 42, asiento de
        cierre publicado, orden `done` con `mf_reportz` 42, carrito borrado y el
        Kiosko deja de recibir pedidos
      - asiento de cierre descuadrado: el cierre nativo revierte y devuelve el
        asistente; la ruta responde con error y la sesión queda abierta (la Z
        ya sincronizada se mantiene, como en la caja)
- [ ] 2.6 Prueba con la máquina fiscal de pruebas (HKA80) en el Kiosko de
      Monfarmacia

## 3. Cierre

- [ ] 3.1 Archivar el change y volcarlo en
      `openspec/specs/pos-mf-self-order-kiosk-close-z/spec.md`
