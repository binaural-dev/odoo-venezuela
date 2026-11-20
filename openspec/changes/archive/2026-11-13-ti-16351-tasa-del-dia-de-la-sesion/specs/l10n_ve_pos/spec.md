## MODIFIED Requirements

### Requirement: Tasa operativa de la caja calculada desde la tasa registrada

`pos.config` DEBE (MUST) exponer `foreign_currency_id` (related a la compañía) y calcular `foreign_rate` y `foreign_inverse_rate` (`digits=(16,15)`) con `res.currency.rate.compute_rate` de `l10n_ve_rate`, para el día de la sesión activa (`pos.session.foreign_rate_date`) o, sin sesión abierta, el día del usuario.

#### Scenario: Carga de la configuración de caja

- **WHEN** se computa `_compute_rate` de una caja cuya compañía tiene moneda alterna con tasa registrada
- **THEN** `foreign_rate` y `foreign_inverse_rate` toman los valores devueltos por `compute_rate` para esa moneda a la fecha actual, o a la del día de la sesión si hay una abierta

### Requirement: Monedas cargadas al PdV restringidas y ordenadas

El loader de `res.currency` DEBE (MUST) restringir las monedas a la de la compañía, la de la caja, la alterna y las de cobro de sus métodos, exponer `inverse_rate`, devolver la de la compañía primero, cargarlas sin el filtro por `write_date` y servir su `rate` del día de la sesión (la alterna, con la tasa exacta de la caja).

#### Scenario: Compañía con moneda alterna

- **WHEN** se abre una caja de una compañía con moneda alterna configurada
- **THEN** al frontend llegan únicamente esas monedas, con la de la compañía primero

#### Scenario: Caja con un método en una moneda de cobro

- **WHEN** la caja tiene un método con moneda de cobro EUR
- **THEN** el EUR también llega al frontend, después de la moneda de la compañía

#### Scenario: Tasa nueva con la caja en caché

- **WHEN** la caja tiene caché de una carga anterior y se registra una tasa nueva, sin cambiar la moneda
- **THEN** la carga limitada trae la moneda igual, con el `rate` del día de la sesión

## ADDED Requirements

### Requirement: La sesión trabaja con la tasa del día de su apertura

Al abrir la sesión (`_set_opening_control_data`: caja y kiosko) el sistema DEBE (MUST) guardar en `pos.session.foreign_rate_date` el día del usuario, y la caja DEBE (MUST) usar la tasa de ese día hasta cerrarse. Una corrección de la tasa de ese mismo día entra al recargar los datos; la de otro día, nunca.

#### Scenario: Sesión que pasa la medianoche

- **WHEN** la sesión se abrió el día 1 con tasa 40 y el día 2, ya con tasa 41, se recargan los datos
- **THEN** la caja, su conversión y la moneda que recibe el PdV siguen con la tasa 40

#### Scenario: Sesión nueva del día siguiente

- **WHEN** el día 2 se abre una sesión nueva
- **THEN** trabaja con la tasa 41 del día 2

#### Scenario: Corrección de la tasa del mismo día

- **WHEN** con la sesión del día 1 abierta se corrige la tasa del día 1 a 40,5
- **THEN** al recargar los datos la caja trabaja con 40,5

### Requirement: Día de la tasa de la caja para las conversiones

`pos.session._get_rate_date()` y `pos.config._get_pos_rate_date()` DEBEN (MUST) devolver el día de la tasa de la sesión activa o, sin sesión abierta, el día del usuario. Toda conversión de montos de la caja con la tasa nativa de Odoo DEBE (MUST) usar ese día, no el de hoy.

#### Scenario: Caja con sesión de ayer

- **WHEN** la sesión de la caja se abrió ayer y hoy se pide el día de la tasa
- **THEN** se obtiene el día de ayer, el de la sesión

#### Scenario: Asiento del cierre después de medianoche

- **WHEN** la sesión abierta el día 1 (tasa 40) se cierra el día 2 (tasa 41)
- **THEN** el asiento de la sesión, fechado el día 2, lleva la tasa 40

### Requirement: Tasas de las monedas de cobro del día de la sesión

`pos.config.tender_currency_rates` DEBE (MUST) calcularse con el día de la tasa de la caja (`_get_pos_rate_date`), y `check_opening_rate` DEBE (MUST) comparar también las tasas de cobro que tiene cargadas el navegador.

#### Scenario: EUR de una sesión de ayer

- **WHEN** la sesión se abrió ayer con el EUR a 1,10 y hoy está a 1,16
- **THEN** la caja sigue con 1,10

#### Scenario: Tasa de cobro vieja en el navegador

- **WHEN** el navegador tiene una tasa de cobro del EUR que no es la de la sesión
- **THEN** la caja no abre y recarga los datos

### Requirement: La caja no abre sin la tasa del día

El sistema NO DEBE (MUST NOT) abrir una sesión cuando la moneda alterna no tiene tasa para el día del usuario: `set_opening_control` lanza un `UserError` y el popup de apertura muestra "Sin tasa del día" sin llamarlo.

#### Scenario: Apertura sin tasa del día

- **WHEN** se confirma la apertura y la moneda alterna no tiene tasa del día
- **THEN** la sesión sigue en "Control de apertura", sin día de tasa, y se avisa que falta la tasa

### Requirement: La caja no abre con una tasa cargada que no es la de la sesión

Antes de confirmar la apertura el PdV DEBE (MUST) mandar a `pos.session.check_opening_rate` la tasa de la caja y el `rate` de cada moneda cargados. Si alguno no es el de la sesión NO DEBE (MUST NOT) abrir: avisa "Tasa desactualizada" y recarga los datos. Lo que se registra al abrir va en `_beforeOpeningSession`, después del chequeo.

#### Scenario: Caja cargada la noche anterior

- **WHEN** la caja se cargó el día 1 (tasa 40) y se confirma la apertura el día 2 (tasa 41) sin recargar
- **THEN** la sesión no abre, se avisa la tasa del día y el PdV recarga los datos completos

#### Scenario: Moneda con la tasa de una carga anterior

- **WHEN** la tasa de la caja es la del día pero el `rate` de la moneda alterna cargado es de otro día
- **THEN** la sesión no abre y el PdV recarga los datos

#### Scenario: Tasa cargada al día

- **WHEN** las tasas cargadas son las de la sesión
- **THEN** la sesión abre como siempre

#### Scenario: Tasa vieja con órdenes pagadas sin enviar

- **WHEN** la tasa cargada es vieja y el equipo tiene órdenes pagadas sin sincronizar
- **THEN** la sesión abre para enviarlas y el PdV recarga los datos enseguida

#### Scenario: Registro de apertura de otros módulos

- **WHEN** la sesión no abre por la tasa
- **THEN** no se ejecuta `_beforeOpeningSession` y nada queda registrado

#### Scenario: Kiosko sin tasa del día

- **WHEN** se abre el kiosko (`action_open_wizard`) sin tasa del día
- **THEN** se lanza el error y no queda sesión

### Requirement: Aviso de sesión de un día anterior

Con la sesión abierta un día anterior al de hoy, el PdV DEBE (MUST) avisar que la sesión cobra con la tasa del día en que se abrió y que se cierre para usar la de hoy, al cargar el PdV y al cobrar, sin bloquear la venta.

#### Scenario: Cobro después de medianoche

- **WHEN** la sesión se abrió ayer y el cajero va a cobrar
- **THEN** ve el aviso como notificación y la venta sigue con la tasa de la sesión

#### Scenario: Equipo que abrió la sesión sin recargar

- **WHEN** el cajero abre la sesión con el popup y vende sin recargar hasta después de medianoche
- **THEN** el navegador tiene el día de la tasa (lo lee al abrir) y el aviso sale al cobrar
