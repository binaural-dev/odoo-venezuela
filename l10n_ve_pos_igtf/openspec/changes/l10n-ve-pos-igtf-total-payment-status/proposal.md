## Why

El fix del 2026-07-14 (`bcec34e55`) eliminó del panel de estado de pago el
bloque fijo TOTAL / IGTF (3%) / TOTAL + IGTF, a pedido de Jesús, porque
`get_total_with_tax()`/`get_foreign_total_with_tax()` estaban sobrescritos sin
`super()` para alimentarlo, rompiendo esos getters compartidos con
`l10n_ve_pos` para el resto de consumidores (subtítulo foráneo, recibo,
ticket, resumen de venta, backend). Quedó solo el desglose BI IGTF / IGTF /
Foreign IGTF.

Ahora Jesús pide recuperar, de ese bloque eliminado, únicamente el renglón
combinado — "TOTAL a Pagar con IGTF" (total de factura en Bs + recargo IGTF en
Bs) — pero sin repetir el bug: sin tocar `get_total_with_tax()` ni
`get_foreign_total_with_tax()`.

## What Changes

- Nuevo getter `get_total_with_igtf()` en `PosOrder` (`order_model.js`):
  `get_total_without_igtf() + compute_igtf_amount(get_total_without_igtf())`,
  redondeado con `_igtfRoundLocal` — el 3% de la factura COMPLETA, fijo. Corregido
  el 19-jul (primera versión usaba `+ igtf_amount`, el recargo parcial que
  `update_igtf()` acumula según lo tecleado en cada línea de pago: al pagar,
  por ejemplo, 10 de una factura de 100, el renglón mostraba 10,30 en vez de
  103 — comportamiento dinámico que Jesús no quería; el renglón debe mostrar
  siempre el mismo total sin importar cuánto se haya pagado). No sustituye ni
  delega en `get_total_with_tax()`/`get_foreign_total_with_tax()`, que
  permanecen intactos (conversión pura de factura, sin IGTF) para todos sus
  demás consumidores.
- Nuevo getter `totalWithIgtfAmount` en `payment_status.js`, que formatea
  `get_total_with_igtf()` con `formatCurrency()`.
- `payment_status.xml`: se mantiene el desglose BI IGTF / IGTF / Foreign IGTF
  existente y se añade debajo, dentro del mismo `t-if="isIgtf"`, un renglón
  separado por línea (`border-top`), en tipografía grande (`fs-3 fw-bolder`),
  con la etiqueta "TOTAL a Pagar con IGTF:" a la izquierda y el monto pegado
  al borde derecho (mismo patrón `d-flex justify-content-between` del resto
  del panel). El div contenedor del bloque IGTF lleva `text-dark`: el
  template nativo (`point_of_sale.PaymentScreenStatus`) pinta todo
  `.paymentlines-container` en `text-danger`/`text-success` según falte o no
  por cobrar, y sin este override el bloque IGTF heredaba ese rojo/verde en
  vez de mostrarse en negro.

## Capabilities

### Modified Capabilities
- `frontend-display`: se añade el requirement "TOTAL a Pagar con IGTF" al
  panel de estado de pago, sin reintroducir el bug de 2026-07-14 (no se toca
  `get_total_with_tax()`/`get_foreign_total_with_tax()`).

## Impact

- Módulo: `l10n_ve_pos_igtf` (frontend POS), rama
  `19.0_mig-ta_77295_cruces_automaticos_de_cuentas_en_v19`.
- Archivos: `static/src/app/overrides/models/order_model.js`,
  `static/src/app/overrides/screens/payment_status.js`,
  `static/src/app/overrides/screens/payment_status.xml`.
- Sin cambios de backend ni de contabilidad; solo display.
