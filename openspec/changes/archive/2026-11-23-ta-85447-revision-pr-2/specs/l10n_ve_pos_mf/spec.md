## ADDED Requirements

### Requirement: Número informado que no corresponde al pedido

Antes de escribir el número de un resultado "impreso", `mf_resolve_print_verification` DEBE (MUST) hacer los chequeos del asistente: serial de la foto, número mayor que el de la foto y libre en esa máquina para ese tipo de documento. Si alguno falla, NO DEBE (MUST NOT) escribirlo: el pedido sigue por verificar, el chatter guarda el motivo y la foto, y responde `manual_review`. El PdV DEBE (MUST) dejar la orden local sin número y por verificar, sacarla de la cola y avisar, sin frenar la venta.

#### Scenario: El número informado ya es de otro documento

- **GIVEN** un pedido por verificar con la foto en el 504 de la máquina Z7C7046254, y otra venta de esa máquina con el "00000505"
- **WHEN** el PdV informa el pedido como emitido con el 505
- **THEN** el pedido no recibe el número, sigue por verificar, el chatter registra el motivo y la foto, y la respuesta es `manual_review` con el nombre de la otra venta

#### Scenario: Otra máquina o un número anterior a la foto

- **WHEN** el PdV informa el pedido como emitido con el serial de otra máquina, o con un número menor o igual al de la foto
- **THEN** la respuesta es `manual_review` y el pedido sigue por verificar sin número

#### Scenario: Sin serial en la respuesta del driver

- **WHEN** el PdV informa el pedido como emitido sin serial
- **THEN** el número se busca entre los documentos de la máquina de la foto

#### Scenario: Lo que no escribe un número sigue igual

- **WHEN** el resultado es "no emitido", el pedido ya tenía número o todavía no está en el servidor
- **THEN** la resolución responde como antes, sin hacer el chequeo

#### Scenario: El PdV recibe manual_review

- **GIVEN** un pedido por verificar que la máquina informa como emitido
- **WHEN** el servidor responde `manual_review`
- **THEN** el pedido queda sin número y por verificar, sale de la cola, se avisa al cajero con el motivo y la venta se imprime

#### Scenario: Volver a validar un pedido cuyo número no se aceptó

- **WHEN** se vuelve a validar ese mismo pedido y el servidor responde `manual_review`
- **THEN** no se reimprime y se sincroniza por verificar
