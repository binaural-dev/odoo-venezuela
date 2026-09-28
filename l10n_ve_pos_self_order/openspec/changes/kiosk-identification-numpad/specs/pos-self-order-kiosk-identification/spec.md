# Spec delta: pos-self-order-kiosk-identification

## ADDED Requirements

### Requirement: Teclado numérico en pantalla para la cédula/RIF

La pantalla de identificación del Kiosko SHALL ofrecer un teclado numérico en
pantalla (grid 3×4: dígitos 1-9, retroceso, 0 y limpiar) debajo del campo de
cédula/RIF, para que el cliente pueda introducir la cédula sin teclado físico.
El campo SHALL seguir siendo editable por teclado físico o del sistema.

#### Scenario: Introducir dígitos con el numpad

- **GIVEN** la pantalla de identificación del Kiosko en el paso de cédula
- **WHEN** el cliente pulsa una tecla de dígito del teclado en pantalla
- **THEN** el dígito se añade al final de la cédula (`state.vat`) y se limpia
  cualquier mensaje de error visible

#### Scenario: Retroceso y limpiar

- **GIVEN** una cédula parcialmente tecleada con el numpad
- **WHEN** el cliente pulsa retroceso (⌫)
- **THEN** se elimina el último carácter de la cédula
- **WHEN** el cliente pulsa limpiar (C)
- **THEN** la cédula queda vacía

#### Scenario: El teclado físico sigue disponible

- **GIVEN** un Kiosko con teclado físico o del sistema operativo
- **WHEN** el cliente escribe la cédula directamente en el campo
- **THEN** el valor se acepta igual que con el numpad — el teclado en pantalla
  es aditivo, no exclusivo

### Requirement: Acción primaria en la barra inferior

La acción primaria de la pantalla de identificación SHALL vivir en el pie de
página, alineada a la derecha, a la misma altura que el botón "Atrás" (alineado
a la izquierda). La acción primaria SHALL conmutar su etiqueta y su handler
según el paso: "Continue" (`onIdentify`) en el paso `identify` y "Create and
continue" (`onCreate`) en el paso `create`. NO SHALL existir un botón de acción
primaria de ancho completo en el área central.

#### Scenario: Paso de identificación

- **GIVEN** la pantalla en el paso `identify`
- **WHEN** se renderiza el pie de página
- **THEN** muestra "Atrás" a la izquierda y "Continue" a la derecha; al pulsar
  "Continue" se ejecuta `onIdentify()`

#### Scenario: Paso de nuevo cliente

- **GIVEN** una cédula no encontrada que llevó al paso `create`
- **WHEN** se renderiza el pie de página
- **THEN** muestra "Atrás" a la izquierda y "Create and continue" a la derecha;
  al pulsar el botón se ejecuta `onCreate()`
