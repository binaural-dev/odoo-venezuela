## ADDED Requirements

### Requirement: Una sola línea por ubicación en Otras Ubicaciones del Producto

`stock.picking.alter.location.line` DEBE (MUST) tener la restricción SQL `UNIQUE(stock_alter_location_id, location_id)`, de modo que un registro de Ubicaciones Físicas (`stock.picking.alter.location`) no pueda tener dos líneas con la misma ubicación, venga de donde venga la escritura (formulario, importación o código). Los métodos que suman o restan cantidades por ubicación (`action_move_to_output`, `action_receive_quantity`, `action_deliver_from_output`, `action_internal_transfer`, `subtract_physical_quantity`, el wizard `move.alter.location.qtities.wizard`, `product.template._sync_relocation_ledger`) dependen de esta garantía para operar sobre un único registro.

#### Scenario: Agregar una ubicación que ya está en el registro

- **WHEN** se crea una línea en un registro de Ubicaciones Físicas con una ubicación que ese registro ya tiene
- **THEN** la base de datos rechaza la línea con el mensaje de la restricción y no se guarda ningún duplicado

#### Scenario: La misma ubicación en registros distintos

- **WHEN** dos registros de Ubicaciones Físicas (productos o almacenes distintos) tienen una línea con la misma ubicación
- **THEN** ambas líneas se guardan sin error

#### Scenario: Validar una transferencia hacia Salida

- **WHEN** se valida un movimiento de un producto con registro de Ubicaciones Físicas cuyo destino es la ubicación de Salida del almacén
- **THEN** la línea de Salida suma la cantidad y la línea de la ubicación física la resta, sin `Expected singleton`

### Requirement: Líneas iniciales agrupadas por ubicación

`product.template._get_quants_for_alter_lines` DEBE (MUST) devolver como máximo una línea por ubicación, con la suma de `available_quantity` de los quants del producto en esa ubicación que tengan cantidad disponible positiva (los quants en cero o negativos se ignoran, como antes), redondeada con el redondeo de la unidad de medida del producto.

#### Scenario: Varios quants en la misma ubicación

- **WHEN** el producto tiene dos o más quants en la misma ubicación interna del almacén (por lote, paquete o propietario) al crearse su registro de Ubicaciones Físicas
- **THEN** el registro nace con una sola línea para esa ubicación, cuya cantidad es la suma de las cantidades disponibles de esos quants

### Requirement: Fusión de líneas duplicadas existentes al actualizar

Al actualizar `l10n_ve_stock` a 19.0.1.0.13, la migración `pre-migrate` DEBE (MUST) fusionar, antes de que se cree la restricción de unicidad, cada grupo de líneas con el mismo `(stock_alter_location_id, location_id)`: conserva la línea de menor `id`, le asigna la suma de `available_qty` del grupo y elimina las demás. La fusión NO DEBE (MUST NOT) cambiar `pick_quantity`, `total_alter_quantity` ni `total_quantity` del registro, que ya se calculaban sumando las líneas. Las líneas sin `stock_alter_location_id` o sin `location_id` no se tocan. Los identificadores externos (`ir_model_data`) de las líneas eliminadas se borran con ellas. Si la tabla `stock_picking_alter_location_line` no existe, la migración no hace nada. El `post-migrate` DEBE (MUST) dejar en el chatter de cada registro fusionado una nota, en el idioma del administrador, con la ubicación, las cantidades originales y la suma.

#### Scenario: Registro con la ubicación física repetida

- **WHEN** un registro tiene dos líneas para su ubicación física con 4 y 6 unidades y se actualiza el módulo
- **THEN** queda una sola línea para esa ubicación con 10 unidades, la cantidad en ubicación física del registro sigue siendo 10 y el chatter del registro tiene una nota con las cantidades 4 y 6 y la suma 10

#### Scenario: Base con l10n_ve_stock anterior a 19.0.1.0.6

- **WHEN** se actualiza una base donde la tabla de líneas todavía no existe
- **THEN** la migración termina sin error y el ORM crea la tabla con la restricción

#### Scenario: Base sin duplicados

- **WHEN** ninguna línea está repetida y se actualiza el módulo
- **THEN** la migración no modifica ninguna línea
