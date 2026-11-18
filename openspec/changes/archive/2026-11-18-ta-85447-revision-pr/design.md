# Diseño: correcciones de la revisión del PR #1572

## Decisiones

**El bloqueo de divisa sin IGTF va en `isOrderValid`.** En Odoo 19,
`validateOrder` llama a `isOrderValid` y después a `shouldHideValidationBehindFeedbackScreen`,
que navega al recibo aunque `finalizeValidation` devuelva `false` (solo se detiene ante un
`RPCError`). La propuesta de la revisión con IA (`blocking: true` y `return false` en
`finalizeValidation`) no deja al cajero en la pantalla de pago. El chequeo es local (la
configuración del método), así que no necesita la máquina. Solo se aplica con la máquina
conectada, que es cuando se imprimiría. Sin máquina, la orden queda pendiente y
`get_data_invoice` la frena al imprimirla. No contradice la decisión de no detener el PdV ante
una falla de la máquina: es un error de configuración que el cajero salva cobrando con otro
método, y la venta sale con su factura.

**El bloqueo de Contabilidad mira el campo, sin dependencia nueva.** `l10n_ve_account_mf`
no depende de `l10n_ve_pos_mf`, ni al revés. Si las dos implementaran un mismo gancho, el
orden de carga decidiría cuál gana. Se usa el mismo patrón que `check_print_out_refund`
(`"pos.order" in self.env`) más `"mf_print_verification" in _fields`, y la búsqueda con
`sudo()`: el contador no necesita leer pedidos del PdV para que se le niegue la impresión.

**Duplicados por valor, máquina y tipo de documento.** La TFHKA lleva contadores separados
de facturas, notas de crédito y notas de débito (S1 [2], [6] y [4]). Comparar solo número y
serial, como proponía la revisión, rechazaría una NC 101 legítima frente a la factura 101. El
número se compara por valor: según el origen se guarda "101" o "00000101". Se busca con
`=like '%101'` y se filtra en Python. La factura del backend usa el mismo contador de la
máquina que el PdV, por eso también se mira `account.move`. El tipo de un pedido sale del
`docType` de la verificación. El de otro pedido sale de `amount_total < 0` o de las líneas
devueltas, igual que en el PdV. La resolución automática no lleva este chequeo: su número sale
de los contadores de la máquina (+1 exacto con el subtotal).

**El mensaje del chatter se publica con `sudo()`.** El cajero resuelve con sus permisos
(sin `sudo()`), pero `message_post` lee la compañía (alias de correo) y el usuario del PdV no
tiene acceso a `res.company`: la resolución automática fallaba. El autor sigue siendo quien
resolvió (`author_id`).

**NC o ND que sigue abierta después del `7`.** Si el `7` no termina el documento y la
máquina sigue en transacción, `_documentOutcome` comparaba S1 con el documento abierto. Para
facturas está medido que S1 ya lo cuenta desde el primer pago; para NC y ND no, y "mismo
número" concluía "no impresa" y habilitaba reimprimir. Ahora, si `abortTransaction()` devuelve
`false` y el documento no es una factura, el resultado es `printed: null` con
`reason: "document_open"`. El PdV lo trata como `no_response`: se vuelve a verificar antes de
la siguiente impresión, que tampoco podría salir con el documento abierto. Tiene su propio
motivo para que el aviso pida reiniciar la máquina y no revisar la conexión. Las facturas no cambian, y si el `7` funciona todo
queda igual que antes.

**Gancho para las órdenes que no van a la máquina.** En el modo mixto de
`binaural_operative_pos` (`pos_operative_mode = "order"`) la máquina está conectada y una
orden operativa se salta la impresión sobrescribiendo `pushToMF`. El bloqueo nuevo corre antes
en `isOrderValid` y la frenaba. `PosStore._mfOrderGoesToFiscalPrinter(order)` concentra la
decisión: lo usan `isOrderValid` y `finalizeValidation`, y el puente lo sobrescribe. El puente se
mergea antes que este PR (o el mismo día): al revés queda un hueco para las órdenes
operativas pagadas con un método inconsistente previo a la restricción.

**El asistente exige el serial y un número posterior a la foto.** El documento solo pudo salir
en la máquina conectada al imprimirlo y con un número mayor al que tenía. Un error de tipeo en
el serial también esquivaría el chequeo de duplicados.
