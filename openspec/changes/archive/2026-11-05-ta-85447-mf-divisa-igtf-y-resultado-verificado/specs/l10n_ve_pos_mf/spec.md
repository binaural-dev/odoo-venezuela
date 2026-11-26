## ADDED Requirements

### Requirement: Código fiscal de divisa solo con IGTF activo

Un `pos.payment.method` con un código fiscal de divisa (20-24, leído solo por sus dígitos, como el driver TFHKA) DEBE (MUST) tener `apply_igtf` activo. Sin `l10n_ve_pos_igtf` instalado, ningún método DEBE (MUST NOT) tener un código de divisa. Al crear o editar un método que no cumpla la regla, el sistema DEBE (MUST) lanzar un `ValidationError` que nombre el método y el código. Los códigos 01-19 NO DEBEN (MUST NOT) verse afectados.

#### Scenario: Código de divisa sin IGTF

- **GIVEN** un método "EFECTIVO USD" con `apply_igtf = False`
- **WHEN** se guarda con `code_fiscal_printer = "20"`
- **THEN** se lanza un `ValidationError` que menciona "EFECTIVO USD" y el código 20

#### Scenario: Código de divisa con IGTF

- **WHEN** un método se guarda con `code_fiscal_printer = "22"` y `apply_igtf = True`
- **THEN** se guarda sin errores

#### Scenario: Se desactiva el IGTF de un método en divisa

- **GIVEN** un método con `code_fiscal_printer = "21"` y `apply_igtf = True`
- **WHEN** se pone `apply_igtf = False`
- **THEN** se lanza un `ValidationError`

#### Scenario: Código nacional sin IGTF

- **WHEN** un método en USD se guarda con `code_fiscal_printer = "15"` y `apply_igtf = False`
- **THEN** se guarda sin errores

#### Scenario: Código de un dígito

- **WHEN** un método se guarda con `code_fiscal_printer = "2"` y `apply_igtf = False`
- **THEN** se trata como el `02` y se guarda sin errores

#### Scenario: Sin el módulo de IGTF del PdV

- **GIVEN** que `l10n_ve_pos_igtf` no está instalado
- **WHEN** un método se guarda con `code_fiscal_printer = "20"`
- **THEN** se lanza un `ValidationError`

### Requirement: Bloqueo de la impresión con un pago en divisa sin IGTF

Si un pago de la orden (monto distinto de cero y con el signo del documento) usa un método con código de divisa (20-24) sin `apply_igtf` (o sin el campo), `get_data_invoice` DEBE (MUST) devolver `valid: false` con un mensaje que nombre el método y pida avisar al administrador (el método solo se corrige con las sesiones de la caja cerradas), antes de cualquier RPC. En ese caso NO DEBE (MUST NOT) enviarse ningún comando a la máquina fiscal.

#### Scenario: Datos inconsistentes previos a la regla

- **GIVEN** un método con código `20` y `apply_igtf = False`, guardado así antes de actualizar el módulo o modificado por SQL, y la máquina fiscal conectada
- **WHEN** el cajero valida una orden pagada en parte con ese método y en parte con efectivo en Bs
- **THEN** el PdV muestra "Error de Máquina Fiscal" nombrando el método, no imprime nada (tampoco "FACTURA ANULADA") y la orden se sincroniza pendiente por facturar

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

### Requirement: Pedido por verificar

Si el driver devuelve `printed: null` (no se pudo saber si la máquina emitió el documento), el PdV DEBE (MUST) guardar la verificación en `pos.order.mf_print_verification` y en la cola local del navegador. Mientras tenga valor, el pedido NO DEBE (MUST NOT) volver a imprimirse, tampoco si se vuelve a validar: "Imprimir pedido pendiente" muestra "Verificar impresión" y avisa en vez de imprimir.

#### Scenario: La máquina no responde después del cierre

- **WHEN** la máquina deja de responder justo después del cierre de una venta
- **THEN** la orden se sincroniza sin número, con `mf_print_verification` y en la cola local

#### Scenario: Pedido pendiente por verificar

- **WHEN** el cajero pulsa el botón de un pedido por verificar que no se pudo resolver
- **THEN** se muestra un aviso y no se envía nada a la máquina

#### Scenario: Volver a validar después de un rechazo del servidor

- **GIVEN** una orden por verificar que el servidor rechazó al sincronizar (el core la deja en borrador en la pantalla de pago)
- **WHEN** el cajero la vuelve a validar
- **THEN** primero se verifica con la máquina: si la emitió, recibe su número sin reimprimirse; si no la emitió, se imprime; si no se sabe, no se imprime y se sincroniza pendiente

### Requirement: Métodos del servidor para pedidos por verificar

`pos.order.mf_set_print_verification` y `pos.order.mf_resolve_print_verification` DEBEN (MUST) escribir con los permisos del usuario del PdV (sin `sudo()`) y rechazar datos mal formados. La resolución solo DEBE (MUST) cambiar pedidos marcados, y un resultado "impreso" DEBE (MUST) traer el número fiscal, solo con dígitos (texto o entero).

#### Scenario: Número fiscal inválido

- **WHEN** el PdV envía un resultado "impreso" con un número vacío, con letras o signos, o que no es texto ni entero
- **THEN** se lanza un `UserError` y el pedido no cambia

#### Scenario: Resolución de un pedido sin marca

- **WHEN** el PdV envía el resultado de la máquina para un pedido que ya no está marcado (por ejemplo, porque se resolvió desde el backend)
- **THEN** el servidor no cambia el pedido y responde que no queda nada por aplicar

#### Scenario: Usuario sin permiso sobre los pedidos

- **WHEN** un usuario interno sin acceso a `pos.order` intenta marcar un pedido
- **THEN** se lanza un `AccessError`

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

### Requirement: Pedido que la verificación no resuelve

Con `printed: null`, el PdV DEBE (MUST) actuar según `reason`: con `no_response` el pedido sigue en la cola y el documento nuevo NO DEBE (MUST NOT) imprimirse (queda pendiente); con `other_printer` el pedido sigue en la cola y se imprime; con `unattributable`, una falla de la verificación o una entrada dañada, el pedido sale de la cola, se avisa y queda para revisión manual, sin frenar la venta.

#### Scenario: Se imprimió otro documento en el medio

- **GIVEN** que después del pedido por verificar se emitió otro documento en la máquina
- **WHEN** se valida la siguiente venta
- **THEN** se avisa que el pedido requiere revisión manual, conserva la marca y la venta se imprime

#### Scenario: La máquina no responde al verificar

- **WHEN** se valida una venta y la máquina no responde a la verificación del pedido anterior
- **THEN** la venta no se imprime, se sincroniza pendiente por facturar y el pedido anterior sigue en la cola

#### Scenario: Otra máquina conectada

- **WHEN** la verificación responde con el serial de otra máquina
- **THEN** el pedido sigue en la cola y la venta se imprime

#### Scenario: Cola dañada

- **WHEN** la cola local tiene una entrada sin datos de verificación
- **THEN** se descarta y la venta se imprime

### Requirement: Resolución manual de un pedido por verificar

El formulario de `pos.order` DEBE (MUST) avisar cuando el pedido está por verificar y ofrecer al gerente del PdV un asistente que sugiera el número esperado (el de la foto más uno), el serial y el Z. Si se indica que la máquina emitió el documento, DEBE (MUST) exigir número y serial y guardarlos; en ambos casos DEBE (MUST) quitar la marca.

#### Scenario: Resolución como emitido

- **WHEN** el gerente confirma que la máquina emitió el documento esperado
- **THEN** el pedido queda con ese número fiscal, serial y Z, sin marca

#### Scenario: Resolución como no emitido

- **WHEN** el gerente confirma que la máquina no lo emitió
- **THEN** el pedido queda como pendiente por facturar, sin marca

## RENAMED Requirements

- FROM: `### Requirement: Impresión fiscal bloqueante en la validación de pago`
- TO: `### Requirement: Impresión fiscal en la validación de pago`

## MODIFIED Requirements

### Requirement: Código fiscal del método de pago del PdV

`pos.payment.method` DEBE (MUST) tener el campo `code_fiscal_printer` (Char de 2 caracteres, default `01`), editable en el formulario del método de pago y cargado siempre en el PdV vía `_load_pos_data_fields`. Ese código es el que se envía a la impresora como método de pago TFHKA. Los códigos 01-19 son de moneda nacional, y los 20-24 son de divisas y DEBEN (MUST) ir con `apply_igtf` activo (ver "Código fiscal de divisa solo con IGTF activo").

#### Scenario: Método de pago mapeado

- **WHEN** un método de pago del PdV tiene `code_fiscal_printer = "20"` y `apply_igtf = True`, y se cobra con él
- **THEN** la línea de pago del payload lleva `payment_method_code = "20"`

### Requirement: Impresión fiscal en la validación de pago

El override de `OrderPaymentValidation.finalizeValidation` DEBE (MUST) ejecutar, antes de la sincronización del core, la conversión del descuento global (si falla, solo se registra) y la impresión fiscal cuando hay máquina conectada y la orden no tiene `mf_invoice_number`. Si la impresión falla, DEBE (MUST) mostrar el error y sincronizar igual: la orden queda sin número, pendiente por facturar (o por verificar).

#### Scenario: Impresión fiscal fallida

- **WHEN** el cajero valida una orden pagada y la impresión en la máquina fiscal devuelve error
- **THEN** el error se muestra en un diálogo, la orden se sincroniza sin número fiscal y aparece en "Pendientes por facturar"

#### Scenario: Sin máquina fiscal conectada

- **WHEN** no hay driver conectado
- **THEN** la impresión fiscal se omite y la validación continúa con el flujo estándar del core

#### Scenario: Orden ya impresa

- **WHEN** la orden ya tiene `mf_invoice_number`
- **THEN** no se vuelve a imprimir y la validación continúa

### Requirement: Impresión de un pedido pendiente

El botón "Imprimir pedido pendiente" DEBE (MUST) mostrarse solo para el pedido sincronizado seleccionado sin `mf_invoice_number`, exigir un driver conectado, resolver antes los pedidos por verificar y no imprimir un pedido por verificar. Reutiliza el flujo de la validación (`get_data_invoice`, `_convertOrderForDriver`, comando según el tipo); tras imprimir DEBE (MUST) persistir los datos con `write_mf_invoice_data` y navegar al recibo. Un error se muestra sin persistir datos fiscales.

#### Scenario: Pedido pendiente impreso

- **WHEN** el cajero imprime un pedido sincronizado sin número fiscal y el driver responde con éxito
- **THEN** se llama a `write_mf_invoice_data` con número, serial y Reporte Z, se navega al recibo y el pedido deja de aparecer en la lista de pendientes

#### Scenario: Pedido ya facturado

- **WHEN** el pedido seleccionado ya tiene `mf_invoice_number`
- **THEN** el botón no se muestra y la acción no se ejecuta

#### Scenario: Error de impresión

- **WHEN** el driver devuelve error al imprimir el pedido pendiente
- **THEN** se muestra el diálogo con el error y no se persiste ningún dato fiscal; si el resultado es desconocido, el pedido queda por verificar
