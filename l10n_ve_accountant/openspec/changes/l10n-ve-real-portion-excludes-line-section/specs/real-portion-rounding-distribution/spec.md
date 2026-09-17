## ADDED Requirements

### Requirement: El reparto del residuo del real portion debe excluir líneas no contables
`l10n_ve_accountant` DEBE (MUST) excluir las líneas con `display_type` en
`('line_section', 'line_subsection', 'line_note')` de las candidatas a
recibir el residuo de redondeo en `_distribute_invoice_real_portion`, tanto
si la factura tiene líneas `payment_term` como si no.

#### Scenario: Factura en moneda extranjera con una sección de combo
- **WHEN** se postea una factura en una moneda distinta a la de la compañía,
  con una línea `line_section` generada por un producto combo
- **THEN** el residuo de redondeo del "real portion" se asigna a una línea
  contable real (producto o impuesto), nunca a la sección

#### Scenario: Factura con una sección tipeada a mano
- **WHEN** se postea una factura con una sección manual (`line_section` sin
  combo) intercalada entre líneas de producto
- **THEN** la sección conserva `balance = 0`, `debit = 0`, `credit = 0` y
  `account_id` vacío después del posteo

#### Scenario: Factura sin líneas de sección
- **WHEN** se postea una factura sin ninguna línea `line_section`,
  `line_subsection` ni `line_note`
- **THEN** el comportamiento del reparto no cambia respecto a antes del fix
