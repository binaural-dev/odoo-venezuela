## ADDED Requirements

### Requirement: Un comando sin respuesta no se reenvía a ciegas

Para los ítems, descuentos por monto (`q-`) y pagos parciales (`2XX`) de una
factura, NC o ND, cuando la máquina fiscal no responde, el driver SHALL leer
S2 antes de reenviar, y SHALL reenviar solo si S2 muestra que la máquina no
registró el comando.

#### Scenario: La MF registró el ítem y se perdió el ACK

- **GIVEN** una factura abierta con un ítem ya confirmado
- **WHEN** el segundo ítem no recibe respuesta y la base de S2 ya lo incluye
- **THEN** el ítem no se reenvía y el documento continúa

#### Scenario: La MF no registró el ítem

- **GIVEN** una factura abierta con un ítem ya confirmado
- **WHEN** el segundo ítem no recibe respuesta y la base de S2 no lo incluye
- **THEN** el ítem se reenvía una vez

#### Scenario: S2 no permite saberlo

- **GIVEN** un comando sin respuesta
- **WHEN** S2 no se puede leer o su base no coincide con ninguno de los dos casos
- **THEN** el documento se anula y la venta muestra el error

### Requirement: Control del documento tras una recuperación

Si en un documento hubo un comando recuperado por S2, el driver SHALL comparar
la base de S2 con la esperada antes de los pagos, y SHALL anular el documento
si no coinciden. Sin recuperaciones, no SHALL hacer lecturas extra.

## MODIFIED Requirements

### Requirement: Anulación del documento abierto

`abortTransaction()` SHALL anular con `7` y usar `9` solo como respaldo.

#### Scenario: MF de la familia Z7C

- **GIVEN** un documento abierto en una MF que responde NAK a `9`
- **WHEN** se llama `abortTransaction()`
- **THEN** se envía `7` y la MF vuelve a reposo
