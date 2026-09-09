## Why

Al aplicar el **descuento global** en una caja con **ambos** flags de
supervisor activos (`pos_discount_require_supervisor_key` **y**
`pos_remove_orderline_require_supervisor_key`), la caja se queda **en negro y
congelada**: tras confirmar el porcentaje, se apilan decenas de popups de
"Supervisor" hasta bloquear el renderer.

La causa es una cadena de tres piezas:

1. `l10n_ve_pos_mf` → `PosStore._applyGlobalDiscountBeforeValidation()`
   (Estrategia A: convertir el descuento global de `pos_discount` en descuento
   por línea para la máquina fiscal) elimina las líneas de descuento con
   `order.removeOrderline(line)` **sin `await`**.
2. `binaural_pos_hr` sobreescribe `PosOrder.removeOrderline` como método
   **async**: con `pos_remove_orderline_require_supervisor_key` abre un popup de
   supervisor y **sólo elimina la línea tras el PIN**. Como la llamada no se
   espera, la línea de descuento **nunca se elimina** → `order.globalDiscountPc`
   sigue distinto de 0.
3. `pos_discount` registra un listener `update` en `pos.order.line` que, si
   `globalDiscountPc ≠ 0`, vuelve a llamar a `applyDiscount` (debounced). Y
   `_applyGlobalDiscountBeforeValidation` justo después hace `setDiscount()`
   sobre las líneas positivas → dispara ese listener → re-entra en
   `applyDiscount` → otro `removeOrderline` → otro popup → **bucle infinito**.

Con el gate de supervisor resolviéndose rápido (o desactivado) el bucle no se
manifiesta porque la línea sí se borra antes de que dispare el debounce; por eso
sólo aparece en cajas con la clave de supervisor de borrado de línea activa.

## What Changes

- `overrides/PosStore.js`, método `_applyGlobalDiscountBeforeValidation`:
  - Las líneas de descuento global, que son **gestionadas por el sistema** (no
    por el cajero), se eliminan con `line.delete()` — borrado **síncrono y sin
    gate**, exactamente como hace el propio `pos_discount` con sus líneas de
    descuento — en lugar de `order.removeOrderline(line)`.
  - Con esto la línea se elimina de inmediato, `globalDiscountPc` pasa a 0 antes
    de tocar las demás líneas, el debounce de `pos_discount` no re-dispara, y el
    descuento se aplica una sola vez.

No se toca el gate de supervisor para el borrado manual de líneas por el cajero:
sigue exigiendo clave.

## Capabilities

### Added Capabilities

- `pos-mf-global-discount`: invariante de la conversión Estrategia A del
  descuento global — la limpieza de las líneas de descuento del sistema no pasa
  por el gate de supervisor de borrado de línea y es síncrona, para no bloquear
  ni entrar en bucle.

## Impact

- Módulo: `l10n_ve_pos_mf` (`static/src/overrides/PosStore.js`).
- Afecta a cualquier caja con `pos_remove_orderline_require_supervisor_key`
  activo que use descuento global (p. ej. cliente 2doce, cajas C1/C3).
- Sin cambios de datos ni de dependencias. Asset estático: requiere
  reconstruir/servir los assets (o `--dev=all` + hard refresh) para verlo.
