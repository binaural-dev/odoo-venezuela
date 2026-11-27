# pos-self-order-kiosk-session-rate Specification

## Purpose
TBD - created by archiving change ti-16351-kiosko-tasa-del-dia-de-la-sesion. Update Purpose after archive.

## Requirements

### Requirement: El Kiosko recibe las monedas con la tasa del día de su sesión

El sistema SHALL servir al Kiosko el `rate` de cada moneda del día de la sesión de su caja (el de su
apertura), el mismo que recibe el PdV, y SHALL NOT abrir la sesión del Kiosko sin la tasa del día.

#### Scenario: Kiosko abierto ayer

- **GIVEN** la sesión del Kiosko se abrió el día 1 con tasa 40
- **WHEN** el día 2, ya con tasa 41, el Kiosko carga sus datos
- **THEN** la moneda alterna llega a 40, igual que la tasa de la caja

#### Scenario: Kiosko sin tasa del día

- **GIVEN** la moneda alterna no tiene tasa del día
- **WHEN** se abre el Kiosko desde el backend
- **THEN** se muestra el error de la tasa y no queda sesión abierta
