# Visualización del descuento del PoS sobre la base imponible

## Purpose

Definir cómo `l10n_ve_pos` muestra la línea de descuento por su monto sobre la
base imponible (sin IVA) sin alterar el cálculo ni el dato de la línea.

## Requirements

### Requirement: La línea de descuento se muestra sin IVA en moneda local

Cuando la caja está en impuestos incluidos (`iface_tax_included == "total"`), la
línea cuyo producto es `pos.config.discount_product_id` DEBE mostrarse por su
monto sobre la base imponible (`priceExcl`), no por el monto con IVA
(`priceIncl`). El resto de las líneas conserva su comportamiento.

#### Scenario: Descuento con IVA al 8% en caja con impuestos incluidos

- GIVEN una caja con `iface_tax_included = "total"` y un producto de base `10,00` con IVA `8%`
- WHEN se aplica un descuento del `10%` (línea de descuento base `-1,00`, IVA `-0,08`)
- THEN el carrito y el recibo muestran la línea de descuento como `-1,00` (no `-1,08`)
- AND las demás líneas siguen mostrándose con IVA

#### Scenario: El dato subyacente no cambia

- GIVEN la línea de descuento mostrada como `-1,00`
- WHEN se calculan base, IVA y total de la orden
- THEN la base se reduce en `1,00`, el IVA en `0,08` y el total en `1,08`
- AND el `price_unit` y el impuesto de la línea de descuento no se modifican

### Requirement: La línea de descuento se muestra sin IVA en divisa

El monto en divisa mostrado para la línea de descuento DEBE ser el equivalente
sin IVA (`get_foreign_price_without_tax`), aunque la caja esté en impuestos
incluidos, para ser consistente con el monto en moneda local. El resto de las
líneas conserva el monto en divisa con IVA (`get_foreign_price_with_tax`).

#### Scenario: Display en divisa del descuento

- GIVEN una orden con moneda extranjera y caja en `iface_tax_included = "total"`
- WHEN se muestra la línea de descuento
- THEN su monto en divisa es la conversión del neto sin IVA, no del monto con IVA

### Requirement: La referencia del descuento por línea es la base imponible

Cuando una línea de producto tiene un descuento propio (`discount > 0`) y la caja
está en impuestos incluidos, el texto de referencia del descuento
("X% discount off on Y", `displayPriceNoDiscount`) DEBE mostrar el precio
pre-descuento sobre la **base imponible** (`priceExclNoDiscount`), no el precio
con IVA (`priceInclNoDiscount`). Es un getter de display (no entra en cálculos).

#### Scenario: Descuento de línea 10% sobre producto con IVA 31%

- GIVEN un producto de base `10.000` con IVA `31%` (con IVA = `13.100`) en caja `iface_tax_included = "total"`
- WHEN se aplica `10%` de descuento a la línea
- THEN la referencia muestra "10% off on 10.000" (base), no "10% off on 13.100"
- AND el total de la orden no cambia (sigue calculándose con el dato real de la línea)

#### Scenario: Línea sin descuento no cambia su referencia

- GIVEN una línea sin descuento
- WHEN se muestra
- THEN `displayPriceNoDiscount` conserva el comportamiento del core

### Requirement: Solo aplica a la línea de descuento

El override NO DEBE alterar la visualización de líneas de producto normales ni
la de cajas configuradas sin impuestos incluidos (`"subtotal"`), donde el core ya
muestra los montos sin IVA.

#### Scenario: Línea de producto normal intacta

- GIVEN una línea de producto normal en caja con impuestos incluidos
- WHEN se muestra
- THEN su precio se muestra con IVA como antes del cambio
