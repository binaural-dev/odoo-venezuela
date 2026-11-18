## MODIFIED Requirements

### Requirement: Bloqueo de la impresión con un pago en divisa sin IGTF

Si un pago de la orden (monto distinto de cero y con el signo del documento) usa un método con código de divisa (20-24) sin `apply_igtf`, NO DEBE (MUST NOT) enviarse nada a la máquina. Si la orden va a la máquina (`_mfOrderGoesToFiscalPrinter`), `isOrderValid` DEBE (MUST) frenar la validación con un aviso que nombre el método: el cajero sigue en el pago. `get_data_invoice` DEBE (MUST) además devolver `valid: false`, para "Imprimir pedido pendiente".

#### Scenario: Datos inconsistentes previos a la regla

- **GIVEN** un método con código `20` y `apply_igtf = False`, guardado así antes de actualizar el módulo o modificado por SQL, y la máquina fiscal conectada
- **WHEN** el cajero valida una orden pagada en parte con ese método y en parte con efectivo en Bs
- **THEN** el PdV muestra un aviso que nombra el método, no imprime nada (tampoco "FACTURA ANULADA"), no sincroniza la orden y el cajero sigue en la pantalla de pago

#### Scenario: Pedido pendiente con un método inconsistente

- **GIVEN** un pedido sincronizado sin número fiscal y pagado con un método `20` sin IGTF
- **WHEN** el cajero pulsa "Imprimir pedido pendiente"
- **THEN** se muestra un error que nombra el método y no se envía nada a la máquina

#### Scenario: Sin máquina fiscal conectada

- **GIVEN** un método con código `20` sin IGTF y ninguna máquina conectada
- **WHEN** el cajero valida una orden pagada con ese método
- **THEN** la validación sigue como siempre: no se imprime y la orden queda pendiente por facturar

#### Scenario: Orden que no va a la máquina

- **GIVEN** un módulo que saca la orden de la impresión fiscal con `_mfOrderGoesToFiscalPrinter` (por ejemplo, una orden operativa en modo mixto)
- **WHEN** el cajero la valida con un método `20` sin IGTF
- **THEN** no se frena

#### Scenario: Sin el módulo de IGTF del PdV

- **GIVEN** un método con código `22` y `apply_igtf` sin cargar (`undefined`)
- **WHEN** se preparan los datos fiscales de una orden pagada con ese método
- **THEN** se devuelve `valid: false` con un mensaje que nombra el método

#### Scenario: Pago en cero o vuelto con un método inconsistente

- **GIVEN** una orden con un pago de monto cero, o un vuelto (monto negativo en una factura), en un método con código `20` sin IGTF, y el resto en efectivo en Bs
- **WHEN** se valida la orden
- **THEN** ese pago no cuenta y la orden se envía a la máquina con el efectivo en Bs

#### Scenario: Nota de crédito

- **GIVEN** una nota de crédito con un pago negativo en un método con código `20` sin IGTF
- **WHEN** se valida
- **THEN** se bloquea igual que una factura

#### Scenario: Pago en divisa correctamente configurado

- **GIVEN** un método con código `20` y `apply_igtf = True`
- **WHEN** se valida una orden pagada con ese método
- **THEN** la orden se envía a la máquina fiscal como hasta ahora

#### Scenario: Aviso del bloqueo

- **WHEN** se frena la validación o la impresión de un pedido pendiente por un método de divisa sin IGTF
- **THEN** el aviso nombra el método y pide al administrador corregirlo (código nacional 01-19 o "Aplicar IGTF"), lo que solo se puede hacer con las sesiones de la caja cerradas

### Requirement: Impresión fiscal en la validación de pago

El override de `OrderPaymentValidation.finalizeValidation` DEBE (MUST), antes de la sincronización del core, normalizar el descuento global (si falla, solo se registra) e imprimir cuando la orden va a la máquina (`PosStore._mfOrderGoesToFiscalPrinter`). Si la impresión falla, también por un error inesperado, DEBE (MUST) mostrar el error y sincronizar igual: la orden queda sin número, pendiente por facturar (o por verificar).

#### Scenario: Impresión fiscal fallida

- **WHEN** el cajero valida una orden pagada y la impresión en la máquina fiscal devuelve error
- **THEN** el error se muestra en un diálogo, la orden se sincroniza sin número fiscal y aparece en "Pendientes por facturar"

#### Scenario: Error inesperado al preparar la impresión

- **WHEN** armar los datos para la máquina lanza un error inesperado (por ejemplo, un `TypeError`)
- **THEN** el cajero ve un diálogo con el detalle, no se envía nada a la máquina y la orden se sincroniza pendiente por facturar

#### Scenario: Sin máquina fiscal conectada

- **WHEN** no hay driver conectado
- **THEN** la impresión fiscal se omite y la validación continúa con el flujo estándar del core

#### Scenario: Orden ya impresa

- **WHEN** la orden ya tiene `mf_invoice_number`
- **THEN** no se vuelve a imprimir y la validación continúa

### Requirement: Métodos del servidor para pedidos por verificar

`pos.order.mf_set_print_verification` y `pos.order.mf_resolve_print_verification` DEBEN (MUST) escribir con los permisos del usuario del PdV (sin `sudo()`) y rechazar datos mal formados. La resolución solo DEBE (MUST) cambiar pedidos marcados, y un resultado "impreso" DEBE (MUST) traer el número fiscal, solo con dígitos (texto o entero). Al resolver, DEBE (MUST) dejar en el chatter del pedido el resultado, los datos fiscales aplicados y la foto previa, con el usuario que resolvió como autor.

#### Scenario: Número fiscal inválido

- **WHEN** el PdV envía un resultado "impreso" con un número vacío, con letras o signos, o que no es texto ni entero
- **THEN** se lanza un `UserError` y el pedido no cambia

#### Scenario: Resolución de un pedido sin marca

- **WHEN** el PdV envía el resultado de la máquina para un pedido que ya no está marcado (por ejemplo, porque se resolvió desde el backend)
- **THEN** el servidor no cambia el pedido y responde que no queda nada por aplicar

#### Scenario: Usuario sin permiso sobre los pedidos

- **WHEN** un usuario interno sin acceso a `pos.order` intenta marcar un pedido
- **THEN** se lanza un `AccessError`

#### Scenario: El pedido ya tenía número

- **WHEN** el PdV informa el resultado de un pedido marcado que ya tenía otro número fiscal (por ejemplo, porque otra caja lo imprimió)
- **THEN** el pedido conserva su número y el chatter dice que lo conserva, sin decir que quedó pendiente; si el número informado es el mismo por su valor, el chatter lo registra como emitido

#### Scenario: Rastro de la resolución

- **WHEN** el usuario del PdV resuelve un pedido por verificar
- **THEN** el chatter del pedido muestra, con ese usuario como autor, si la máquina lo emitió, con qué número, serial y Z, y la lectura previa (último número, serial y contador de Z)

### Requirement: Resolución manual de un pedido por verificar

El formulario de `pos.order` DEBE (MUST) avisar cuando el pedido está por verificar y ofrecer al gerente del PdV un asistente que sugiera número (el de la foto más uno), serial y Z. Como emitido, DEBE (MUST) exigir un número de solo dígitos, mayor que el de la foto y libre en esa máquina para ese tipo de documento, y el serial de la foto. En ambos casos DEBE (MUST) dejar el rastro en el chatter y quitar la marca.

#### Scenario: Resolución como emitido

- **WHEN** el gerente confirma que la máquina emitió el documento esperado
- **THEN** el pedido queda con ese número fiscal, serial y Z, sin marca, y el chatter lo registra

#### Scenario: Resolución como no emitido

- **WHEN** el gerente confirma que la máquina no lo emitió
- **THEN** el pedido queda como pendiente por facturar, sin marca, y el chatter lo registra con la foto previa

#### Scenario: El número sugerido ya es de otro documento

- **GIVEN** un pedido por verificar con la foto en el 504 y otra venta que la máquina emitió como "00000505"
- **WHEN** el gerente confirma el 505 sugerido
- **THEN** se lanza un `UserError` que nombra la otra venta y el pedido sigue por verificar

#### Scenario: Mismo número en otro contador o en otra máquina

- **WHEN** el número solo coincide con una nota de crédito de la misma máquina, o con una factura de otra máquina
- **THEN** se acepta

#### Scenario: Serial o número imposibles

- **GIVEN** un pedido por verificar con la foto en el 504 de la máquina Z7C7046254
- **WHEN** el gerente escribe otro serial (por ejemplo, con una O en vez de un 0) o un número menor o igual a 504
- **THEN** se lanza un `UserError` que nombra el serial o el número de la foto

#### Scenario: Número con letras

- **WHEN** el gerente escribe un número con letras, signos o espacios en el medio
- **THEN** se lanza un `UserError`

### Requirement: Pedido que la verificación no resuelve

Con `printed: null`, el PdV DEBE (MUST) actuar según `reason`: con `no_response` o `document_open` el pedido sigue en la cola y el documento nuevo NO DEBE (MUST NOT) imprimirse (queda pendiente); con `other_printer` el pedido sigue en la cola y se imprime; con `unattributable`, una falla de la verificación o una entrada dañada, el pedido sale de la cola, se avisa y queda para revisión manual, sin frenar la venta.

#### Scenario: Se imprimió otro documento en el medio

- **GIVEN** que después del pedido por verificar se emitió otro documento en la máquina
- **WHEN** se valida la siguiente venta
- **THEN** se avisa que el pedido requiere revisión manual, conserva la marca y la venta se imprime

#### Scenario: La máquina no responde al verificar

- **WHEN** se valida una venta y la máquina no responde a la verificación del pedido anterior
- **THEN** la venta no se imprime, se sincroniza pendiente por facturar y el pedido anterior sigue en la cola

#### Scenario: Documento abierto que no se pudo cerrar

- **WHEN** se valida una venta y la verificación del pedido anterior responde `document_open`
- **THEN** la venta no se imprime, se sincroniza pendiente por facturar, el aviso pide reiniciar la máquina fiscal y el pedido anterior sigue en la cola

#### Scenario: Otra máquina conectada

- **WHEN** la verificación responde con el serial de otra máquina
- **THEN** el pedido sigue en la cola y la venta se imprime

#### Scenario: Cola dañada

- **WHEN** la cola local tiene una entrada sin datos de verificación
- **THEN** se descarta y la venta se imprime

#### Scenario: Aviso según el motivo

- **WHEN** la impresión se frena por una verificación con `no_response` o `document_open`
- **THEN** el aviso pide esperar a que la máquina responda o, con un documento abierto, reiniciarla

## ADDED Requirements

### Requirement: Filtro de pedidos por verificar en el backend

La búsqueda de pedidos del PdV DEBE (MUST) ofrecer el filtro "Impresión fiscal por verificar", que muestra los pedidos con `mf_print_verification`.

#### Scenario: Pedidos que esperan resolución

- **WHEN** el gerente activa el filtro en la lista de pedidos
- **THEN** ve solo los pedidos por verificar, para resolverlos con el asistente
