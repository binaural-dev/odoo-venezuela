# Spec delta: product-batch-tax-validation

## ADDED Requirements

### Requirement: Cada producto de un `write()` en batch se valida individualmente

El sistema SHALL validar la regla fiscal "exactamente un impuesto de venta y uno de compra" evaluando el
estado resultante de **cada `product.template`** de `records` por separado (su propio baseline de
`taxes_id`/`supplier_taxes_id` combinado con los comandos M2M de `vals`), y SHALL NOT calcular un único
estado agregado (unión) sobre todo el recordset.

Motivo: un `write()` puede tocar dos o más productos no relacionados a la vez (ej.
`account.chart.template` forzando el impuesto por defecto de una compañía sobre todos sus productos vía
`Command.link`). Cada producto puede tener, individualmente, exactamente un impuesto válido aunque sean
impuestos distintos entre sí; agregar sus estados en una sola unión produce falsos positivos y, además,
el acceso a campos escalares (`records.name`, `records.company_id`) sobre un recordset de 2+ ids dispara
`ensure_one()` en Odoo 19 y rompe con `ValueError: Expected singleton` antes de validar nada.

#### Scenario: Batch write que fuerza el impuesto por defecto de una compañía nueva

- **GIVEN** dos o más `product.template` no-combo, cada uno con su propio impuesto de venta válido (uno
  solo, pero distinto entre productos)
- **WHEN** se ejecuta un único `write({'taxes_id': [Command.link(default_tax.id)]})` sobre el recordset
  combinado de esos productos
- **THEN** no se lanza `ValueError: Expected singleton`
- **AND** cada producto se evalúa contra su propio estado resultante, no contra la unión de todos

#### Scenario: Un solo producto termina con 2+ impuestos tras el batch write

- **GIVEN** un recordset de 2+ productos donde solo uno queda con 2 o más impuestos de venta tras aplicar
  el `write()`
- **WHEN** se ejecuta la validación
- **THEN** se lanza un `UserError` que menciona únicamente al producto realmente afectado
- **AND** el mensaje no incluye ni combina errores de los productos que quedaron válidos

### Requirement: Solo se valida el campo presente en `vals`

El sistema SHALL restringir la validación, en `write()`, a los campos (`taxes_id`, `supplier_taxes_id`)
que efectivamente están presentes en `vals` — salvo cuando `type` cambia a un valor distinto de `combo`,
caso en que SHALL validar ambos campos (el producto puede cargar impuestos inválidos heredados de su fase
combo).

#### Scenario: Write que solo toca `taxes_id`

- **GIVEN** dos productos con `supplier_taxes_id` distintos entre sí, cada uno individualmente válido
- **WHEN** se ejecuta un `write({'taxes_id': [...]})` que no incluye `supplier_taxes_id`
- **THEN** `supplier_taxes_id` no se evalúa en absoluto para ninguno de los dos productos

### Requirement: Un impuesto de una compañía no relacionada no cuenta para la validación

El sistema SHALL contar, para la regla de "exactamente un impuesto", únicamente los `account.tax` cuyo
`company_id` sea la compañía relevante para la validación (la del propio `write`/`vals`, o
`record.company_id`) o un ancestro de ella en su jerarquía de sucursales (`company.parent_ids`). El
sistema SHALL NOT contar impuestos de compañías no relacionadas, aunque estén físicamente enlazados al
mismo producto.

Motivo: `account.tax.company_id` es obligatorio y no `company_dependent`; `taxes_id`/`supplier_taxes_id`
en `product.template` no tienen dominio por compañía. Un producto compartido entre compañías (sin
`company_id` propio, común en productos base/demo) puede legítimamente acumular impuestos de varias
compañías a la vez sin que eso sea una inconsistencia fiscal para ninguna de ellas individualmente.

#### Scenario: Producto compartido con impuesto de otra compañía recibe el default de una compañía nueva

- **GIVEN** un `product.template` sin `company_id` (compartido) que ya tiene un impuesto de venta válido
  perteneciente a la Compañía A
- **WHEN** se crea la Compañía B y su carga de plan de cuentas enlaza (`Command.link`) el impuesto de
  venta por defecto de B sobre ese mismo producto
- **THEN** la validación para B no lanza error (el producto tiene exactamente 1 impuesto relevante para
  B: el recién enlazado)
- **AND** el impuesto de la Compañía A permanece en el producto sin ser removido

#### Scenario: Compañías en la misma jerarquía de sucursales comparten configuración fiscal

- **GIVEN** una compañía hija cuyo `parent_id` es la compañía raíz de una jerarquía de sucursales
- **WHEN** un producto compartido tiene un impuesto perteneciente a la compañía raíz
- **THEN** ese impuesto SÍ cuenta como relevante para la validación de la compañía hija

### Requirement: La inyección del impuesto por defecto no sobrescribe productos ya válidos

Cuando, tras la validación, uno o más productos de un `write()` en batch requieran el impuesto por
defecto de la compañía (porque su conjunto de impuestos relevantes quedó vacío), el sistema SHALL
inyectar ese impuesto vía `Command.link` (no `Command.set`) y SHALL aplicar la escritura únicamente sobre
el subconjunto de productos que lo necesitan.

#### Scenario: Batch mixto donde solo algunos productos necesitan el default

- **GIVEN** un recordset de 3 productos: dos ya tienen un impuesto de venta válido para la compañía, uno
  no tiene ninguno
- **WHEN** se ejecuta el `write()` que dispara la validación
- **THEN** solo el tercer producto recibe el impuesto por defecto
- **AND** los dos primeros conservan su impuesto original sin cambios
