# l10n_ve_donation

## Purpose

Gestiona el flujo completo de donaciones: pedidos de venta marcados como donación, facturas de donación que se anulan automáticamente con una nota de crédito valorada contra la cuenta de gasto de donación, salidas de mercancía por donación (picking del menú Donaciones, con su asiento de valoración, certificado de entrega y bloqueo de devoluciones), y los certificados de donación en PDF. La donación por scrap no existe. Extiende `account.move`, `account.move.line`, `account.asset`, `product.template`, `res.company`, `res.config.settings`, `sale.order`, `stock.location`, `stock.move`, `stock.picking`, `stock.picking.type`, `stock.return.picking` y `stock.warehouse`. Depende de `l10n_ve_accountant`, `l10n_ve_stock`, `l10n_ve_invoice`, `l10n_ve_sale`, `l10n_ve_stock_account`, `stock_account` y `account_asset`. Define el grupo de seguridad `l10n_ve_donation.group_donation_manager` (Donation Manager).

## Requirements


### Requirement: Cuenta de donación por compañía

Cada compañía (`res.company`) DEBE (MUST) poder definir una cuenta de donación en el campo `donation_account_id` (Many2one a `account.account`, con dominio restringido a cuentas de tipo `expense`), editable desde los ajustes generales (campo related `donation_account_id` en `res.config.settings` con `readonly=False`).

#### Scenario: Configuración desde ajustes

- **WHEN** un administrador selecciona una cuenta de gasto como "Donation Account" en ajustes y guarda
- **THEN** el campo `donation_account_id` de la compañía activa queda establecido a esa cuenta

### Requirement: Producto de donación único

El sistema DEBE (MUST) impedir, vía constraint sobre `is_donation_product` de `product.template`, que exista más de un producto marcado como producto de donación.

#### Scenario: Segundo producto de donación

- **WHEN** se marca `is_donation_product` en un producto y ya existe otro producto con `is_donation_product` activo
- **THEN** se lanza un error de validación indicando que ya existe un producto de donación

### Requirement: NC de donación exenta de la validación de origen por `is_donation`

Una nota de crédito con `is_donation` activo DEBE (MUST) quedar exenta de la validación de productos y montos contra la factura origen de `l10n_ve_invoice` (que corre al publicar), sin depender de ninguna clave de contexto: `account.move` sobrescribe `_l10n_ve_skip_refund_origin_validation()` para devolver `is_donation`. El producto de donación nunca está en la factura original y la nota de crédito se publica en una llamada distinta a la que la creó.

#### Scenario: Nota de crédito de donación confirmada a mano

- **WHEN** la nota de crédito automática de una factura de donación, que quedó en borrador, se publica en una llamada posterior sin la clave `l10n_ve_skip_refund_origin_validation`
- **THEN** se publica sin error, aunque su producto de donación no esté en la factura original

#### Scenario: La misma nota de crédito sin la marca de donación

- **WHEN** se publica una nota de crédito equivalente (producto de donación, monto mayor al facturado) con `is_donation` desactivado
- **THEN** se lanza un error de validación de `l10n_ve_invoice`

### Requirement: Reversión de facturas de donación con el producto de donación agrupado por impuestos

La reversión (`_reverse_moves`) de un movimiento con `is_donation` activo y `move_type` distinto de `entry` DEBE (MUST) crear una nota de crédito (`out_refund`, también marcada `is_donation`) cuyas líneas usan el producto marcado `is_donation_product` y la cuenta `donation_account_id` de la compañía: una línea por cada combinación de impuestos de las líneas originales, con `price_unit` igual a la suma de las bases (`price_subtotal`) de ese grupo y los mismos impuestos. Si no existe producto de donación configurado o la compañía no tiene `donation_account_id`, DEBE (MUST) lanzar un error.

#### Scenario: Factura con dos grupos de impuestos

- **WHEN** se revierte una factura de donación cuyas líneas tienen dos combinaciones distintas de impuestos
- **THEN** la nota de crédito creada tiene dos líneas con el producto de donación, cada una con la suma de bases y los impuestos de su grupo, imputadas a la cuenta de donación

#### Scenario: Sin producto de donación configurado

- **WHEN** se revierte una factura de donación y no existe ningún producto con `is_donation_product` activo
- **THEN** se lanza un error pidiendo configurar el producto de donación

#### Scenario: Sin cuenta de donación configurada

- **WHEN** se revierte una factura de donación y la compañía no tiene `donation_account_id` establecida
- **THEN** se lanza un error pidiendo configurar la cuenta de donación

### Requirement: Excepción de cuenta por cobrar para la cuenta de donación

La validación de cuentas por cobrar/pagar de `account.move.line` (`_check_payable_receivable`) DEBE (MUST) aceptar, en documentos de venta marcados `is_donation`, que la línea de `display_type = payment_term` use la cuenta de donación de la compañía (`donation_account_id`) en lugar de una cuenta de tipo `asset_receivable`; el resto de las validaciones estándar (cuenta payable en ventas, cuenta receivable en compras, correspondencia entre `payment_term` y el tipo de cuenta) se mantienen.

#### Scenario: Línea de vencimiento con la cuenta de donación

- **WHEN** un documento de venta de donación tiene una línea `payment_term` con la cuenta `donation_account_id` de la compañía
- **THEN** la validación pasa sin error

#### Scenario: Cuenta de gasto arbitraria en línea de vencimiento

- **WHEN** un documento de venta (donación o no) tiene una línea `payment_term` con una cuenta que no es receivable ni la cuenta de donación
- **THEN** se lanza un error indicando que los apuntes en cuentas por cobrar deben tener fecha de vencimiento y viceversa

### Requirement: Inmutabilidad de la marca de donación en pedidos confirmados

El sistema DEBE (MUST) impedir, vía constraint sobre `is_donation` y `state` de `sale.order`, modificar el valor de `is_donation` en pedidos en estado `sale` o `done`.

#### Scenario: Cambio en pedido confirmado

- **WHEN** se intenta cambiar `is_donation` en un pedido ya confirmado
- **THEN** se lanza un error de validación indicando que el campo no puede modificarse en un pedido confirmado o completado

### Requirement: Propagación de la marca de donación a la factura

Las facturas generadas desde un pedido de venta (`_prepare_invoice`) DEBEN (MUST) heredar el valor de `is_donation` del pedido.

#### Scenario: Facturación de un pedido de donación

- **WHEN** se genera la factura de un pedido con `is_donation` activo
- **THEN** la factura se crea con `is_donation` activo

### Requirement: Reversión de asientos de donación restringida al grupo Donation Manager

El campo computado `can_reverse_donation_move` de `account.move` DEBE (MUST) ser verdadero solo cuando el usuario pertenece al grupo `l10n_ve_donation.group_donation_manager`; la vista de formulario oculta el botón de reversión de los asientos de donación a los usuarios sin ese grupo.

#### Scenario: Usuario sin el grupo

- **WHEN** un usuario que no pertenece a `l10n_ve_donation.group_donation_manager` abre un asiento de donación publicado
- **THEN** `can_reverse_donation_move` es falso y el botón de reversión no está disponible

### Requirement: Restablecer a borrador oculto en asientos de donación

La vista de formulario de `account.move` DEBE (MUST) ocultar el botón "Restablecer a borrador" (`button_draft`) cuando el movimiento está marcado `is_donation`, cuando es una factura o nota de crédito de cliente (`move_type` en `out_invoice` / `out_refund`) o cuando ya está en borrador; el campo `is_donation` solo es editable en asientos manuales (`move_type = entry`) en estado borrador.

#### Scenario: Asiento de donación publicado

- **WHEN** un usuario abre un asiento de donación publicado
- **THEN** el botón "Restablecer a borrador" no está disponible y el campo `is_donation` es de solo lectura

### Requirement: Recibo de donación en PDF

El sistema DEBE (MUST) permitir generar el reporte qweb-pdf "Donation Receipt" (`l10n_ve_donation.action_donation_receipt_account_move`) desde el botón `print_donation_receipt` de `account.move`, disponible únicamente en asientos manuales (`move_type = entry`) publicados y marcados `is_donation`, que no sean el asiento de valoración de una entrega por picking ni una donación recibida (REQ-DON-016, REQ-DON-018). Las donaciones recibidas tienen Certificado de donación (REQ-DON-023).

#### Scenario: Impresión del recibo

- **WHEN** un usuario pulsa "Generate Donation Receipt" en un asiento de donación otorgada publicado
- **THEN** se genera el PDF del recibo de donación de ese asiento

### Requirement: La nota de crédito de reverso de una donación usa la fecha del usuario

La nota de crédito de reverso de una donación DEBE (MUST) crearse con la fecha `fields.Date.context_today(self)` (zona horaria del usuario) y no con la fecha UTC del servidor (`fields.Date.today()`), tanto en el wizard de reversión de `action_post` como en el valor por defecto de `_reverse_moves`, para no quedar con fecha posterior a "hoy" y ser rechazada por el guard de fecha futura de `l10n_ve_invoice` al confirmarse.

#### Scenario: Donación confirmada en la noche (hora de Caracas)

- **WHEN** se confirma una factura de donación entre las 20:00 y las 24:00 hora de Caracas, cuando la fecha UTC ya es la del día siguiente
- **THEN** la nota de crédito de reverso se crea con la fecha local de hoy y se confirma sin error

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

### Requirement: REQ-DON-006 · Recibo de entrega de donación
Una salida de donación sin pedido validada DEBE (MUST) permitir imprimir el recibo de entrega (`l10n_ve_donation.action_donation_receipt_stock_picking`, REQ-DON-019), con el costo por línea tomado del valor guardado del movimiento (`stock.move.value`) y por tanto estable entre reimpresiones; antes de validar el costo es cero.

#### Scenario: Reimpresión tras un cambio de costo
- **Dado** una salida de donación validada con costo unitario 15
- **Cuando** el costo estándar del producto cambia a 99 y se reimprime
- **Entonces** el recibo sigue mostrando 15

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


### Requirement: REQ-DON-010 · Almacén de donación único por compañía y sucursal
El sistema DEBE (MUST) impedir que exista más de un almacén marcado `is_donation_warehouse` por compañía (y por sucursal, cuando existe `subsidiary_id`).

#### Scenario: Segundo almacén en la misma compañía
- **Dado** un almacén de donación en una compañía
- **Cuando** se marca otro almacén de la misma compañía
- **Entonces** se lanza un error de validación

#### Scenario: Otra compañía
- **Dado** un almacén de donación en la compañía A
- **Cuando** se marca uno en la compañía B
- **Entonces** se permite

### Requirement: REQ-DON-011 · El contacto de cabecera de una donación es el real
El contacto de cabecera (`partner_id`) de un pedido, picking o asiento de donación NO se fuerza al partner de la compañía: registra al donante o beneficiario real. El constraint `_check_partner_donation` valida únicamente los **apuntes** de los asientos manuales o de valoración (`move_type = entry`), que DEBEN (MUST) llevar el partner de la compañía, asignado mientras el asiento es borrador (REQ-DON-014); las facturas y notas de crédito siguen el contacto de cabecera. Marcar `is_donation` en un pedido establece `document = invoice` y el almacén de donación de la compañía, sin tocar el cliente.

#### Scenario: Cambio de cliente en un pedido de donación
- **Dado** un pedido con `is_donation` activo
- **Cuando** el usuario cambia el cliente
- **Entonces** se permite y el pedido conserva el cliente elegido

#### Scenario: Apunte con otro contacto
- **Dado** un asiento manual con `is_donation`
- **Cuando** un apunte tiene un contacto distinto al de la compañía
- **Entonces** se lanza un error de validación

### Requirement: REQ-DON-012 · Publicar una factura de donación respeta el asistente de alerta
Al publicar (`action_post`) una factura de cliente de donación, si `l10n_ve_accountant` devuelve su asistente de alerta (un `dict`), el flujo de donación NO continúa y no se publica nada. Cuando el asistente confirma (`move_action_post_alert=True`), la factura se publica, se crea su reversión con el asistente `account.move.reversal` (fecha en la zona horaria del usuario) y la nota de crédito se publica si está en borrador. El flujo DEBE (MUST) recorrer todas las facturas del lote y reversar solo las que esa llamada publica.

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

### Requirement: REQ-DON-016 · Recibo de donación de dinero
El recibo del asiento (`l10n_ve_donation.action_donation_receipt_account_move`) es el de una donación de dinero otorgada: DEBE (MUST) mostrar el monto en números, sin monto en letras (el bolívar primero y su equivalente con la tasa, REQ-DON-026), el concepto (las líneas de débito que no son de caja, banco ni por cobrar/pagar) y la referencia del asiento como observación; NO DEBE (MUST NOT) hablar de bienes. El asiento de valoración de una entrega por picking NO DEBE (MUST NOT) ofrecer el botón "Generate Donation Receipt", y `print_donation_receipt` DEBE (MUST) rechazarlo con un error que remite al recibo del picking (REQ-DON-006).

#### Scenario: Asiento manual con monto alterno
- **Dado** un asiento manual de donación otorgada publicado por 38.000,00 en bolívares, con tasa BCV 450
- **Cuando** se imprime el recibo
- **Entonces** muestra el monto, el equivalente en USD con la tasa BCV, el concepto y la referencia como observación, sin monto en letras y sin mencionar bienes

#### Scenario: Asiento sin monto alterno
- **Dado** un asiento de donación cuya moneda alterna es la de la compañía
- **Cuando** se imprime el recibo
- **Entonces** muestra solo el monto, sin equivalente ni tasa

#### Scenario: Asiento de valoración de una entrega por picking
- **Dado** el asiento de valoración de una entrega de donación validada
- **Cuando** el usuario abre el asiento
- **Entonces** no ve el botón "Generate Donation Receipt"; si se invoca la acción, falla con un error que indica imprimir el recibo del picking

### Requirement: REQ-DON-017 · Las donaciones no se listan en las guías de despacho
Una entrega con `is_donation` NO DEBE (MUST NOT) cumplir `match_guide_dispatch_domain`: el recibo de entrega de donación (REQ-DON-006) sustituye a la guía de despacho, así que la entrega no aparece en el listado de guías aunque su tipo de operación sea el de entregas estándar del almacén.

#### Scenario: Entrega de donación con el tipo de entrega estándar
- **Dado** una entrega de donación validada con el tipo de operación de entregas estándar de un almacén
- **Cuando** se calcula si entra en el listado de guías de despacho
- **Entonces** no entra; la misma entrega sin la marca de donación sí entra

### Requirement: REQ-DON-018 · Certificado de la recepción y Recibo de la entrega
El **Certificado de donación** es el documento de una donación RECIBIDA (lo recibe el donante) y el **Recibo de donación** el de una donación OTORGADA (lo recibe el beneficiario), en dinero (`account.move`) y en mercancía (`stock.picking`). `print_donation_certificate` imprime el certificado y `print_donation_receipt` el recibo; cada método DEBE (MUST) rechazar el documento de la otra dirección con un error que indica el que corresponde, y los botones se muestran según la dirección.

#### Scenario: Cada documento en su dirección
- **Dado** un asiento de donación recibida y uno de donación otorgada, publicados
- **Cuando** se imprime el certificado y el recibo de cada uno
- **Entonces** el certificado solo se imprime en la recibida y el recibo solo en la otorgada; el otro falla indicando el documento que corresponde

### Requirement: REQ-DON-019 · Recibo de donación estandarizado
El recibo DEBE (MUST) tener una estructura única para el dinero y la mercancía: encabezado de la compañía, número y fecha, datos del beneficiario (nombre, RIF o cédula, dirección y teléfono) (el RIF es el del contacto comercial: un contacto hijo usa el RIF y el prefijo de su empresa), monto con equivalente y tasa, concepto (en dinero, las líneas de gasto; en mercancía, la tabla de productos compartida con lote, vencimiento y costo), observaciones (referencia del asiento o motivo de donación), constancia de donación y firmas, en media hoja carta. Los elementos `donation_receipt_beneficiary_extra` y `donation_receipt_legal` DEBEN (MUST) existir para que otros módulos agreguen datos (paciente, texto legal) por herencia.

#### Scenario: Recibo de una entrega
- **Dado** una entrega de donación validada con un beneficiario y un motivo
- **Cuando** se imprime el recibo
- **Entonces** muestra al beneficiario, la tabla de productos con su total al costo y el motivo como observación

### Requirement: REQ-DON-020 · Cuentas y dirección de las donaciones recibidas
La compañía DEBE (MUST) poder configurar varias cuentas de ingresos de donaciones recibidas (`donation_income_account_ids`, también en los ajustes). Un asiento es una donación recibida (`_is_incoming_donation`, `is_incoming_donation`) si es un asiento manual (`entry`) marcado `is_donation` con alguna línea en una de esas cuentas; la dirección se decide por la cuenta y no por el diario. Una factura de donación no lo es, aunque use la misma cuenta. Sin cuentas configuradas ningún asiento es recibido y el comportamiento no cambia (la recepción de mercancía tampoco exige donante ni configuración contable, REQ-DON-024). Los ajustes solo admiten cuentas de ingresos de la compañía activa (`check_company` y dominio por compañía). Como la dirección se deduce de las cuentas, NO DEBE (MUST NOT) poder agregarse ni quitarse una cuenta que use algún asiento de donación publicado de la compañía: el documento de ese asiento cambiaría entre Certificado y Recibo.

#### Scenario: Con y sin cuentas
- **Dado** un asiento manual de donación con una línea en la cuenta de ingresos
- **Cuando** la compañía no tiene cuentas configuradas, y luego se configura esa cuenta
- **Entonces** el asiento no es una donación recibida, y después sí lo es

#### Scenario: Cambio de cuentas con asientos publicados
- **Dado** una donación recibida publicada con la cuenta de ingresos configurada
- **Cuando** se intenta quitar esa cuenta (o agregar la de una donación otorgada publicada)
- **Entonces** falla con un error que indica cuántos asientos la usan; los borradores y las cuentas sin uso no bloquean el cambio

### Requirement: REQ-DON-021 · Las líneas de una donación recibida llevan al donante
Las líneas de un asiento de donación recibida DEBEN (MUST) llevar al donante como contacto. `_check_partner_donation` (compañía en las líneas) y `_fill_donation_entry_line_partner` (relleno con la compañía al crear la línea, al marcar la donación y antes de publicar) NO DEBEN (MUST NOT) aplicarse a ellas; las donaciones otorgadas conservan el contacto de la compañía en las líneas. Cuando la cabecera y las líneas traen contactos distintos, el donante del certificado es el de la cabecera (comportamiento heredado de 17: solo se validan las líneas y `_get_donation_counterparty` toma primero la cabecera).

#### Scenario: Donante en las líneas
- **Dado** un asiento de donación recibida con el donante en sus líneas
- **Cuando** se guarda
- **Entonces** se acepta y las líneas conservan al donante; la misma entrega de líneas en una donación otorgada se rechaza

#### Scenario: Cabecera distinta del donante de las líneas
- **Dado** una donación recibida cuya cabecera es otro contacto que el de sus líneas
- **Cuando** se imprime el certificado
- **Entonces** nombra al contacto de la cabecera

### Requirement: REQ-DON-022 · Validación al publicar una donación recibida
Antes de publicar, `_check_incoming_donation_before_post` (punto de extensión) se ejecuta en `_post`, así que lo cubren `action_post`, la publicación automática y cualquier publicación directa, y DEBE (MUST) verificar que todas las líneas tengan contacto, distinto de la compañía, y que sea el mismo donante en todas. La validación corre con el asiento en borrador y NO DEBE (MUST NOT) escribir nada en él: funciona en diarios con "Bloquear asientos con hash".

#### Scenario: Líneas sin donante o con donantes distintos
- **Dado** un asiento de donación recibida con una línea sin contacto, o con la compañía, o con dos donantes
- **Cuando** se publica
- **Entonces** falla con un mensaje que indica el donante y el asiento sigue en borrador

### Requirement: REQ-DON-023 · Certificado de donación recibida en dinero
El certificado del asiento (`l10n_ve_donation.action_donation_certificate_account_move`) DEBE (MUST) declarar la recepción de "la suma de" el monto (REQ-DON-026) del donante (nombre, RIF o cédula del contacto comercial, domicilio y teléfono, `_get_donation_counterparty`: la cabecera o el contacto de las líneas), con descripción del uso y tipo de donativo en blanco, destino de la donación, fecha y firmas. Los elementos `donation_certificate_legal` (datos del representante legal de la compañía) y `donation_certificate_extra` DEBEN (MUST) existir como puntos de extensión.

#### Scenario: Certificado al donante
- **Dado** una donación recibida en dinero, publicada
- **Cuando** se imprime el certificado
- **Entonces** muestra al donante con su RIF y domicilio, la suma recibida y no menciona bienes

### Requirement: REQ-DON-024 · Recepción de donaciones de mercancía
Cuando la compañía tiene cuentas de donaciones recibidas (REQ-DON-020), una recepción de donación sin pedido (`is_donation`, entrante) DEBE (MUST) tener al donante ("Recibir de") para validarse; sin cuentas la recepción valida como antes, sin donante ni configuración contable. Con productos de valoración automatizada, `_get_donation_receipt_config_errors` (punto de extensión) DEBE (MUST) exigir, solo cuando la compañía tiene cuentas de donaciones recibidas, que el origen sea una ubicación de tipo Pérdida de inventario y que su cuenta de valoración sea una de ellas: el asiento de valoración (core 19: crédito = cuenta de la ubicación de origen cuando la tiene) queda Debe inventario / Haber ingreso por donación. Una entrega de donación NO DEBE (MUST NOT) tener como destino una ubicación cuya cuenta sea de donaciones recibidas. Un picking nuevo abierto desde la tarjeta de un tipo de donación queda marcado como donación.

#### Scenario: Recepción correcta
- **Dado** una recepción de un producto `real_time` desde "Donaciones recibidas" con la cuenta de ingresos como cuenta de valoración
- **Cuando** se valida
- **Entonces** el asiento de valoración acredita la cuenta de ingresos y debita el inventario

#### Scenario: Compañía sin cuentas de donaciones recibidas
- **Dado** una compañía sin cuentas de donaciones recibidas y una recepción de donación sin donante, desde cualquier origen
- **Cuando** se valida
- **Entonces** valida como una recepción normal, sin exigir donante ni configuración contable

#### Scenario: Configuración incoherente
- **Dado** una recepción cuyo origen no es de pérdida de inventario, no tiene cuenta, o tiene una que no es de donaciones recibidas
- **Cuando** se valida
- **Entonces** falla con un mensaje que indica qué corregir

### Requirement: REQ-DON-025 · Certificado de la recepción de mercancía
El certificado de una recepción (`l10n_ve_donation.action_donation_certificate_stock_picking`) DEBE (MUST) listar los productos con la tabla compartida (lote, vencimiento y costo desde `stock.move.value`) y el total al costo de todas sus líneas con su equivalente (`_get_donation_picking_amounts`): el total por la tasa guardada en el primer asiento de valoración publicado, o por la tasa de la fecha del documento cuando no hay asientos (sin tasa se omite el equivalente), de modo que una reimpresión da los mismos datos aunque el picking mezcle productos con y sin valoración automatizada. Bajo la tabla, que muestra el total en la moneda de la compañía, el "Equivalent value" DEBE (MUST) ser el valor en la otra moneda: el monto en bolívares cuando la compañía está en USD (como Higea) y el equivalente en USD cuando está en bolívares; el monto en bolívares nunca falta (REQ-DON-026). Las líneas se calculan una vez por documento (`_get_donation_goods_data`). El botón y `print_donation_certificate` se ofrecen solo en recepciones de donación `done` de una compañía con cuentas de donaciones recibidas (`has_donation_income_accounts`); sin cuentas la recepción es inerte y no tiene certificado.

#### Scenario: Certificado de una recepción
- **Dado** una recepción de donación validada
- **Cuando** se imprime el certificado
- **Entonces** muestra al donante, los productos con su total al costo y "los siguientes bienes"

#### Scenario: Compañía en USD con alterna en bolívares
- **Dado** una recepción de donación de una compañía en USD con alterna en bolívares
- **Cuando** se imprime el certificado
- **Entonces** bajo la tabla (en USD) se muestra el monto en bolívares como "Equivalent value" con la tasa BCV

#### Scenario: Compañía sin cuentas de donaciones recibidas
- **Dado** una recepción de donación `done` de una compañía sin cuentas de donaciones recibidas
- **Cuando** el usuario abre el picking o invoca `print_donation_certificate`
- **Entonces** no ve el botón y el método falla indicando que se deben configurar las cuentas

#### Scenario: Picking con productos de las dos valoraciones
- **Dado** una recepción con un producto de valoración automatizada (costo 10) y otro de valoración periódica (costo 5)
- **Cuando** se imprime el certificado
- **Entonces** el monto es 15 y el equivalente es 15 por la tasa del asiento de valoración

### Requirement: REQ-DON-026 · Monto y tasa de los documentos de donación
Los documentos DEBEN (MUST) mostrar el monto en bolívares primero (`_compute_donation_amounts`): la moneda de la compañía si está en bolívares, la alterna si la compañía está en otra moneda (como USD), con su equivalente en la otra moneda y la tasa BCV guardada en el asiento (bolívares por unidad de esa moneda), de modo que una reimpresión dé los mismos datos. La tasa DEBE (MUST) elegirse según cuál moneda es el bolívar: `foreign_rate` si la compañía está en bolívares y `foreign_inverse_rate` si la alterna lo es. Sin monto alterno o sin tasa se omite el equivalente.

#### Scenario: Compañía en USD con alterna en bolívares
- **Dado** una compañía en USD con alterna VEF y un monto de 84,44 USD (38.000,00 VEF)
- **Cuando** se imprime un documento
- **Entonces** el monto en bolívares va primero y la tasa es 450,0000 bolívares por USD, no su inversa

### Requirement: REQ-DON-027 · Beneficiario de una donación otorgada en dinero
En un asiento manual de donación otorgada (`is_donation`, `entry`, no recibida) el formulario DEBE (MUST) mostrar el contacto de la cabecera como "Beneficiary" (editable en borrador; no se muestra en las recibidas, donde el donante va en las líneas). Las líneas siguen con la compañía: las que copian el contacto de la cabecera al crearse (o al marcar la donación) se reemplazan por la compañía, y un contacto distinto en una línea sigue rechazándose (`_check_partner_donation`). El Recibo de donación DEBE (MUST) mostrar al beneficiario (nombre, RIF o cédula y dirección).

#### Scenario: Donación otorgada con beneficiario
- **Dado** un asiento manual de donación otorgada con un contacto en la cabecera y sin contacto en las líneas
- **Cuando** se guarda y se publica
- **Entonces** se acepta, la cabecera conserva al beneficiario, las líneas quedan con la compañía y el Recibo muestra al beneficiario

#### Scenario: Marcar la donación después
- **Dado** un asiento manual con un contacto en la cabecera y sin la marca de donación (sus líneas copiaron el contacto comercial de la cabecera)
- **Cuando** se marca "Es Donación"
- **Entonces** se acepta y las líneas quedan con la compañía; el reemplazo corre antes de escribir la marca porque la restricción corre dentro de la escritura

### Requirement: REQ-DON-028 · Guardas de impresión de los documentos
Los métodos `print_donation_receipt` y `print_donation_certificate` DEBEN (MUST) revisar el documento antes de imprimir, sin depender de la visibilidad de los botones: en `account.move`, que sea un asiento manual (`entry`) de donación publicado, el recibo de una otorgada y que no sea el asiento de valoración de una entrega, el certificado de una recibida; en `stock.picking`, que sea una donación sin pedido y `done`, el recibo de una entrega (saliente) y el certificado de una recepción (entrante). Cada negación DEBE (MUST) fallar con un error que indica el documento que corresponde. El asiento de reversión de otro (`reversed_entry_id` lleno) NO DEBE (MUST NOT) tener documento: copia la marca y las cuentas del original, pero los documentos pertenecen al original.

#### Scenario: Documentos que no son donación
- **Dado** una factura, un asiento normal, un asiento de donación en borrador y un picking de donación sin hacer
- **Cuando** se invoca el método de impresión
- **Entonces** falla con un error sin generar el documento

#### Scenario: Reversión de una donación
- **Dado** el asiento de reversión de una donación publicada (copia la marca y las cuentas del original)
- **Cuando** se invoca el método de impresión o se abre el formulario
- **Entonces** el método falla indicando que el documento es el del asiento original y los botones no se ofrecen; el original conserva su Recibo o Certificado
