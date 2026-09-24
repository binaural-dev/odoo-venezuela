# Notas técnicas de diseño

Contenido migrado desde comentarios/docstrings largos en el código (regla del
equipo: máximo 4 líneas por comentario). Cada sección es referenciada desde
el código con `# Ver openspec: design-notes.md § <título>`.

## § foreign_exposure_at_residual (algoritmo)

`_foreign_exposure_at_residual(residual)` reemplaza la vieja fórmula basada
en tasa (`_compute_foreign_exchange_amount`). Es una función PURA de
`residual`: `foreign_original * (residual / original)`, donde `original =
debit - credit` (monto original en moneda de compañía, inmutable una vez
contabilizada la línea) y `foreign_original = foreign_debit - foreign_credit`
(fijado al contabilizar, nunca re-derivado de una tasa aquí).

Ser pura es lo que garantiza que una liquidación partida en varios partials
sume EXACTAMENTE el monto alterno fijo de la línea, sin arrastre de
redondeo: el residual DESPUÉS del partial N es el mismo valor que el
residual ANTES del partial N+1, así que la función evalúa idéntico en ambos
puntos y las diferencias de partials consecutivos "telescopan"
perfectamente (`foreign_at(original) - foreign_at(0)` para la suma de
CUALQUIER partición del rango `[0, original]`).

Los dos extremos (`residual == 0` o `residual == original`) se retornan
EXACTOS (0.0, o el monto alterno fijo sin modificar) sin multiplicar/redondear
ningún float ahí — ratio 0 o ratio 1 deben reproducir el valor guardado
exactamente, no una aproximación de punto flotante.

Cubierto por `test_foreign_exposure_at_residual_is_exact_at_both_extremes` y
`test_three_uneven_partials_sum_exactly_to_the_line_fixed_foreign_amount`.

## § Exclusión: factura ya denominada en la moneda alterna

`_alt_exchange_diff_currency(rate_source)` retorna `False` (sin intentar
ningún cálculo) si: el toggle de compañía está apagado, no hay moneda
alterna configurada (o coincide con la de compañía), o `rate_source` (el
lado factura del partial, o el lado de fecha más antigua si ninguno es
factura — ver `_prepare_reconciliation_single_partial`) está denominado
directamente en esa moneda alterna.

Ese último caso preserva la exclusión histórica: cuando la factura ya está
en la moneda alterna, su exposición en esa moneda es fija y exacta desde el
origen (`amount_currency`) — no hay nada que revaluar, sin importar cuánto
diferencial nativo en VEF se genere (ese diferencial es un artefacto de
medir valor en una moneda que se devaluó, no un cambio real en la deuda en
USD). Ver requirement "Ninguna factura denominada en la moneda alterna
genera diferencial alterno" en `specs/foreign-currency-exchange-difference/spec.md`.

## § compute_alt_exchange_diff_from_settlement (caso standalone)

Diferencial alterno introducido al liquidar `self` y `other` dentro de un
mismo partial, donde el residual en moneda de compañía de cada línea se
mueve de `_before` a `_after`. Se calcula como `consumed(self) +
consumed(other)`, con `consumed(line) = foreign_at(residual_before) -
foreign_at(residual_after)` usando SOLO el monto alterno fijo de esa línea
(nunca una tasa re-derivada independientemente — el bug que esto reemplaza,
ver § "Bug de redondeo reportado en producción" abajo).

El resultado es simétrico en `self`/`other` por construcción: no importa
cuál es debit o credit, ni cuál es `rate_source` — nunca hace falta
re-orientar el signo en el caller. Verificado contra ambas orientaciones:
aplicar el resultado tal cual a la línea de cierre de `rate_source` siempre
sale con el signo correcto de pérdida/ganancia (convención `positivo =
pérdida`).

## § compute_alt_exchange_diff_from_slice (caso combinado)

Versión de un solo lado de la fórmula anterior, para una porción de
residual de ESTA línea que va de `residual_before` hasta cerrarse del todo
(0) — usado en `_inject_foreign_exchange_amounts`, donde el propio core ya
aisló esa porción como "lo que a esta línea específica le falta corregir",
sin nada pendiente del lado de la contraparte para esa misma corrección.

## § resolve_closing_line

Identifica a cuál de `debit_line`/`credit_line` pertenece un dict
`closing_vals` (construido por `_prepare_exchange_difference_move_vals` del
core), vía el comando `reconciled_lines_ids` que el core embebe ahí
(`Command.set` del AML exacto que se está cerrando) — más robusto que asumir
un orden de pareja fijo, ya que el core es libre de emitir una corrección
para un solo lado, el otro, o ambos, en cualquier orden. Retorna `None` si
no se puede determinar (defensivo ante un cambio futuro de esa forma en el
core).

## § inject_foreign_exchange_amounts (dos ramas del core)

El monto base se reconstruye del `debit`/`credit` que el propio core ya
calculó para la línea de cierre (`'debit': -residual si residual<0 else 0,
'credit': residual si residual>0 else 0'` — ver
`_prepare_exchange_difference_move_vals` del core). El core tiene una
SEGUNDA rama (`recon_currency == company_currency`) donde la corrección se
expresa vía `amount_residual_currency` en vez de `debit`/`credit` (ambos en
0 ahí) — se usa `amount_currency` (`-amount_residual_currency`) como
fallback para no saltarse esa rama.

Caveat conocido (preexistente, no reintroducido por esta sesión): en esa
segunda rama, `amount_currency` está expresado en la moneda PROPIA de la
línea de cierre, no necesariamente en moneda de compañía —
`_foreign_exposure_at_residual` lo sigue tratando como si tuviera la forma
de un residual en moneda de compañía, lo cual solo cuadra exacto cuando esa
moneda propia coincide con la moneda alterna (el caso real común: pagar una
factura en VEF desde un diario en USD).

## § _prepare_reconciliation_single_partial (hook principal)

Se engancha en `_prepare_reconciliation_single_partial` (corre en cada
partial, a diferencia de `_prepare_exchange_difference_move_vals`, que corre
una vez por asiento). Reglas:

- Honra `no_exchange_difference`/`no_exchange_difference_no_recursive`: si
  el propio core suprime su lógica bajo ese contexto (p. ej. al cerrar la
  línea receivable del propio asiento de diferencial), un `exchange_values`
  ausente NO debe leerse como "nada que corregir" y caer al branch
  standalone — eso crearía un asiento que el core deliberadamente no quiso.
- Fecha: reusa `exchange_values['move_values']['date']` si el core construyó
  un asiento (la misma fecha `max(debit.date, credit.date)` que usa el
  core), o ese mismo `max()` si no construyó ninguno — nunca
  `fields.Date.context_today()`, que usaría la tasa de HOY en vez de la
  fecha real de liquidación de ese partial.
- `rate_source`: se prefiere el lado factura (mismo criterio que
  `account.partial.reconcile._compute_company_id`, "los asientos de
  diferencial deben crearse del lado factura si existe"). Si ninguno de los
  dos lados es factura (asientos varios, ambos 'entry'), se prefiere el
  lado de fecha MÁS ANTIGUA — es el único cuya tasa de reserva puede
  realmente diferir de la tasa de liquidación; preferir un lado arbitrario
  (p. ej. siempre debit) arriesga escoger la línea fechada EN la
  liquidación, cuya tasa siempre coincide con la actual, anulando el
  diferencial silenciosamente.
- Cuando `line_commands` no está vacío, el core ya decidió que hace falta
  una corrección en moneda de compañía para al menos uno de los dos lados —
  se reusa el monto que el core mismo calculó por pareja, nunca se
  re-deriva independientemente: una comparación de residual antes/después
  a secas da un valor distinto de cero para AMBOS lados de cualquier
  conciliación ordinaria, no solo el lado que de verdad necesita
  corrección, y misatribuiría el ajuste al lado equivocado.
- Cuando `line_commands` SÍ está vacío, significa genuinamente que nada
  necesitaba corrección en moneda de compañía (el core ya deja
  `remaining_debit/credit_amount` en cero ANTES de decidir qué módulo
  construye el documento final — verificado contra
  `account/models/account_move_line.py` del core — así que esto es
  independiente de si `l10n_ve_exchange_difference` desvía el asiento hacia
  una nota fiscal). Es seguro derivar el monto liquidado de una comparación
  de residual antes/después: sin ninguna corrección de por medio, ambos
  lados liquidan el mismo principal exacto, sin asimetría que misatribuir.

## § open_reconcile_view (Reconciled Items)

El `open_reconcile_view` del core solo incluye líneas con
`matched_debit_ids`/`matched_credit_ids` — el asiento standalone nunca
reconcilia contra nada por diseño, así que nunca aparecería ahí aunque sea
económicamente parte de la misma liquidación. El caso combinado no necesita
esta extensión: reusa el asiento nativo del core, que SÍ reconcilia de
verdad.

Se busca por `l10n_ve_exchange_foreign_source_move_id` O
`l10n_ve_exchange_foreign_payment_move_id` (el asiento standalone registra
ambos independientemente), filtrando solo la línea de "cierre" (mismo
`account_type` que la cuenta cobrar/pagar liquidada) — la otra línea
(contrapartida de ganancia/pérdida) no pertenece a esta vista. Se excluyen
asientos con `reversal_move_ids` (una reversión queda `posted`, "reversado,
no cancelado" — debe dejar de aparecer en el momento en que se revierte, ya
que la liquidación que rastreaba ya no existe).

El domain de `action` se parsea defensivamente (no se asume
`action['domain'][0][2]`) porque el core construye hoy un único leaf
`[('id', 'in', ids)]`, pero nada garantiza que esa forma sobreviva un
parche futuro del core.

## § _reverse_moves (account_move.py) — fix de reversión

Core revierte negando `balance`/`amount_currency`, pero no sabe nada de
`foreign_debit`/`foreign_credit` (campos propios de este módulo) — sin este
fix, esos campos quedaban en 0/0 (duplicados sin invertir, según el caso) en
vez de invertidos. El fix intercambia `foreign_debit`↔`foreign_credit` línea
por línea, emparejando posicionalmente contra el original (`zip(original.
line_ids, reversal.line_ids)` — el orden de `line_ids` del asiento de
reversión replica exactamente el del original, generado por
`_reverse_moves` del core línea por línea).

Sin este fix, revertir un asiento de diferencial alterno (standalone o
combinado) dejaba su registro en moneda alterna desbalanceado
permanentemente, aunque el asiento en VEF sí quedara correctamente revertido
— un hueco silencioso, ya que nada en el asiento de VEF delata el problema.

## § _get_all_reconciled_invoice_partials — fila sintética en el widget de Pagos

`_get_all_reconciled_invoice_partials` es el único método que TODAS las
variantes de `_compute_payments_widget_reconciled_info` llaman (la del
core, y la reimplementación desde cero de `l10n_ve_igtf`, que nunca llama a
`super()`) — el único hook honesto para que el asiento standalone aparezca
en el widget "Pagos" de la factura, ya que nunca reconcilia por diseño y el
SQL propio del core jamás lo encuentra.

`is_exchange=True` es deliberado: oculta el botón "Desconciliar" (que de
otro modo quedaría muerto — no hay un partial real detrás de esta fila para
desconciliar) en el popover. El costo aceptado es que el renderer
duplicado/no-modificable de ese popover fija el `currency_id` de esa fila a
la moneda de COMPAÑÍA en vez de respetar la moneda alterna que este método
sí provee — un detalle visual, no afecta el monto ni el asiento contable
real.

Se filtra por `reversal_move_ids = False` por la misma razón que en
`open_reconcile_view`: un asiento reversado sigue `posted`, pero la
liquidación que rastreaba ya no existe — debe dejar de aparecer en el
widget de Pagos en el momento en que se revierte (antes de este fix, la
nota "Diferencial de cambio" seguía apareciendo en la factura después de
desconciliar, aunque el asiento ya estuviera revertido).

## § account_partial_reconcile.unlink() — red de seguridad

`account.partial.reconcile.unlink()` normalmente NO necesita hacer nada
extra: al deshacer una conciliación por el camino nativo
(`remove_move_reconcile`/desconciliar desde la UI), el propio core ya
revierte `exchange_move_id` automáticamente antes o durante el `unlink`. La
red de seguridad cubre el escenario en que un flujo de terceros borra el
`account.partial.reconcile` SIN pasar por ese camino nativo completo (por
ejemplo, un `unlink()` directo sobre el partial disparado por lógica externa
que no invoca la reversión de core) — en ese caso, esta override revierte el
`exchange_move_id` (si sigue `posted` y sin `reversal_move_ids` ya) después
de que el `unlink()` del partial se complete. Es un no-op cuando el camino
nativo ya hizo el trabajo: la condición `move.state == 'posted' and not
move.reversal_move_ids` es falsa en ese caso porque el asiento ya quedó
revertido por el core.

## § Bug de redondeo reportado en producción (motivó `_foreign_exposure_at_residual`)

Caso real: factura de 133,00 VEF reservada a 8,65, liquidada en un solo
partial a 8,79. Con la fórmula VIEJA basada en tasa,
`round(133.00 * (1/8.65 - 1/8.79), 2)` da `0.24` — un centavo distinto del
valor real entre los dos montos fijos y ya redondeados de factura y pago
(`15.38 - 15.13 == 0.25`), porque esa fórmula reinventa el monto a partir de
una tasa en vez de leer los dos números reales que factura y pago ya llevan.
Este es el mismo patrón del caso reportado en producción
(`foreign_debit == 15.37`, `foreign_credit == 15.14`, dando `0.22` en vez de
`0.23`). Cubierto por
`test_full_settlement_with_non_clean_rates_matches_real_reported_amounts_exactly`.
