# Spec delta: l10n_ve_accountant (ticket 16196)

## MODIFIED Requirements

### Requirement: Fecha del asiento de diferencial alterno standalone

Cuando el core no construye asiento de diferencial para un partial (solo difiere
la moneda alterna), el asiento standalone SHALL fecharse con la misma regla que
el core aplica a su asiento nativo: `journal.accounting_date` calculado sobre
`max(debit.date, credit.date)`. SHALL NOT usar la fecha cruda ni "hoy".

#### Scenario: Cada pago se concilia el día de su fecha

- **GIVEN** una factura en Bs pagada en USD con pagos en fechas distintas, cada uno conciliado el día de su fecha
- **WHEN** se generan los asientos alternos standalone
- **THEN** cada uno SHALL tener la fecha de su pago

#### Scenario: Re-conciliación posterior

- **GIVEN** los mismos pagos conciliados de nuevo en una fecha posterior
- **WHEN** se generan los asientos alternos standalone
- **THEN** su fecha SHALL coincidir con la que el core daría a su asiento nativo (`journal.accounting_date`)

#### Scenario: Factura en la moneda alterna

- **GIVEN** una factura en USD (moneda alterna) con el toggle encendido
- **WHEN** se concilian sus pagos
- **THEN** el alterno SHALL NOT inyectar montos y las fechas SHALL ser idénticas a las del toggle apagado
