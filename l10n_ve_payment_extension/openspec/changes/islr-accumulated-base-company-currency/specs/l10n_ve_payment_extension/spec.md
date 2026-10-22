# Spec delta: l10n_ve_payment_extension

## MODIFIED Requirements

### Requirement: Fórmula de retención ISLR con tarifa acumulada por tramos en UT

Para tarifas con `accumulated_rate`, la selección del tramo
(`_compute_related_fields`) DEBE (MUST): (1) determinar el inicio del ejercicio
fiscal con `fiscalyear_last_day`/`fiscalyear_last_month` de la compañía y
buscar las facturas publicadas del mismo partner, de la misma compañía, con
`move_type` igual al **tipo del comprobante** (`retention_id.type`) y fecha
entre el inicio del ejercicio y la fecha de la factura actual, conservando solo
las que ya tienen líneas de retención ISLR; (2) acumular su base **en la moneda
de la compañía**, sumando el valor absoluto de `amount_untaxed_signed` de esas
facturas más el de la factura actual, sin importar la moneda de cada documento;
(3) dividir ese total entre el valor de la UT de la tarifa
(`tax_unit_ids.value`, un Many2one) y multiplicarlo por
`percentage_tax_base / 100`; y (4) elegir, sobre los tramos ordenados por
`start`, el primero cuyo rango `start`–`stop` contenga ese valor, tratando
`stop = 0` como tramo infinito, tomando su porcentaje y un sustraendo igual a
`subtract_ut × valor UT`. El monto retenido (`_compute_retention_amount`) se
calcula sobre la base de la **propia línea** (`invoice_amount`, en moneda de la
compañía): base en UT redondeada, por el porcentaje de base imponible, por el
porcentaje del tramo, menos el sustraendo expresado en UT, todo multiplicado de
vuelta por el valor de la UT y en valor absoluto.

> Reemplaza la regla anterior, que sumaba `amount_untaxed` en la moneda de cada
> documento (o la base foreign si la compañía era USD) y calculaba el monto con
> `foreign_invoice_amount` en compañías con base distinta de VEF. La base del
> sistema es siempre VEF.

#### Scenario: Factura en divisas

- **WHEN** el proveedor tiene una factura de USD 1.000 con tasa 390 y la UT vale
  Bs 43
- **THEN** su aporte al acumulado es Bs 390.000 (9.069,77 UT) y no 1.000

#### Scenario: Ejercicio con facturas en monedas distintas

- **WHEN** el ejercicio tiene facturas en USD y en Bs
- **THEN** el acumulado suma las bases de todas en Bs
