# Diseño

## D1. Override en `l10n_ve_accountant`, no parche del core
`account.chart.template` ya se extiende en este módulo (`_load`). Se agrega `_post_load_data` con la misma herencia. Es el mismo
patrón que el core usa para `res.company` (`chart_template.py`, fallback `company[fname] or company.root_id[fname]`).

## D2. Se quita el campo de `template_data` en vez de capturar la excepción
Capturar el `ValueError` a mitad del bucle del core abortaría el resto de `_post_load_data`. Se prueba cada xmlid con
`self.ref(xmlid, raise_if_not_found=False)` antes del `super()`, se retira solo el que no resuelve y el resto del método corre normal.

## D3. La fuente del valor es `ir.default` de la matriz
`ir.default._get(model, field, company_id=root.id)` devuelve lo que el cliente configuró. No se adivina una cuenta por código o
nombre. Sin valor → `UserError` (falla ruidosa, no silenciosa).

## D4. Solo sucursales
`if not company.parent_id: return super()...` deja intacto el camino de compañías raíz.

## D5. Un default global ya lo hereda la sucursal
`ir.default._get(model, field, company_id=root.id)` solo encuentra defaults de esa compañía. Una BD migrada desde `ir.property` puede
tener el default sin compañía (global); el contacto de la sucursal ya lo recibe, así que no hay nada que copiar ni por qué fallar.
Si no hay default de la matriz pero sí uno global, se omite (log `info`). Solo sin ninguno de los dos se lanza `UserError`.

## D6. Propiedades de `res.company` se dejan al core
`_get_property_accounts` incluye campos de la propia compañía (p. ej. `downpayment_account_id`, agregado por `sale`). No son defaults de
otro modelo y no están en `ir.default`; el fallback no los toca y mantienen el comportamiento previo.

## D7. Sucursales de varios niveles
Los valores se toman de la compañía raíz (`company.root_id`), igual que `ref()` (`account.<root_id>_<xmlid>`) y que la creación de
cuentas utilitarias del core (`parent_ids[0]`). Una sub-sucursal hereda de la matriz, no de una sucursal intermedia.

## Código
```python
def _post_load_data(self, template_code, company, template_data):
    company = company or self.env.company
    if not company.parent_id:
        return super()._post_load_data(template_code, company, template_data)
    data = dict(template_data)
    unresolved = []
    for field, model in self._get_property_accounts(data.get('additional_properties', {})).items():
        if model == 'res.company':
            continue  # campos de la compañía: los resuelve el core
        xmlid = data.get(field)
        if xmlid and field in self.env[model]._fields and not self.ref(xmlid, raise_if_not_found=False):
            unresolved.append((field, model, xmlid))
            data.pop(field)
    res = super()._post_load_data(template_code, company, data)
    ...  # por cada propiedad sin resolver: copia ir.default de company.root_id; si solo hay uno global, lo omite; si no, UserError
```

## Testing
`tests/test_branch_chart_template_defaults.py` (`post_install`): 6 tests unitarios con el paso del core simulado
(`unittest.mock.patch`) y 1 de extremo a extremo (matriz con plantilla `ve`, xmlids de cuentas eliminados, creación real de la
sucursal y `cr.precommit.run()`; comprueba por cobrar y por pagar). Los avisos del log se verifican con `assertLogs`.
