# Fix: precio de la variante convertido dos veces en cajas en otra moneda (l10n_ve_pos)

Tarea: https://binaural.odoo.com/odoo/action-341/83148

## Why

En una caja cuya moneda no es la de la compañía (caja USD, compañía VEF) el
producto de Bs 10.399,71 se mostraba bien en la tarjeta ($ 12,95) pero la
línea de la orden quedaba en **$ 0,02** (Bs 16,07 a tasa 803,34).

`product.product._load_pos_data_read` de `l10n_ve_pos` convertía `lst_price`
de la moneda de la compañía a la de la caja. Es herencia de Odoo 17, donde el
core no convertía. En Odoo 19 el core ya lo convierte
(`pos.load.mixin._convert_pos_data_currency`, llamado por
`product.product._load_pos_data_read`), así que el precio llegaba convertido
dos veces: 10.399,71 × 0,0012448 = 12,95 → 12,95 × 0,0012448 = 0,02. La
tarjeta usa `product.template.list_price` (una sola conversión); la línea usa
`variant.lst_price`.

## What Changes

- `l10n_ve_pos/models/product_product.py`: se quita la conversión de
  `lst_price`; queda solo la del core.
- Test `test_lst_price_converted_once_when_currency_differs`: con tasa 36,5,
  $ 10 llegan como Bs 365,00 (antes Bs 13.322,50).

## Impact

- Cajas en la moneda de la compañía: sin cambios (ninguna de las dos
  conversiones aplicaba).
- Cajas en otra moneda: la línea toma el mismo precio que la tarjeta.
- El PdV cachea los productos en IndexedDB: tras actualizar hay que borrar la
  caché del PdV (o esperar a que se refresque) para ver el precio corregido.
