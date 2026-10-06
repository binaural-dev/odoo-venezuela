# Spec delta: pos-self-order-kiosk-phone-required

## ADDED Requirements

### Requirement: Teléfono venezolano obligatorio y validado

El Kiosko SHALL pedir el teléfono del cliente como un código de operadora
móvil venezolana (uno de `0412`, `0414`, `0416`, `0422`, `0424`, `0426`,
elegido en un desplegable) más un número de exactamente 7 dígitos. El
teléfono SHALL ser obligatorio tanto al crear un contacto nuevo como al
completar el teléfono faltante de un contacto existente. El valor SHALL
guardarse en `res.partner.phone` compuesto como
`"<código>-<7 dígitos>"` (p. ej. `"0414-1234567"`).

La validación de formato SHALL ejecutarse en el cliente (para dar
retroalimentación inmediata) y SHALL repetirse en el servidor
(`controllers/orders.py`, rutas `identify/create` y `identify/set_phone`),
sin confiar en lo que el cliente ya validó.

#### Scenario: Teléfono con formato válido

- **GIVEN** el paso de creación de contacto o de completar teléfono
- **WHEN** el cliente elige un código de operadora válido y escribe 7 dígitos
- **THEN** el teléfono se guarda como `"<código>-<7 dígitos>"`

#### Scenario: Código de operadora no reconocido

- **GIVEN** el paso de creación de contacto o de completar teléfono
- **WHEN** el cliente no elige un código de operadora de la lista
- **THEN** se rechaza con un mensaje de error, tanto en cliente como en
  servidor si se fuerza la llamada

#### Scenario: Número con largo distinto de 7 dígitos

- **GIVEN** un código de operadora válido
- **WHEN** el número tiene menos o más de 7 dígitos, o contiene caracteres
  no numéricos
- **THEN** se rechaza con un mensaje de error, tanto en cliente como en
  servidor

#### Scenario: Teléfono vacío

- **GIVEN** el paso de creación de contacto o de completar teléfono
- **WHEN** el cliente no completa el teléfono
- **THEN** no se puede continuar: al pulsar el botón se muestra el motivo
  (operadora sin elegir o número incompleto) y el servidor también lo rechaza
  si se llama directamente. El botón NO se deshabilita por datos incompletos
  (solo mientras hay una petición en curso), para que el cliente siempre vea
  qué le falta

#### Scenario: Caracteres no válidos o de más en el número

- **GIVEN** el campo de número de teléfono
- **WHEN** el cliente teclea una letra o un octavo dígito
- **THEN** el carácter no aparece en el campo (el valor saneado se reescribe
  también en el input, no solo en el estado)
- **AND** mientras el número tenga menos de 7 dígitos se muestra bajo el campo
  el aviso "El número de teléfono debe tener exactamente 7 dígitos."
