# l10n_ve_stock_reports

## Purpose

Genera el libro de inventario venezolano ("Registro detallado de entradas y salidas de inventario de mercancías") como archivo Excel, a partir de las capas de valoración de inventario (`stock.valuation.layer`). Define el wizard `wizard.stock.book.report` y el controlador HTTP de descarga. Declara dependencias de `stock`, `account` y `sale_stock`, pero el código usa además el modelo `stock.valuation.layer` (que en Odoo 19 ya no existe: `stock_account` lo sustituyó por `product.value`), el campo `transfer_reason_id` de `stock.picking` (definido en `l10n_ve_stock_account`) y los campos `production_id` / `raw_material_production_id` de `stock.move` (definidos en `mrp`), ninguno de los cuales está declarado como dependencia.

## Requirements

### Requirement: Descarga del libro de inventario en Excel

El wizard `wizard.stock.book.report` DEBE (MUST) exponer la acción `generate_report`, que devuelve una `ir.actions.act_url` hacia `/web/download_stock_book?company_id=<id del wizard>`. La ruta (tipo `http`, autenticación `user`) DEBE (MUST) tomar el `company_id` del query string —con 1 como valor por omisión—, recuperar el último registro del wizard existente (`search([], order="id desc", limit=1)`, no necesariamente el que el usuario acaba de enviar), escribir esa compañía sobre el wizard y devolver el binario `xlsx` con el nombre `Libro_de_Inventario.xlsx`. La compañía recibida por parámetro NO se valida contra las compañías permitidas del usuario. El encabezado DEBE (MUST) incluir la razón social y el RIF (`vat`) de la compañía y el rango de fechas, y cada columna numérica DEBE (MUST) cerrar con una fila de totales calculada con una fórmula `SUM` de Excel.

#### Scenario: Generación desde el wizard

- **WHEN** un usuario ejecuta la acción de generar el reporte del wizard
- **THEN** el navegador es redirigido a `/web/download_stock_book` y descarga el archivo `Libro_de_Inventario.xlsx`

#### Scenario: Acceso sin sesión

- **WHEN** se invoca la ruta `/web/download_stock_book` sin usuario autenticado
- **THEN** el acceso es rechazado por la autenticación `user` de la ruta

#### Scenario: Compañía indicada por parámetro

- **WHEN** un usuario autenticado invoca la ruta con un `company_id` que no está entre sus compañías permitidas
- **THEN** el reporte se genera igualmente para esa compañía, porque el controlador no verifica el acceso

### Requirement: Acceso al wizard sin grupo y menú contable

El módulo DEBE (MUST) declarar la ACL `access_l10n_ve_stock_report` sobre `wizard.stock.book.report` con `group_id` vacío y los cuatro permisos en 1, de modo que cualquier usuario pueda crear y leer registros del wizard, y DEBE (MUST) publicar la acción bajo el menú `account.menu_finance_reports` sin restricción de grupo adicional.

#### Scenario: Usuario interno sin permisos contables

- **WHEN** un usuario interno cualquiera crea un registro de `wizard.stock.book.report`
- **THEN** la ACL sin grupo se lo permite

### Requirement: Clasificación de los movimientos del período

El método `parse_stock_book_data` DEBE (MUST) construir una línea por producto a partir de los registros de `stock.valuation.layer` de la compañía del wizard cuyo movimiento está hecho (`stock_move_id.state = done`) y cuya `create_date` cae entre `date_from` y `date_to`. La clasificación DEBE (MUST) hacerse con cuatro condiciones independientes (no excluyentes entre sí), acumulando cantidad (`quantity`) y monto (`value`) de la capa:

- entradas: traslados con `picking_code = incoming` (con o sin `origin_returned_move_id`, de modo que la distinción entre recepción y devolución entrante no cambia el resultado), ajustes de inventario (`is_inventory`) con cantidad positiva, y movimientos con `production_id`;
- salidas: traslados con `picking_code = outgoing` (con o sin `origin_returned_move_id`), ajustes de inventario con cantidad negativa, y movimientos con `raw_material_production_id`;
- retiros: movimientos cuyo traslado tiene razón `donation`;
- autoconsumos: movimientos cuyo traslado tiene razón `self_consumption`.

Como las condiciones no se excluyen, un despacho por donación o autoconsumo DEBE (MUST) contarse a la vez en salidas y en su columna específica. La columna "EXISTENCIA" DEBE (MUST) ser la suma neta de las cantidades y valores de todas las capas del período, sin incluir la existencia anterior. Las salidas, retiros y autoconsumos se presentan en valor absoluto.

Dado que en Odoo 19 el modelo `stock.valuation.layer` no existe, la búsqueda DEBE (MUST) fallar al resolver el modelo y el reporte no puede generarse.

#### Scenario: Despacho por donación

- **WHEN** un movimiento del período pertenece a un traslado de salida con razón donación
- **THEN** su cantidad y valor se acumulan tanto en las columnas de salidas como en las de retiros

#### Scenario: Ejecución sobre Odoo 19

- **WHEN** se invoca `parse_stock_book_data` en una base Odoo 19
- **THEN** la operación falla porque el modelo `stock.valuation.layer` fue reemplazado por `product.value`

### Requirement: Existencia anterior del mes previo

El método `get_old_stock_by_product` DEBE (MUST) calcular la existencia anterior de cada producto (cantidad y valor en Bs) sumando las capas de valoración de movimientos hechos cuya `create_date` va desde `date_from` menos un mes hasta antes de `date_from`, sin filtrar por compañía (a diferencia de la búsqueda del período, que sí acota a la compañía del wizard) y calculándose una sola vez, la primera vez que el producto aparece en el recorrido.

#### Scenario: Producto con movimientos el mes anterior

- **WHEN** un producto tiene capas de valoración hechas dentro del mes previo a la fecha inicial
- **THEN** las columnas de existencia y valor anterior muestran la suma de esas cantidades y valores

#### Scenario: Movimientos de otra compañía en el mes previo

- **WHEN** el producto tuvo movimientos del mes previo en una compañía distinta a la del wizard
- **THEN** esas cantidades y valores también se suman a la existencia anterior
