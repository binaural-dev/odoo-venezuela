## 1. l10n_ve_pos

- [x] 1.1 `_reconcile_statement_line_with_cross`: concilia la línea de extracto contra su línea del cruce, con sus resguardos
- [x] 1.2 `_create_cross_real_statement_lines`: concilia cada línea de extracto contra su línea del cruce, uno a uno
- [x] 1.3 Docstrings de `_create_cross_move` y `_create_cross_real_statement_lines`
- [x] 1.4 Opción `pos_post_cross_moves` (compañía, Ajustes) marcada por defecto; el cruce en borrador crea y concilia su línea al publicarse (`account.move._post_pos_cross`), una sola vez

## 2. Tests (`tests/test_pos_session_cross_account_move.py`)

- [x] 2.1 Cruce en efectivo: su línea de extracto queda conciliada y la transitoria en cero
- [x] 2.2 Transitoria sin conciliación: la línea queda abierta, sin error
- [x] 2.3 Cruce a otra tasa: la línea queda abierta
- [x] 2.4 Línea del cruce ya conciliada: no se concilia dos veces
- [x] 2.5 Cruce combinado: cada pata con su línea de extracto
- [x] 2.6 Cajero sin permisos contables: se concilia en sudo
- [x] 2.7 Opción marcada por defecto en una compañía nueva
- [x] 2.8 Cruce en borrador sin línea del diario real; al publicarlo, la línea conciliada
- [x] 2.9 Publicado otra vez: una sola línea de extracto

## 3. Revisión en enterprise

- [x] 3.1 Cajero con `accountant`: la transitoria queda conciliada y la línea sin revisar (`checked`) espera la revisión de contabilidad; se deja así (ver proposal)
