## 1. l10n_ve_pos

- [x] 1.1 `_reconcile_statement_line_with_cross`: concilia la línea de extracto contra su línea del cruce, con sus resguardos
- [x] 1.2 `_create_cross_real_statement_lines`: concilia cada línea de extracto contra su línea del cruce, uno a uno
- [x] 1.3 Docstrings de `_create_cross_move` y `_create_cross_real_statement_lines`

## 2. Tests (`tests/test_pos_session_cross_account_move.py`)

- [x] 2.1 Cruce en efectivo: su línea de extracto queda conciliada y la transitoria en cero
- [x] 2.2 Transitoria sin conciliación: la línea queda abierta, sin error
- [x] 2.3 Cruce a otra tasa: la línea queda abierta
- [x] 2.4 Línea del cruce ya conciliada: no se concilia dos veces
- [x] 2.5 Cruce combinado: cada pata con su línea de extracto
- [x] 2.6 Cajero sin permisos contables: se concilia en sudo

## 3. Pendiente

- [ ] 3.1 Prueba con un cajero en un staging con `accountant`: si la línea no revisada (`checked`) queda pendiente en el tablero
