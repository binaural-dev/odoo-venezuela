## 1. Implementación

- [x] 1.1 `pos.config.check_stock_availability` contra el stock a mano de la ubicación origen de la caja
- [x] 1.2 `PosStore.pay()` y `validateOrderFast()` (pago rápido): bloquear antes de cobrar con el detalle por producto
- [x] 1.3 Traducciones es_VE de las cadenas JS
- [x] 1.4 Tests `tests/test_pos_config_stock_availability.py` (a mano suficiente/insuficiente,
      reservado por otra orden no bloquea, otro almacén no cuenta, no almacenables, check apagado)
- [x] 1.4b Respaldo sin conexión solo con `ConnectionLostError`; caja sin ubicación origen no valida (test)
- [x] 1.5 Versión del manifest 19.0.1.26.0 (19.0 está en 1.24.0; la 1.25.0 la usa el PR del ticket 15725, #1441)
- [x] 1.6 Prueba en navegador en posv19-consultor: 7 con 1 a mano bloquea; 7 con 8 a mano y 7 reservadas pasa a pago

## 2. Correcciones del code review

- [x] 2.1 `check_stock_availability` omite con `exists()` los productos borrados (antes `MissingError`) y test
- [x] 2.2 Archivar el change y volcarlo en `openspec/specs/l10n_ve_pos/spec.md`, con la nota de que las
      rutas `/validate_products_*` no las llama ningún JS de O19
