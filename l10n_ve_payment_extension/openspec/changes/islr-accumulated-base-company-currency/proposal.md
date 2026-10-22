# Fix: la base acumulada del ISLR se mide en la moneda de la compañía

> **Estado:** aplicado en la rama de trabajo; pendiente de ticket (sin id) y
> de commit.

## Why

Con tarifa acumulada (`accumulated_rate`) el tramo de retención se elige con la
base acumulada del ejercicio fiscal **medida en UT**, y el valor de la UT está
en bolívares. `_compute_related_fields` sumaba `amount_untaxed` de las
facturas, que está en la **moneda del documento**:

- Una factura de USD 1.000 (Bs 390.000 con tasa 390) aportaba 1.000 al
  acumulado en lugar de 390.000. Con UT = Bs 43: 23 UT en vez de 9.070 UT.
  El tramo y el % de retención salían incorrectos (15 % en lugar de 34 % en el
  ejemplo).
- Un ejercicio con facturas en USD y en Bs sumaba monedas distintas.

La base del sistema es siempre VEF, así que además la rama que sumaba
`groups_by_foreign_subtotal` cuando la compañía es USD era código muerto de v17.

## What Changes

- `l10n_ve_payment_extension/models/account_retention_line.py`
  (`_compute_related_fields`): el acumulado suma
  `abs(amount_untaxed_signed)` de las facturas anteriores más el de la factura
  actual, ambos en moneda de la compañía. Se elimina la rama de compañía USD.
- `tests/test_retention_islr_tarifa_2.py`: nueva prueba con una factura en USD
  cuyo monto en Bs cae en el Tramo 3 y cuyo monto en USD caería en el Tramo 1.

## Impact

- **Capability:** `l10n_ve_payment_extension` (ISLR con tarifa acumulada).
- **Facturas en VEF:** sin cambio (su `amount_untaxed_signed` es su
  `amount_untaxed`).
- **Facturas en divisas:** cambia el tramo elegido. Las retenciones ISLR
  acumuladas ya emitidas sobre facturas en divisas pudieron quedar con un
  tramo menor al que correspondía; este cambio es hacia adelante.
- **Fuera de alcance:** el redondeo a 2 decimales de la base en UT y qué valor
  de UT aplica según la fecha (hoy se usa la UT activa más reciente). Ambos
  requieren criterio del asesor tributario.
