# Fix: método de redondeo de impuestos por defecto en "por línea"

## Why

Ticket de helpdesk #15432: Odoo trae por defecto
`tax_calculation_rounding_method = 'round_globally'` ("por impuesto") en
`res.company`, heredado del módulo `account`. La normativa fiscal
venezolana (método de máquina fiscal) exige redondear el impuesto de
cada línea individualmente ("por línea", `round_per_line`), y cada
compañía nueva nacía con el default incorrecto, obligando a corregirlo
a mano en Configuración cada vez.

## What Changes

- `l10n_ve_accountant/models/res_company.py`
  - Se sobreescribe el default heredado de
    `tax_calculation_rounding_method` (de `account`) a
    `'round_per_line'`.
  - Alcance: solo aplica a compañías creadas DESPUÉS de instalar/
    actualizar este módulo -- no migra retroactivamente compañías ya
    existentes (la columna ya fue poblada por `account` antes de que
    este override cargue en el registro, y una actualización de módulo
    no re-ejecuta el default sobre filas ya existentes). Verificado en
    base de prueba. Por petición de los superiores, el encargado de la
    vertical (Saul Ortega) mantiene este alcance (solo compañías
    nuevas); no se agrega migración retroactiva.
- `l10n_ve_accountant/tests/test_multi_currency_rounding.py`
  - Nuevo test `test_55_new_company_defaults_to_round_per_line`: crea
    una compañía nueva desde cero y verifica el default, sin depender
    de `self.company` (la compañía principal del fixture, que no
    refleja el nuevo default por la razón de alcance de arriba).
  - `test_31` (línea negativa mezclada con una positiva) se elimina:
    ninguna línea de producto puede tener monto negativo, ni siquiera
    un descuento. Queda `test_31b_two_lines_same_tax_both_rounding_modes`
    con dos líneas positivas, comparando cada modo contra su fórmula.
  - `test_33` verifica `amount_total` (25,90) e impuesto (3,58) en ambos
    modos de redondeo.

## Impact

- **Requirement**: reemplaza (`MODIFIED`) el requirement existente
  `round_per_line` es la configuración esperada para compañías
  venezolanas (hallazgo de configuración, no implementado)`, que
  documentaba esto como un hallazgo pendiente -- con este cierre queda
  implementado para compañías nuevas.
- **Módulo**: `l10n_ve_accountant`.
- **Riesgo**: bajo. Cambio de un solo `default=` en un campo
  `Selection` ya existente; no toca lógica de cálculo ni datos
  existentes.
- **Verificado**: suite completa de `l10n_ve_accountant` (300 tests) corrida en
  contenedor Docker sobre base limpia (`--without-demo=True`), tanto sin
  como con `l10n_ve_invoice` instalado (vía `l10n_ve_payment_extension`,
  escenario real de producción) - sin fallos en ningún caso.
