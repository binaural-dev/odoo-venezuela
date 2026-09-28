# Spec delta: default-tax-rounding-round-per-line

## ADDED Requirements

### Requirement: Una compañía nueva debe nacer con el método de redondeo de impuestos "por línea"

El sistema SHALL usar `'round_per_line'` como valor por defecto de
`res.company.tax_calculation_rounding_method` para cualquier compañía
creada después de instalar/actualizar `l10n_ve_accountant`, en vez del
default de Odoo (`'round_globally'`, "por impuesto").

Este requirement aplica solo a la creación de compañías nuevas -- no
migra el valor de compañías ya existentes al momento de instalar/
actualizar el módulo.

#### Scenario: Compañía nueva creada con el módulo ya instalado

- **GIVEN** `l10n_ve_accountant` instalado
- **WHEN** se crea una nueva `res.company` sin declarar
  `tax_calculation_rounding_method` explícitamente
- **THEN** su `tax_calculation_rounding_method` SHALL ser
  `'round_per_line'`

#### Scenario: Compañía ya existente no se modifica retroactivamente

- **GIVEN** una compañía ya existente con
  `tax_calculation_rounding_method = 'round_globally'`
- **WHEN** se instala o actualiza `l10n_ve_accountant`
- **THEN** su valor SHALL permanecer sin cambios
