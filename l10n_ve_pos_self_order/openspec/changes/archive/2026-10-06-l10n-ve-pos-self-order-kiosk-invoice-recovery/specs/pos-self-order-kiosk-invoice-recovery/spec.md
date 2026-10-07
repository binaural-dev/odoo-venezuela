# Spec delta: pos-self-order-kiosk-invoice-recovery

## ADDED Requirements

### Requirement: La orden del Kiosko se crea aunque la facturación sea rechazada

El sistema SHALL crear y dejar pagada la `pos.order` del Kiosko cuando el pago se
aprueba, con independencia de que la creación de la factura (`account.move`)
falle. La facturación SHALL ejecutarse aislada en un `savepoint`; si lanza, se
captura y la orden queda en estado **pendiente de facturar** (`state='paid'`,
`to_invoice=True`, `account_move` vacío), conservando su línea de pago. La
resiliencia SHALL aplicarse en el seam de facturación del Kiosko (gateada a
`self_ordering_mode == 'kiosk'`), de modo que sea independiente del método de
pago. Un pago aprobado NUNCA debe perderse por un fallo de facturación.

#### Scenario: La facturación es rechazada tras aprobar el pago

- **GIVEN** una caja en modo Kiosko, un pago aprobado, y una condición que hace
  fallar la creación de la factura (p. ej. secuencia SENIAT o impuesto mal
  configurado)
- **WHEN** el cliente finaliza y el servidor registra la orden
- **THEN** la `pos.order` queda creada y pagada con su `pos.payment`, en estado
  `paid` con `to_invoice=True` y sin `account_move`, se emite el resultado de pago
  exitoso, y el cliente ve la pantalla de confirmación

#### Scenario: La facturación es exitosa (camino feliz)

- **GIVEN** una caja en modo Kiosko con el pago aprobado y la configuración fiscal
  correcta
- **WHEN** el servidor registra la orden
- **THEN** la orden queda facturada (`account_move` creado) exactamente igual que
  antes de este cambio, sin diferencias observables en el camino feliz

#### Scenario: El fallo de factura no arrastra el pago ni el picking

- **GIVEN** una orden del Kiosko cuya facturación falla dentro del `savepoint`
- **WHEN** el `savepoint` revierte la facturación
- **THEN** la línea de pago, el estado `paid` y el picking/costo de la orden
  permanecen (solo se revierte el `account.move`), y el request se commitea con la
  orden pendiente de facturar

### Requirement: La verificación de pago Megasoft se persiste como prueba durable

El sistema SHALL persistir en la `pos.payment` la respuesta del VPOS de Megasoft
que aprobó el cobro (JSON crudo y un subconjunto para mostrar: número de
autorización, referencia, lote, tarjeta enmascarada, tipo de tarjeta,
banco/autorizador y código de respuesta), y SHALL exponer esos datos al cliente
del Kiosko para el panel de recuperación.

#### Scenario: El pago aprobado guarda su verificación

- **GIVEN** un pago Megasoft del Kiosko aprobado por el VPOS con su JSON de
  respuesta
- **WHEN** el servidor registra el pago
- **THEN** la `pos.payment` guarda el JSON crudo y los campos extraídos
  (autorización, referencia, lote, tarjeta, banco, código de respuesta)

#### Scenario: El panel puede mostrar el método verificado

- **GIVEN** una orden del Kiosko con un pago Megasoft persistido
- **WHEN** el cliente del Kiosko carga la orden en el panel de recuperación
- **THEN** los campos Megasoft del pago llegan al cliente (vía
  `_load_pos_self_data_fields`) y el panel muestra el método y sus datos de
  verificación

### Requirement: No se imprime la factura fiscal si la contable está pendiente

El sistema SHALL abstenerse de auto-imprimir la factura fiscal en la confirmación
(`confirmationPage`) cuando la orden aún no tiene `account_move` (factura contable
pendiente). Esas órdenes quedan **pendientes por facturar en la máquina fiscal** y
se imprimen desde el panel de recuperación una vez creada la factura contable.

#### Scenario: Orden pagada sin factura contable llega a la confirmación

- **GIVEN** una orden del Kiosko `state='paid'` sin `account_move` (facturación
  pendiente) y la máquina fiscal conectada
- **WHEN** el cliente llega a `confirmationPage`
- **THEN** NO se dispara la impresión fiscal automática; la orden queda pendiente
  de fiscal y disponible en el panel de recuperación

#### Scenario: Orden facturada sigue imprimiéndose en la confirmación

- **GIVEN** una orden del Kiosko facturada (`account_move` presente) sin
  `mf_invoice_number`
- **WHEN** el cliente llega a `confirmationPage`
- **THEN** la impresión fiscal automática ocurre como hasta ahora (comportamiento
  de `pos-self-order-kiosk-fiscal-print` sin cambios para el caso facturado)

### Requirement: Facturación diferida idempotente por endpoint público

El sistema SHALL ofrecer un endpoint público del Kiosko para crear la factura de
una orden pendiente, que valide el `access_token` y que la orden pertenezca a la
caja, y que sea idempotente (si la orden ya tiene `account_move`, no crea una
segunda). Devuelve el resultado para que el panel refresque el estado.

#### Scenario: Crear la factura de una orden pendiente

- **GIVEN** una orden del Kiosko pendiente de facturar (paid, sin `account_move`),
  con la causa del rechazo ya corregida
- **WHEN** se invoca el endpoint de facturación con el `access_token` de la caja y
  el id de la orden
- **THEN** el servidor crea el `account.move`, la orden pasa a facturada, y se
  devuelve `{success: true, invoice_id}`

#### Scenario: Reintento sobre una orden ya facturada

- **GIVEN** una orden del Kiosko que ya tiene `account_move`
- **WHEN** se invoca de nuevo el endpoint de facturación
- **THEN** no se crea una segunda factura y se devuelve el estado actual

#### Scenario: El endpoint rechaza una orden ajena a la caja

- **GIVEN** un `access_token` de una caja y un `order_id` de otra caja
- **WHEN** se invoca el endpoint de facturación
- **THEN** no se factura nada y se devuelve un error de pertenencia

### Requirement: Recuperación de órdenes pendientes desde el panel del Kiosko

El sistema SHALL extender el panel de órdenes fiscales del Kiosko para distinguir
tres estados por orden —pendiente de factura contable, pendiente de fiscal, y
completa— mostrar el pago verificado, y ofrecer la acción adecuada a cada estado
(crear factura → imprimir fiscal → reimprimir copia).

#### Scenario: Orden pendiente de factura contable

- **GIVEN** una orden del Kiosko `paid` sin `account_move`
- **WHEN** el operador la selecciona en el panel
- **THEN** el panel la marca "pendiente factura backend", muestra el pago
  verificado, y ofrece "Crear factura"; tras crearla, ofrece "Imprimir factura
  fiscal"

#### Scenario: Orden facturada pendiente de fiscal

- **GIVEN** una orden del Kiosko con `account_move` pero sin `mf_invoice_number`
- **WHEN** el operador la selecciona
- **THEN** el panel la marca "pendiente fiscal" y ofrece "Imprimir factura fiscal"

#### Scenario: Orden completa

- **GIVEN** una orden del Kiosko con `mf_invoice_number`
- **WHEN** el operador la selecciona
- **THEN** el panel la marca "completa" y ofrece "Reimprimir copia"

### Requirement: El panel de recuperación se abre desde el menú de Debug MF

El sistema SHALL exponer el panel de órdenes fiscales del Kiosko —con las
acciones de recuperación (crear factura / imprimir / reimprimir) y el pago
verificado— desde el menú de Debug MF, disponible en modo debug (`?debug=1`). NO
se muestra un punto de entrada de cara al cliente fuera de modo debug: la
recuperación es una tarea de operador/soporte.

#### Scenario: Abrir el panel de recuperación en modo debug

- **GIVEN** un Kiosko abierto con `?debug=1`
- **WHEN** el operador abre el menú Debug MF y elige "Órdenes fiscales"
- **THEN** se abre el panel con las órdenes de la caja, su estado (pendiente
  factura / pendiente fiscal / completa) y las acciones de recuperación

#### Scenario: Sin modo debug no hay punto de entrada en el Kiosko

- **GIVEN** un Kiosko abierto sin `?debug=1`
- **WHEN** el cliente usa el Kiosko normalmente
- **THEN** no se muestra ningún botón de recuperación; las órdenes pendientes de
  facturar se resuelven desde el menú de backend (o desde el panel en modo debug)

### Requirement: Menú de backend para las órdenes de Kiosko pendientes de facturar

El sistema SHALL ofrecer en el backend de Odoo una acción de menú que liste las
órdenes de Kiosko pendientes de facturar (modo kiosko, `paid`, `to_invoice=True`,
sin `account_move`) y permita crear su factura con el mismo código idempotente que
el endpoint del Kiosko.

#### Scenario: Contabilidad ve y resuelve las pendientes

- **GIVEN** órdenes de Kiosko pendientes de facturar y un usuario de contabilidad
- **WHEN** abre el menú de órdenes pendientes de facturar
- **THEN** las ve listadas con su pago verificado y puede crear la factura de cada
  una (sin duplicar si ya tuviera `account_move`)
