# l10n_ve_tax_payer

## Purpose

Módulo técnico que agrega la clasificación de contribuyente venezolano a los contactos. Extiende únicamente `res.partner` (un solo campo, `taxpayer_type`, más su vista). Depende de `base`, `l10n_ve_rate` y `l10n_ve_accountant`. El campo del contacto lo consume `l10n_ve_iot_mf` (armado del libro de ventas en `wizard.accounting.reports`, que agrupa según `partner_id.taxpayer_type == "ordinary"`); `l10n_ve_payment_extension` lo declara como dependencia pero su código no lee `taxpayer_type` (solo lo usan sus pruebas). El campo homónimo de la compañía (`res.company.taxpayer_type`), que es el que usan la lógica de períodos fiscales de `l10n_ve_invoice` y las alertas de guías de `l10n_ve_stock_account`, NO lo define este módulo sino `l10n_ve_accountant`.

## Requirements

### Requirement: Tipo de contribuyente en el contacto

Todo contacto (`res.partner`) DEBE (MUST) tener el campo `taxpayer_type` (Selection con opciones `formal` "Formal", `special` "Special" y `ordinary` "Ordinary"), con valor por defecto `ordinary` y con seguimiento (`tracking=True`) de sus cambios en el chatter. El campo NO es obligatorio a nivel de modelo: la obligatoriedad se impone solo en la vista, mediante la herencia de `base.view_partner_form` que lo inyecta con `required="1"` después de `category_id`; una creación por código, importación o desde otra vista sin el campo se guarda con el valor por defecto en lugar de fallar. El campo se declara sin `string` propio, por lo que su etiqueta se deriva del nombre técnico y solo cambia por traducción (`i18n/es_VE.po`).

#### Scenario: Contacto nuevo sin especificar tipo

- **WHEN** se crea un contacto sin indicar `taxpayer_type`
- **THEN** el contacto queda con tipo de contribuyente `ordinary` y no se lanza ningún error de campo obligatorio

#### Scenario: Cambio de tipo de contribuyente

- **WHEN** un usuario cambia el `taxpayer_type` de un contacto (por ejemplo de `ordinary` a `special`)
- **THEN** el cambio se registra en el chatter del contacto por el tracking del campo

#### Scenario: Formulario de contacto sin tipo

- **WHEN** un usuario borra el tipo de contribuyente en el formulario de contacto heredado y trata de guardar
- **THEN** la vista impide guardar por el `required="1"` del campo inyectado

### Requirement: Alcance del campo limitado al contacto

El módulo DEBE (MUST) limitarse a `res.partner`: no define el campo en `res.company`, no agrega reglas de acceso ni ACLs propias, y no propaga el valor a contactos hijos ni a la compañía. Por la delegación de `res.users` hacia `res.partner`, el campo queda disponible también sobre `res.users` (`field_res_users__taxpayer_type`). Cualquier consumidor que lea `company.taxpayer_type` depende de `l10n_ve_accountant`, no de este módulo.

#### Scenario: Lectura del tipo de contribuyente de la compañía

- **WHEN** un módulo lee `env.company.taxpayer_type`
- **THEN** el valor proviene del campo definido en `l10n_ve_accountant` y no se ve afectado por el `taxpayer_type` del contacto

#### Scenario: Contacto hijo de una compañía cliente

- **WHEN** se crea un contacto hijo de un partner con `taxpayer_type = special`
- **THEN** el hijo queda con `ordinary` (el valor por defecto), porque el módulo no propaga el valor del padre
