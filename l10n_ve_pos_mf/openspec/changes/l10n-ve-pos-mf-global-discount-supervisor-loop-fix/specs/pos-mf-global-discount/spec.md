## ADDED Requirements

### Requirement: Limpieza síncrona y sin gate de las líneas de descuento global

Al normalizar el descuento global a descuento por línea (Estrategia A), la
conversión SHALL eliminar las líneas de descuento creadas por `pos_discount`
mediante un borrado **síncrono** (`line.delete()`), y NO a través de
`order.removeOrderline()`. Estas líneas son gestionadas por el sistema, por lo
que su borrado NO SHALL pasar por el gate de supervisor de borrado de línea
(`pos_remove_orderline_require_supervisor_key`).

#### Scenario: Descuento global con clave de supervisor de borrado activa

- **GIVEN** una caja con `pos_remove_orderline_require_supervisor_key` y
  `pos_discount_require_supervisor_key` activos
- **WHEN** el cajero aplica un descuento global y confirma el porcentaje
- **THEN** se pide la clave de supervisor **una sola vez** (al abrir el
  descuento), el descuento se aplica como descuento por línea, y la caja NO se
  bloquea ni apila popups de supervisor adicionales

#### Scenario: Sin re-disparo del debounce de pos_discount

- **WHEN** la conversión elimina las líneas de descuento del sistema
- **THEN** el borrado es inmediato, `order.globalDiscountPc` queda en 0 antes de
  modificar el resto de líneas, y el listener `update` de `pos_discount` no
  vuelve a invocar `applyDiscount`

#### Scenario: El gate de borrado manual del cajero se conserva

- **WHEN** el cajero elimina manualmente una línea de producto normal
- **THEN** se sigue exigiendo la clave de supervisor (este cambio no afecta ese
  camino)
