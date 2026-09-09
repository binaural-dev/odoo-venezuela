## 1. Corrección del bucle

- [x] 1.1 En `_applyGlobalDiscountBeforeValidation` (`PosStore.js`), eliminar las
      líneas de descuento global con `line.delete()` en vez de
      `order.removeOrderline(line)` (síncrono, sin gate de supervisor)
- [x] 1.2 Comentario explicando por qué NO se usa `removeOrderline` (async +
      gateado por `binaural_pos_hr` → línea no borrada → bucle del debounce)

## 2. Verificación

- [x] 2.1 Reproducción en navegador (BD 212, caja C1-CCS, ambos flags activos):
      confirmado el bucle de popups / pantalla negra con el código anterior
- [x] 2.2 Verificación del fix en vivo (patch equivalente en runtime):
      `removeOrderline` se llama 1 sola vez, descuento aplicado por línea, sin
      pantalla negra ni diálogos colgados
- [ ] 2.3 Reconstruir assets y re-verificar en navegador con el código commiteado
- [ ] 2.4 Prueba: aplicar descuento global con y sin
      `pos_remove_orderline_require_supervisor_key`; y sobre orden de 1 y de
      varias líneas
