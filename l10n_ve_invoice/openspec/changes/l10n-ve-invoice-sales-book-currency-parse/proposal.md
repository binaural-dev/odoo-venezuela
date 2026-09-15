# Fix: parseo de importes formateados en el Libro de Compras/Ventas

## Why

Ticket Helpdesk #15026 (validación en 2doce). Al generar el Libro de Ventas de
un período con muchos registros (1–15 sep), el reporte prácticamente da timeout
(la conexión se pierde y reconecta) y el log se inunda de miles de líneas:

```
WARNING ... l10n_ve_invoice.wizard.accounting_reports:
No se pudo convertir la cadena de moneda 'Bs. 876,18' a float. Valor final procesado: '.'
```

Causa raíz en `convert_currency_to_float` (`wizard/accounting_reports.py`): los
importes llegan formateados por Odoo desde `move.tax_totals`, con la forma
`"Bs.\xa01.234,56"` (símbolo + espacio no-separable `\xa0` + monto es_VE). La
función partía la cadena por `\xa0` y se quedaba con el **lado izquierdo**:

```python
if '\xa0' in cleaned_str:
    cleaned_str = cleaned_str.split('\xa0', 1)[0]   # -> "Bs." (¡el símbolo!)
```

Como en la localización venezolana el símbolo va **antes** del monto, el lado
izquierdo es `"Bs."`, la regex posterior lo reduce a `"."`, y `float(".")` lanza
`ValueError` → la función devuelve `0.0` y loguea el warning. Es decir:

1. **Todos los importes VES daban 0.0** → el resumen del pie del Libro de
   Compras/Ventas (`_determinate_resume_books`) sumaba ceros; los totales del
   reporte salían mal.
2. **Inundación de logs / timeout**: `_determinate_amount_taxeds` (que llama a
   `convert_currency_to_float` ~varias veces por asiento) se invoca ~30+ veces
   por asiento entre el cuerpo y el resumen (16 líneas de resumen × varias
   pasadas). Con el bug, cada llamada emite un `WARNING`, produciendo cientos de
   miles de líneas de log síncronas en un período grande → la petición se
   estanca y el proxy corta la conexión.

`move.tax_totals` es un campo computado `store=False`, cacheado por el ORM dentro
del request, así que la recomputación repetida no es el cuello de botella: el
motor del timeout es la avalancha de logs, que este fix elimina.

## What Changes

- `wizard/accounting_reports.py`, `convert_currency_to_float`: se elimina el
  bloque que partía por `\xa0`. La regex `[^\d,\.-]` ya descarta el símbolo, las
  letras y cualquier espacio (incluido `\xa0`), y la regla "si hay punto y coma,
  el punto es de miles" limpia el punto sobrante de `"Bs."`. El resultado es
  correcto tanto con el símbolo antes (`"Bs.\xa0876,18"` → `876.18`) como
  después (`"876,18\xa0Bs."` → `876.18`).
- `tests/test_accounting_reports.py`: casos nuevos para símbolo antes con `\xa0`,
  miles + decimales, cero, y símbolo después.

### Rendimiento (segunda iteración)

Tras el fix del parseo, en 2doce (4690 asientos de venta en 1–15 sep) el reporte
seguía muriendo por `CPU time limit exceeded` (`limit_time_cpu = 60`). Causa:
`_determinate_amount_taxeds` se invoca ~1 vez por asiento en el cuerpo y ~16
veces por asiento en el resumen (`_determinate_resume_books` se llama una vez por
línea de resumen y recorre todos los asientos), o sea ~17× por asiento → ~80k
invocaciones en el período. `move.tax_totals` ya lo cachea el ORM por request,
pero la reconstrucción del dict + parseo de importes se repetía en cada llamada.

- Se memoiza `_determinate_amount_taxeds` por `move.id` durante una generación
  del libro. El cache vive en el contexto (`_ve_book_amounts_cache`), porque los
  recordsets no admiten atributos (`__slots__`), y lo siembran los entrypoints
  `generate_sales_book` / `generate_purchases_book` con
  `self.with_context(...)`. No cambia ninguna firma → cero riesgo para los
  overrides de `l10n_ve_payment_extension` / `binaural_third_party_invoice`.
- El resultado del método solo se consume en lectura (`_fields_sale_book_line`
  arma un dict nuevo, `_determinate_resume_books` solo suma valores), así que
  devolver el mismo objeto cacheado es seguro.
- `__manifest__.py`: versión `19.0.1.0.13` → `19.0.1.0.15`.

## Non-goals

- No se toca la memoización de `_determinate_amount_taxeds`: `tax_totals` ya está
  cacheado por el ORM y el fix del parseo elimina la avalancha de logs, que era
  el driver del timeout. Queda como follow-up solo si tras esto sigue lento.
- No se cambia el diseño de leer importes ya formateados desde `tax_totals`
  (huele a re-parseo, pero es el diseño base de la migración V19 y excede este
  fix).
