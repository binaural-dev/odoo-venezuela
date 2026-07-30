# Fix: las líneas COGS descuadran la columna alterna de las facturas

## Why

Reportado el 2026-07-27 sobre la BD `pos2`, comparando dos facturas de PdV
idénticas de `Binaural C.A` por `31.243,04 Bs`:

| asiento | cobrable | Σ débito | Σ crédito | descuadre |
|---|---|---|---|---|
| `INV/2026/0204` (id 1035) | 42,56 | 42,77 | 42,56 | **+0,21** |
| `INV/2026/0205` (id 1048) | 42,35 | 42,56 | 42,56 | 0,00 |

Los 0,21 son exactamente el lado crédito de las tres líneas COGS
(`0,00 + 0,07 + 0,14`).

`_distribute_foreign_pt_residual` asignaba a las líneas `payment_term` la suma
**bruta** del lado contrario de las demás líneas:

```python
total_debit  = sum(other.mapped("foreign_debit"))
total_credit = sum(other.mapped("foreign_credit"))
...
foreign_total = total_debit if is_credit_side else total_credit   # ← bruto
```

Correcto mientras las "otras" líneas sean solo producto e impuesto, que en una
factura de venta viven todas del lado crédito. Pero las líneas **COGS son un
par autobalanceado**: aportan el mismo importe como débito y como crédito.
Sumar un solo lado las cuenta una vez y descuadra el asiento por ese importe.

Y están presentes cuando la función corre: `stock_account._post()`
(`stock_account/models/account_move.py:29`) las crea **antes** de llamar a
`super()._post()`, o sea con el asiento todavía en `draft`, que es la condición
que exige la función.

La fórmula bruta entró con el commit `8a048a82b` (2026-06-15, SaulOrte), que
está en `origin/19.0` y llegó a esta rama con el merge previo a este cambio.

## What Changes

- `l10n_ve_accountant/models/account_move.py`, `_distribute_foreign_pt_residual`,
  rama de moneda de compañía / moneda alterna: la contrapartida pasa de bruta a
  **neta**.

  ```python
  total_debit  = gross_debit - gross_credit
  total_credit = gross_credit - gross_debit
  ```

  Cualquier par autobalanceado queda neutro. Con el neto el asiento cuadra por
  construcción: si el `payment_term` va al debe recibe `haber − debe` de las
  demás líneas, y el total al debe queda `debe + (haber − debe) = haber`.

- Guarda para documentos ya corruptos: si el neto sale negativo se vuelve al
  bruto. Sin ella, `INV/2026/0137` —que tiene una línea de impuesto al débito
  con el importe alterno al haber y arrastra 71,28 de descuadre de origen—
  pasaría de un valor equivocado positivo a uno **negativo**, que es peor.

- La rama de tercera moneda no se toca.

## Qué flujos cambian, y cuáles no

El cambio solo puede alterar un documento si sus líneas no-`payment_term`
tienen importe alterno **en los dos lados**. Si no, `gross_debit` vale 0 y el
neto es aritméticamente idéntico al bruto.

Quedan fuera por las guardas de entrada de la función:

| flujo | por qué no le llega |
|---|---|
| pagos, IGTF, anticipos, retenciones | `if not move.is_invoice(...)`: son `entry` |
| cierre de sesión de PdV, extractos | ídem (707 asientos en `pos2`) |
| nómina, costes en destino | ídem |
| cualquier asiento ya publicado | `if move.state != 'draft'` |
| factura en tercera moneda | entra por la rama del agregado, que no se toca |
| compañía sin moneda alterna | `if not fc` |

De los que sí le llegan, los tipos de línea que aparecen del mismo lado que el
término de pago en `pos2` son solo tres:

```
cogs      248 apuntes / 165 facturas + 17 / 13 notas   ← el bug que se arregla
product     8 apuntes /   8 facturas +  4 /  4 notas   ← líneas de precio negativo
tax         2 apuntes /   2 facturas +  4 /  4 notas   ← consecuencia de las anteriores
```

Las de precio negativo ya están bloqueadas en el PdV por decisión del usuario.
Así que **el único flujo cuyo comportamiento cambia es el de facturación con
valoración de inventario en tiempo real**, que es justo el que estaba mal.

## Impact

- **Capability**: `invoice-foreign-column-balance` (nueva).
- **Módulo**: `l10n_ve_accountant`. Cambio solo Python, basta reiniciar Odoo.
- **Tests existentes**: los 22 de `tests/test_real_portion.py` pasan sin
  cambios. Del 07 al 22 son asientos manuales, que la función descarta. Del 01
  al 06 son facturas (USD, EUR, VEF, con uno y con tres plazos de pago) y
  ninguno monta valoración en tiempo real, así que `gross_debit` vale 0 y el
  neto coincide con el bruto.
- **Riesgo**: bajo, acotado al flujo de valoración en tiempo real.
- **Sin verificar en navegador todavía**: pendiente facturar desde el PdV con
  producto valorado y comprobar Σ débito alterno = Σ crédito alterno.

## Un aserto de test que conviene corregir aparte

`_assert_pt_vs_other_foreign` (`tests/test_real_portion.py:192`) codifica la
invariante **bruta**:

```python
self.assertAlmostEqual(pt_fd, other_fc, ...)   # PT debe == suma del haber ajeno
```

Hoy pasa porque ningún test tiene líneas del lado del término de pago. Pero en
cuanto alguien escriba un test con COGS fallará, y quien estará mal será el
aserto, no el código. La invariante correcta es la neta
(`pt_fd == other_fc - other_fd`) o directamente que el asiento cuadre. No se
toca aquí por no mezclar el fix con cambios en tests.

## Datos existentes

El fix actúa solo sobre asientos en borrador, así que **no corrige los ya
posteados**. En `pos2` quedan 177 facturas descuadradas —156 explicadas por sus
COGS, entre el 2026-07-13 y el 2026-07-27, $133,03 acumulados— cuya línea de
término de pago está congelada con `not_foreign_recalculate = t`. Necesitan
data-fix aparte.

Simulación sobre esos 207 documentos: de los 30 que hoy cuadran, el fix cambia
**cero**; de los 177 descuadrados, corrige 176 (el que falta es
`INV/2026/0137`, corrupta de origen).

## Hallazgos fuera de alcance

Salieron al simular y quedan anotados sin tocar:

1. **Líneas de precio negativo pierden el importe alterno.**
   `l10n_ve_pos/static/src/overrides/models/pos_order_line.js` corta con
   `if (baseUnitPrice <= 0) return 0`, así que toda línea de devolución dentro
   de una orden sale con `foreign_price = 0`. En `pos2`: 44 de 44 líneas
   afectadas, **201.855,30 Bs sin convertir**, y arrastra los impuestos, que se
   calculan sobre base incompleta (`INV/2026/0114`: IVA de 8,87 donde tocaba
   1,77). Ya bloqueado para órdenes nuevas; los documentos existentes siguen
   mal.

2. **Redondeo acumulado en facturas grandes.** `foreign_subtotal` multiplica la
   cantidad por un precio unitario alterno ya redondeado a 2 decimales. En
   facturas de miles de dólares se acumulan hasta 3,55 de desviación
   (`INV/2026/0157`).

3. **El cobrable no coincide con el pago.** En 179 de 190 facturas el importe
   alterno del término de pago difiere de la conversión de su propio total, que
   es la cifra que usan la orden del PdV, el asiento de venta y el pago.

   Se midió que aplicar `foreign = |balance| × tasa` a todas las líneas —la
   ruta *tercera moneda → principal → secundaria*, ya que `balance` siempre
   está en la principal— dejaría los 208 documentos dentro de **2 céntimos**
   (hoy el peor está en 88,73), resolviendo 1, 2 y 3 de una vez. Es una
   reescritura del núcleo del cálculo y se deja fuera deliberadamente. La
   factura emitida en la moneda alterna seguiría siendo excepción: su importe
   alterno sale de `amount_currency`, que es el dólar que firmó el cliente.

4. **La porción real que trajo el merge, sin auditar**:
   `_distribute_final_real_portion`, `_fix_company_currency_rounding` y
   `_apply_product_real_portion` reescriben `balance` —moneda legal— de líneas
   de impuesto y producto.

5. **Sin cobertura de datos**: en `pos2` y `pos` no hay ninguna factura emitida
   en la moneda alterna ni facturas de compra más allá de una. Los tests sí
   cubren ambos casos.
