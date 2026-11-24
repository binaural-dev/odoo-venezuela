## MODIFIED Requirements

### Requirement: Resolución de pedidos por verificar antes de imprimir

Antes de imprimir cualquier documento (una venta o un pedido pendiente), el PdV DEBE (MUST) resolver la cola local con `verifyDocument`, una resolución a la vez: `printed: true` asigna el número en el pedido y en el servidor; `printed: false` lo deja como pendiente normal. Si el servidor no responde, DEBE (MUST) guardar el resultado y reintentar sin volver a consultar la máquina.

#### Scenario: La máquina emitió el documento

- **GIVEN** un pedido por verificar cuya factura la máquina emitió
- **WHEN** se valida la siguiente venta
- **THEN** primero el pedido recibe su número y después se imprime la venta nueva

#### Scenario: La máquina no lo emitió

- **WHEN** la verificación responde `printed: false`
- **THEN** el pedido queda como pendiente por facturar, sin marca

#### Scenario: Sin conexión con el servidor

- **WHEN** la máquina responde pero el servidor no guarda el resultado
- **THEN** la entrada conserva el resultado y en la siguiente impresión se guarda sin volver a verificar

#### Scenario: Varias bases en el mismo dominio

- **WHEN** dos bases de datos se abren en el mismo navegador y dominio
- **THEN** cada una tiene su propia cola local (la clave lleva el nombre de la base)

#### Scenario: Cola local perdida (limitación conocida)

- **GIVEN** un pedido por verificar cuya entrada de la cola local se perdió (almacenamiento del navegador borrado, otro navegador u otra PC)
- **WHEN** se valida la siguiente venta
- **THEN** la venta se imprime sin verificar ese pedido; el pedido conserva la marca, no se reimprime y queda para el asistente, que rechaza un número que ya es de otro documento
