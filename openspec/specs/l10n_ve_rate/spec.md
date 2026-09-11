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

El método `compute_rate(foreign_currency_id, rate_date, raise_if_not_found=False)` de `res.currency.rate` DEBE (MUST) devolver la tasa (`foreign_rate`) y la tasa inversa (`foreign_inverse_rate`) tomando el registro de tasa más reciente cuya fecha sea menor o igual a `rate_date` para esa moneda y la compañía activa. Si la moneda solicitada es la moneda principal de la compañía, ambos valores son `company_rate`; en caso contrario `foreign_rate` es `inverse_company_rate` y `foreign_inverse_rate` es `company_rate`. La tasa inversa es el factor por el que se multiplican los montos para obtener su equivalente en moneda alterna. Solo considera tasas con fecha `<=` `rate_date`: si existe una tasa exacta para esa fecha o una anterior, se usa la más cercana hacia atrás; las tasas con fecha posterior a `rate_date` quedan excluidas y nunca se consideran, sin importar qué tan cercanas estén.

#### Scenario: Moneda alterna distinta a la de la compañía

- **WHEN** se invoca `compute_rate` con una moneda distinta a la moneda principal de la compañía y existe una tasa registrada en o antes de la fecha dada
- **THEN** devuelve `foreign_rate = inverse_company_rate` y `foreign_inverse_rate = company_rate` de la tasa más reciente aplicable

#### Scenario: Sin tasa registrada (comportamiento por defecto)

- **WHEN** se invoca `compute_rate` sin `raise_if_not_found` (o con `raise_if_not_found=False`) y no existe ninguna tasa registrada en o antes de la fecha dada para esa moneda y compañía
- **THEN** devuelve un diccionario vacío

#### Scenario: Sin tasa registrada, con `raise_if_not_found=True`

- **WHEN** se invoca `compute_rate` con `raise_if_not_found=True` y no existe ninguna tasa registrada en o antes de la fecha dada para esa moneda y compañía
- **THEN** lanza `UserError` indicando que no hay tasa configurada para esa fecha

`raise_if_not_found=True` está reservado para un punto de entrada que se construya específicamente para que el usuario reaccione al error en el momento (por ejemplo, un botón dedicado de recálculo). Ningún llamador actual del código pasa `True`: los `default` de creación, las comparaciones de `create()` para el chatter, y el propio compute explícito de `foreign_rate`/`foreign_inverse_rate` (que el ORM puede disparar por su cuenta con solo leer el campo) usan el valor por defecto (`False`), porque ninguno de esos puntos puede reaccionar de forma útil a un error duro sin bloquear una operación no relacionada (crear la orden, preparar la factura).

### Requirement: Inversión de tasa solo con moneda alterna USD

El método `compute_inverse_rate(rate)` de `res.currency.rate` DEBE (MUST) devolver `1/rate` únicamente cuando la moneda alterna de la compañía activa es USD (`base.USD`); en cualquier otro caso devuelve la misma tasa recibida.

#### Scenario: Compañía con moneda alterna USD

- **WHEN** la moneda alterna de la compañía es USD y se invoca `compute_inverse_rate` con una tasa distinta de cero
- **THEN** devuelve el inverso matemático de la tasa

#### Scenario: Compañía con otra moneda alterna

- **WHEN** la moneda alterna de la compañía no es USD
- **THEN** devuelve la tasa recibida sin modificar
