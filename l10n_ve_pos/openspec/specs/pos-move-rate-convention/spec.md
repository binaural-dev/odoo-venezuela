# pos-move-rate-convention Specification

## Purpose
TBD - created by archiving change l10n-ve-pos-move-rate-convention. Update Purpose after archive.
## Requirements
### Requirement: Los asientos del PdV siguen la convención de tasas de la compañía

La factura y los asientos de pago de una orden del PdV SHALL guardar
`foreign_inverse_rate` igual al multiplicador moneda de la compañía → alterna
con que se valoró la orden o el pago, y `foreign_rate` igual a su inverso, con
`manually_set_rate`. Sin multiplicador, el sistema SHALL dejar que el asiento
tome la tasa de su fecha. El alterno de las líneas MUST NOT cambiar.

#### Scenario: Factura de una venta en una caja en Bs

- **GIVEN** una orden valorada a 803,34 Bs por $ (multiplicador
  0,001244802947693)
- **WHEN** se factura
- **THEN** la factura lleva `foreign_rate` 803,34 y `foreign_inverse_rate`
  0,001244802947693, y sus líneas y totales en $ son los mismos que antes

#### Scenario: Compañía con base en USD

- **GIVEN** una compañía en USD con alterna Bs y una orden valorada al
  multiplicador 803,34 (USD → Bs)
- **WHEN** se factura y se crea el asiento de pago
- **THEN** llevan `foreign_inverse_rate` 803,34 y `foreign_rate` 1 / 803,34,
  la misma pareja que da `compute_rate` a los demás asientos y a la caja (antes
  803,34 / 803,34)

#### Scenario: Asiento de pago

- **GIVEN** un pago con `foreign_rate` 36,5 y `foreign_amount` 4.234
- **WHEN** se crea su asiento de pago (también con `l10n_ve_pos_igtf`)
- **THEN** el asiento lleva `foreign_inverse_rate` 36,5 y `foreign_rate`
  1 / 36,5, y sus líneas 4.234 en alterno

#### Scenario: Pago sin tasa

- **GIVEN** un pago con `foreign_rate` 0
- **WHEN** se crea su asiento de pago
- **THEN** el asiento conserva la tasa de su fecha, sin fijarla a mano

