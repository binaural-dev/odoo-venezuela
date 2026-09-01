## Why

En la pantalla de pago del PdV, el renglón "TOTAL a Pagar con IGTF" del panel de estado (`l10n_ve_pos_igtf`) solo se muestra en moneda principal (Bs.). El cajero que cobra en divisa no tiene a la vista el equivalente foráneo de ese total de referencia, a diferencia del total principal de la orden —que sí muestra su equivalente foráneo debajo—. Además ese total foráneo bajo el monto grande (`l10n_ve_pos`) queda demasiado pequeño para leerse con comodidad.

## What Changes

- `l10n_ve_pos`: agrandar el total foráneo que se muestra debajo del monto grande en la pantalla de pago (`payment_screen_top.xml`, `fs-3` → `fs-2`). Cambio puramente cosmético; no altera ninguna requirement (el total alterno adeudado ya está cubierto por "Recibo y pantallas con totales en moneda alterna").
- `l10n_ve_pos_igtf`: mostrar, bajo el renglón "TOTAL a Pagar con IGTF" del panel de estado, su equivalente en moneda foránea. Nuevo getter de orden `get_foreign_total_with_igtf()` (espejo foráneo de `get_total_with_igtf`, derivado con conversiones simples para no introducir drift) y getter de pantalla `foreignTotalWithIgtfAmount`.

## Impact

- Specs afectadas: `l10n_ve_pos_igtf` (requirement "Panel de estado de pago con desglose IGTF").
- Código: `l10n_ve_pos/static/src/overrides/screens/payment_screen/payment_screen_top.xml`, `l10n_ve_pos_igtf/static/src/app/overrides/models/order_model.js`, `l10n_ve_pos_igtf/static/src/app/overrides/screens/payment_status.{js,xml}`.
- Solo display en la pantalla de pago; no cambia cálculo de IGTF, sincronización, asientos ni validación de "orden pagada".
