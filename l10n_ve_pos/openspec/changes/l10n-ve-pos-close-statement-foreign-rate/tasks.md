# Tasks

## 1. Diagnóstico

- [x] 1.1 Reproducir en posv19 (sesión `Caja 1/00054`, tasa del cierre 870 vs venta 854,4637): extractos CSH1 687,50 vs 700,00 y CSH2 98,21 vs 100,00
- [x] 1.2 Confirmar en BD: la línea por cobrar tiene `not_foreign_recalculate = True` y la de caja no
- [x] 1.3 Descartar `foreign_amount` en el extracto (doble conteo en `binaural_pos_close`)

## 2. Implementación

- [x] 2.1 `set_foreign_amount_in_line`: copiar y bloquear la contrapartida solo en extractos
- [x] 2.2 Test `tests/test_pos_session_close_statement_foreign_rate.py` (extracto cuadra con tasa distinta el día del cierre; asiento de sesión no bloquea ventas)
- [x] 2.3 Bump `l10n_ve_pos` 1.18 → 1.19
- [x] 2.4 `tests/test_pos_session_accounting_common.py`: crear el producto con `with_company(cls.company)` — el guard de compañía de `l10n_ve_stock` (sin bypass de `su`) tumbaba el `setUpClass` de todas las clases que heredan de la base. Mismo cambio en `test_pos_data_loading.py` y `test_pos_serialization.py`, que crean su propio producto

## 3. Validación

- [x] 3.1 Correr los tests de `l10n_ve_pos` en BD temporal: 0 fallos / 0 errores de 82 tests; el test nuevo falla sin el fix
- [x] 3.2 Repetir en navegador el caso de posv19 y comprobar que ambos extractos cuadran en alterno (`Caja 1/00087`: CSH1 426,62/426,62, CSH2 2,78/2,78)
- [x] 3.3 Documentar el emparejamiento por monto (origen, por qué lo obliga el core, riesgo y camino propuesto)
