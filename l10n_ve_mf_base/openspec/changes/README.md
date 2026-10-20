# Cambios de este módulo especificados en otro módulo

Algunos cambios del driver nacen de un requerimiento del PdV y su spec vive en
el módulo que la origina. Referencias cruzadas:

- **Descuento por monto sobre el ítem (`discount_amount` → `q-`)**, en
  `TfhkaDriver._appendItemDiscount`, usado por `printInvoice` y
  `printCreditNote`: una línea del documento puede traer `discount_amount` y el
  driver envía `q-<monto>` justo después del ítem, antes del subtotal `3`
  (manual HKA V8.5.0, págs. 27, 34-35 y 37). Lo usa el PdV para facturar una
  línea con descuento del 100% en el mínimo fiscal 0,01 mostrando la cantidad
  real (N × 0,01 con `q-` (N − 1) × 0,01).
  Spec: `l10n_ve_pos_mf/openspec/changes/l10n-ve-pos-mf-full-discount-min-price/`
  (ticket #15105).
