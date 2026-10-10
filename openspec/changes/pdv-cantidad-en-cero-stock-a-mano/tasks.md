## 1. Implementación

- [x] 1.1 `pos.config.check_stock_availability` contra el stock a mano de la ubicación origen de la caja
- [x] 1.2 `PosStore.pay()` y `validateOrderFast()` (pago rápido): bloquear antes de cobrar con el detalle por producto
- [x] 1.3 Traducciones es_VE de las cadenas JS
- [x] 1.4 Tests `tests/test_pos_config_stock_availability.py` (a mano suficiente/insuficiente,
      reservado por otra orden no bloquea, otro almacén no cuenta, no almacenables, check apagado)
- [x] 1.4b Respaldo sin conexión solo con `ConnectionLostError`; caja sin ubicación origen no valida (test)
- [x] 1.5 Versión del manifest 19.0.1.22.0
- [x] 1.6 Prueba en navegador en posv19-consultor: 7 con 1 a mano bloquea; 7 con 8 a mano y 7 reservadas pasa a pago
