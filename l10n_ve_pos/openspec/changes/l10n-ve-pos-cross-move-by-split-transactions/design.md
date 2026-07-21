# Design: cruce automático regido por `split_transactions`

Este change **supera** a `l10n-ve-pos-cross-account-move` en dos puntos: qué
dispara el cruce y contra qué cuenta se cruza. El resto de aquel design
(asiento en `draft`, secuencia del diario en `name`, texto en `ref`) sigue
vigente y no se repite acá.

## El bug que motivó todo: dos disparadores

El flujo tenía dos entradas que se ignoraban mutuamente.

```
action_pos_session_close()
  └─ super()                                  # pipeline nativo
  │    └─ _create_account_move()
  │         └─ _create_bank_payment_moves()    # SOLO métodos bank
  │              └─ _create_combine_account_payment()
  │                   └─ _create_cross_move_payment()   ← disparador 2
  └─ _validate_cross_move()                              ← disparador 1
       for cada pos.payment de la sesión:                  (sin filtrar
         crea un asiento                                    split_transactions)
```

Resultado por tipo de método, con `N` pagos en la sesión:

| Método | Disparador 1 | Disparador 2 | Total | Esperado |
|---|---|---|---|---|
| bank, split | N | — | N | N ✓ |
| bank, combine | N | 1 | **N+1** | 1 ✗ |
| cash, split | N | — | N | N ✓ |
| cash, combine | N | — | **N** | 1 ✗ |

El efectivo nunca llega al disparador 2 porque `_create_bank_payment_moves`
solo recorre métodos `bank` (nativo `pos_session.py:1057`); el efectivo va por
`_create_cash_statement_lines_and_cash_move_lines` (nativo `:1172`).

Por eso el usuario veía "un asiento por cada pago" con "Identificar cliente"
activo **y** desactivado: en split era el comportamiento correcto por
accidente, y en combine el disparador 1 lo pisaba todo.

## La granularidad correcta, según el nativo

`split_transactions` ("Identify Customer") ya define la granularidad en el
pipeline nativo. En `_accumulate_amounts` (nativo `pos_session.py:892`) la
clave del acumulador cambia:

```python
elif is_split_payment and payment_type == 'bank':
    split_receivables_bank[payment] = ...          # clave = pos.payment
elif not is_split_payment and payment_type == 'bank':
    combine_receivables_bank[payment_method] = ... # clave = método de pago
```

Nota: el `help` nativo del campo dice "splits the journal entries for each
customer", pero la implementación agrupa por **pago**, no por partner. Cada
pago lleva un partner, así que en la práctica coincide salvo cuando un mismo
cliente paga varias veces en la sesión — ahí el nativo genera un registro por
pago, no uno por cliente. El cruce replica exactamente esa clave.

## Diseño resultante

Un único punto de entrada, que lee `pos.payment` directamente en vez del
`account.payment` que produce el pipeline bancario. Eso es lo que permite que
`cash` y `bank` compartan código: el efectivo nunca genera un `account.payment`.

```
action_pos_session_close()
  └─ super()
  └─ _validate_cross_move()
       payments = pagos de la sesión filtrados por _is_cross_move_eligible
       for cada payment_method en esos pagos:
         if split_transactions:
           for cada pago: _create_cross_move_for(...)      # N asientos
         else:
           neto = suma(amount);  if neto == 0: skip
           _create_cross_move_for(..., neto, suma(foreign_amount))  # 1 asiento
```

`_create_cross_move_for` elige rama por el signo: `incoming` si `amount >= 0`,
`outgoing` si es negativo. Bajo granularidad combine el importe ya viene
neteado, así que una sesión con más devoluciones que ventas produce un único
asiento saliente — la rama que la ruta combine legacy nunca tuvo (el design
anterior la documentaba como limitación heredada, "el vuelto siempre se paga
en efectivo"; al netear deja de ser cierto).

La tasa del agregado se toma de `method_payments[0].foreign_rate`, no de
`config_id.foreign_rate`: la tasa operativa es de sesión y todos los pagos
neteados la comparten, pero el valor del `config` es editable después de abrir
la sesión, mientras que el pago guarda la tasa que realmente se aplicó.

## La cuenta transitoria depende del tipo de método

Los dos pipelines nativos dejan el dinero en sitios distintos:

| Tipo | Cómo lo contabiliza el nativo | Dónde queda el saldo |
|---|---|---|
| `bank` | `account.payment` con `force_outstanding_account_id = payment_method.outstanding_account_id` (nativo `:1104`) | `outstanding_account_id` |
| `cash` | statement line: debita `journal_id.default_account_id`, acredita la POS receivable (`_get_combine_statement_line_vals`, nativo `:1452`) | `journal_id.default_account_id` |

En `cash` la POS receivable queda **saldada en cero** al cerrar: el statement
line la acredita justo por lo que las líneas de venta la debitaron. Cruzar
contra ella descuadraba una cuenta en cero y dejaba el efectivo intacto en la
cuenta del diario.

`outstanding_account_id` no es una alternativa para `cash`: es
`invisible="type != 'bank'"` en la vista nativa
(`point_of_sale/views/pos_payment_method_views.xml:24`), así que un método
cash siempre lo tiene vacío.

```python
if payment_method.type == "cash":
    account = payment_method.journal_id.default_account_id
else:
    account = payment_method.outstanding_account_id or payment_method.journal_id.default_account_id
return account or self.company_id.account_default_pos_receivable_account_id
```

La POS receivable queda como último recurso para que una configuración
incompleta degrade en un cruce omitido (vía `_is_cross_move_eligible`) en vez
de un `account_move_line_check_accountable_required_fields` por `account_id`
nulo.

### El descuadre, con números

Venta de $100 con un método `cash` "Efectivo $" (diario *Caja $*, cuenta
`101-02`). Al cerrar sesión el nativo genera **dos** asientos:

**1. Asiento de sesión** (`_get_combine_receivable_vals`, nativo `:1365`):

```
                             Debe      Haber
101-01  POS por cobrar     100.00
401-01  Ingresos                     100.00
```

**2. Statement line del diario de caja** (`_get_combine_statement_line_vals`,
nativo `:1452`):

```
                             Debe      Haber
101-02  Caja $             100.00
101-01  POS por cobrar               100.00
```

Saldos resultantes: `101-01` POS por cobrar = **0** (debitada y acreditada por
lo mismo dentro del propio cierre); `101-02` Caja $ = **100**. La POS por
cobrar es una cuenta puente que nace y muere en la misma operación, no la
transitoria del efectivo.

**Cruce con el código viejo** (transitoria = POS por cobrar):

```
                             Debe      Haber
102-05  Banco Real         100.00
101-01  POS por cobrar               100.00     ← ya estaba en cero
```

| Cuenta | Antes | Después |
|---|---|---|
| `101-01` POS por cobrar | 0 | **−100** ← saldo acreedor fantasma |
| `101-02` Caja $ | 100 | **100** ← intacto, nunca se movió |
| `102-05` Banco Real | 0 | 100 |

El activo queda duplicado ($100 en caja + $100 en banco cuando solo entraron
$100) y una cuenta por cobrar queda con saldo acreedor sin respaldo. El asiento
cuadra (debe = haber) pero el mayor miente, y el cruce no cumplió su función:
el efectivo sigue en `101-02`.

**Cruce con el fix** (transitoria = cuenta del diario):

```
                             Debe      Haber
102-05  Banco Real         100.00
101-02  Caja $                       100.00
```

| Cuenta | Antes | Después |
|---|---|---|
| `101-01` POS por cobrar | 0 | **0** ← no se toca |
| `101-02` Caja $ | 100 | **0** ← vaciada |
| `102-05` Banco Real | 0 | **100** ← el dinero llegó |

**Por qué `bank` nunca sufrió esto**: el nativo no usa statement lines para
bank, crea un `account.payment` que debita la outstanding y acredita la POS
por cobrar. El saldo **sí** queda en la outstanding, así que apuntar ahí era
correcto desde el principio — de ahí que la verificación en producción con
"Zelle" (change anterior, tarea 4.3) diera bien y el bug pasara inadvertido.

### Detección en datos existentes

La huella del bug es un saldo distinto de cero en la POS por cobrar tras un
cierre limpio:

```python
env["account.move.line"].read_group(
    [("account_id", "=", <id POS por cobrar>), ("parent_state", "=", "posted")],
    ["balance:sum"], [],
)
```

Si no da cero, revisar los asientos del diario de cruce con
`ref = "PoS Payment Method Adjustment"` que toquen esa cuenta: son los
generados sobre métodos `cash` y hay que revertirlos y regenerarlos contra la
cuenta del diario de caja.

Nota adicional: el código viejo usaba `account_default_pos_receivable_account_id`
(el default de la compañía), mientras que el nativo resuelve
`payment_method.receivable_account_id or <default>`. Si algún método tenía una
cuenta por cobrar propia, el cruce ni siquiera apuntaba a la misma cuenta que
el nativo había usado. Con el fix el punto es discutible: esa cuenta ya no se
toca en absoluto.

## Por qué `is_foreign_currency` y no un flag propio

`apply_one_cross_move` era un segundo opt-in encima de `is_foreign_currency`.
No aportaba ninguna decisión que los diarios de cruce no expresaran ya: un
método sin `cross_journal` no puede cruzar, y uno que tiene ambos diarios
configurados es porque alguien los puso a propósito. Su único efecto real era
dejar el flujo apagado en métodos que claramente lo necesitaban — de hecho el
change anterior nació de descubrir que el campo llevaba años en la UI sin
hacer nada.

El guard de `pay_later` **no** es redundante: un método pay_later no tiene
`journal_id`, así que caería en el fallback de la POS receivable y pasaría por
elegible. Se excluye por tipo, explícitamente.

## Trazabilidad de los borradores

Detectado verificando en producción (BD `pos`, sesión 65, método "Efectivo $"
con "Identificar cliente"): el usuario reportó que sólo se había generado el
cruce de una de las dos órdenes. En realidad **se generaron los dos** — pero
en la lista de asientos salían idénticos:

```
Número   Fecha        Socio     Referencia                       Importe   Estado
/        21/07/2026   (vacío)   PoS Payment Method Adjustment    19,29     Borrador
/        21/07/2026   (vacío)   PoS Payment Method Adjustment    19,29     Borrador
```

Mismo `/` (la secuencia no se asigna hasta postear, por diseño), misma fecha,
mismo importe, misma referencia, y la columna "Socio" vacía en ambos porque
el partner iba sólo en las líneas. Dos filas calcadas que se leen como una.

Con granularidad split una sesión genera N borradores; sin discriminador son
inauditables. `ref` es el único campo libre disponible: `name` está reservado
para la secuencia del diario (ver bug #5 del change anterior).

**Por qué el `ref` baja hasta el pago y no se queda en la orden**: una orden
puede tener varios pagos del mismo método. Ya hay un caso real en la BD `pos`
(orden 5, dos pagos "Efectivo $" de 11.821,08 y 354,63). Con el nombre de la
orden como única referencia, ese caso volvería a producir borradores
idénticos.

**Por qué el id como discriminador**: `pos.payment.name` es un "Label" libre
que sólo llenan los terminales de pago — está vacío en todos los pagos
manuales de la BD `pos` — y `display_name` cae al importe formateado, que
tampoco es único. El id es el único valor garantizado distinto, y además
permite buscar el pago directamente.

```
split:    PoS Payment Method Adjustment - Binaural C.A - 000004 - #77
combine:  PoS Payment Method Adjustment - <nombre de la sesión>
```

### El partner de la cabecera puede bloquear el cierre

Fijar `partner_id` en la cabecera parecía gratis y no lo es:

| Campo | `check_company` |
|---|---|
| `account.move.partner_id` | **Sí** (`account/models/account_move.py:425`) |
| `account.move.line.partner_id` | No |
| `pos.order.partner_id` | No (`point_of_sale/models/pos_order.py:316`) |

Odoo acepta sin chistar una orden de PoS cuyo cliente pertenezca a otra
compañía, porque ese campo no valida nada. Pero al propagarlo a la cabecera
del asiento, `_check_company` lanza `UserError` y **tumba el cierre completo
de la sesión** — a cambio de una mejora de legibilidad. Detectado por el test
`test_split_move_header_carries_the_partner`, que reventó con
`"Uh-oh! You've got some company inconsistencies here"` antes de añadir el
guard.

`_cross_move_header_partner` devuelve un recordset vacío en ese caso. El
asiento se crea igual, las líneas conservan el partner (no tienen
`check_company`) y el `ref` sigue identificando el pago. Se degrada la
presentación, nunca la operación.

## Decisiones

| Decisión | Elegido | Por qué |
|---|---|---|
| ¿Disparador del cruce? | `is_foreign_currency` + ambos diarios | El cruce es la contrapartida contable de un método en divisa; el flag extra solo apagaba el flujo |
| ¿Qué hacer con `apply_one_cross_move`? | Eliminarlo | Dejarlo ignorado repetiría el problema original: un interruptor en la UI que no hace nada |
| ¿Unificar split y combine en un solo hook? | Sí | La asimetría era la causa raíz del doble asiento; además permite tratar cash y bank igual |
| ¿Netear los pagos en combine? | Sí | Es lo que hace el `account.payment` combinado nativo; habilita la rama saliente |
| ¿Neto cero crea asiento? | No | No hay saldo que trasladar |
| ¿Tasa del agregado? | `method_payments[0].foreign_rate` | El `config` es mutable tras abrir la sesión; el pago guarda la tasa aplicada |
| ¿Cuenta transitoria de `cash`? | `journal_id.default_account_id` | Es donde el nativo deja el efectivo; la POS receivable queda en cero |
| ¿Postear automáticamente? | No, sigue en `draft` | Sin cambios: contabilidad revisa y valida a mano |
| ¿Granularidad del `ref`? | Hasta el `pos.payment` | Una orden puede tener varios pagos del mismo método; el nombre de la orden aún repetiría |
| ¿Discriminador del pago? | `payment.name or #id` | `name` sólo lo llenan los terminales; `display_name` cae al importe, que no es único |
| ¿Partner en la cabecera? | Sí, con guard de compañía | Sin él la columna "Socio" sale vacía; con él, un cliente de otra compañía tumbaría el cierre |

## Verificación

Pendiente de correr la suite y de prueba manual en navegador (ver `tasks.md`).
El escenario clave a validar a mano es el que originó el reporte: un método
bank combinado con varios pagos en una sesión debe producir **un** asiento, y
el mismo método con "Identificar cliente" activo debe producir uno por pago.
