# Spec delta: pos-negative-qty-guard

## ADDED Requirements

### Requirement: El PdV rechaza cantidades negativas en líneas que no son de reembolso

El sistema SHALL impedir que una línea de una orden del PdV quede con
cantidad negativa cuando esa línea no pertenezca a un flujo de reembolso o
devolución. El bloqueo SHALL aplicarse en `PosOrderline.setQuantity`, punto
por el que pasan todos los caminos de edición de cantidad del PdV (numpad,
`QuantityButtons`, código de barras con peso, `setQuantityByLot` y la
propagación a líneas hijas de combo).

Cuando la cantidad solicitada sea negativa y la línea no esté exenta, el
sistema SHALL devolver un objeto `{title, body}` en vez de aplicar el
cambio, de forma que `OrderSummary._setValue` lo muestre como `AlertDialog`
y resetee el `number_buffer` (mismo contrato que usa el core para
"Positive quantity not allowed"). El sistema SHALL NOT modificar la
cantidad de la línea en ese caso.

#### Scenario: Tecla +/- del numpad sobre una línea de venta normal

- **GIVEN** una orden de venta con una línea de 2 unidades de un producto,
  sin `refunded_orderline_id` y con un preset que no es de devolución
- **WHEN** el cajero selecciona la línea y pulsa la tecla `+/-` del numpad
- **THEN** aparece un diálogo indicando que solo las líneas de reembolso
  pueden tener cantidad negativa
- **AND** la línea conserva su cantidad de 2 unidades
- **AND** el `number_buffer` queda reseteado

#### Scenario: Tecleo directo de una cantidad negativa

- **GIVEN** una orden de venta con una línea seleccionada y el numpad en
  modo `quantity`
- **WHEN** el cajero teclea `-3`
- **THEN** aparece el mismo diálogo y la cantidad de la línea no cambia

#### Scenario: Bajar la cantidad hasta cero sigue permitido

- **GIVEN** una orden de venta con una línea de 1 unidad
- **WHEN** el cajero fija la cantidad a `0`
- **THEN** la cantidad se aplica normalmente sin diálogo de error, porque
  cero no es negativo

### Requirement: Las líneas de reembolso conservan su cantidad negativa

El sistema SHALL permitir cantidad negativa cuando la línea tenga
`refunded_orderline_id` (línea de reembolso creada por
`TicketScreen.onDoRefund`) o cuando la orden use un preset de devolución
(`order_id.preset_id.is_return`, modo "Return" nativo, donde el core fuerza
`-Math.abs(qty)` en todas las líneas del carrito).

El guard SHALL NOT interferir con la creación de líneas de reembolso, que
el core hace directamente vía
`models["pos.order.line"].create({qty: -refundDetail.qty, ...})` sin pasar
por `setQuantity`.

#### Scenario: Reembolso desde la pantalla de órdenes

- **GIVEN** una orden sincronizada con 3 unidades de un producto
- **WHEN** el cajero la selecciona en el `TicketScreen`, marca 3 unidades a
  reembolsar y pulsa "Refund"
- **THEN** se crea la orden de reembolso con una línea de −3 unidades sin
  ningún diálogo de bloqueo

#### Scenario: Ajustar a la baja la cantidad de una línea de reembolso

- **GIVEN** una orden de reembolso con una línea de −3 unidades vinculada a
  su línea original
- **WHEN** el cajero selecciona la línea y fija la cantidad a `-2`
- **THEN** la cantidad se aplica normalmente y siguen vigentes las
  validaciones nativas de reembolso (cantidad positiva no permitida,
  cantidad mayor a la reembolsable)

#### Scenario: Orden con preset de devolución

- **GIVEN** una configuración de PdV con `use_presets` y un preset con
  `is_return = True`
- **WHEN** el cajero selecciona ese preset y agrega productos al carrito
- **THEN** las líneas quedan en negativo como hace el core, sin diálogo de
  bloqueo

### Requirement: El servidor rechaza líneas negativas fuera de reembolso

El sistema SHALL validar en `pos.order.line` mediante
`@api.constrains("qty", "refunded_orderline_id", "order_id")` que ninguna
línea con cantidad negativa se cree o modifique fuera de un flujo de
reembolso, levantando `ValidationError` en caso contrario. La comparación
con cero SHALL usar `float_compare` a la precisión decimal
`Product Unit` para no disparar por ruido de redondeo.

Las exenciones SHALL ser: `refunded_orderline_id` presente,
`order_id.is_refund` verdadero, u `order_id.preset_id.is_return` verdadero.

El mensaje de error SHALL identificar el producto y la orden afectados, y
SHALL estar escrito en inglés dentro de `_()` con traducción al español en
`i18n/es_VE.po`, siguiendo la convención del proyecto.

#### Scenario: Escritura por RPC de una cantidad negativa en una orden de venta

- **GIVEN** una línea de una orden de venta del PdV sin
  `refunded_orderline_id`, en una orden con `is_refund = False` y sin
  preset de devolución
- **WHEN** se escribe `qty = -1` sobre esa línea (por RPC, por el sync del
  PdV o desde el backend)
- **THEN** la operación falla con `ValidationError` indicando el producto y
  la orden

#### Scenario: Sync de una orden de reembolso

- **GIVEN** una orden de reembolso creada en el PdV, con `is_refund = True`
  y líneas negativas vinculadas a sus líneas originales
- **WHEN** la orden se sincroniza con el servidor
- **THEN** la constraint no se dispara y la orden se guarda normalmente

#### Scenario: Órdenes negativas históricas ya existentes

- **GIVEN** una base de datos con órdenes de venta antiguas que tienen
  líneas de cantidad negativa
- **WHEN** se actualiza el módulo `l10n_ve_pos`
- **THEN** la actualización no falla, porque `@api.constrains` solo se
  evalúa al crear o escribir los campos vigilados
