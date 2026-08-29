## ADDED Requirements

### Requirement: Búsqueda de producto por Código Alterno al agregar línea de compra
El sistema DEBE (MUST) resolver un producto por su `alternate_code` (Código Alterno) cuando se escribe texto en el selector de producto de una línea de orden de compra, además de los criterios ya soportados por el núcleo (`default_code`, `barcode`, nombre). Los resultados obtenidos por `alternate_code` DEBEN agregarse después de los que devuelve el comportamiento estándar, sin duplicar productos ya incluidos, respetando el `domain` y el `limit` recibidos, y sin aplicarse cuando el operador de búsqueda es negativo.

#### Scenario: Coincidencia exacta por Código Alterno
- **WHEN** un usuario escribe el Código Alterno completo de un producto (por ejemplo `RPCL4-1001`) en el selector de producto de una línea de orden de compra
- **THEN** el desplegable muestra el producto cuyo `alternate_code` coincide

#### Scenario: Coincidencia parcial por Código Alterno
- **WHEN** un usuario escribe una parte del Código Alterno de un producto (por ejemplo `RPCL4-18`)
- **THEN** el desplegable muestra los productos cuyo `alternate_code` contiene ese texto

#### Scenario: Sin regresión en la búsqueda estándar
- **WHEN** un usuario escribe la Referencia Interna (`default_code`) o el nombre de un producto en la línea de compra
- **THEN** el producto sigue resolviendo igual que antes de este cambio, y en el mismo orden de relevancia

#### Scenario: Producto que coincide por dos criterios no se duplica
- **WHEN** el texto escrito coincide simultáneamente con el `default_code`/nombre/`barcode` de un producto y también con su `alternate_code`
- **THEN** ese producto aparece una sola vez en el desplegable

#### Scenario: Sin coincidencias
- **WHEN** el texto escrito no coincide con ningún `default_code`, nombre, `barcode` ni `alternate_code`
- **THEN** el desplegable no muestra productos

#### Scenario: Operador de búsqueda negativo
- **WHEN** la búsqueda de producto se ejecuta con un operador negativo (por ejemplo `not ilike`)
- **THEN** el comportamiento es exactamente el del núcleo, sin considerar `alternate_code`

### Requirement: Columna Código Alterno en la línea de orden de compra
El sistema DEBE (MUST) mostrar el Código Alterno del producto seleccionado como columna de solo lectura en la lista de líneas de la orden de compra, disponible como columna opcional y traducida a `es_VE`.

#### Scenario: Columna visible por defecto
- **WHEN** un usuario abre una orden de compra con líneas
- **THEN** la columna "Código Alterno" se muestra junto a la columna de producto, con el valor de `product_id.alternate_code`, y no es editable desde la línea

#### Scenario: Columna ocultable
- **WHEN** un usuario abre el selector de columnas opcionales de la lista de líneas de compra
- **THEN** puede ocultar la columna "Código Alterno" sin afectar el dato almacenado en el producto
