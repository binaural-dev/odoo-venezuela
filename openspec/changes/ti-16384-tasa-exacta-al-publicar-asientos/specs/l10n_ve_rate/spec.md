## MODIFIED Requirements

### Requirement: Cálculo de tasa y tasa inversa por fecha

El método `compute_rate(foreign_currency_id, rate_date, raise_if_not_found=True, use_last_rate=False)` de `res.currency.rate` DEBE (MUST) devolver la tasa (`foreign_rate`) y la tasa inversa (`foreign_inverse_rate`) tomando el registro de tasa de la fecha `rate_date` para esa moneda y la compañía activa o, si esta es una sucursal nativa, las de su compañía raíz (ver el requisito «Las tasas de cambio pertenecen a la compañía principal»). Si la moneda solicitada es la moneda principal de la compañía, ambos valores son `company_rate` (o `1.0` si esa moneda no tiene ningún registro de tasa: su tasa contra sí misma); en caso contrario `foreign_rate` es `inverse_company_rate` y `foreign_inverse_rate` es `company_rate`. La tasa inversa es el factor por el que se multiplican los montos para obtener su equivalente en moneda alterna. Por defecto (`use_last_rate=False`) la tasa se busca únicamente para la fecha exacta `rate_date`: no se usa la más cercana, ni una anterior ni una posterior. Si la moneda no tiene un registro de tasa con esa fecha, se considera «no encontrada». Una tasa en 0 no puede existir: Odoo 19 define en `res.currency.rate` la restricción `CHECK (rate>0)` (`_currency_rate_check`), por lo que `compute_rate` nunca devuelve una tasa en cero para un registro existente y la única condición de falla es la ausencia del registro.

Con `use_last_rate=True`, cuando no existe una tasa de la fecha exacta `rate_date`, `compute_rate` DEBE (MUST) usar la última tasa anterior: el registro de mayor `name` menor o igual a `rate_date` para esa moneda, recorriendo las compañías en el mismo orden que la búsqueda exacta (activa y luego raíz). La tasa de la fecha exacta, si existe, siempre tiene prioridad. NUNCA (MUST NOT) se usa una tasa posterior a `rate_date` ni se devuelve `1.0` como sustituto de una tasa ausente. Si no existe ninguna tasa anterior, el comportamiento es el mismo que con `use_last_rate=False`: `UserError` de tasa no asignada, o diccionario vacío con `raise_if_not_found=False`. El parámetro es opt-in y está apagado por defecto: cada llamador decide si admite la última tasa anterior. Hoy lo usa únicamente el puente `l10n_ve_accountant_asset` para la tasa de la fecha de adquisición de un activo; `l10n_ve_accountant` NO lo usa (facturas, pagos y asientos exigen la tasa exacta de su fecha).

#### Scenario: Moneda alterna distinta a la de la compañía

- **WHEN** se invoca `compute_rate` con una moneda distinta a la moneda principal de la compañía y existe una tasa registrada con esa fecha exacta
- **THEN** devuelve `foreign_rate = inverse_company_rate` y `foreign_inverse_rate = company_rate` de la tasa de esa fecha

#### Scenario: Sin tasa para la fecha exacta pero con tasas en otras fechas

- **WHEN** se invoca `compute_rate` sin `use_last_rate` con una fecha para la cual no hay tasa, aunque existan tasas anteriores o posteriores
- **THEN** lanza `UserError` de tasa no asignada; no se usa la tasa más cercana

#### Scenario: Fecha de fin de semana con use_last_rate

- **WHEN** se invoca `compute_rate` con `use_last_rate=True` para un sábado o domingo sin tasa y existe la tasa del viernes
- **THEN** devuelve la tasa del viernes

#### Scenario: Fecha entre dos tasas con use_last_rate

- **WHEN** se invoca `compute_rate` con `use_last_rate=True` para una fecha sin tasa que está entre dos fechas con tasa
- **THEN** devuelve la tasa de la fecha anterior, no la posterior

#### Scenario: Fecha futura con use_last_rate

- **WHEN** se invoca `compute_rate` con `use_last_rate=True` para una fecha posterior a la última tasa cargada
- **THEN** devuelve la tasa más reciente existente

#### Scenario: La tasa exacta tiene prioridad con use_last_rate

- **WHEN** se invoca `compute_rate` con `use_last_rate=True` y existe una tasa de la fecha exacta
- **THEN** devuelve la tasa de esa fecha, aunque existan otras anteriores

#### Scenario: Sin tasa previa con use_last_rate

- **WHEN** se invoca `compute_rate` con `use_last_rate=True` y la moneda no tiene ninguna tasa con fecha menor o igual a `rate_date` (solo existen tasas posteriores o ninguna)
- **THEN** lanza `UserError` de tasa no asignada; no usa la tasa posterior ni devuelve `1.0`

#### Scenario: Sin tasa previa con use_last_rate y raise_if_not_found=False

- **WHEN** se invoca `compute_rate` con `use_last_rate=True` y `raise_if_not_found=False` y no existe ninguna tasa anterior
- **THEN** devuelve un diccionario vacío

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

Toda búsqueda de tasa que no encuentre resultado DEBE (MUST) detener la operación con el error de tasa no asignada, para que el usuario sepa que falta cargar la tasa antes de continuar. Esto incluye los `default` de creación de documentos, el compute de `foreign_rate`/`foreign_inverse_rate` y la confirmación de órdenes: crear una orden de venta, preparar una factura o registrar un pago un día sin tasa cargada falla con ese error. Es una decisión funcional (ticket 15923) que revierte el comportamiento silencioso anterior; quien necesite trabajar sin tasa debe pasar `raise_if_not_found=False` explícitamente. La única excepción es el llamador que pasa `use_last_rate=True` (ticket 16384), que acepta la última tasa anterior y solo falla si no existe ninguna.
