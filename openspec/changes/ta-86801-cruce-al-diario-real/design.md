## Context

`_create_cross_move` es el único punto por el que pasan todos los cruces: ventas
(`_validate_cross_move`), entradas/salidas de los cajones (`binaural_pos_close`,
que ya no cruza sus diferencias) y las cajas en otra moneda
(`binaural_pos_multicurrency`).
Un cruce en efectivo (`use_suspense=True`) deja el dinero en
`cross_journal.suspense_account_id`.

## Decisions

- **Publicar en `_create_cross_move`.** Un borrador no se concilia desde el
  tablero y los cierres acumulaban borradores. Contabilidad puede devolverlo a
  borrador mientras no esté conciliado.
- **Línea de extracto por cada línea del cruce en la transitoria del diario
  real**, no por cruce: un cruce combinado con entrada y salida tiene dos, y el
  tablero solo concilia una línea contra un cruce de su transitoria. Monto =
  `amount_currency` de esa línea (va en la moneda del diario real), alterna =
  `foreign_debit - foreign_credit`, fecha = la del cruce. Su contrapartida cae en
  la misma transitoria con el signo contrario. No se concilia sola: la concilia
  contabilidad desde el tablero, como pide la tarea.
- **Sin línea si las dos transitorias coinciden.** Las dos patas caen en la
  misma cuenta y no hay cómo saber cuál es la del diario real.
- **Etiqueta = `ref`**, que empieza con la sesión: es lo que muestra el tablero.
- **`_crosses_sales`** como gancho y no dentro de `_is_cross_move_eligible`: la
  elegibilidad la usan también las entradas/salidas, que sí deben cruzar.
- **De dónde sale la venta en efectivo.** El core solo registra salidas de
  efectivo en el diario de caja de la sesión (`cash_journal_id`), y
  `binaural_pos_close` en sus cajones, que no cruzan ventas. En ese diario la
  venta sale de su transitoria, donde la salida la deja en el debe; en cualquier
  otro (`_cross_sale_stays_in_journal`) sale de la cuenta del diario, donde la
  dejó el extracto nativo del cierre. Va por contexto
  (`CROSS_SALE_FROM_JOURNAL_ACCOUNT`, `_get_sales_cross_session`) para no cambiar
  la firma de `_create_cross_move_for`, que sobrescriben otros módulos.
- **Signo de la venta en efectivo** en el camino de las ventas
  (`_get_sales_cross_sign`, `_sign_cross_amounts`), no en
  `_get_cross_move_line_vals`: esa construcción la comparten las entradas/salidas
  de `binaural_pos_close`, que ya iban bien. La venta se arma como la salida de
  efectivo que la lleva al diario real.
- **`sudo` en `_create_cross_move`**, el punto por el que pasan todos los
  cruces; el asiento vuelve en el entorno de quien llama.

## Risks / Trade-offs

- La línea de extracto en un diario en divisa convierte con la tasa de su fecha;
  si el cruce usó otra, la conciliación genera diferencia en cambio por la
  diferencia en Bs (en el cruce de una entrada/salida es la misma tasa del día).
- Publicar puede fallar en el cierre por validaciones contables (fecha
  bloqueada, tasa faltante): las mismas que ya exigen los asientos nativos de la
  sesión.
