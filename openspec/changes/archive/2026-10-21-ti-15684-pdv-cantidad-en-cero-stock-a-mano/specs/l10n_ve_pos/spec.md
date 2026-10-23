## ADDED Requirements

### Requirement: "Cantidad en 0" bloquea el pago sin stock a mano

Con `amount_to_zero` activo en la caja, al pulsar "Pago" (o al validar con el pago rápido) el PdV DEBE (MUST) comparar la cantidad
pedida por producto almacenable (suma de líneas positivas) contra el stock a mano de la ubicación
origen de la caja y, si alguna la supera, mostrar "Stock insuficiente" con el detalle y no pasar
a la pantalla de pago. Lo reservado por otras órdenes no reduce el stock a comparar.

#### Scenario: Stock a mano suficiente aunque esté reservado por otra orden

- **WHEN** hay 8 a mano, otra orden confirmada reservó 7 y la orden del PdV lleva 7
- **THEN** el PdV pasa a la pantalla de pago

#### Scenario: Stock a mano insuficiente

- **WHEN** hay 1 a mano y la orden del PdV lleva 7
- **THEN** se muestra "Stock insuficiente" con "pedido 7, a mano 1" y no se abre la pantalla de pago ni se imprime en la MF

#### Scenario: Check apagado o producto no almacenable

- **WHEN** la caja no tiene `amount_to_zero`, o el producto es servicio/consumible no almacenable
- **THEN** no se valida stock

#### Scenario: Pago rápido

- **WHEN** la caja usa el pago rápido y la orden lleva más de lo que hay a mano
- **THEN** se muestra "Stock insuficiente" y la orden no se valida ni se imprime en la MF

#### Scenario: Producto que ya no existe

- **WHEN** la orden trae el id de un producto borrado después de que la caja lo cargó
- **THEN** ese producto se omite y el resto de la orden se valida normalmente

## MODIFIED Requirements

### Requirement: Endpoints de validación de stock del PdV

El controlador DEBE (MUST) exponer las rutas JSON `/validate_products_order` y `/validate_products_in_warehouse` (ambas `auth="public"`):

- `/validate_products_order` recorre los ids recibidos y devuelve `msg_error` con el nombre del producto en cuanto una PLANTILLA (`product_tmpl_id`) con `is_storable` y `type == "consu"` tiene `qty_available` GLOBAL (sin acotar por almacén) menor a la cantidad pedida. Si se llama sin `lines` o sin `qty` no devuelve nada (`None`).
- `/validate_products_in_warehouse` suma la `available_quantity` de los quants `on_hand` de la plantilla que pertenecen al almacén del `picking_type_id` recibido y distingue DOS fallos con tratamiento distinto:
  - Stock insuficiente en ese almacén (el producto sí está en él): devuelve `msg_error` de inmediato, SIN importar el valor de `sell_kit_from_another_store`.
  - Producto sin quants o sin presencia en el almacén de la caja: se acumula en una lista y solo se convierte en `msg_error` al final `if not sell_kit_from_another_store`.

Es decir, `sell_kit_from_another_store` exime únicamente los productos ausentes del almacén de la caja; nunca el stock insuficiente.

En O19 ningún JS del PdV llama estas rutas (son código heredado de O17). El bloqueo por stock antes del pago con "Cantidad en 0" lo hace `pos.config.check_stock_availability` (ver el requirement «"Cantidad en 0" bloquea el pago sin stock a mano»), con otra semántica: stock a mano de la ubicación origen de la caja, sin kits de otra tienda.

#### Scenario: Stock insuficiente en el almacén de la caja

- **WHEN** se llama `/validate_products_in_warehouse` con una cantidad mayor a la disponible en el almacén del picking type, con `sell_kit_from_another_store` verdadero
- **THEN** la respuesta incluye igualmente un `msg_error` indicando el producto y el almacén

#### Scenario: Producto ausente del almacén de la caja con la venta cruzada habilitada

- **WHEN** el producto no tiene quants en el almacén del picking type y se pasa `sell_kit_from_another_store` verdadero
- **THEN** la respuesta vuelve con `msg_error` en `False` y la venta se permite
