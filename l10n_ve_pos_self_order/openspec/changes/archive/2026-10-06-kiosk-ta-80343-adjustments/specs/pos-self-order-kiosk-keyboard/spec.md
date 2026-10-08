# Spec delta: pos-self-order-kiosk-keyboard

## ADDED Requirements

### Requirement: Teclado en pantalla para los campos de texto del Kiosko

El Kiosko SHALL ofrecer un componente OWL propio (`KioskKeyboard`), sin
librerías externas, con dos modos:

- **Texto**: QWERTY en español (incluida la Ñ) + fila de números + espacio +
  borrar + mayúsculas (alternable).
- **Numérico**: solo dígitos, mismo layout 3×4 (1-9, borrar/0/limpiar) que el
  numpad propio de la cédula en `IdentificationPage`.

El teclado SHALL mostrarse al enfocar un campo de texto de la pantalla de
identificación/creación de contacto (nombre, apellido, calle, teléfono) y
SHALL escribir en el campo que tiene el foco. El campo de teléfono SHALL usar
el modo numérico. El layout SHALL seguir al campo tocado cada vez (al enfocarlo
y al tocarlo aunque ya tuviera el foco), y las teclas del teclado NO SHALL
quitarle el foco al campo activo.

#### Scenario: Volver de teléfono a un campo de texto

- **GIVEN** el teclado en modo numérico tras tocar el teléfono
- **WHEN** el cliente vuelve a tocar nombre, apellido o calle
- **THEN** el teclado cambia de nuevo al modo QWERTY

#### Scenario: Enfocar un campo de texto muestra el teclado

- **GIVEN** el paso de creación de contacto del Kiosko
- **WHEN** el cliente toca el campo de nombre, apellido o calle
- **THEN** aparece el teclado QWERTY y cada tecla tocada escribe en ese campo

#### Scenario: Enfocar el teléfono muestra el modo numérico

- **GIVEN** el paso de completar teléfono o de creación de contacto
- **WHEN** el cliente toca el campo de número de teléfono
- **THEN** aparece el teclado en modo numérico (solo dígitos) y escribe en
  ese campo

#### Scenario: Mayúsculas

- **GIVEN** el teclado en modo texto
- **WHEN** el cliente activa mayúsculas y toca una letra
- **THEN** se escribe la letra en mayúscula; al desactivar mayúsculas vuelve
  a escribir en minúscula

#### Scenario: Borrar y espacio

- **GIVEN** el teclado en modo texto con un campo activo
- **WHEN** el cliente toca "borrar"
- **THEN** se borra el último carácter del campo activo
- **WHEN** el cliente toca "espacio" (y el campo activo no es el teléfono)
- **THEN** se inserta un espacio en el campo activo

#### Scenario: Limpiar en modo numérico

- **GIVEN** el teclado en modo numérico con el teléfono como campo activo
- **WHEN** el cliente toca "C"
- **THEN** se vacía el campo activo

#### Scenario: El teclado queda completo en pantalla

- **GIVEN** el formulario de cliente nuevo (nombre, apellido, teléfono,
  dirección), donde el teclado se muestra al final del formulario
- **WHEN** el teclado aparece o cambia de modo (texto ↔ numérico)
- **THEN** se desplaza a la vista para que su última fila (borrar, 0,
  limpiar) sea visible sin desplazar a mano
