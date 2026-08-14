# Spec delta: pos-sale-details-foreign-totals

## ADDED Requirements

### Requirement: El reporte "Detalles de venta" usa la estructura nativa de Odoo 19

El sistema SHALL generar `report.point_of_sale.report_saledetails.get_sale_details()`
delegando en la implementación nativa de `point_of_sale` (categorías de
productos, reembolsos, impuestos, descuentos, facturas, arqueo de caja),
sin reemplazarla por una estructura de datos distinta.

#### Scenario: Sesión con ventas de varias categorías de producto

- **GIVEN** una sesión de PdV cerrada con órdenes de al menos dos
  categorías de producto distintas
- **WHEN** se genera el reporte "Detalles de venta" de esa sesión
- **THEN** el reporte se renderiza sin error, agrupando los productos
  vendidos por categoría (`products[].name`, `products[].products`)

### Requirement: El reporte agrega los totales en moneda foránea de la compañía

El sistema SHALL agregar a la salida de `get_sale_details()` el total
pagado en la moneda foránea de la compañía (`company.foreign_currency_id`)
y su desglose por método de pago, sin alterar ninguno de los campos
nativos ya presentes.

#### Scenario: Compañía con moneda foránea configurada

- **GIVEN** una compañía con `foreign_currency_id` configurado (p. ej.
  USD) y una sesión con pagos en uno o más métodos
- **WHEN** se genera el reporte "Detalles de venta"
- **THEN** la sección de pagos muestra, junto al monto nativo de cada
  pago y del total de la sesión, su equivalente en la moneda foránea
  (`payments[].f_total`, `foreign_total_paid`,
  `payments_per_method[].f_total`)

#### Scenario: Compañía sin moneda foránea configurada

- **GIVEN** una compañía sin `foreign_currency_id`
- **WHEN** se genera el reporte "Detalles de venta"
- **THEN** el reporte se renderiza igual que el nativo de Odoo 19, sin
  columnas ni valores adicionales de moneda foránea
