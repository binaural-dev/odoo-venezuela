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
