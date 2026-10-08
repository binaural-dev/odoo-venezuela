# Spec delta: default-tax-rounding-round-per-line

## MODIFIED Requirements

### Requirement: Una compañía nueva nace con `round_per_line`; una compañía ya existente al instalar/actualizar el módulo NO se migra

La normativa de máquinas fiscales de Venezuela exige el método de
redondeo por línea. El sistema DEBE (MUST) usar `'round_per_line'` como
valor por defecto de `tax_calculation_rounding_method` en `res.company`
(sobreescribiendo el default `'round_globally'` heredado de `account`)
para cualquier compañía CREADA después de instalar/actualizar
`l10n_ve_accountant`.

Este default NO DEBE (SHALL NOT) migrar retroactivamente compañías que
ya existían al momento de instalar o actualizar el módulo: la columna
ya fue poblada por `account` antes de que este default cargue en el
registro, y una actualización de módulo no re-ejecuta el default sobre
filas existentes. Este alcance -- solo compañías nuevas, sin migración
retroactiva de las existentes -- es una decisión de negocio: por petición de los
superiores, el encargado de la vertical (Saul Ortega) mantiene este
alcance, no es un gap pendiente de resolver.

Reemplaza al requirement previo ("`round_per_line` es la configuración
esperada para compañías venezolanas (hallazgo de configuración, no
implementado)"), que documentaba esto como un hallazgo sin resolver:
con este cierre, el caso de compañía nueva queda implementado.

#### Scenario: Compañía nueva creada con el módulo ya instalado

- **GIVEN** `l10n_ve_accountant` instalado
- **WHEN** se crea una nueva `res.company` sin declarar
  `tax_calculation_rounding_method` explícitamente
- **THEN** su `tax_calculation_rounding_method` SHALL ser
  `'round_per_line'`

#### Scenario: Compañía ya existente al instalar o actualizar el módulo

- **GIVEN** una compañía ya existente con
  `tax_calculation_rounding_method = 'round_globally'`
- **WHEN** se instala o actualiza `l10n_ve_accountant`
- **THEN** su valor SHALL permanecer sin cambios (`round_globally`),
  sin ninguna migración automática
