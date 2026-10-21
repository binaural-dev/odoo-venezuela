# l10n_ve_rate

## Purpose

Configura la moneda alterna (foreign currency) de cada compañía y centraliza el cálculo de la tasa y la tasa inversa que el resto de la localización usa para llevar la contabilidad espejo en la segunda moneda. Extiende `res.company`, `res.config.settings` y `res.currency.rate`. Depende de `base` y `l10n_ve_base`; módulos como `l10n_ve_accountant`, `l10n_ve_invoice` y `l10n_ve_currency_rate_live` consumen sus campos y métodos.

## Requirements

### Requirement: Moneda alterna por compañía

Cada compañía (`res.company`) DEBE (MUST) poder definir una moneda alterna en el campo `foreign_currency_id` (Many2one a `res.currency`), editable desde la app "Binaural Settings" de los ajustes generales (campo related `foreign_currency_id` en `res.config.settings`, con `readonly=False`).

#### Scenario: Configuración desde ajustes

- **WHEN** un administrador selecciona una moneda en "Set foreign currency" dentro de Binaural Settings y guarda
- **THEN** el campo `foreign_currency_id` de la compañía activa queda establecido a esa moneda

### Requirement: La moneda alterna debe ser distinta a la de la compañía

El sistema DEBE (MUST) impedir, vía constraint sobre `foreign_currency_id` y `currency_id`, que la moneda alterna sea igual a la moneda principal de la compañía.

#### Scenario: Selección de la misma moneda

- **WHEN** se intenta establecer como `foreign_currency_id` la misma moneda que `currency_id` de la compañía
- **THEN** se lanza un error indicando que la moneda alterna debe ser diferente a la de la compañía

### Requirement: Bloqueo de cambio de moneda alterna con movimientos contables

El sistema DEBE (MUST) impedir modificar `foreign_currency_id` de una compañía cuando ya existen apuntes contables (`account.move.line`) cuya `foreign_currency_id` es la moneda alterna vigente.

#### Scenario: Cambio con historial contable

- **WHEN** se escribe `foreign_currency_id` en una compañía que ya tenía moneda alterna y existen apuntes contables registrados con esa moneda
- **THEN** se lanza un error de validación y el cambio no se aplica

#### Scenario: Cambio sin historial contable

- **WHEN** se escribe `foreign_currency_id` y no existe ningún apunte contable con la moneda alterna anterior
- **THEN** el cambio se aplica normalmente

### Requirement: Cálculo de tasa y tasa inversa por fecha

El método `compute_rate(foreign_currency_id, rate_date, raise_if_not_found=True)` de `res.currency.rate` DEBE (MUST) devolver la tasa (`foreign_rate`) y la tasa inversa (`foreign_inverse_rate`) tomando el registro de tasa de la fecha `rate_date` para esa moneda y la compañía activa o, si esta es una sucursal nativa, las de su compañía raíz (ver el requisito «Las tasas de cambio pertenecen a la compañía principal»). Si la moneda solicitada es la moneda principal de la compañía, ambos valores son `company_rate` (o `1.0` si esa moneda no tiene ningún registro de tasa: su tasa contra sí misma); en caso contrario `foreign_rate` es `inverse_company_rate` y `foreign_inverse_rate` es `company_rate`. La tasa inversa es el factor por el que se multiplican los montos para obtener su equivalente en moneda alterna. La tasa se busca únicamente para la fecha exacta `rate_date`: no se usa la más cercana, ni una anterior ni una posterior. Si la moneda no tiene un registro de tasa con esa fecha, se considera «no encontrada». Una tasa en 0 no puede existir: Odoo 19 define en `res.currency.rate` la restricción `CHECK (rate>0)` (`_currency_rate_check`), por lo que `compute_rate` nunca devuelve una tasa en cero para un registro existente y la única condición de falla es la ausencia del registro.

#### Scenario: Moneda alterna distinta a la de la compañía

- **WHEN** se invoca `compute_rate` con una moneda distinta a la moneda principal de la compañía y existe una tasa registrada con esa fecha exacta
- **THEN** devuelve `foreign_rate = inverse_company_rate` y `foreign_inverse_rate = company_rate` de la tasa de esa fecha

#### Scenario: Sin tasa para la fecha exacta pero con tasas en otras fechas

- **WHEN** se invoca `compute_rate` con una fecha para la cual no hay tasa, aunque existan tasas anteriores o posteriores
- **THEN** lanza `UserError` de tasa no asignada; no se usa la tasa más cercana

#### Scenario: Sin tasa registrada (comportamiento por defecto)

- **WHEN** se invoca `compute_rate` sin `raise_if_not_found` (o con `raise_if_not_found=True`) y la moneda no tiene una tasa registrada con esa fecha exacta en la compañía ni en su raíz
- **THEN** lanza `UserError` indicando que no hay tasa asignada para esa moneda y fecha («No hay una tasa asignada para USD al 2026-10-20, configúrela.»); nunca devuelve un diccionario vacío ni una tasa `0.0` silenciosa

#### Scenario: Sin tasa registrada, con `raise_if_not_found=False`

- **WHEN** se invoca `compute_rate` con `raise_if_not_found=False` y la moneda no tiene una tasa registrada con esa fecha exacta
- **THEN** devuelve un diccionario vacío (comportamiento silencioso, solo para un llamador que pueda trabajar sin tasa de forma deliberada)

#### Scenario: Moneda principal de la compañía sin registro de tasa

- **WHEN** se invoca `compute_rate` con la moneda principal de la compañía y esa moneda no tiene ningún registro de tasa
- **THEN** devuelve `foreign_rate = 1.0` y `foreign_inverse_rate = 1.0` (no lanza error)

#### Scenario: Sin moneda alterna

- **WHEN** se invoca `compute_rate` sin moneda (`foreign_currency_id` vacío, p. ej. una compañía sin moneda alterna configurada)
- **THEN** devuelve un diccionario vacío, porque no hay ninguna moneda que buscar; es el único caso que no devuelve una tasa ni lanza error

Toda búsqueda de tasa que no encuentre resultado DEBE (MUST) detener la operación con el error de tasa no asignada, para que el usuario sepa que falta cargar la tasa antes de continuar. Esto incluye los `default` de creación de documentos, el compute de `foreign_rate`/`foreign_inverse_rate` y la confirmación de órdenes: crear una orden de venta, preparar una factura o registrar un pago un día sin tasa cargada falla con ese error. Es una decisión funcional (ticket 15923) que revierte el comportamiento silencioso anterior; quien necesite trabajar sin tasa debe pasar `raise_if_not_found=False` explícitamente.

### Requirement: Las tasas de cambio pertenecen a la compañía principal

Por diseño de Odoo base (19.0), los registros `res.currency.rate` solo pueden pertenecer a compañías principales (sin `parent_id`); una sucursal nativa NUNCA tiene tasas propias. Por lo tanto, cuando se opera desde una sucursal nativa, `compute_rate` DEBE (MUST) buscar las tasas primero en la compañía activa y, si no hay resultado en ella, en su compañía raíz (`env.company | env.company.root_id`; `root_id` es un Many2one que no depende de la compañía activa del selector ni de permisos sobre la matriz) y, en la práctica, siempre resuelve la tasa de la compañía matriz. La sucursal no puede sobrescribir ni afectar las tasas de la matriz. Si no existe tasa en la jerarquía se aplica el comportamiento normal (`UserError`, o `{}` con `raise_if_not_found=False`), nunca una tasa `0.0` silenciosa. Esto es una restricción de Odoo base, no de esta localización: la localización no la modifica ni la evade.

Intentar crear (o mover) una tasa a una sucursal lanza, desde Odoo base (`res.currency.rate._check_company_id`), el error:

`ValidationError: Currency rates should only be created for main companies`

#### Scenario: Sucursal sin tasa propia

- **WHEN** se invoca `compute_rate` desde una sucursal nativa y la tasa está registrada solo en la compañía matriz
- **THEN** devuelve la tasa de la matriz (la de la fecha exacta `rate_date`), no `{}` ni `0.0`

#### Scenario: Sucursal sin ninguna tasa en la jerarquía

- **WHEN** no hay tasa ni en la sucursal ni en su matriz para la moneda y fecha
- **THEN** se lanza el `UserError` de tasa no asignada

#### Scenario: Tasa de compañía ajena a la jerarquía

- **WHEN** existe una tasa en una compañía que no es la sucursal ni su compañía raíz
- **THEN** esa tasa no se considera

#### Scenario: Intento de crear una tasa en una sucursal

- **WHEN** se intenta crear un `res.currency.rate` con `company_id` de una sucursal nativa
- **THEN** Odoo base lanza `ValidationError` con el mensaje «Currency rates should only be created for main companies»

#### Scenario: Moneda alterna de la sucursal

- **WHEN** la sucursal define su propio `foreign_currency_id` (puede ser distinto al de la matriz)
- **THEN** `compute_inverse_rate` usa esa moneda y las tasas de esa moneda se resuelven desde la matriz

#### Scenario: Sucursal sin moneda alterna configurada

- **WHEN** la sucursal no tiene `foreign_currency_id`
- **THEN** NO se hereda la de la matriz (la moneda alterna es configuración propia de cada compañía y no se adivina); el documento queda sin moneda alterna y `compute_rate` devuelve `{}` (sin moneda no hay tasa que buscar), igual que una matriz mal configurada. Es un error de configuración manual

#### Scenario: Usuario sin la matriz activa en el selector

- **WHEN** un usuario no administrador opera con solo la sucursal activa
- **THEN** `compute_rate` resuelve la tasa de la matriz sin `AccessError`

### Requirement: Inversión de tasa solo con moneda alterna USD

El método `compute_inverse_rate(rate)` de `res.currency.rate` DEBE (MUST) devolver `1/rate` únicamente cuando la moneda alterna de la compañía activa es USD (`base.USD`); en cualquier otro caso devuelve la misma tasa recibida. La moneda alterna se toma siempre de la compañía activa (`foreign_currency_id` propio, sin heredar de la matriz).

#### Scenario: Compañía con moneda alterna USD

- **WHEN** la moneda alterna de la compañía es USD y se invoca `compute_inverse_rate` con una tasa distinta de cero
- **THEN** devuelve el inverso matemático de la tasa

#### Scenario: Compañía con otra moneda alterna

- **WHEN** la moneda alterna de la compañía no es USD
- **THEN** devuelve la tasa recibida sin modificar

El método DEBE (MUST) lanzar `UserError` («No hay una tasa asignada, configúrela.») cuando la tasa recibida es cero o vacía (`0`, `None`, `False`): no hay tasa que invertir y devolverla tal cual ocultaría la falta de tasa.

#### Scenario: Tasa vacía

- **WHEN** se invoca `compute_inverse_rate` con `0`, `None` o `False`
- **THEN** se lanza `UserError` indicando que no hay tasa asignada
