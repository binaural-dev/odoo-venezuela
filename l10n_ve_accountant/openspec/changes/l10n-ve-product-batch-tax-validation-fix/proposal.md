# Fix: error al crear una compañía nueva por validación de impuestos agregada por lote

## Why

Ticket Helpdesk **#15065** (ref #15101, cliente `Sucursales-Miguel-New-V19`): al crear una compañía nueva
desde Ajustes > Empresas, Odoo fallaba con:

```
ValueError: Expected singleton: product.template(4, 41, 1, 3, 2, 33)
```

### Cadena completa

`account/models/product.py` `_force_default_sale_tax`/`_force_default_purchase_tax` (invocado desde la
carga del plan de cuentas al crear una compañía, `account.chart.template._post_load_data`):

```python
links = [Command.link(t.id) for t in default_customer_taxes]
for sub_ids in split_every(self.env.cr.IN_MAX, self.ids):
    chunk = self.browse(sub_ids)
    chunk.write({'taxes_id': links})   # write en BATCH sobre 2+ product.template a la vez
```

`l10n_ve_accountant/models/product_template.py` extiende `write()` para forzar "exactamente un impuesto
de venta y uno de compra" (`_enforce_single_tax_vals`). Esa validación asumía que `records` en `write()`
podía tratarse como un solo bloque:

```python
current_ids = set(records.mapped(field_name).ids) if records else set()
...
name = vals.get('name') or (records.name if records else '')
company = ... (records.company_id if records else ...)
```

`records.name` y `records.company_id` son accesos a campos **escalares** — sobre un recordset de 2+
`product.template`, `Field.__get__` (`odoo/orm/fields.py:1655-1660`) llama a `record.ensure_one()` y
lanza el `ValueError` reportado, **antes de llegar a la validación de impuestos**.

Al corregir solo ese crash (envolviendo `records.name`/`records.company_id` con `.mapped()`/similar, como
ya se había hecho parcialmente para `records[field_name]` en un fix previo, PR `odoo-venezuela#1127`),
apareció un segundo problema, más de fondo: `records.mapped(field_name)` calcula la **unión** de los
impuestos de TODOS los productos del batch, no el estado individual de cada uno. En producción, esto
generaba falsos positivos sistemáticos:

```
Fiscal inconsistencies were found in product: 'Iphone 17, ..., TX GS 250 CC':
- Sales Taxes: Has 3 taxes assigned (exactly one tax is required due to local fiscal policies).
- Purchase Taxes: Has 2 taxes assigned (exactly one tax is required due to local fiscal policies).
```

Investigando el porqué: `account.tax.company_id` es obligatorio y **no** `company_dependent`, y
`taxes_id`/`supplier_taxes_id` en `product.template` no tienen dominio por compañía — un producto
compartido entre compañías/sucursales (`company_id = False`, común en productos base/demo) puede
legítimamente tener impuestos de varias compañías a la vez. Al crear una compañía nueva, el `Command.link`
del default de esa compañía se suma a lo que el producto ya tenía de OTRAS compañías, y la unión agregada
de `records.mapped('taxes_id')` cuenta esos impuestos ajenos como si fueran del mismo producto —
bloqueando la creación de **cualquier** compañía nueva cuyos productos compartidos ya tuvieran el impuesto
de otra compañía existente (el caso normal en una base de datos con más de una compañía).

Estos mismos puntos habían quedado registrados como deuda técnica en la tarea **[Integra 3.0] #81303**,
abierta durante la revisión del PR `odoo-venezuela#1127` (que introdujo la exención de productos combo y
corrigió parcialmente el acceso a `taxes_id`/`supplier_taxes_id`, pero dejó sin cubrir
`records.company_id`/`records.name` y el problema de fondo de la validación agregada).

## What Changes

- `l10n_ve_accountant/models/product_template.py`
  - `_enforce_single_tax_vals` se separa en `_enforce_single_tax_vals_create` (sin cambios de
    comportamiento) y `_enforce_single_tax_vals_write`, que ahora **itera cada producto de `records`
    individualmente** — calcula el `company` y el baseline de impuestos de cada registro por separado, en
    vez de operar sobre el recordset agregado. Esto elimina el `ensure_one()` (ya no se accede a
    `records.name`/`records.company_id` como escalares sobre multi-registro) y elimina el falso positivo
    de la unión.
  - Nuevo método `_relevant_tax_ids(tax_ids, company)`: filtra los impuestos resultantes a solo los que
    pertenecen a la compañía relevante (ella misma o un ancestro en su jerarquía de sucursales,
    `company.parent_ids`) antes de contar "cuántos impuestos tiene" el producto. Un impuesto de una
    compañía no relacionada deja de contar como inconsistencia.
  - La inyección del impuesto por defecto pasa de `Command.set` (reemplaza toda la relación) a
    `Command.link` (agrega sin destruir), y de un único `write()` uniforme sobre todo el subset a un
    `write()` por campo, escrito solo sobre los productos que realmente lo necesitan — un producto que ya
    tenía un impuesto válido (propio o de otra compañía) nunca es tocado por la inyección de otro.
  - El mensaje de `UserError` ahora agrupa los errores por producto (`Product '%s':`) cuando hay 2+
    productos afectados; con un solo producto mantiene el formato plano original.
  - Se conserva íntegra la exención de productos combo y el resto del comportamiento de los fixes
    FIX-060/061/062 ya mergeados en `maintenance-19.0` (PR #1127) — este cambio no los toca, solo corrige
    los dos defectos descritos arriba.
- `l10n_ve_accountant/tests/test_product_template.py`: 4 tests nuevos (`test_24`-`test_27`, agregados
  después de los 23 existentes, sin modificarlos) que reproducen el batch multi-registro, el campo no
  tocado que no debe validarse, el caso donde solo un producto realmente ofensor debe reportarse, y el
  producto compartido con impuesto de otra compañía.
- `l10n_ve_accountant/i18n/es_VE.po`: se agrega la traducción del único string nuevo (`Product '%s':`).
- `l10n_ve_accountant/__manifest__.py`: bump `19.0.1.0.15` → `19.0.1.0.16`.

## Impact

- **Capability**: `product-batch-tax-validation` (nueva).
- **Módulos**: `l10n_ve_accountant`. No requiere cambios en otros módulos ni en core.
- **Alcance real**: afecta a cualquier `write()` de `taxes_id`/`supplier_taxes_id` sobre 2 o más
  `product.template` a la vez — el disparador más común es la creación de una compañía nueva
  (`account.chart.template._post_load_data`), pero también aplica a cualquier edición masiva de impuestos
  sobre productos (cambio de alícuota de IVA, por ejemplo).
- **Riesgo**: bajo para el caso de un solo registro (comportamiento sin cambios, cubierto por los 23 tests
  existentes que se mantienen intactos). Riesgo medio para el caso de batch multi-registro heterogéneo si
  la política real de la empresa esperaba que un producto compartido "hereda" la restricción de una sola
  compañía a la vez — se decidió que NO es así (ver spec delta), consistente con que
  `account.tax.company_id` es por compañía y el propio core permite productos compartidos entre
  compañías.
- **Coordinación pendiente**: la rama `maint-19.0-ti-13828-fix-product-validation-taxes-regression`
  (PR `odoo-venezuela#1111`, aún sin mergear) también reescribe `_enforce_single_tax_vals` (agrega
  `company.unique_tax` como toggle de la política) sobre una base **anterior** a este fix y al PR #1127 —
  quien mergee ese PR después de este debe reconciliar ambas lógicas manualmente.
- **Sin verificar en navegador todavía**: sí verificado — el usuario confirmó manualmente en la instancia
  real (`odoo-Sucursales-Miguel-New-V19`, BD `sucursales-miguel-19`) que la creación de la compañía ya
  funciona.

## Deuda técnica resuelta

Este cambio resuelve la tarea **[Integra 3.0] #81303** (https://binaural.odoo.com/odoo/action-341/81303),
registrada durante la revisión del PR #1127.

## Referencias

- Ticket: https://binaural.odoo.com/odoo/my-tickets/15065
- Tarea (deuda técnica): https://binaural.odoo.com/odoo/action-341/81303
- PR: https://github.com/binaural-dev/odoo-venezuela/pull/1305 (`maint-19.0-fix-ti-15065-error-in-create-company` → `maintenance-19.0`)
- Coordinación: https://github.com/binaural-dev/odoo-venezuela/pull/1111 (`maint-19.0-ti-13828-fix-product-validation-taxes-regression`)
