# pos-payment-foreign-rate Specification

## Purpose
TBD - created by archiving change l10n-ve-pos-payment-foreign-rate. Update Purpose after archive.
## Requirements
### Requirement: Cada pago del PdV guarda la tasa con la que se valoró

El PdV SHALL enviar en cada pago de la orden sincronizada `foreign_rate` igual al
multiplicador efectivo de la orden (`get_effective_foreign_multiplier`), el que
usó para su `foreign_amount`. El servidor SHALL rellenar con la tasa de la orden
(o la de la orden original en un reembolso) los pagos que no son vuelto y
lleguen sin tasa, y SHALL respetar la tasa que llegue.

#### Scenario: Venta cobrada en una caja en Bs

- **GIVEN** una venta de 9.318,74 Bs (11,60 $) a 803,34 cobrada con el
  efectivo Bs
- **WHEN** el PdV sincroniza la orden
- **THEN** el comando del pago lleva `foreign_rate` 0,001244802947693 y el pago
  lo guarda

#### Scenario: Reembolso

- **GIVEN** un reembolso cuya venta original se cobró a 795 Bs por $
- **WHEN** el PdV sincroniza el reembolso
- **THEN** su pago lleva `foreign_rate` 1 / 795, no la tasa de hoy

#### Scenario: PdV con el bundle anterior

- **GIVEN** una orden cuyos pagos llegan con `foreign_rate` 0
- **WHEN** el servidor procesa los pagos
- **THEN** cada pago que no es vuelto toma la `foreign_currency_rate` de la
  orden, o la de la orden original si es un reembolso (una aproximación: el PdV
  actual usa la tasa exacta del pago foráneo original, `get_refund_foreign_rate`,
  o la proporción de los totales en un cambio de producto)

#### Scenario: Pago que ya trae tasa

- **GIVEN** un pago que llega con `foreign_rate` 33
- **WHEN** el servidor procesa los pagos
- **THEN** conserva 33

