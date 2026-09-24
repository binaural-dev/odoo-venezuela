# Spec delta: user-timezone-default

## ADDED Requirements

### Requirement: Todo usuario nuevo tiene una zona horaria resuelta

El sistema SHALL asignar `tz = "America/Caracas"` a todo `res.partner`
(incluido `res.users`, que delega el campo) creado sin un `tz` presente en
el contexto de creación ni pasado explícitamente en los valores. El
sistema SHALL priorizar el `tz` del contexto de creación (p. ej. el
detectado por el navegador del cliente) por encima del fallback regional.

Motivo: `fields.Date.context_today()`/`fields.Datetime.context_timestamp()`
(core) solo son conscientes de la zona horaria del usuario si logran
resolver un `tz` — si no, degradan silenciosamente a la hora del servidor
(UTC en despliegues containerizados). Un usuario con `tz` vacío desfasa un
día cualquier fecha calculada así durante las horas en que el día local
todavía no coincide con el día UTC.

#### Scenario: Usuario nuevo sin tz en el contexto

- **GIVEN** una creación de `res.users` (o `res.partner`) sin `tz` en
  `vals` y sin `tz` en el contexto de la request
- **WHEN** se crea el registro
- **THEN** `tz` queda en `"America/Caracas"`

#### Scenario: Usuario nuevo con tz provisto por el cliente

- **GIVEN** una creación con `context={"tz": "Europe/Madrid"}` y sin `tz`
  en `vals`
- **WHEN** se crea el registro
- **THEN** `tz` queda en `"Europe/Madrid"` (el contexto gana sobre el
  fallback regional)

#### Scenario: Valor explícito en la creación

- **GIVEN** una creación con `vals={"tz": "UTC", ...}`
- **WHEN** se crea el registro
- **THEN** `tz` queda en `"UTC"` (un valor explícito nunca es sobrescrito
  por el default)

### Requirement: Los usuarios existentes con tz vacío se corrigen al actualizar el módulo

El sistema SHALL backfillear `tz = "America/Caracas"` en todo `res.users`
cuyo `tz` esté vacío al momento de actualizar `l10n_ve_base` a la versión
que introduce este cambio, vía script de migración (`migrations/`, no
`post_init_hook`, porque este último no corre en actualizaciones de un
módulo ya instalado). El sistema SHALL NOT modificar el `tz` de usuarios
que ya tengan un valor asignado, sea o no `America/Caracas`.

#### Scenario: Usuario existente con tz vacío

- **GIVEN** un `res.users` con `tz = False` antes de la migración
- **WHEN** se actualiza el módulo `l10n_ve_base`
- **THEN** el usuario queda con `tz = "America/Caracas"`

#### Scenario: Usuario existente con tz ya configurado

- **GIVEN** un `res.users` con `tz = "UTC"` antes de la migración
- **WHEN** se actualiza el módulo `l10n_ve_base`
- **THEN** el usuario conserva `tz = "UTC"` sin cambios

#### Scenario: Ningún usuario con tz vacío

- **GIVEN** que todos los `res.users` ya tienen un `tz` asignado
- **WHEN** se actualiza el módulo `l10n_ve_base`
- **THEN** la migración no falla y no realiza ninguna escritura
