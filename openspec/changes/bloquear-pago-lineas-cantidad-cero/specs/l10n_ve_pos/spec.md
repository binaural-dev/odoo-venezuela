## ADDED Requirements

### Requirement: Bloqueo del pago con líneas en cantidad cero

Antes de pasar a la pantalla de pago, el PdV DEBE (MUST) impedir el avance cuando la orden tiene al menos una línea con cantidad exactamente 0. El bloqueo se implementa interceptando `PosStore.pay()` (punto único que atienden tanto el botón "Pago" del panel de acciones como el botón de pago en vista móvil): si hay líneas con `getQuantity() === 0`, el sistema DEBE (MUST) mostrar un `AlertDialog` que liste los nombres de esos productos (`getFullProductName`) e indique al cajero eliminarlos o colocarles la cantidad correcta, y NO DEBE (MUST NOT) navegar a la pantalla de pago. Cuando no hay líneas en 0, el flujo delega en el comportamiento base sin cambios. Las líneas con cantidad negativa (devoluciones) NO se bloquean.

#### Scenario: Orden con una línea en cantidad 0

- **WHEN** el cajero pulsa "Pago" con al menos un renglón cuya cantidad es 0
- **THEN** aparece una alerta con los nombres de los productos en 0 y el mensaje de eliminarlos o corregir la cantidad, y la orden permanece en la pantalla de productos

#### Scenario: Orden sin líneas en cantidad 0

- **WHEN** el cajero pulsa "Pago" y todas las líneas tienen cantidad distinta de 0
- **THEN** la orden pasa a la pantalla de pago con el comportamiento estándar

#### Scenario: Línea de devolución

- **WHEN** la orden contiene una línea con cantidad negativa y ninguna en 0
- **THEN** el pago no se bloquea por esta validación
