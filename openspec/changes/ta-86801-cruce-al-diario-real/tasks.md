## 1. l10n_ve_pos

- [x] 1.1 `_create_cross_move`: etiqueta de las líneas = `ref`, publicar el asiento
- [x] 1.2 `_create_cross_real_statement_lines`: una línea de extracto en `cross_journal` por cada línea del cruce en su transitoria; nada si coincide con la del diario del método
- [x] 1.3 `_cross_move_ref`: sesión primero; el combinado nombra el método (`payment_method`)
- [x] 1.4 Gancho `_crosses_sales` consultado por `_validate_cross_move`
- [x] 1.5 `i18n/es_VE.po`: "Sales" → "Ventas"; fuera "PoS Payment Method Adjustment"
- [x] 1.7 Venta en efectivo cruzada como la salida (`_get_sales_cross_sign`, `_sign_cross_amounts`)
- [x] 1.8 Cruce y línea de extracto en `sudo`; socio de otra compañía fuera de la línea
- [x] 1.6 Bump de manifest

## 2. Tests (`tests/test_pos_session_cross_account_move.py`)

- [x] 2.1 Los cruces quedan publicados y toman la secuencia del diario
- [x] 2.2 Etiqueta de las líneas con la sesión y el método
- [x] 2.3 Cruce en efectivo: línea de extracto en el diario real con monto, alterna y etiqueta; se concilia uno a uno con el cruce
- [x] 2.4 Entrada y salida: una línea de extracto cada una, con signos contrarios
- [x] 2.5 Cruce de banco: sin línea de extracto
- [x] 2.6 Transitorias compartidas: sin línea de extracto
- [x] 2.7 `_crosses_sales` en `False`: no se cruza la venta
- [x] 2.8 Venta en efectivo + salida nativa: la transitoria del método queda en cero
- [x] 2.9 Cruce creado por un cajero sin permisos contables
- [x] 2.10 Socio de otra compañía fuera de la línea de extracto
- [x] 2.11 Signos de la venta en efectivo invertidos en los tests de la moneda de cobro
