## Context

Una línea de extracto en Bs nace con la cuenta puente como contrapartida. Al conciliarla contra una cuenta en $ el asiento deja de cuadrar en la moneda alterna, y el formulario de la línea de extracto permite dejar `amount` y `amount_currency` incoherentes. Este change corrige esos tres puntos en `l10n_ve_accountant`; los datos ya publicados se corrigen con un script de implementación, fuera del módulo.

## Decisions

### `create` completa `amount` y no se usa `foreign_amount`

`foreign_amount` (con `not_foreign_recalculate`) fija el débito y crédito **alterno** de las líneas del asiento, pero no cambia `amount` ni `amount_currency` de la línea de extracto: el asiento sigue naciendo en 0 Bs y la conciliación sigue mandando el valor del pago al diferencial cambiario. Además congela las líneas del recálculo. Por eso no alcanza y se completa `amount` en `create`, solo cuando llega en 0 o vacío con un monto en moneda extranjera distinta de la del diario; un `amount` explícito no se toca. No hay dos mecanismos para lo mismo: `foreign_amount` sigue siendo el alterno de la línea y `create` es el monto contable en la moneda del diario.

### Qué monto manda al cambiar la fecha o el diario

En un diario en Bs el monto en Bs es lo que el banco movió de verdad y de él sale el saldo del extracto. Al cambiar la fecha o el diario, `amount` se conserva y `amount_currency` se recalcula a la tasa de la nueva fecha. El monto en moneda extranjera solo fija `amount` cuando el usuario edita ese campo (o la moneda extranjera).

### Lectura de las líneas hermanas una vez por asiento

Con `move_id.line_ids.amount_currency` y `move_id.line_ids.currency_id` en el `depends`, cambiar una línea recalcula todas las del asiento, y cada una leía todas sus hermanas: crecimiento cuadrático. Ahora las hermanas se leen una vez por asiento durante `_compute_foreign_debit_credit` (`foreign_sibling_cache` en el contexto).

Medición (base de pruebas, un asiento por tamaño, editar dos líneas):

| Líneas, todo en Bs | Antes del change | Dependencias sin optimizar | Con lectura única |
|---|---|---|---|
| 201 | 0,02 s | 0,18 s | 0,02 s |
| 601 | 0,03 s | 1,38 s | 0,06 s |
| 1.201 | 0,06 s | 5,50 s | 0,11 s |

Crear el asiento de 1.201 líneas pasó de 6,9 s a 1,5 s. Con una línea en Bs y el resto en $ no hay diferencia apreciable en ningún caso (editar sigue en torno a 0,1 s).

### Montos alternos escritos a mano

Los ajustes manuales (`foreign_debit_adjustment`, `foreign_credit_adjustment`) y las líneas con `not_foreign_recalculate` no se pisan cuando cambia una línea hermana: lo cubre una prueba. Un valor escrito directamente en `foreign_debit`/`foreign_credit` sin esas marcas sí se recalcula, como ya ocurría al cambiar la propia línea; ahora también cuando cambia el monto o la moneda de una hermana, que es justo lo que busca el change.
