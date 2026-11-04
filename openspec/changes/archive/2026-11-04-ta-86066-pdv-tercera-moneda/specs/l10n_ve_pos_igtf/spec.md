## ADDED Requirements

### Requirement: Captura en una moneda de cobro consciente del IGTF

Al teclear un pago en una tercera moneda de cobro (`setTenderAmount` de `l10n_ve_pos`) con la orden a facturar y contexto IGTF (método con `apply_igtf` o deuda IGTF acumulada), lo adeudado DEBE (MUST) ser el mismo restante que usa la captura en divisa: la base de factura pendiente más la deuda IGTF, sin el IGTF que generará la línea.

#### Scenario: Pago en euros que cubre la base pendiente y la deuda IGTF

- **WHEN** la orden tiene deuda IGTF de un pago anterior y el cajero cobra en euros lo que se propone
- **THEN** la línea vale exactamente la base pendiente más la deuda IGTF, sin ruido de conversión
