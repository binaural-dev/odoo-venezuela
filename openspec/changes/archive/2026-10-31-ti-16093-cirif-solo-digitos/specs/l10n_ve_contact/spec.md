## ADDED Requirements

### Requirement: CI/RIF solo con dígitos al escribir

El `vat` de los formularios de contacto DEBE (MUST) usar el widget `l10n_ve_vat`, que descarta al escribir o pegar todo carácter que no sea un dígito ASCII, con cualquier `prefix_vat`, y pide el teclado numérico. Si `partner_autocomplete` le pone `field_partner_autocomplete`, `res.partner._get_view` DEBE (MUST) devolverle `l10n_ve_vat`. El widget DEBE (MUST) estar en `web.assets_backend` y `point_of_sale._assets_pos`.

#### Scenario: Letras tecleadas por error

- **WHEN** un usuario teclea "12a3B4" en el CI/RIF del formulario de contacto
- **THEN** el campo muestra "1234", las letras nunca aparecen y se guarda "1234"

#### Scenario: CI/RIF pegado con prefijo y separadores

- **WHEN** un usuario pega "V-12.345.678" en el CI/RIF
- **THEN** el campo queda en "12345678"

#### Scenario: Pasaporte

- **WHEN** el prefijo es `P` y el usuario teclea "AB98765"
- **THEN** el campo queda en "98765": la letra va en el prefijo

#### Scenario: Una letra sola

- **WHEN** el contacto tiene "1234" guardado y el usuario teclea una letra al final
- **THEN** el campo sigue en "1234" y el formulario no queda con cambios sin guardar

#### Scenario: partner_autocomplete instalado

- **WHEN** `partner_autocomplete` está instalado y fuerza `field_partner_autocomplete` en el `vat` de los formularios de contacto
- **THEN** el `vat` usa `l10n_ve_vat` y el `name` conserva el autocompletado

#### Scenario: Contacto desde el PdV

- **WHEN** el cajero crea o edita un cliente desde el PdV (formulario `l10n_ve_pos.view_partner_form_pos` en un diálogo) y teclea o pega letras en el CI/RIF
- **THEN** el campo descarta las letras igual que en el backend
