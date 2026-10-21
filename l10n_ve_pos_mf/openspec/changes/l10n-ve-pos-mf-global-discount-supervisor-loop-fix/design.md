## Contexto

`_applyGlobalDiscountBeforeValidation` (Estrategia A del hand-off MF, TA 78328)
normaliza el descuento global de `pos_discount` a descuento por línea para que la
máquina fiscal lo imprima. El primer paso es retirar las líneas de descuento que
`pos_discount` creó (producto de descuento con precio negativo).

## Decisión

Retirar esas líneas con `line.delete()` en vez de `order.removeOrderline(line)`.

### Por qué

- `order.removeOrderline` está sobreescrito en `binaural_pos_hr` como **async**
  y, con `pos_remove_orderline_require_supervisor_key`, abre un `SupervisorPopup`
  y sólo elimina la línea si el PIN es válido. `_applyGlobalDiscountBeforeValidation`
  es **síncrono** y llama sin `await`, así que la promesa queda pendiente y la
  línea no se elimina.
- `pos_discount` re-aplica el descuento (debounced) cada vez que cambia una
  `pos.order.line` mientras `order.globalDiscountPc ≠ 0`. Como la línea negativa
  sigue presente, `globalDiscountPc` nunca baja a 0; y el `setDiscount()` que
  este mismo método hace sobre las líneas positivas dispara ese re-cálculo →
  re-entrada infinita, un popup por vuelta, hasta congelar la caja.
- `line.delete()` es el mismo mecanismo que usa `pos_discount` internamente para
  limpiar sus líneas de descuento (ver `applyDiscount` en su `pos_store.js`):
  borrado síncrono en memoria, sin pasar por el gate de cajero. Son líneas del
  sistema, no acciones del cajero, así que el gate no aplica.

### Alternativas descartadas

- **Hacer `_applyGlobalDiscountBeforeValidation` async y `await` el
  `removeOrderline`**: no resuelve la UX (dispararía un segundo popup de
  supervisor por una línea interna) y obliga a `await` en todos los llamadores
  (`OrderPaymentValidation.js`, `applyDiscount`).
- **Excluir las líneas de descuento del gate en `binaural_pos_hr.removeOrderline`**
  (`orderline.isDiscountLine`): válido como defensa en profundidad, pero modifica
  el contrato de un módulo compartido; se prefirió el arreglo localizado en el
  módulo que introdujo la conversión.

## Riesgos

- `line.delete()` no reajusta la línea seleccionada como sí lo hace
  `removeOrderline`; en este flujo la selección se rehace después (el propio
  `applyDiscount`/Estrategia A reselecciona), y `pos_discount` usa el mismo
  patrón, así que es seguro.
