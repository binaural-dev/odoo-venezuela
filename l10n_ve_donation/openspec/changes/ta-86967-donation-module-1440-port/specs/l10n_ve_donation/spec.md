## ADDED Requirements

### Requirement: REQ-DON-001 · Donación de mercancía desde el menú Donaciones
Un `stock.picking` creado desde Inventario > Operaciones > Transferencias > Donaciones DEBE (MUST) quedar marcado `is_donation` mediante el contexto `donation_menu` (en `default_get`), no mediante `default_is_donation`. Para un picking con pedido de venta, `is_donation` sigue al pedido (`sale_id.is_donation`). La bandera `is_donation_picking_type` del tipo de operación solo filtra los tipos que ofrece el formulario del menú.

#### Scenario: Picking creado desde el menú
- **Dado** que el usuario abre el menú Donaciones
- **Cuando** crea un picking nuevo
- **Entonces** el picking tiene `is_donation` activo y el selector de tipo de operación solo ofrece los tipos marcados como de donación

#### Scenario: Picking de un pedido de donación
- **Dado** un pedido de venta con `is_donation` activo
- **Cuando** se genera su picking de entrega
- **Entonces** el picking tiene `is_donation` activo

### Requirement: REQ-DON-002 · Motivo de traslado 'Donación' en las salidas de donación
La salida de una donación (con o sin pedido) DEBE (MUST) tener el motivo de traslado `l10n_ve_stock_account.transfer_reason_donation`, agregado a los motivos permitidos sin reemplazar los de la base, asignado automáticamente y en solo lectura en la vista. Las entradas de donación no lo reciben.

#### Scenario: Salida de donación
- **Dado** un picking de salida con `is_donation` activo
- **Cuando** se crea
- **Entonces** `transfer_reason_id` es 'Donación' y los motivos permitidos conservan los de la base

#### Scenario: Entrega que no es donación
- **Dado** una entrega con `is_donation` desactivado
- **Cuando** se crea
- **Entonces** el motivo 'Donación' no es el suyo ni está permitido

### Requirement: REQ-DON-003 · Contacto o motivo para validar una donación sin pedido
Al validar una salida de donación sin pedido (`is_donation and not sale_id and outgoing`), DEBE (MUST) existir el contacto (`partner_id`, el beneficiario) o el motivo de donación (`donation_reason`).

#### Scenario: Sin contacto ni motivo
- **Dado** una salida de donación sin pedido, sin contacto y sin motivo
- **Cuando** el usuario la valida
- **Entonces** se lanza un error pidiendo el contacto o el motivo

### Requirement: REQ-DON-004 · Configuración coherente de la entrega de donación
La validación de una salida de donación sin pedido DEBE (MUST) rechazar el picking cuando la ubicación de destino no es de tipo `inventory`, o cuando hay un producto almacenable con valoración `real_time` y la ubicación de destino no tiene `valuation_account_id`. Un producto no almacenable o con valoración periódica no exige la cuenta. `_get_donation_delivery_config_errors()` es el punto de extensión.

#### Scenario: Destino que no es inventario
- **Dado** una salida de donación con destino Clientes
- **Cuando** el usuario la valida
- **Entonces** se lanza un error que pide cambiar el destino a una ubicación de pérdida de inventario

#### Scenario: Destino sin cuenta de valoración
- **Dado** una salida de donación de un producto `real_time` hacia una ubicación `inventory` sin `valuation_account_id`
- **Cuando** el usuario la valida
- **Entonces** se lanza un error que pide configurar la cuenta de valoración de la ubicación

#### Scenario: Valoración periódica
- **Dado** el mismo picking con el producto en valoración periódica
- **Cuando** el usuario la valida
- **Entonces** no hay errores de configuración

### Requirement: REQ-DON-005 · Asiento de valoración de la salida de donación
El asiento de valoración de una salida de donación sin pedido DEBE (MUST) quedar marcado `is_donation`, con el contacto de cabecera del picking (el beneficiario), el partner de la compañía en cada apunte, el motivo en la referencia del asiento y en el nombre de los apuntes, debitando la cuenta de valoración de la ubicación de destino y acreditando la de valoración del producto. Los movimientos que no son de donación DEBEN (MUST) valorarse en asientos aparte y quedar con `is_donation` desactivado.

#### Scenario: Entrega con beneficiario
- **Dado** una salida de donación con un beneficiario y un motivo
- **Cuando** se valida
- **Entonces** el asiento publicado tiene `is_donation`, cabecera = beneficiario, apuntes con el partner de la compañía y el motivo en la referencia

#### Scenario: Lote mixto
- **Dado** un movimiento de donación y otro que no lo es validados juntos
- **Cuando** el core genera los asientos
- **Entonces** el de donación está marcado y el otro no, y son asientos distintos

#### Scenario: Entrega de un pedido de donación
- **Dado** una entrega que viene de un pedido de donación
- **Cuando** se valida
- **Entonces** su asiento no se marca como donación (su contabilidad no cambia)

#### Scenario: `default_is_donation` filtrado en el contexto
- **Dado** un `default_is_donation` en el contexto del llamador (por ejemplo de una acción de otro módulo)
- **Cuando** se valida una entrega que no es de donación y genera asiento de valoración
- **Entonces** su asiento no se marca como donación; el de una entrega de donación sí

### Requirement: REQ-DON-006 · Certificado de entrega de donación
Una salida de donación sin pedido validada DEBE (MUST) permitir imprimir el certificado de entrega (`l10n_ve_donation.action_donation_delivery_certificate`), con el costo por línea tomado del valor guardado del movimiento (`stock.move.value`) y por tanto estable entre reimpresiones; antes de validar el costo es cero.

#### Scenario: Reimpresión tras un cambio de costo
- **Dado** una salida de donación validada con costo unitario 15
- **Cuando** el costo estándar del producto cambia a 99 y se reimprime
- **Entonces** el certificado sigue mostrando 15

### Requirement: REQ-DON-007 · Las donaciones sin pedido no se devuelven
El asistente de devolución (`stock.return.picking._create_return`) DEBE (MUST) rechazar la devolución de un picking con `is_donation` y sin pedido de venta; los pickings de un pedido de donación siguen el flujo de devoluciones de ventas. El botón de devolución se oculta en esos pickings. La devolución de la entrega de un pedido de donación NO DEBE (MUST NOT) conservar el motivo de traslado 'Donación': el libro de inventario cuenta como retiro todo movimiento con ese motivo sin mirar su dirección, y la devolución (un movimiento de entrada) contaría como entrada y como retiro.

#### Scenario: Devolución de una donación
- **Dado** una salida de donación sin pedido validada
- **Cuando** el usuario intenta devolverla
- **Entonces** se lanza un error indicando que las donaciones no se devuelven

#### Scenario: Devolución de la entrega de un pedido de donación
- **Dado** la entrega validada de un pedido de donación con el motivo 'Donación'
- **Cuando** se devuelve
- **Entonces** la devolución se crea sin el motivo 'Donación' (el de la entrega no cambia); la devolución de una entrega que no es de donación conserva su motivo

### Requirement: REQ-DON-008 · Tipo de operación de donación
Un tipo de operación marcado `is_donation_picking_type` DEBE (MUST) ser de entrada o de salida. Si es de salida DEBE (MUST) pertenecer a un almacén de donación y, cuando tiene destino por defecto, este DEBE (MUST) ser de tipo `inventory`.

#### Scenario: Tipo de salida en un almacén normal
- **Dado** un tipo de operación de salida marcado como de donación
- **Cuando** su almacén no es de donación
- **Entonces** se lanza un error de validación

### Requirement: REQ-DON-009 · Cuenta de valoración propuesta en ubicaciones de donación
Una ubicación nueva de tipo `inventory` bajo el almacén de donación DEBE (MUST) proponer como `valuation_account_id` la cuenta de donación de la compañía, sin sobrescribir una cuenta ya indicada (ni una vacía explícita). Una ubicación que es destino por defecto de un tipo de operación de donación de salida DEBE (MUST) seguir siendo de tipo `inventory`.

#### Scenario: Ubicación nueva
- **Dado** el almacén de donación y una cuenta de donación en la compañía
- **Cuando** se crea una ubicación `inventory` debajo
- **Entonces** su `valuation_account_id` es la cuenta de donación

### Requirement: REQ-DON-014 · Asiento manual de donación
Las donaciones recibidas en dinero se registran con un asiento manual (`move_type = entry`) que el usuario marca como donación. El campo `is_donation` DEBE (MUST) verse siempre y ser editable solo en asientos manuales en borrador (de solo lectura en facturas, que lo toman del pedido). El partner de la compañía DEBE (MUST) asignarse a los apuntes **mientras el asiento es borrador** —al crear la línea (el cliente web envía `partner_id: False`), al marcar `is_donation` en un asiento existente y justo antes de publicar— y los apuntes que ya tienen partner se respetan. Publicar el asiento NO DEBE (MUST NOT) escribir nada en sus apuntes: un diario con "Bloquear asientos con hash" no permite editar el partner ni la etiqueta de un asiento publicado, y la referencia del asiento no se agrega a la etiqueta.

#### Scenario: Marcar un asiento nuevo como donación
- **Dado** un asiento manual nuevo
- **Cuando** el usuario abre el formulario
- **Entonces** puede marcar "Es Donación", y en una factura el campo no es editable

#### Scenario: Apuntes creados por el cliente web
- **Dado** un asiento de donación cuyos apuntes llegan con `partner_id: False`
- **Cuando** se guarda
- **Entonces** los apuntes quedan con el partner de la compañía, también los agregados después

#### Scenario: Marcar un asiento existente
- **Dado** un asiento manual con apuntes sin partner
- **Cuando** se marca `is_donation`
- **Entonces** los apuntes sin partner reciben el de la compañía; un asiento que no es donación no se toca

#### Scenario: Publicar en un diario con hash
- **Dado** un diario con "Bloquear asientos con hash" y un asiento de donación en borrador
- **Cuando** se publica
- **Entonces** se publica sin error y sus apuntes no se modifican (partner y etiqueta quedan como estaban)

### Requirement: REQ-DON-015 · Una donación sin pedido no se factura
En una salida de donación sin pedido (`is_donation and not sale_id`) el botón "Crear factura" (`show_create_invoice`) DEBE (MUST) estar oculto: facturarla emitiría una factura fiscal normal al beneficiario, sin marca de donación ni nota de crédito.

#### Scenario: Entrega de donación validada
- **Dado** una salida de donación sin pedido ya validada
- **Cuando** el usuario abre el picking
- **Entonces** no se ofrece "Crear factura"; la misma entrega sin la marca de donación sí lo ofrece

### Requirement: REQ-DON-016 · Certificado de donación de dinero
El certificado del asiento (`l10n_ve_donation.action_donation_certificate_account_move`) es el de una donación de dinero: DEBE (MUST) enunciar "la suma de" el monto en números, sin monto en letras, con el bolívar primero (la moneda de la compañía si está en bolívares; la moneda alterna si la compañía está en otra moneda, como USD) y la referencia como concepto, y, si el asiento tiene monto alterno, su equivalente en la otra moneda con la tasa BCV guardada en el asiento (bolívares por unidad de esa moneda), con 4 decimales, y su fecha (una reimpresión da los mismos datos). La tasa DEBE (MUST) elegirse según cuál de las dos monedas es el bolívar: `foreign_rate` si la compañía está en bolívares y `foreign_inverse_rate` si la alterna es el bolívar. NO DEBE (MUST NOT) hablar de bienes. El asiento de valoración de una entrega por picking (asiento con movimientos de stock) NO DEBE (MUST NOT) ofrecer el botón "Generar Certificado de Donación", y `print_donation_certificate` DEBE (MUST) rechazarlo con un error que remite al certificado de entrega del picking (REQ-DON-006).

#### Scenario: Asiento manual con monto alterno
- **Dado** un asiento manual de donación publicado por 38.000,00 en bolívares, con tasa BCV 450
- **Cuando** se imprime el certificado
- **Entonces** dice "la suma de 38.000,00, equivalente a 84,44 USD a la tasa BCV del día <fecha> de 450,0000", la referencia como concepto, sin monto en letras y sin mencionar bienes

#### Scenario: Compañía en USD con el bolívar como moneda alterna
- **Dado** una compañía en USD con alterna VEF y un asiento por 84,44 USD (38.000,00 VEF)
- **Cuando** se imprime el certificado
- **Entonces** el monto en bolívares va primero (38.000,00), el equivalente es 84,44 USD y la tasa es 450,0000 bolívares por USD, no su inversa

#### Scenario: Asiento sin monto alterno
- **Dado** un asiento de donación cuya moneda alterna es la de la compañía
- **Cuando** se imprime el certificado
- **Entonces** dice "la suma de" sin la parte del equivalente ni la tasa

#### Scenario: Asiento de valoración de una entrega por picking
- **Dado** el asiento de valoración de una entrega de donación validada
- **Cuando** el usuario abre el asiento
- **Entonces** no ve el botón "Generar Certificado de Donación"; si se invoca la acción, falla con un error que indica imprimir el certificado de entrega del picking

### Requirement: REQ-DON-017 · Las donaciones no se listan en las guías de despacho
Una entrega con `is_donation` NO DEBE (MUST NOT) cumplir `match_guide_dispatch_domain`: el certificado de entrega de donación (REQ-DON-006) sustituye a la guía de despacho, así que la entrega no aparece en el listado de guías aunque su tipo de operación sea el de entregas estándar del almacén.

#### Scenario: Entrega de donación con el tipo de entrega estándar
- **Dado** una entrega de donación validada con el tipo de operación de entregas estándar de un almacén
- **Cuando** se calcula si entra en el listado de guías de despacho
- **Entonces** no entra; la misma entrega sin la marca de donación sí entra

## MODIFIED Requirements

### Requirement: REQ-DON-010 · Almacén de donación único por compañía y sucursal
El sistema DEBE (MUST) impedir que exista más de un almacén marcado `is_donation_warehouse` por compañía (y por sucursal, cuando existe `subsidiary_id`). *(Antes: uno global.)*

#### Scenario: Segundo almacén en la misma compañía
- **Dado** un almacén de donación en una compañía
- **Cuando** se marca otro almacén de la misma compañía
- **Entonces** se lanza un error de validación

#### Scenario: Otra compañía
- **Dado** un almacén de donación en la compañía A
- **Cuando** se marca uno en la compañía B
- **Entonces** se permite

### Requirement: REQ-DON-011 · El contacto de cabecera de una donación es el real
El contacto de cabecera (`partner_id`) de un pedido, picking o asiento de donación NO se fuerza al partner de la compañía: registra al donante o beneficiario real. El constraint `_check_partner_donation` valida únicamente los **apuntes** de los asientos manuales o de valoración (`move_type = entry`), que DEBEN (MUST) llevar el partner de la compañía, asignado mientras el asiento es borrador (REQ-DON-014); las facturas y notas de crédito siguen el contacto de cabecera. Marcar `is_donation` en un pedido establece `document = invoice` y el almacén de donación de la compañía, sin tocar el cliente. *(Reemplaza "Partner de la compañía obligatorio en asientos de donación" y "Pedido de venta de donación usa el partner de la compañía".)*

#### Scenario: Cambio de cliente en un pedido de donación
- **Dado** un pedido con `is_donation` activo
- **Cuando** el usuario cambia el cliente
- **Entonces** se permite y el pedido conserva el cliente elegido

#### Scenario: Apunte con otro contacto
- **Dado** un asiento manual con `is_donation`
- **Cuando** un apunte tiene un contacto distinto al de la compañía
- **Entonces** se lanza un error de validación

### Requirement: REQ-DON-012 · Publicar una factura de donación respeta el asistente de alerta
Al publicar (`action_post`) una factura de cliente de donación, si `l10n_ve_accountant` devuelve su asistente de alerta (un `dict`), el flujo de donación NO continúa y no se publica nada. Cuando el asistente confirma (`move_action_post_alert=True`), la factura se publica, se crea su reversión con el asistente `account.move.reversal` (fecha en la zona horaria del usuario) y la nota de crédito se publica si está en borrador. El flujo DEBE (MUST) recorrer todas las facturas del lote y reversar solo las que esa llamada publica. *(Antes: la factura se publicaba saltando el asistente y la NC quedaba en borrador.)*

#### Scenario: Primera llamada
- **Dado** una factura de donación en borrador
- **Cuando** el usuario pulsa Confirmar
- **Entonces** se abre el asistente de alerta y la factura sigue en borrador

#### Scenario: Confirmación del asistente
- **Dado** el asistente de alerta abierto
- **Cuando** el usuario confirma
- **Entonces** la factura y su nota de crédito de donación quedan publicadas

#### Scenario: Varias facturas en una sola llamada
- **Dado** tres facturas de donación en borrador
- **Cuando** se publican juntas (`move_action_post_alert=True`)
- **Entonces** cada una queda publicada con su propia nota de crédito, y un asiento de donación del mismo lote también se procesa

#### Scenario: Volver a publicar una factura ya publicada
- **Dado** una factura de donación publicada, con su nota de crédito
- **Cuando** se llama otra vez a `action_post`
- **Entonces** no se crea una segunda nota de crédito

### Requirement: REQ-DON-013 · Reversión de una donación con API de 19
`_reverse_moves` DEBE (MUST) aceptar `default_values_list` ausente, copiar `invoice_date` de la factura y usar `fields.Date.context_today`. La nota de crédito DEBE (MUST) crearse **sin** `skip_invoice_sync`: con esa llave el core de 19 no genera las líneas de impuesto ni de cobro y la nota queda en cero (en 17.0 ya se había quitado, `ea52357301`, tarea 69610). La nota DEBE (MUST) copiar la base, el impuesto y el total de la factura. La exención de la validación de origen se decide únicamente por `is_donation` (`_l10n_ve_skip_refund_origin_validation`), sin clave de contexto. En un lote que mezcla facturas de donación con otros asientos, `_reverse_moves` DEBE (MUST) revertir también los que no son de donación por el flujo estándar, con sus valores por defecto alineados, en lugar de omitirlos en silencio.

#### Scenario: Reversión sin valores por defecto
- **Dado** una factura de donación publicada
- **Cuando** se llama `_reverse_moves()` sin argumentos
- **Entonces** se crea una nota de crédito `out_refund` con `is_donation` activo

#### Scenario: La nota copia los montos de la factura
- **Dado** una factura de donación con impuesto, publicada
- **Cuando** se publica su nota de crédito automática
- **Entonces** la nota tiene la misma base, el mismo impuesto y el mismo total, con una línea de impuesto y una de cobro que cuadran en cero

#### Scenario: Lote mixto
- **Dado** una factura de donación y una factura normal publicadas
- **Cuando** se revierten juntas con `_reverse_moves`
- **Entonces** la de donación recibe su nota con el producto de donación y la normal se revierte por el flujo estándar, cada una con sus valores por defecto

### Requirement: Asignación del partner de la compañía al publicar un asiento manual de donación
**Razón**: reemplazado por REQ-DON-014. El partner se asigna en borrador y publicar no escribe sobre el asiento (un diario con hash no lo permite). También se retira el sufijo " - <ref>" que `action_post` agregaba a la etiqueta de los apuntes.

### Requirement: Certificado de donación en PDF
**Razón**: el certificado era un acta de donación de bienes (el motivo como "bienes" y el valor en blanco) y el botón se mostraba también en el asiento de valoración de las entregas por picking. Pasa a ser el de una donación de dinero y se oculta en esos asientos (REQ-DON-016).
