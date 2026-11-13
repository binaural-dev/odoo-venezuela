## ADDED Requirements

### Requirement: Un solo esquema de descuento por documento
El sistema DEBE (MUST) permitir un único esquema de descuento por pedido de venta o factura de cliente (porcentaje en líneas, importe en líneas, global sobre Subtotal o global sobre Total) y rechazar cualquier descuento por línea de otro tipo mientras haya un esquema aplicado.

#### Scenario: Descuento global aplicado y descuento manual en una línea
- **WHEN** el documento tiene un descuento global y se intenta escribir un descuento en una línea
- **THEN** el sistema rechaza la operación con un `UserError` indicando que debe quitar el descuento global

#### Scenario: El esquema viaja del pedido a la factura
- **WHEN** se factura un pedido con un esquema aplicado
- **THEN** la factura conserva el esquema, sus valores y los descuentos de línea sin que la guarda los trate como un cambio manual

### Requirement: Descuento global siempre con cuenta definida y sin línea negativa
El sistema DEBE (MUST) exigir la cuenta de descuento global de la compañía para aplicar un descuento global y NO DEBE (MUST NOT) crear líneas de producto con precio negativo.

#### Scenario: Global sobre Total
- **WHEN** se aplica un descuento global sobre el Total
- **THEN** el IVA no cambia, el total se reduce, `tax_totals` muestra el descuento y un único apunte de débito en la cuenta global reduce la cuenta por cobrar

#### Scenario: Sin cuenta configurada
- **WHEN** se aplica un descuento global y la compañía no tiene cuenta de descuento global
- **THEN** el asistente rechaza la operación con un `UserError`

### Requirement: Límite de método de descuento
Cuando la compañía activa "Limitar método de descuento", el sistema DEBE (MUST) rechazar, para cualquier usuario sin excepción, un descuento con un método que no esté marcado como permitido, tanto desde la ventana Descuento como al escribirlo a mano en una línea.

#### Scenario: Método sin marcar
- **WHEN** el método "líneas en importe fijo" no está marcado y cualquier usuario (incluido un aprobador) intenta aplicarlo
- **THEN** el sistema rechaza la operación con un `UserError`

#### Scenario: Límite de método desactivado
- **WHEN** "Limitar método de descuento" está desactivado
- **THEN** todos los métodos se pueden aplicar

### Requirement: Descuento máximo y aprobación del excedente, independientes del límite de método
Cuando la compañía activa "Limitar el descuento máximo", el sistema DEBE (MUST) comparar el descuento con el máximo de su esquema, con o sin límite de método; si lo excede, enviar el documento a "Descuento por aprobar" si la aprobación está activa, o rechazarlo con un error si no lo está, salvo que el usuario sea aprobador.

#### Scenario: Excedente con aprobación
- **WHEN** un usuario no aprobador aplica un descuento mayor al máximo y la aprobación está activa
- **THEN** el documento queda en `to_approve` y no se puede confirmar ni publicar

#### Scenario: Excedente sin aprobación
- **WHEN** un usuario aplica un descuento mayor al máximo y la aprobación está desactivada
- **THEN** el sistema rechaza el descuento con un `UserError`

#### Scenario: Aprobador
- **WHEN** un aprobador aplica un descuento mayor al máximo
- **THEN** el documento no entra en `to_approve`

#### Scenario: Máximo con el límite de método desactivado
- **WHEN** "Limitar método de descuento" está desactivado y "Limitar el descuento máximo" está activo
- **THEN** el máximo se aplica igual

### Requirement: Los campos del esquema y la aprobación no se pueden escribir directamente
El sistema NO DEBE (MUST NOT) permitir que un usuario cambie `discount_mode`, los campos `global_discount_*` o `discount_approval_state` por escritura directa ni saltarse la evaluación enviando claves de contexto; solo el botón Descuento y las acciones aprobar y rechazar los modifican.

#### Scenario: Escritura directa del estado de aprobación
- **WHEN** un usuario sin permiso de aprobador escribe `discount_approval_state = 'approved'`
- **THEN** el sistema rechaza la operación con un `AccessError`

#### Scenario: Clave de contexto enviada por el cliente
- **WHEN** un cliente escribe un descuento de línea con la clave de contexto `l10n_ve_discount_apply`
- **THEN** la clave se ignora y el descuento se evalúa contra el límite

### Requirement: Descuento y deducible se excluyen mutuamente
El sistema DEBE (MUST) rechazar cualquier descuento en un documento deducible y rechazar activar el deducible en un documento con descuento por línea o global.

#### Scenario: Descuento sobre un documento deducible
- **WHEN** se intenta aplicar cualquier esquema de descuento a una factura deducible
- **THEN** el sistema rechaza la operación con un `UserError`

#### Scenario: Deducible sobre un documento con descuento global
- **WHEN** se activa el deducible en una factura con descuento global
- **THEN** el sistema rechaza la operación con un `ValidationError`

### Requirement: El excedente pasa a una etapa de aprobación al confirmar
Con la aprobación activa, aplicar un descuento mayor al máximo DEBE (MUST) solo aplicarlo y avisar en el documento; al confirmar el pedido o publicar la factura, el documento DEBE (MUST) pasar a "Descuento por aprobar" y quedar bloqueado hasta que un aprobador lo apruebe (continúa el flujo natural de Odoo) o lo rechace (se quita el descuento).

#### Scenario: Aplicar el excedente
- **WHEN** un usuario no aprobador aplica un descuento mayor al máximo con la aprobación activa
- **THEN** el descuento se aplica, el documento queda en `exceeds` y se muestra un aviso de que al confirmar pasará a aprobación

#### Scenario: Confirmar el pedido con excedente
- **WHEN** el usuario confirma el pedido en `exceeds`
- **THEN** el pedido pasa a la etapa "Descuento por aprobar", desaparece Confirmar y aparecen Aprobar y Rechazar descuento

#### Scenario: Aprobar
- **WHEN** un aprobador aprueba el descuento
- **THEN** el pedido continúa a "Orden de venta" (la factura se publica)

#### Scenario: Volver a cotización
- **WHEN** el pedido vuelve a cotización o se cancela
- **THEN** la aprobación se reinicia y al confirmar de nuevo se vuelve a evaluar

### Requirement: Etapa de aprobación bloqueada y notificada
En la etapa "Descuento por aprobar" el pedido NO DEBE (MUST NOT) poder editarse (campos, líneas, botón Descuento), ni por la interfaz ni por RPC. El sistema DEBE (MUST) rechazar entrar en la etapa si no hay aprobadores asignados, notificar a todos los aprobadores al entrar y notificar al dueño del documento al aprobar o rechazar.

#### Scenario: Sin aprobadores
- **WHEN** se confirma un pedido en `exceeds` y ningún usuario tiene el permiso de aprobar
- **THEN** el sistema muestra un `UserError` y el pedido no entra en la etapa

#### Scenario: Edición en la etapa
- **WHEN** se intenta escribir en el pedido o sus líneas durante la etapa
- **THEN** el sistema rechaza la operación con un `UserError`

#### Scenario: Notificaciones
- **WHEN** el pedido entra en la etapa
- **THEN** cada aprobador recibe un mensaje, una actividad y un aviso; al aprobar o rechazar, el dueño recibe una notificación

### Requirement: Alternos de los apuntes de descuento
Los apuntes contables de descuento (`display_type='discount'`) DEBEN (MUST) llevar su débito y crédito en moneda alterna, calculados como `l10n_ve_accountant` calcula los de las líneas del producto, y cuadrar en ambas monedas.

#### Scenario: Global sobre Subtotal
- **WHEN** se factura con un descuento global sobre el Subtotal
- **THEN** los apuntes de descuento muestran el importe alterno (precio alterno bruto menos subtotal alterno) en débito y crédito

#### Scenario: Global sobre Total
- **WHEN** se factura con un descuento global sobre el Total
- **THEN** el apunte de débito del descuento lleva el descuento por la proporción del total alterno

### Requirement: Totales consistentes en widget y PDF
El widget de totales, el de moneda alterna, el de bolívares y el PDF de la factura DEBEN (MUST) llamar siempre "Subtotal" al subtotal y mostrar el descuento global en positivo: antes del subtotal si es global sobre Subtotal, después de impuestos si es global sobre Total.

#### Scenario: Global sobre Total
- **WHEN** la factura tiene un descuento global sobre el Total
- **THEN** "Descuento global" aparece después de los impuestos y antes del Total, en positivo

### Requirement: Botón Descuento solo si algún método está permitido
El botón Descuento NO DEBE (MUST NOT) mostrarse en pedido ni factura cuando la compañía limita el método y no deja ninguno marcado.

#### Scenario: Ningún método permitido
- **WHEN** "Limitar método de descuento" está activo y ningún método está marcado
- **THEN** el botón Descuento no aparece

### Requirement: La factura sigue el mismo flujo de aprobación que el pedido
La factura de cliente DEBE (MUST) seguir el flujo del pedido: aplicar el excedente solo lo marca; al publicar pasa a "Descuento por aprobar", queda bloqueada (campos, líneas, botón Descuento y Publicar), se notifica a los aprobadores y un aprobador la aprueba (se publica) o la rechaza (se quita el descuento). Cancelar la factura o volverla a borrador reinicia la aprobación. Una factura que viene de pedidos confirmados NO DEBE (MUST NOT) pedir aprobación otra vez si su descuento es el del pedido (mismo esquema y porcentaje no mayor); si el descuento se quitó y se aplicó otro mayor o de otro esquema, DEBE (MUST) pedirse de nuevo.

#### Scenario: Factura de un pedido aprobado
- **WHEN** se publica la factura de un pedido que se confirmó por aprobación, sin cambiar el descuento
- **THEN** la factura se publica sin pedir aprobación

#### Scenario: Descuento distinto al del pedido
- **WHEN** en la factura se quita el descuento y se aplica uno mayor al del pedido (o de otro esquema) sobre el máximo
- **THEN** la factura queda en `exceeds` y al publicar pasa a "Descuento por aprobar"

#### Scenario: Factura en la etapa
- **WHEN** se intenta editar la factura o sus líneas durante la etapa
- **THEN** el sistema rechaza la operación con un `UserError`

### Requirement: Ajustes de descuento en el bloque Descuentos
Los ajustes "Tipo de descuento en líneas" (pedidos y facturas) y "Mostrar descuento en facturas" DEBEN (MUST) mostrarse en el bloque Descuentos de los ajustes, y la columna de descuento de las líneas de la factura DEBE (MUST) respetar "Mostrar descuento en facturas".

#### Scenario: Mostrar descuento en facturas apagado
- **WHEN** "Mostrar descuento en facturas" está apagado
- **THEN** las líneas de la factura no muestran la columna de descuento
