## Why

En el PdV un cajero puede dejar una línea de la orden con cantidad en 0 (p. ej. tras teclear cantidades o por un escaneo que no incrementó). Al pulsar "Pago" la orden pasa a la pantalla de pago con ese renglón en 0, que no aporta importe pero ensucia el ticket/factura y confunde el cobro. El núcleo de Odoo solo bloquea el pago cuando la orden está vacía (`canPay` = hay líneas), no cuando hay líneas válidas mezcladas con líneas en 0.

## What Changes

- `l10n_ve_pos`: interceptar `PosStore.pay()` (el método que dispara tanto el botón "Pago" del panel de acciones como el botón de pago móvil) para, antes de navegar a la pantalla de pago, detectar las líneas con cantidad exactamente 0. Si existe al menos una, se muestra un `AlertDialog` con los nombres de esos productos y se aborta el paso a pago; el mensaje indica al cajero eliminarlos o colocarles la cantidad correcta. Las órdenes sin líneas en 0 pasan a pago sin cambios.

## Impact

- Specs afectadas: `l10n_ve_pos` (nueva requirement "Bloqueo del pago con líneas en cantidad cero").
- Código: `l10n_ve_pos/static/src/overrides/services/pos_store.js` (nuevo).
- Solo validación de flujo en el frontend antes de abrir la pantalla de pago; no altera cálculo de totales, sincronización, asientos ni la validación de "orden pagada/facturada". No bloquea cantidades negativas (devoluciones), solo el cero exacto.
