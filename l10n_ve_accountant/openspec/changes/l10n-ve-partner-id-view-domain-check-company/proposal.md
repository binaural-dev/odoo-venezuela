# Fix: el campo Cliente de la factura no muestra contactos compartidos ni de la matriz en compañías hijas (TA84292)

## Why

En el formulario de factura, el campo **Cliente** (`partner_id`) no lista los
contactos **"Compartido con companias"** (`company_ids` con valores) ni los
contactos de la **compañía matriz** cuando la factura pertenece a una
compañía hija (branch). El usuario reportó el bug en el ambiente
`ta84292-review` (Odoo 19.0) y está relacionado con el PR
https://github.com/binaural-dev/integra-addons/pull/3018
(`binaural_partner_multi_company`).

### Causa raíz

`l10n_ve_accountant/views/account_move.xml`, record
`view_account_move_form_l10n_ve_accountant`, xpath
`//field[@name='partner_id']` con `position="replace"` (líneas 97-104),
reemplaza el nodo `partner_id` del formulario de `account.move` declarándole
un `domain` explícito:

```xml
domain="[('type', '!=', 'private'), ('company_id', 'in', (False, company_id))]"
```

Ese `domain` **sobreescribe** el dominio `check_company` que el ORM genera
para el campo (`account.move.partner_id` tiene `check_company=True`,
`odoo-19.0/addons/account/models/account_move.py:426`). El mecanismo está
confirmado en core:

- `fields_relational.py:130` `_description_domain`: cuando el campo tiene
  `check_company`, el ORM arma el dominio del campo como
  `company_id and res.partner._check_company_domain('[company_id]') or ...`,
  que para `res.partner` (cuyo `_check_company_domain` es
  `check_company_domain_parent_of`, `res_partner.py:192`) incluye
  `('company_id', '=', False)` y `('company_id', 'parent_of', company_id)` —
  o sea: contactos sin compañía, de la matriz (padre) y compartidos vía
  `binaural_partner_multi_company` (`('company_ids', 'parent_of', ...)`).
- `web/static/src/views/fields/field.js:438-443` `dynamicInfo.domain()`: si
  el nodo de la vista trae un `domain` propio, el cliente web usa **solo**
  ese dominio; si no lo trae, cae al dominio del campo desde `fields_get`
  (el que incluye `check_company`).

Es decir: el `domain` del nodo en la vista **reemplaza** al dominio
`check_company`, y el dominio reemplazado es más restrictivo
(`company_id in (False, company_id)` no acepta el contacto de la matriz ni
los compartidos, porque para la compañía hija `company_id` solo puede ser la
compañía hija o False). El filtro `('type', '!=', 'private')` es un residuo
de versiones anteriores: en Odoo 19 el selection de `res.partner.type` ya no
incluye `private` (es `contact`/`invoice`/`delivery`/`other`), así que no
filtra nada.

## What Changes

- `l10n_ve_accountant/views/account_move.xml`
  - `view_account_move_form_l10n_ve_accountant`, xpath
    `//field[@name='partner_id']` position=replace: **se elimina el
    atributo `domain`** del nodo `partner_id`. Es el fix mínimo: el campo
    vuelve a usar el dominio `check_company` que el ORM genera
    (`check_company_domain_parent_of` + el override de
    `binaural_partner_multi_company` cuando está instalado).
  - No se tocan `context`, `options`, `invisible` ni el resto del nodo
    (incluido el `manually_set_rate` hermano).
- `l10n_ve_accountant/tests/test_partner_id_domain.py` (nuevo)
  - `test_form_view_partner_id_has_no_domain`: verifica que el nodo
    `partner_id` (primer match, el del formulario principal, según
    `locate_node` de `template_inheritance.py:92-93`) no tenga atributo
    `domain`, y que `context`/`options`/`invisible` sigan presentes
    (protege el cambio mínimo).
  - `test_check_company_domain_matrix_valid_unrelated_invalid`: toma el
    dominio efectivo que usa el cliente web (el `domain` del nodo
    `partner_id` de `get_view()` si existe; si no, el de
    `fields_get(['partner_id'])`), verifica que contiene `parent_of` y lo
    evalúa con `safe_eval` para una compañía hija: el contacto de la matriz
    entra y el de una compañía ajena no. Falla si se reintroduce el
    `domain` viejo en la vista.
  - `test_binaural_shared_partner_satisfies_effective_domain`
    (condicional: se omite si `binaural_partner_multi_company` no está
    instalado): un contacto de una compañía ajena compartido vía
    `company_ids` con la matriz entra en el dominio efectivo de la hija, y
    un control negativo comprueba que el dominio de core por sí solo no lo
    admite.

## Impact

- **Capability**: `invoice-partner-company-domain` (nueva).
- **Módulos**: solo `l10n_ve_accountant` (vista). Sin cambio de Python de
  negocio; requiere actualización del módulo (`-u l10n_ve_accountant`) o
  reinicio para que el cliente web recargue la vista.
- **Alcance**: formulario de factura (venta y compra). El campo Cliente
  ahora lista contactos de la matriz y compartidos en compañías hijas; los
  contactos de compañías ajenas dejan de ser seleccionables (antes el
  dominio viejo tampoco los mostraba, así que en ese sentido no hay
  regresión: el dominio `check_company` es igualmente restrictivo con
  compañías ajenas).
- **Sin cambios de comportamiento ORM**: el `check_company=True` del campo
  ya validaba de la misma forma al guardar; lo que cambia es únicamente lo
  que el dropdown muestra.
- **`binaural_partner_multi_company` (PR 3018)**: el fix funciona solo
  (contactos de la matriz y sin compañía ya los acepta el
  `check_company_domain_parent_of` de core); los contactos "Compartido con
  companias" (`company_ids`) se listan cuando ese módulo está instalado,
  porque su `_check_company_domain` agrega `('company_ids', 'parent_of', ...)`
  al dominio que el cliente web evalúa.
- **Riesgo**: muy bajo. Es la eliminación de un atributo `domain` en una
  vista; el dominio resultante es estrictamente más completo que el
  eliminado para compañías hijas y equivalente para la compañía principal.
