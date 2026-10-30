# Tasks

## 1. Implementación

- [x] 1.1 `controllers/orders.py`: `_ve_partner_payload` firma el `id` del
      partner con `pos.order._get_signed_self_partner_id` de la caja; lo usan
      `identify`, `identify/create` (nuevo y dedup) y `set_phone`
- [x] 1.2 `__manifest__.py`: `19.0.1.7.0` (la `1.6.0` la usa #1545, ticket 16064)

## 2. Pruebas

- [x] 2.1 `tests/test_kiosk_public_routes.py`: `identify`, `identify/create`
      (nuevo y dedup) y `set_phone` devuelven un id firmado que el core
      resuelve al partner
- [x] 2.2 `tests/test_kiosk_public_routes.py`: `_check_pos_order` con el id
      que devolvió `identify` guarda la orden con ese `partner_id`; con el id
      numérico no asigna cliente (contrato del core que motivó el fix)
- [x] 2.3 Los tests existentes que leían el partner de la respuesta resuelven
      el id firmado (`_partner_from_result`)
- [x] 2.4 Suite del módulo en base nueva (2026-10-30, instancia `monfarmacia`):
      `./odoo test monfarmacia -m l10n_ve_pos_self_order --tags /l10n_ve_pos_self_order`
      → 65 tests; `TestKioskPublicRoutes` 33/33 en verde (incluidos los 4
      nuevos). Los 13 fallos y 4 errores de
      `test_kiosk_invoice_foreign_debit_credit` son previos (búsqueda de tasa
      por fecha exacta) y los corrige el commit `[TEST]` del PR #1545
- [x] 2.5 E2E por HTTP contra `monfarmacia_20261030` (Autopago CCCT 1, caja
      14): `identify` con V-29737018 devuelve `91094-<hmac>`; `process-order`
      con ese id guarda la orden 55 con `partner_id = 91094` y la respuesta trae
      el mismo id firmado; con el id numérico la orden 56 queda sin cliente.
      Ambas órdenes de prueba canceladas con `remove-order`

## 3. Prueba funcional

- [x] 3.1 Copia del staging de Monfarmacia (`monfarmacia_20261030`),
      Autopago CCCT 1: identificarse (cliente existente y cliente nuevo),
      agregar productos, elegir un método Megasoft → no aparece "Cliente sin
      cédula" y la `pos.order` queda con el `partner_id` del cliente.
      Probado en el navegador el 2026-10-30: funciona

## 4. Cierre

- [x] 4.1 Archivar el change y volcarlo en
      `openspec/specs/pos-self-order-kiosk-identification/spec.md`
