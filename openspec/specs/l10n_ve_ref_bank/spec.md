# l10n_ve_ref_bank

## Purpose

Valida las referencias bancarias (memo) de los pagos: exige una longitud exacta configurada por diario bancario y evita referencias duplicadas entre pagos publicados de la misma compañía. Extiende `account.payment`, `account.journal`, `res.company` y `res.config.settings`. Depende de `l10n_ve_invoice`; agrega su configuración al bloque "Bank Reference" de la vista de ajustes de `l10n_ve_base`.

## Requirements

### Requirement: Configuración de la validación de referencias bancarias

Cada compañía (`res.company`) DEBE (MUST) poder activar la validación de referencias con el campo `ref_required`, editable desde los ajustes generales (campo related en `res.config.settings` con `readonly=False`); cada diario (`account.journal`) DEBE (MUST) poder definir la longitud exigida en el campo entero `ref_length_required` (por defecto `0`), visible en el formulario del diario solo cuando `ref_required` está activo y el diario es de tipo `bank`.

#### Scenario: Activación por compañía y diario

- **WHEN** un administrador activa `ref_required` en ajustes y define `ref_length_required` mayor que 0 en un diario bancario
- **THEN** los pagos de ese diario quedan sujetos a las validaciones de referencia al publicarse

### Requirement: Longitud exacta de la referencia en pagos bancarios

Al publicar (`action_post`) un pago (`account.payment`), con `ref_required` activo en la compañía activa del usuario (`env.company`) y `ref_length_required` mayor que 0 en el diario, el sistema DEBE (MUST) validar que la longitud de la referencia (`ref`) del pago sea exactamente igual a `ref_length_required` cuando el diario es de tipo `bank`.

#### Scenario: Referencia con longitud incorrecta

- **WHEN** se publica un pago de un diario bancario con `ref_length_required = 8` y una referencia de longitud distinta a 8
- **THEN** se lanza un error de validación indicando que no se cumple la condición de longitud bancaria configurada en el diario

#### Scenario: Referencia con longitud correcta

- **WHEN** se publica un pago de un diario bancario cuya referencia tiene exactamente la longitud configurada
- **THEN** la validación de longitud pasa

### Requirement: Referencia bancaria única por compañía

Al publicar (`action_post`) un pago, con `ref_required` activo en la compañía activa del usuario (`env.company`) y `ref_length_required` mayor que 0 en el diario, el sistema DEBE (MUST) impedir que exista otro pago publicado (`move_id.state = posted`) de la misma compañía del pago en un diario de tipo `bank` con la misma referencia (`ref`).

#### Scenario: Referencia duplicada

- **WHEN** se publica un pago cuya referencia coincide con la de otro pago bancario ya publicado en la misma compañía
- **THEN** se lanza un error indicando que ya existe un pago con la misma referencia (memo)

#### Scenario: Referencia nueva

- **WHEN** se publica un pago cuya referencia no coincide con ningún pago bancario publicado de la compañía
- **THEN** el pago se publica normalmente
