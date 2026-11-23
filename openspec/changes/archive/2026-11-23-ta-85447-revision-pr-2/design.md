# Diseño: segunda revisión del PR #1572

## Decisiones

**NC/ND: S1 solo con la máquina en reposo.** El manual de la TFHKA, en los medios de pago, dice
que si se aplicaron pagos parciales y se envía el `7`, el documento no se anula: sigue en la
totalización. Que S1 ya cuente el documento abierto desde el primer pago está medido solo para
facturas (HKA80, design de la 85447). Por eso, para NC y ND el ACK del `7` no alcanza: después de
`abortTransaction()` se relee el estado y, si la máquina no está en reposo, el resultado es
`document_open` sin mirar S1. Se le da el mismo margen que antes del `7` (4 consultas con
`retryDelay`), porque la máquina sigue un momento en `0x61` mientras imprime el cierre. Si no
responde, `no_response`: el PdV trata los dos igual (no imprime el documento nuevo y lo vuelve a
verificar en la siguiente impresión). Con `abortTransaction()` en `false` el resultado sigue
siendo `document_open`, como antes. Las facturas no cambian.

**Un solo chequeo del número para el asistente y el PdV.** `_mf_check_fiscal_number` devuelve el
motivo, o `False`, con los mismos textos que tenía el asistente. El asistente sigue igual: exige
el serial, así que la comparación de seriales y la búsqueda de duplicados usan el que escribe el
gerente. En la resolución del PdV el serial viene del driver (`registeredMachineNumber` de S1, el
mismo campo que la foto). Si viene vacío, no se compara y los duplicados se buscan en la máquina
de la foto; el número se escribe como antes, con el serial que vino.

**El chequeo solo corre cuando se va a escribir un número.** "No emitido", un pedido que ya tenía
número (lo conserva) y un pedido que todavía no está en el servidor (`False`, el PdV reintenta)
no escriben nada y siguen igual.

**Si el chequeo falla, revisión manual y no un error.** Un `UserError` haría que el PdV
reintentara la misma entrada en cada impresión. Se responde `{"manual_review": True, "reason"}`:
el pedido conserva la marca, el chatter guarda el motivo, el número informado y la foto, y el PdV
saca la entrada de la cola y avisa. El gerente lo resuelve con el asistente.

**El PdV sigue aplicando el número antes de llamar al servidor.** Una orden que todavía no está
en el servidor recibe el número en la orden local, y con él se sincroniza sin reimprimirse. Ese
orden no cambia. Solo con `manual_review` la orden local vuelve a sus valores previos (sin
número, por verificar).

**Mismas versiones.** Ningún cambio toca datos ni vistas, y las versiones del PR ya son
mayores que las de 19.0 (`l10n_ve_mf_base` 19.0.1.2.0, `l10n_ve_pos_mf` 19.0.3.3.0). El `-u`
de los módulos carga las traducciones.
