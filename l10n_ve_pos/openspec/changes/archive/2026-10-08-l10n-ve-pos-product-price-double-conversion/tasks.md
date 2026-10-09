## 1. Fix

- [x] 1.1 Quitar la conversión de `lst_price` de `product.product._load_pos_data_read`
- [x] 1.2 Test `test_lst_price_converted_once_when_currency_differs` (sin correr en local)
- [x] 1.3 Bump `l10n_ve_pos` 1.20

## 2. Verificación

- [x] 2.1 Probado en posv19 (30-sep, reinicio sin `-u` + caché IndexedDB del PdV borrada): caja USD, línea del PRODUCTO 2 = $ 12,95 (Bs 10.403,25); Caja 1 VEF sigue en Bs 10.399,71
- [x] 2.2 Tests en CI (verde el 08-oct con el core 19.0 actual)
