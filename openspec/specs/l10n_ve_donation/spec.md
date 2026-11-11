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

### Requirement: Certificado de donación en PDF

El sistema DEBE (MUST) permitir generar el reporte qweb-pdf "Donation Certificate" (`l10n_ve_donation.action_donation_certificate_account_move`) desde el botón `print_donation_certificate` de `account.move`, disponible únicamente en asientos manuales (`move_type = entry`) publicados y marcados `is_donation`, que no sean el asiento de valoración de una entrega por picking (REQ-DON-016).

#### Scenario: Impresión del certificado

- **WHEN** un usuario pulsa "Generar Certificado de Donación" en un asiento de donación publicado
- **THEN** se genera el PDF del certificado de donación de ese asiento

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
