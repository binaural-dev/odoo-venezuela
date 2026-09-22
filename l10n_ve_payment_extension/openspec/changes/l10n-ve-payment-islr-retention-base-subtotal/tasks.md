# Tasks

## 1. Diagnóstico

- [x] 1.1 Reproducido el reporte del cliente: orden de compra `P00192`,
      proveedor Hierros Miranda C.A., diario "Facturas de Proveedores
      Guarenas"
- [x] 1.2 Localizada la causa raíz en
      `_get_payment_concepts_from_invoice()`
      (`l10n_ve_payment_extension/models/account_move.py:577`):
      `use_price_unit` (más de una línea ISLR) usaba `line.price_unit` en
      vez de `line.price_subtotal`
- [x] 1.3 Confirmado que el bug afecta a los dos flujos que comparten esta
      función: creación manual (`action_create_islr_from_invoice`) y
      automática (`auto_create_islr_retention`)
- [x] 1.4 Confirmado que el caso de una sola línea ISLR no está afectado
      (usa `move_id.tax_totals["base_amount"]`)

## 2. Fix

- [x] 2.1 `l10n_ve_payment_extension/models/account_move.py:577`:
      `abs(line.price_unit)` → `abs(line.price_subtotal)`

## 3. Verificación

- [x] 3.1 Test nuevo `test_16b_get_payment_concepts_from_invoice_multi_line_qty_discount`
      (`tests/test_payment_retention.py`): dos líneas ISLR con cantidad y
      descuento distintos de 1/0, verifica que el monto base sea
      `price_subtotal` y no `price_unit`
- [x] 3.2 Corrido en contenedor Docker (`proj`) sobre una base de datos de
      prueba descartable (creada y eliminada para esta verificación,
      sin tocar `testing`): `test_16` y `test_16b` pasan con el fix
- [ ] 3.3 Revisar si hay retenciones ISLR ya emitidas con base mal
      calculada (facturas multi-línea con cantidad ≠ 1 o descuento) en las
      instancias productivas de clientes con ISLR habilitado — pendiente,
      requiere data-fix aparte si aplica

## 4. Manifest

- [x] 4.1 `l10n_ve_payment_extension` 19.0.2.0.28 → 19.0.2.0.29

## 5. OpenSpec

- [x] 5.1 `proposal.md` + spec delta
