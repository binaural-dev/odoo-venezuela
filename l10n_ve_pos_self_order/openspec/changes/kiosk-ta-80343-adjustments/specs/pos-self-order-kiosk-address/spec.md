# Spec delta: pos-self-order-kiosk-address

## ADDED Requirements

### Requirement: Dirección opcional/obligatoria por configuración

El punto de venta SHALL exponer un ajuste booleano
`self_ordering_require_address` (Ajustes → sección de Autopedido/Kiosko,
visible solo en modo `kiosk`, mismo patrón que
`self_ordering_hide_catalog`). El paso de creación de contacto del Kiosko
SHALL ofrecer siempre Estado (`res.country.state`, restringido a Venezuela),
Municipio (`res.country.municipality`, filtrado por el estado elegido) y
Calle (texto libre). Con el ajuste desactivado estos campos SHALL ser
opcionales; con el ajuste activo SHALL ser obligatorios, tanto en cliente
como en servidor (`controllers/orders.py`, ruta `identify/create`).

El Municipio SHALL depender del Estado elegido: al cambiar el Estado, el
Municipio previamente elegido (si ya no pertenece al nuevo Estado) SHALL
limpiarse. El servidor SHALL validar que el Municipio recibido pertenezca al
Estado recibido, sin confiar en el pareo que mandó el cliente.

#### Scenario: Ajuste desactivado, dirección opcional

- **GIVEN** un Kiosko con `self_ordering_require_address` desactivado
- **WHEN** el cliente crea un contacto sin completar Estado/Municipio/Calle
- **THEN** el contacto se crea igualmente

#### Scenario: Ajuste activado, dirección obligatoria

- **GIVEN** un Kiosko con `self_ordering_require_address` activado
- **WHEN** el cliente intenta crear un contacto sin Estado, sin Municipio o
  sin Calle
- **THEN** se rechaza con un mensaje de error, tanto en cliente (al pulsar
  Crear se indica el campo que falta) como en servidor si se fuerza la llamada

#### Scenario: Municipio depende del Estado

- **GIVEN** el paso de creación de contacto con el desplegable de Municipio
- **WHEN** el cliente cambia el Estado elegido
- **THEN** el desplegable de Municipio se limpia y solo ofrece los
  municipios del nuevo Estado

#### Scenario: Servidor rechaza un pareo Estado/Municipio inconsistente

- **GIVEN** el ajuste `self_ordering_require_address` activado
- **WHEN** llega una llamada a `identify/create` con un `municipality_id` que
  no pertenece al `state_id` recibido
- **THEN** el servidor rechaza la creación con un mensaje de error, sin
  confiar en el pareo que mandó el cliente

### Requirement: Datos de Estados/Municipios de Venezuela expuestos al Kiosko

El Kiosko SHALL recibir los `res.country.state` de Venezuela (ya expuestos
por el core `pos_self_order`) y los `res.country.municipality` de
`l10n_ve_location` (expuestos por este módulo vía
`pos.config._load_self_data_models` + `res.country.municipality` heredando
`pos.load.mixin`), con al menos `id`, `name`, `code`, `state_id` y
`country_id`.

#### Scenario: Municipios disponibles en el frontend del Kiosko

- **GIVEN** el Kiosko cargado
- **WHEN** el frontend consulta `this.selfOrder.models["res.country.municipality"]`
- **THEN** están disponibles los municipios de Venezuela con su(s)
  Estado(s) asociado(s)
