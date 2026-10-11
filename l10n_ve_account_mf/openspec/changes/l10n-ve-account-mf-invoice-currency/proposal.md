## Why

Tarea 82427 (Flujos restantes POS Operativo). Con la máquina fiscal usada solo desde
Contabilidad (sin PdV), una factura en USD de una compañía en Bs se imprime en dólares:
`account_move._mf_build_invoice_lines` decide por la moneda de la **compañía** y no por la
de la **factura**, y manda `price_unit` tal cual. La MF trabaja siempre en Bs. Es el mismo
caso que resuelve `binaural_pos_multicurrency_mf` (integra-addons) para el PdV.

## What Changes

Solo cuando la factura está en una moneda distinta a la de la compañía (las facturas en
Bs no cambian):

- **Líneas**: el monto de la línea en la moneda de la compañía tal como quedó en el
  asiento. Con impuesto excluido, la base (`balance`); con impuesto incluido, el total
  con IVA a la tasa de la factura. El unitario se redondea hacia arriba al céntimo y el
  exceso se descuenta con `q-` sobre el ítem (`discount_amount`).
- **Pagos**: lo conciliado en la moneda de la factura llevado a la compañía a la tasa de
  la factura; la diferencia en cambio no se envía; con la factura pagada completa el
  último pago absorbe el redondeo.
- `toDriverOrder` (backend Web Serial) pasa `discount_amount` al driver.

## Impact

- `l10n_ve_account_mf` 19.0.1.3.0: `models/account_move.py`,
  `static/src/backend/mf_webserial_service.js`, tests nuevos.
- Fuera de alcance: la NC de una orden del PdV impresa desde Contabilidad sigue tomando
  `pos.payment.amount` (en una caja en USD, dólares).
