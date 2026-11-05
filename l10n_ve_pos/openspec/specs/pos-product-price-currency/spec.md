# pos-product-price-currency Specification

## Purpose
TBD - created by archiving change l10n-ve-pos-product-price-double-conversion. Update Purpose after archive.
## Requirements
### Requirement: El precio del producto llega al PdV convertido una sola vez a la moneda de la caja

El sistema SHALL entregar `product.product.lst_price` al PdV en la moneda de la caja convertido una única vez desde la moneda del producto (conversión del core, `_convert_pos_data_currency`). `l10n_ve_pos` SHALL NOT volver a convertirlo.

#### Scenario: Caja USD en compañía VEF

- **GIVEN** un producto de Bs 10.399,71 y tasa 803,34 Bs/$
- **WHEN** se carga el PdV de la caja USD y se añade el producto a la orden
- **THEN** la línea vale $ 12,95, igual que la tarjeta, y no $ 0,02

#### Scenario: Caja en la moneda de la compañía

- **WHEN** la caja está en la moneda de la compañía
- **THEN** `lst_price` llega sin conversión, como antes

