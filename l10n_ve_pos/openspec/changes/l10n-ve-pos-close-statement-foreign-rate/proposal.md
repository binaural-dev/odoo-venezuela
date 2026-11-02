# Fix: el extracto de caja del cierre mezcla tasa de venta y tasa de cierre en moneda alterna (l10n_ve_pos)

Ticket #15169.

## Why

Si la tasa BCV cambia entre la venta y el cierre de la sesión, los asientos
de extracto de caja que genera el cierre (uno por método de efectivo, p. ej.
ESVEF / C1USD) quedan descuadrados en moneda alterna: el Crédito alterno de la
cuenta por cobrar del PdV sale a la tasa de la venta y el Débito alterno de la
cuenta de caja a la tasa del cierre, sobre el mismo monto en Bs.

Reproducido en posv19 (sesión `Caja 1/00054`): venta de $800 a 854,4637
(Efectivo $100 + Efectivo Bs 598.124,59), tasa del día del cierre 870,00.

| Asiento | Débito alterno | Crédito alterno |
|---|---|---|
| extracto Efectivo Bs | $687,50 (598.124,59 / 870) | $700,00 |
| extracto Efectivo USD | $98,21 (85.446,37 / 870) | $100,00 |

### Causa raíz

El core crea los extractos del cierre solo con el monto en Bs.
`set_foreign_amount_in_line` fija el `foreign_amount` de la venta en la línea
por cobrar (con `not_foreign_recalculate = True`) y lo copia en la línea de
caja, pero **sin bloquearla**. `l10n_ve_accountant`
(`_compute_foreign_debit_credit`) vuelve a calcular esa línea con la tasa de
la fecha del asiento, que es la del cierre.

### Emparejamiento por monto (preexistente, se mantiene)

`_create_cash_statement_lines_and_cash_move_lines` recorre, por cada pago
(split) o método (combine), las líneas de **todos** los pagos/métodos y
`set_foreign_amount_in_line` elige la línea por `debit/credit == amount` (Bs).
No es un descuido de este change: viene de 17.0 (9f93e9512, 2024-04-17, tarea
[#24422](https://binaural.odoo.com/web#id=24422&model=project.task&view_type=form)),
sin motivo documentado, y después solo se movió de sitio (52b588e1d,
6e967a9c4, 6708d0ea2) o se tocó en
`l10n-ve-pos-session-close-cash-foreign-amount-fix`, que ya lo anota como caso
borde.

Lo que obliga a emparejar por monto es el core
(`point_of_sale/models/pos_session.py::_create_cash_statement_lines_and_cash_move_lines`):

- `split/combine_cash_statement_lines` son las líneas por cobrar de los
  extractos creados (`mapped('move_id.line_ids').filtered(receivable)`) y
  `split/combine_cash_receivable_lines` las del asiento de sesión
  (`MoveLine.create(vals)`), en recordsets planos: pese a los comentarios
  ("maps journal -> lines"), la línea no trae ni el pago ni el método.
- La línea por cobrar del asiento de sesión tampoco lleva el diario del
  método. La única pista común entre el bucket (`amounts['amount']`) y la
  línea es el monto.
- Emparejar por índice sería posible (`create()` preserva el orden de los
  vals y se arman recorriendo el mismo dict), pero depende de un detalle de
  implementación del core y en combine hay que replicar el filtro
  `if not float_is_zero(amounts['amount'])` para no desalinear.

**Riesgo conocido**: dos pagos (split) o dos métodos (combine) con el mismo
monto en Bs y distinto `foreign_amount` —posible si la sesión abarca un cambio
de tasa— se quedan con el alterno del último que se escribe. Con este change,
además, ese valor queda bloqueado en la línea de caja del extracto. Cada
extracto sigue cuadrado (se copia el mismo valor a las dos patas), pero con el
alterno de otro pago.

No se corrige aquí (fuera del alcance del ticket). Camino propuesto para otro
change: emparejar por identidad donde exista —extracto split por
`payment_ref == payment.name`, extracto combine por
`line.move_id.journal_id == payment_method.journal_id`— y dejar monto o
índice solo para la línea por cobrar del asiento de sesión, que no tiene
identidad.

## What Changes

- `models/pos_session.py::set_foreign_amount_in_line`: cuando el asiento de la
  línea es un extracto (`move_id.statement_line_id`), la contrapartida de caja
  se copia **siempre** y se marca `not_foreign_recalculate = True`.
- En cualquier otro asiento (el asiento de la sesión) ya no se copia nada a la
  "primera línea no por cobrar": ahí no es una contrapartida de caja sino una
  línea de ventas o impuestos de órdenes no facturadas, y bloquearla dejaría
  fijo un valor equivocado. Esa línea sigue en manos del cálculo base.

Se descartó pasar `foreign_amount` al `account.bank.statement.line` del
cierre: `binaural_pos_close` suma `foreign_amount` de las líneas de extracto
del diario de efectivo foráneo para el saldo en dólares de la sesión, y
contaría dos veces lo vendido.

## Impact

- **Módulo**: `l10n_ve_pos`, solo Python (sin schema): basta reiniciar Odoo.
- **Asientos ya generados**: no se corrigen (sin data-fix en este change).
- **Fuera de alcance**:
  - Órdenes **no facturadas**: sus líneas de ventas/impuestos del asiento de
    la sesión se valoran a la tasa del cierre mientras las por cobrar quedan a
    la tasa de venta. No ocurre en la práctica (en VE toda orden del PdV se
    factura: 2doce 3.703/3.703), requiere acumular el alterno de ventas e
    impuestos por orden.
  - Diario de efectivo **con moneda USD**: el core registra en el extracto la
    conversión de los Bs a la tasa del cierre (`_prepare_statement_line_amount_values`),
    no los dólares cobrados. Los diarios de efectivo del PdV de los clientes
    actuales no tienen moneda.
  - Emparejamiento por monto entre pagos/métodos con el mismo monto en Bs
    (ver "Emparejamiento por monto" arriba).

## Validación en posv19

Fix superpuesto (solo `pos_session.py`) en posv19. Venta `Caja 1 - 000006`
(INV/2026/0063) a 870: 4.540 Bs en Efectivo + 2.420 Bs ($2,78) en Efectivo
USD-1. Tasa del 28-09 subida a 880 y cierre de la sesión `Caja 1/00087` desde
el PdV.

| Asiento | Débito alterno | Crédito alterno | Sin el fix (caja a 880) |
|---|---|---|---|
| CSH1 `/2026/0004` (Efectivo Bs) | 426,62 | 426,62 | 421,77 |
| CSH2 `CSH2/2026/0017` (Efectivo USD-1) | 2,78 | 2,78 | 2,75 |
| POSS/2026/0098 (asiento de sesión) | 429,40 | 429,40 | — |

Ambas patas de cada extracto quedan con `not_foreign_recalculate = True`.
