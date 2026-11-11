## MODIFIED Requirements

### Requirement: Visibilidad y orden de productos según disponibilidad

Con el flag de compañía `pos_show_just_products_with_available_qty` activo, el sistema DEBE (MUST) ordenar el `product.product` cargado al PdV por `qty_available` descendente, y la cuadrícula del PdV, también al buscar, NO DEBE (MUST NOT) mostrar los almacenables sin ninguna variante con `qty_available` positiva (`ProductTemplate.canBeDisplayed`). Lo no almacenable se muestra siempre. `qty_available` se calcula en la ubicación de origen de la caja y sus hijas, la que valida "Cantidad en 0".

#### Scenario: Flag activo

- **WHEN** la compañía activa el flag y se abre la caja
- **THEN** los productos llegan ordenados por disponibilidad descendente, computada contra la ubicación de origen de la caja

#### Scenario: Flag activo y almacenable sin stock en la ubicación de origen de la caja

- **WHEN** la compañía activa el flag y un producto almacenable disponible en el PdV tiene stock a mano 0 o negativo en la ubicación de origen de la caja
- **THEN** el producto no aparece en la cuadrícula ni en la búsqueda del PdV

#### Scenario: Stock solo en otro almacén

- **WHEN** el flag está activo y el producto tiene stock en otro almacén de la compañía pero no en el de la caja
- **THEN** el PdV recibe `qty_available` 0 para ese producto y no lo muestra

#### Scenario: Stock en otra ubicación del almacén de la caja

- **WHEN** el flag está activo y el producto tiene stock en una ubicación del almacén de la caja que no es la de origen ni hija de ella
- **THEN** el PdV recibe `qty_available` 0 para ese producto y no lo muestra, igual que "Cantidad en 0" no lo dejaría vender

#### Scenario: Alguna variante con stock

- **WHEN** el flag está activo y al menos una variante del producto tiene stock a mano positivo en la ubicación de origen de la caja
- **THEN** el producto aparece en la cuadrícula

#### Scenario: Producto no almacenable

- **WHEN** el flag está activo y el producto es un servicio, un consumible sin control de stock o un combo
- **THEN** el producto aparece aunque no tenga stock

#### Scenario: Flag apagado

- **WHEN** la compañía no activa el flag
- **THEN** los productos almacenables sin stock aparecen en la cuadrícula y el bloqueo de vender sin stock depende de "Cantidad en 0" (`amount_to_zero`)

## ADDED Requirements

### Requirement: Stock actual al abrir la caja con "Mostrar solamente los productos disponibles"

Con el flag activo, `pos.session.load_data` DEBE (MUST) cargar `product.template` y `product.product` sin el filtro por `write_date` de la carga incremental, porque un movimiento de stock no lo cambia: una sesión nueva o la entrada desde el backend traen el stock actual aunque la caja tenga caché. F5 con la sesión abierta no consulta al servidor: para eso lo recomendado es "Volver a cargar datos" → "Limitado".

#### Scenario: Stock cambiado con la caja ya cargada

- **WHEN** el flag está activo, la caja cargó un producto almacenable y después su stock cambia en la ubicación de origen de la caja (se repone o se agota) sin que cambie el producto
- **THEN** al abrir una sesión nueva o entrar desde el backend el producto aparece o desaparece según el stock actual

#### Scenario: F5 con la sesión abierta

- **WHEN** el flag está activo, la sesión sigue abierta y se repone el stock de un producto oculto
- **THEN** tras F5 sigue oculto, y aparece tras "Volver a cargar datos" → "Limitado", que vacía la caché del navegador igual que "Completo" y recarga hasta `point_of_sale.limited_product_count` plantillas

#### Scenario: Flag apagado

- **WHEN** la compañía no activa el flag y la caja abre con caché
- **THEN** la carga incremental conserva el filtro por `write_date` del core y solo reenvía los productos modificados
