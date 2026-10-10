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

El método `compute_rate(foreign_currency_id, rate_date, raise_if_not_found=False)` de `res.currency.rate` DEBE (MUST) devolver la tasa (`foreign_rate`) y la tasa inversa (`foreign_inverse_rate`) tomando el registro de tasa más reciente cuya fecha sea menor o igual a `rate_date` para esa moneda y la compañía activa o, si esta es una sucursal nativa, las de su jerarquía de compañías padre (ver el requisito «Las tasas de cambio pertenecen a la compañía principal»). Si la moneda solicitada es la moneda principal de la compañía, ambos valores son `company_rate`; en caso contrario `foreign_rate` es `inverse_company_rate` y `foreign_inverse_rate` es `company_rate`. La tasa inversa es el factor por el que se multiplican los montos para obtener su equivalente en moneda alterna. Solo considera tasas con fecha `<=` `rate_date`: si existe una tasa exacta para esa fecha o una anterior, se usa la más cercana hacia atrás; las tasas con fecha posterior a `rate_date` quedan excluidas y nunca se consideran, sin importar qué tan cercanas estén.

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

### Requirement: Las tasas de cambio pertenecen a la compañía principal

Por diseño de Odoo base (19.0), los registros `res.currency.rate` solo pueden pertenecer a compañías principales (sin `parent_id`); una sucursal nativa NUNCA tiene tasas propias. Por lo tanto, cuando se opera desde una sucursal nativa, `compute_rate` DEBE (MUST) buscar las tasas en la jerarquía de la compañía activa (`company_id in env.company.parent_ids`) y, en la práctica, siempre resuelve la tasa de la compañía matriz. La sucursal no puede sobrescribir ni afectar las tasas de la matriz. Si no existe tasa en la jerarquía se aplica el comportamiento normal (`{}` o `UserError` según `raise_if_not_found`), nunca una tasa `0.0` silenciosa. Esto es una restricción de Odoo base, no de esta localización: la localización no la modifica ni la evade.

Intentar crear (o mover) una tasa a una sucursal lanza, desde Odoo base (`res.currency.rate._check_company_id`), el error:

`ValidationError: Currency rates should only be created for main companies`

#### Scenario: Sucursal sin tasa propia

- **WHEN** se invoca `compute_rate` desde una sucursal nativa y la tasa está registrada solo en la compañía matriz
- **THEN** devuelve la tasa de la matriz (la más reciente con fecha `<=` `rate_date`), no `{}` ni `0.0`

#### Scenario: Tasa de compañía ajena a la jerarquía

- **WHEN** existe una tasa en una compañía que no es la sucursal ni uno de sus padres
- **THEN** esa tasa no se considera

#### Scenario: Intento de crear una tasa en una sucursal

- **WHEN** se intenta crear un `res.currency.rate` con `company_id` de una sucursal nativa
- **THEN** Odoo base lanza `ValidationError` con el mensaje «Currency rates should only be created for main companies»

#### Scenario: Moneda alterna propia de la sucursal

- **WHEN** la sucursal define su propio `foreign_currency_id`
- **THEN** `compute_inverse_rate` usa esa moneda y no la de la matriz; si no la define, usa la de la matriz

### Requirement: Inversión de tasa solo con moneda alterna USD

El método `compute_inverse_rate(rate)` de `res.currency.rate` DEBE (MUST) devolver `1/rate` únicamente cuando la moneda alterna de la compañía activa es USD (`base.USD`); en cualquier otro caso devuelve la misma tasa recibida. La moneda alterna se toma de la compañía activa y, solo si esta no tiene `foreign_currency_id`, de la compañía padre más cercana que sí lo tenga (la moneda alterna propia de la sucursal tiene prioridad sobre la de la matriz).

#### Scenario: Compañía con moneda alterna USD

- **WHEN** la moneda alterna de la compañía es USD y se invoca `compute_inverse_rate` con una tasa distinta de cero
- **THEN** devuelve el inverso matemático de la tasa

#### Scenario: Compañía con otra moneda alterna

- **WHEN** la moneda alterna de la compañía no es USD
- **THEN** devuelve la tasa recibida sin modificar
