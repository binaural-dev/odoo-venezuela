## 1. Diagnóstico

- [x] 1.1 Reproducir el reporte: factura con producto sin "Concepto de
      pago" no aparece en el selector "Retención de" del wizard de
      Retención de ISLR; asignar el concepto al producto después no
      resuelve el problema.
- [x] 1.2 Rastrear el domain del campo "Retención de"
      (`account_retention_islr.xml`) hasta `allowed_lines_move_ids`
      (`account_retention.py`), que filtra por
      `is_isrl_retention_available = True` para retenciones tipo ISLR.
- [x] 1.3 Ubicar `_compute_retention_islr_avalability`
      (`models/account_move.py`) y confirmar que su `@api.depends` no
      incluye `payment_concept` del producto, solo `product_id` de la
      línea — por eso cambiar el concepto en el producto no dispara el
      recompute sobre facturas ya creadas.

## 2. Fix

- [x] 2.1 Agregar
      `"invoice_line_ids.product_id.product_tmpl_id.payment_concept"` al
      `@api.depends` de `_compute_retention_islr_avalability`.
- [x] 2.2 Bump de versión del manifest (`19.0.2.0.29` -> `19.0.2.0.30`).

## 3. Verificación manual

- [ ] 3.1 Crear una factura de proveedor con un producto tipo Servicio
      sin "Concepto de pago" configurado; confirmar que no aparece en el
      selector de retención ISLR.
- [ ] 3.2 Asignarle "Concepto de pago" al producto (sin tocar la
      factura) y confirmar que la factura ahora sí aparece disponible en
      el selector, sin necesidad de reabrir/editar sus líneas.
- [ ] 3.3 Confirmar que quitarle el concepto de pago al producto excluye
      la factura de nuevo del selector.
