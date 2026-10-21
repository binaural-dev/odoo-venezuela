# Spec delta: ta-84146-email-reescritura-sin-cambio

## MODIFIED Requirements

### Requirement: Duplicidad de email en contactos

**EARS: Ubiquitous (control global) + Event-driven (create/write) + Unwanted behaviour (ValidationError).**

El sistema DEBE (MUST) rechazar, vía `check_duplicate_email`, que se guarde un `res.partner` de tipo `contact` con un email que ya tenga **cualquier** otro partner (el dominio filtra por `email` e `id`, sin filtrar por `type`): en `create` cuando los valores traen `email` y el `type` es `contact` (o no viene), y en `write` cuando traen `email` **distinto del que ya tiene el registro**, evaluando el `type` de cada registro y después del `super().write()`. El filtro `email_changed` de `write` solo observa `email`; un `write` que cambia `type` a `contact` dejando un email ya ajeno no dispara la validación (límite conocido, idéntico al upstream). Igual que en el RIF, los flags de compañía solo determinan si la búsqueda se restringe a `company_id` o es global y qué mensaje se muestra; nunca desactivan el control.

#### Scenario: Email repetido (event: create con email duplicado)

- **WHEN** se guarda un contacto de tipo `contact` con un email que ya tiene otro partner dentro del alcance configurado, aunque ese otro partner sea una dirección de entrega o una compañía
- **THEN** se lanza `ValidationError`

#### Scenario: Reescribir el mismo email (event: write sin cambio de email)

- **WHEN** un `write` envía en `email` el mismo valor que ya tiene el contacto (un formulario, una importación o cualquier proceso que reenvía todos los campos), aunque otro partner ya comparta ese email por datos previos
- **THEN** no se valida la duplicidad y el `write` se guarda

#### Scenario: Escritura multi-record parcialmente cambiada (event: write sobre varios registros)

- **WHEN** un `write` aplica el mismo `email` sobre un recordset de varios contactos donde al menos uno ya tiene ese email y otro lo está cambiando a un valor que ya existe en otro partner
- **THEN** se lanza `ValidationError` por el registro cuyo email cambió realmente; el registro que reescribe su email actual no participa en la validación

#### Scenario: Hijos de cualquier tipo con email compartido (event: write de contacto con hijos)

- **WHEN** un contacto tiene hijos de tipo `delivery`, `invoice` u `other` que comparten su email y el contacto se reescribe enviando el mismo email (con o sin otros campos)
- **THEN** no se valida la duplicidad y el `write` se guarda

#### Scenario: Cambio de email a uno ajeno (unwanted: intento de duplicar)

- **WHEN** un `write` cambia el `email` de un contacto a un valor que ya tiene otro partner
- **THEN** se lanza `ValidationError`

#### Scenario: Dirección de entrega (event: write con type != contact)

- **WHEN** se escribe un registro con `type` distinto de `contact` (por ejemplo una dirección de entrega) cambiando el email a uno repetido
- **THEN** la validación de email no se aplica a ese registro

#### Known Limit: cambio de type a contact sin cambiar email (state-driven)

- **WHEN** un `write` cambia el `type` de un registro a `contact` dejando un `email` igual al de otro partner (el `email` no viene en `vals` o viene igual)
- **THEN** no se valida la duplicidad (`email_changed` queda vacío); comportamiento idéntico al upstream 19.0, documentado sin cambio de lógica

## Out of Scope

- Re-validación de duplicidad de email **dentro del mismo lote de `create`** (dos contactos del lote con un email que no existía antes): diferido a la tarea 84357. `create()` permanece como en `maintenance-19.0`; no hay escenario "Email repetido dentro del mismo lote" en esta spec.

## Traceability (requirement → task → test)

| Scenario | Task | Test |
|---|---|---|
| Email repetido (create) | pre-existente | `test_duplicate_email` |
| Reescribir el mismo email | 2, 5 | `test_write_same_email_on_already_duplicated_partners`, `test_portal_address_reedit_unchanged_email` |
| Escritura multi-record parcialmente cambiada | 5 | `test_write_multi_record_only_changed_fails` |
| Hijos de cualquier tipo con email compartido | 5 | `test_write_unchanged_email_with_child_of_any_type` |
| Cambio de email a uno ajeno | 2, 5 | `test_write_new_duplicated_email`, `test_portal_address_reedit_unchanged_email` |
| Dirección de entrega (type != contact) | 3, 5 | `test_write_changed_email_on_delivery_address_skips_check` |
| Known Limit (type → contact, email sin cambio) | — | Sin test (comportamiento upstream, solo documentado) |
| Lote en create (out of scope 84357) | — | — |
