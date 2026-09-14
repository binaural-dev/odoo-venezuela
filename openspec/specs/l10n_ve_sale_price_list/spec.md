# l10n_ve_sale_price_list

## Purpose

Extiende el reporte nativo "Imprimir lista de precios" de Odoo (`product.report_pricelist`) para comparar varias listas de precios en columnas, en vez de una sola lista con varias cantidades. La vista en pantalla pagina los productos para que catálogos grandes sigan siendo ágiles; la exportación a PDF y XLSX siempre cubre todos los productos seleccionados, sin paginar. Restringe el acceso al reporte multi-lista a un grupo de permisos dedicado. Depende de `product`.

## Requirements

### Requirement: Reporte multi-lista en columnas

El reporte DEBE (MUST) mostrar, para cada producto seleccionado, una columna de precio por cada lista de precios elegida por el usuario (en vez del formato nativo de una sola lista con varias cantidades). El usuario DEBE (MUST) poder agregar o quitar listas de precios dinámicamente antes de generar el reporte.

#### Scenario: Selección de varias listas de precios

- **WHEN** el usuario abre el reporte desde la acción "Pricelist Report" y agrega más de una lista de precios
- **THEN** la vista y las exportaciones (PDF, CSV, XLSX) muestran una columna de precio por cada lista de precios agregada, calculada en la moneda de esa lista

#### Scenario: Precarga de listas por compañía activa

- **WHEN** el usuario abre el reporte
- **THEN** se precargan por defecto las listas de precio de su compañía activa, más las que no tienen compañía asignada (compartidas entre compañías)

### Requirement: Paginación en la vista en pantalla, sin paginar en las exportaciones

La vista HTML en pantalla DEBE (MUST) paginar los productos seleccionados en bloques de 20, para que seleccionar una cantidad grande de productos (p. ej. 800) no obligue a calcular el precio de todos en todas las listas de una sola vez. Las exportaciones a PDF, CSV y XLSX DEBEN (MUST) cubrir siempre la totalidad de los productos seleccionados, sin aplicar esa paginación.

#### Scenario: Selección grande en pantalla

- **WHEN** el usuario selecciona 800 productos y varias listas de precios, y visualiza el reporte en pantalla
- **THEN** solo se calculan y muestran los precios de la página actual (20 productos), navegable con controles de página siguiente/anterior

#### Scenario: Exportación de una selección grande

- **WHEN** el usuario exporta a PDF, CSV o XLSX la misma selección de 800 productos
- **THEN** el archivo generado incluye los 800 productos completos, no solo la página visible en pantalla

### Requirement: Encabezado de fecha, hora, logo y compañía en las exportaciones

El PDF DEBE (MUST) mostrar el logo de la compañía y la fecha y hora de emisión del reporte. El XLSX DEBE (MUST) incluir en su primera fila una leyenda con el nombre del reporte, la compañía y la fecha y hora de emisión, para que el archivo sea identificable por sí solo una vez descargado.

#### Scenario: Encabezado del PDF

- **WHEN** se genera el reporte en PDF
- **THEN** el encabezado muestra el logo de la compañía activa del usuario y la fecha y hora de emisión (no solo la fecha)

#### Scenario: Leyenda del XLSX

- **WHEN** se exporta el reporte a XLSX
- **THEN** la primera fila del archivo contiene, en celdas separadas, el texto "Price list report" (traducido en `es_VE`), el nombre de la compañía activa y la fecha y hora de emisión; los encabezados de columna (Producto, UOM, listas de precios) y los datos comienzan en la fila siguiente

### Requirement: Grupo de permisos dedicado para el reporte multi-lista

El reporte multi-lista DEBE (MUST) requerir el grupo `l10n_ve_sale_price_list.group_pricelist_report_multi`, verificado a nivel de servidor. Este grupo es independiente del grupo nativo `product.group_product_pricelist` (que solo controla si el usuario puede asignar/ver más de una lista de precios en el producto, no si puede imprimir este reporte comparativo).

#### Scenario: Usuario sin el grupo

- **WHEN** un usuario sin `group_pricelist_report_multi` intenta generar el reporte multi-lista
- **THEN** el sistema lanza un `AccessError` indicando que no tiene permiso

#### Scenario: Usuario con el grupo

- **WHEN** un usuario con `group_pricelist_report_multi` genera el reporte
- **THEN** el reporte se genera normalmente

### Requirement: Nombre de la lista de precios identifica su compañía

El nombre visible (`display_name`) de una lista de precios con compañía asignada DEBE (MUST) incluir el nombre de esa compañía entre paréntesis, para identificarla en entornos multi-sucursal. Las listas sin compañía asignada (compartidas entre compañías) usan el `display_name` calculado por el core, sin modificar.

**Efecto global, no acotado a este reporte**: `display_name` es un campo del propio `product.pricelist`, así que este sufijo aparece en cualquier lugar de Odoo donde se muestre el nombre de una lista de precios — el formulario de producto, las líneas de venta, el selector de PdV, el menú de configuración de Listas de Precios — no solo en este reporte multi-lista.

#### Scenario: Lista con compañía

- **WHEN** se calcula el `display_name` de una lista de precios con `company_id` asignado
- **THEN** el resultado es `"<nombre> (<moneda>) (<compañía>)"`

#### Scenario: Lista sin compañía

- **WHEN** se calcula el `display_name` de una lista de precios sin `company_id`
- **THEN** el resultado es el que calcula el core, sin sufijo de compañía

### Requirement: Aviso de selección grande

Al agregar una lista de precios, imprimir en PDF, o exportar a XLSX, si la cantidad de productos seleccionados supera 800 y la cantidad de listas de precios agregadas es 5 o más, el sistema DEBE (MUST) mostrar una notificación de advertencia no bloqueante indicando que la combinación es grande y que imprimir/exportar puede tardar. La vista en pantalla no se ve afectada por este aviso: sigue paginando de 20 en 20 independientemente del tamaño de la selección.

#### Scenario: Selección grande al agregar una lista

- **WHEN** el usuario tiene más de 800 productos seleccionados y agrega una quinta (o posterior) lista de precios
- **THEN** se muestra una notificación de advertencia con la cantidad de productos y listas seleccionadas

#### Scenario: Selección grande al imprimir o exportar

- **WHEN** el usuario imprime en PDF o exporta a XLSX con más de 800 productos y 5 o más listas ya agregadas
- **THEN** se muestra la misma notificación de advertencia antes de generar el archivo

#### Scenario: Selección por debajo del umbral

- **WHEN** la cantidad de productos es 800 o menos, o hay menos de 5 listas agregadas
- **THEN** no se muestra ninguna advertencia

## Known limitations

- El aviso de selección grande es una notificación no bloqueante, no un límite duro: el usuario puede seguir imprimiendo/exportando combinaciones grandes. La paginación de la vista en pantalla mitiga el impacto de rendimiento al navegar, pero las exportaciones (que no paginan) siguen calculando la totalidad de la selección en una sola pasada.
