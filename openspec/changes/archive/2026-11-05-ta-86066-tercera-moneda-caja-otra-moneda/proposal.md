## Why

Tarea https://binaural.odoo.com/odoo/action-341/86066, fase 2. La fase 1
(`archive/2026-11-04-ta-86066-pdv-tercera-moneda`) cobra en una tercera moneda (EUR) en una caja en
la moneda de la compañía y bloquea las cajas en otra moneda (`binaural_pos_multicurrency`): las tasas
de `tender_currency_rates` son contra la moneda de la compañía. Ahora una caja en otra moneda también
tiene que poder cobrar en una tercera moneda: EUR en una caja en USD y USD en una caja en EUR.

Decisiones con el usuario (2026-11-04, opciones recomendadas del plan): commits en la misma rama y los
mismos PRs; en la caja en EUR la tercera moneda es la alterna (USD); el diario del método es el
transitorio en la moneda de la caja; la conversión es la nativa de `binaural_pos_multicurrency`, que
pasa por la moneda de la compañía sin redondear (EUR → Bs × Bs → USD), con la regla de la fase 1 de
no cobrar sin la tasa del día; IGTF se mide primero.

## What Changes

- **Validaciones por caja**: lo que depende de la caja lo valida cada caja del método con un gancho,
  `pos.config._get_tender_currency_error`. Aquí sigue igual: solo cajas en la moneda de la compañía,
  sin la alterna como moneda de cobro. `binaural_pos_multicurrency` lo extiende para las cajas en otra
  moneda. El método valida solo lo suyo: no es `is_foreign_currency`, no es la moneda de la compañía,
  no es de crédito y tiene sus dos diarios de cruce, el real en esa moneda.
- **Cruce**: sin `currency_amount`, la línea del diario real convierte el monto **desde la moneda de la
  compañía** (antes, desde la de la sesión: en una caja en otra moneda tomaba los Bs como USD).
- **Transitoria en la moneda de su diario**: parámetro opcional `transitory_amount_currency` en
  `_create_cross_move_for`, `_get_cross_move_line_vals`, los constructores de líneas y las patas del
  cruce combinado (`transitory_amount_of`). Con él, la línea transitoria va en la moneda del diario del
  método con ese monto, y la transitoria queda en cero también en esa moneda. Sin él, como siempre. Solo
  lo pasa `binaural_pos_multicurrency` (diario transitorio en la moneda de una caja en otra moneda).

## Non-goals

- Lo de las cajas en otra moneda en sí (tasa, montos, cajón): `binaural_pos_multicurrency`,
  `binaural_pos_close` y `binaural_pos_close_multicurrency`, en integra-addons.
- Los no-objetivos de la fase 1 siguen: vuelto en la moneda de cobro, código fiscal en la máquina
  fiscal, columnas en EUR en los reportes.

## Impact

- **Módulo:** `l10n_ve_pos` 19.0.1.29.1 → 19.0.1.30.0. Sin campos nuevos.
- **Caja en la moneda de la compañía:** sin cambios. Las mismas validaciones (el mensaje de la alterna
  sale ahora al agregar el método a la caja) y el mismo cruce (el parámetro nuevo no se pasa; la
  conversión desde la compañía da lo mismo cuando caja y compañía coinciden).
- **Método sin caja con la alterna como moneda de cobro:** se acepta; se rechaza al agregarlo a una caja
  en la moneda de la compañía.
- **Despliegue:** igual que la fase 1, odoo-venezuela primero y en la misma ventana que integra-addons.
