# l10n_ve_stock_reports

## Purpose

Genera el libro de inventario venezolano ("Registro detallado de entradas y salidas de inventario de mercancías") como archivo Excel, a partir de las capas de valoración de inventario (`stock.valuation.layer`). Define el wizard `wizard.stock.book.report` y el controlador HTTP de descarga. Depende de `stock`, `account` y `sale_stock`.

## Requirements

### Requirement: Descarga del libro de inventario en Excel

El wizard `wizard.stock.book.report` DEBE (MUST) generar el libro vía la ruta `/web/download_stock_book` (autenticación de usuario), que devuelve un archivo `xlsx` llamado `Libro_de_Inventario.xlsx` construido con los datos del último wizard creado y la compañía indicada por parámetro, con encabezado que incluye la razón social, el RIF de la compañía y el rango de fechas, y una fila final de totales por columna numérica.

#### Scenario: Generación desde el wizard

- **WHEN** un usuario ejecuta la acción de generar el reporte del wizard
- **THEN** el navegador descarga el archivo `Libro_de_Inventario.xlsx` con los movimientos del período

#### Scenario: Acceso sin sesión

- **WHEN** se invoca la ruta `/web/download_stock_book` sin usuario autenticado
- **THEN** el acceso es rechazado por la autenticación `user` de la ruta

### Requirement: Clasificación de los movimientos del período

El método `parse_stock_book_data` DEBE (MUST) construir una línea por producto a partir de las capas de valoración (`stock.valuation.layer`) de la compañía del wizard cuyo movimiento está hecho (`stock_move_id.state = done`) y cuya fecha de creación cae entre `date_from` y `date_to`, clasificando cantidades y valores así: entradas para recepciones, devoluciones entrantes, ajustes de inventario positivos y producciones; salidas para despachos, devoluciones salientes, ajustes negativos y consumos de producción; retiros para movimientos cuyo traslado tiene razón `donation`; y autoconsumos para razón `self_consumption` (razones definidas en `l10n_ve_stock_account`). Los montos se toman del campo `value` de la capa y las salidas, retiros y autoconsumos se presentan en valor absoluto.

#### Scenario: Recepción del período

- **WHEN** existe una capa de valoración de una recepción hecha dentro del rango de fechas
- **THEN** su cantidad y valor se acumulan en las columnas de entradas del producto

#### Scenario: Despacho por autoconsumo

- **WHEN** un movimiento del período pertenece a un traslado con razón autoconsumo
- **THEN** su cantidad y valor se acumulan en las columnas de auto-consumos

### Requirement: Existencia anterior del mes previo

El método `get_old_stock_by_product` DEBE (MUST) calcular la existencia anterior de cada producto (cantidad y valor en Bs) sumando las capas de valoración de movimientos hechos creadas en el mes inmediatamente anterior a `date_from` (desde `date_from` menos un mes hasta antes de `date_from`).

#### Scenario: Producto con movimientos el mes anterior

- **WHEN** un producto tiene capas de valoración hechas dentro del mes previo a la fecha inicial
- **THEN** las columnas de existencia y valor anterior muestran la suma de esas cantidades y valores
