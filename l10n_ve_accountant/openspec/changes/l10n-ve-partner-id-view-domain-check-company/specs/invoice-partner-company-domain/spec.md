# Spec delta: invoice-partner-company-domain

## ADDED Requirements

### Requirement: El campo Cliente de la factura usa el dominio check_company

El nodo `partner_id` del formulario de `account.move` definido por
`l10n_ve_accountant` (record
`view_account_move_form_l10n_ve_accountant`, xpath
`//field[@name='partner_id']` position=replace) SHALL NOT declarar un
atributo `domain` propio, de modo que el cliente web use el dominio que el
ORM genera para el campo (`check_company=True` →
`res.partner._check_company_domain` → `check_company_domain_parent_of`, y
cuando `binaural_partner_multi_company` está instalado, también el
`('company_ids', 'parent_of', ...)` de su override). En particular, el nodo
SHALL NOT declarar el filtro `('type', '!=', 'private')`: el selection
`type` de `res.partner` en Odoo 19 no incluye el valor `private`
(`contact`/`invoice`/`delivery`/`other`), por lo que el filtro no tiene
efecto y solo enmascara la intención del dominio.

Un `domain` declarado en el nodo de la vista reemplaza — no concatena — al
dominio `check_company` en el cliente web
(`web/static/src/views/fields/field.js`, `dynamicInfo.domain()`).

#### Scenario: El nodo partner_id del formulario no tiene atributo domain

- **GIVEN** el módulo `l10n_ve_accountant` instalado
- **WHEN** se obtiene la vista formulario de `account.move` con
  `get_view(view_type='form')`
- **THEN** el primer nodo `field[@name='partner_id']` del arquitecto
  combinado (el del formulario principal, que es el que el xpath
  position=replace reemplaza) no tiene atributo `domain`
- **AND** no filtra por `type != private` (por lo tanto no tiene ningún
  `domain` declarado)
- **AND** los atributos `context`, `options` e `invisible` del mismo nodo
  siguen presentes

#### Scenario: El dominio efectivo admite contactos de la matriz

- **GIVEN** el módulo `l10n_ve_accountant` instalado, una compañía matriz
  P, una hija H y una compañía ajena D
- **WHEN** se toma el dominio efectivo del campo Cliente (el `domain` del
  nodo de la vista si existe; si no, el de `fields_get(['partner_id'])`) y
  se evalúa con `company_id` = H
- **THEN** el dominio contiene el operador `parent_of`
- **AND** un contacto de P satisface el dominio
- **AND** un contacto de D NO satisface el dominio

### Requirement: Integración con binaural_partner_multi_company para contactos compartidos

Cuando `binaural_partner_multi_company` está instalado (PR
binaural-dev/integra-addons#3018), su override de
`res.partner._check_company_domain` agrega la rama
`('company_ids', 'parent_of', ...)` al dominio efectivo del campo Cliente.
Este módulo (`l10n_ve_accountant`) no redefine ese comportamiento: su
contribución es únicamente no declarar un `domain` en el nodo de la vista
para que el dominio ORM (incluida la extensión de binaural) llegue al
cliente web.

El escenario de contacto compartido (presencia en `company_ids` con
`parent_of`) se valida con la suite conjunta
`l10n_ve_accountant` + `binaural_partner_multi_company`
(test condicional `test_binaural_shared_partner_satisfies_effective_domain`
en este módulo, que se omite si binaural no está instalado). La lógica de
`company_ids` vive en binaural_partner_multi_company, no en este módulo.
