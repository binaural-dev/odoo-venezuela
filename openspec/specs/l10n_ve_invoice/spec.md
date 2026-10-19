# l10n_ve_invoice

## Purpose

Núcleo de facturación fiscal venezolana: asigna y controla el número de control (`correlative`) de las facturas, gestiona series de facturación y diarios de contingencia/débito, agrega las validaciones fiscales de confirmación (impuesto por línea, precio distinto de cero, máximo de productos), la forma libre de impresión y los libros fiscales de compras y ventas en Excel (`wizard.accounting.reports`). Extiende `account.move`, `account.journal`, `account.debit.note`, `ir.actions.report`, `res.company` y `res.config.settings`. Depende de `l10n_ve_accountant` (de donde consume `invoice_date_display`, `vat`, `tax_totals` extendido y la configuración de alícuotas por compañía), `l10n_ve_rate`, `l10n_ve_base`, `l10n_ve_contact`, `od_journal_sequence` y `account_debit_note`. El módulo `l10n_ve_igtf` extiende sus libros fiscales.

## Requirements

### Requirement: Asignación del número de control al publicar

Al publicar (`_post`) una factura de venta sin `correlative`, el sistema DEBE (MUST) asignarle el siguiente número de la secuencia `invoice.correlative` de la compañía (creándola con padding 5 si no existe), siempre que el diario sea de tipo `sale`, no sea de contingencia (o la facturación por series esté activa) y el tipo de impresión de la compañía no sea `fiscal` (`is_valid_to_sequence` y `get_sequence`).

#### Scenario: Publicación de factura de cliente

- **WHEN** se publica una factura de un diario de venta sin número de control
- **THEN** el campo `correlative` recibe el siguiente número de la secuencia `invoice.correlative`

#### Scenario: Impresora fiscal

- **WHEN** la compañía tiene tipo de impresión `fiscal`
- **THEN** la publicación no asigna número de control

### Requirement: Series de facturación por diario

Cuando la compañía activa `group_sales_invoicing_series`, el número de control DEBE (MUST) obtenerse de la secuencia `series_correlative_sequence_id` configurada en el diario de la factura, lanzando un error si el diario no la tiene; activar o desactivar la opción en ajustes activa/desactiva la secuencia `series.invoice.correlative`.

#### Scenario: Diario sin secuencia de serie

- **WHEN** se publica una factura con series activas y el diario no tiene secuencia de serie
- **THEN** se lanza un error indicando que la secuencia de serie debe estar en el diario

#### Scenario: Diario con secuencia de serie

- **WHEN** el diario tiene su secuencia de serie configurada
- **THEN** el número de control se toma de esa secuencia

### Requirement: Unicidad del número de control en ventas

El sistema DEBE (MUST) impedir que un documento de venta (`out_invoice`/`out_refund`) de un diario no de contingencia lleve un `correlative` que ya use otro documento de venta **publicado** de la misma compañía (constraint `_check_correlative`). La validación se aplica cualquiera sea el estado del documento que se guarda: solo el documento con el que se compara debe estar en `posted`.

#### Scenario: Número de control repetido

- **WHEN** se guarda una factura de venta cuyo `correlative` ya está en uso por otra factura publicada de la compañía
- **THEN** se lanza un error de validación indicando el número y la factura que lo usa

#### Scenario: Duplicado contra un borrador

- **WHEN** el `correlative` solo coincide con el de otro documento en borrador
- **THEN** el guardado se permite

### Requirement: Correlativo en diarios de contingencia

En facturas de diarios de contingencia (`is_contingency` del `account.journal`), el `correlative` DEBE (MUST) ser obligatorio cuando la facturación por series no está activa, y único por diario entre los documentos de contingencia.

#### Scenario: Contingencia sin correlativo

- **WHEN** se guarda una factura de un diario de contingencia sin número de control y sin series activas
- **THEN** se lanza un error de validación exigiendo el correlativo

#### Scenario: Correlativo repetido en el diario

- **WHEN** dos facturas de contingencia del mismo diario tienen el mismo correlativo
- **THEN** se lanza un error indicando que debe ser único por diario

### Requirement: Compras internacionales usan la DUA como número de control

En facturas de un diario con `is_purchase_international` (de `l10n_ve_accountant`), el sistema DEBE (MUST) copiar `declaration_unique_of_customs` al campo `correlative` en la creación y en cada escritura; si el documento deja de ser internacional y el correlativo era la DUA, ambos campos se limpian.

#### Scenario: Registro de una importación

- **WHEN** se crea una factura de compra internacional con número de declaración de aduana y sin correlativo
- **THEN** `correlative` queda igual a `declaration_unique_of_customs`

### Requirement: Prohibición de líneas con precio cero

El sistema DEBE (MUST) impedir guardar facturas con líneas de producto cuyo `price_unit` sea menor o igual a cero (constraint `_check_price_in_zero`), exceptuando las líneas de descuento reconocidas por `_get_discount_lines`, las secciones/notas y los flujos con contexto `from_pos` o `from_loyalty`.

#### Scenario: Línea en cero

- **WHEN** se guarda una factura con una línea de producto a precio cero fuera de POS/lealtad
- **THEN** se lanza un error "An invoice cannot have a line with a price of zero"

#### Scenario: Línea de descuento

- **WHEN** la línea a precio no positivo es una línea de descuento reconocida
- **THEN** la factura se guarda sin error

### Requirement: Impuesto obligatorio por línea para confirmar

`action_post` DEBE (MUST) impedir confirmar facturas y notas (`out_invoice`, `in_invoice`, `out_refund`, `in_refund`) con alguna línea de producto sin impuestos (`tax_ids` vacío), excluyendo secciones y notas.

#### Scenario: Línea sin impuesto

- **WHEN** se confirma una factura con una línea de producto sin impuesto
- **THEN** se lanza un error de validación pidiendo agregar un impuesto a cada línea

### Requirement: Máximo de productos por factura

El sistema DEBE (MUST) impedir agregar a facturas de venta más líneas que el máximo configurado en `max_product_invoice` de la compañía (por defecto 23), mediante el onchange de `invoice_line_ids`.

#### Scenario: Factura con demasiadas líneas

- **WHEN** un usuario agrega más productos que el máximo configurado en una factura de venta
- **THEN** se lanza un error indicando el máximo de productos permitido

### Requirement: Fecha de factura no posterior a la fecha contable en compras

Cuando la compañía activa `block_invoice_display_date_upper_than_date`, el sistema DEBE (MUST) impedir en documentos de compra que `invoice_date_display` sea mayor que la fecha contable `date` (constraint `_check_invoice_date_display_purchases`).

#### Scenario: Fecha de documento futura

- **WHEN** se guarda una factura de proveedor con fecha de documento posterior a la fecha contable y el bloqueo activo
- **THEN** se lanza un error "The invoice date cannot be greater than the accounting date."

### Requirement: Solo documentos contables confirmados se imprimen

`ir.actions.report` DEBE (MUST) filtrar las impresiones (PDF y HTML) de `account.move` a documentos en estado `posted`, lanzando un error cuando ningún documento seleccionado cumple la condición. La restricción NO DEBE (MUST NOT) aplicarse a otros modelos: en particular `sale.order`, cuyas cotizaciones se imprimen y se envían por correo estando en borrador.

#### Scenario: Imprimir factura en borrador

- **WHEN** se solicita el PDF de una factura no publicada
- **THEN** se lanza un error indicando que solo se imprimen documentos publicados

#### Scenario: Imprimir o enviar una cotización en borrador

- **WHEN** se solicita el reporte de una orden de venta en estado `draft` (por el botón Imprimir o por el adjunto que genera el diálogo de envío de correo)
- **THEN** el reporte se genera normalmente, sin restricción alguna

### Requirement: Registro de la fecha-hora de emisión

Al crear o modificar `invoice_date_display`, el sistema DEBE (MUST) almacenar en `invoice_date_display_datetime` esa fecha combinada con la hora actual, y limpiarlo cuando la fecha se vacía.

#### Scenario: Establecer la fecha de factura

- **WHEN** se crea una factura con `invoice_date_display`
- **THEN** `invoice_date_display_datetime` queda con esa fecha y la hora del momento del registro

### Requirement: Período fiscal según tipo de contribuyente

El campo `entry_in_period` DEBE (MUST) indicar si un documento entra en el período fiscal vigente: los documentos de compra no cancelados (`in_invoice`, `in_refund`, `in_receipt`) siempre entran; los de venta (`out_invoice`, `out_refund`) entran cuando su `invoice_date` pertenece al mismo mes y año del límite del período **y** no es posterior a ese límite, donde el límite es el día 15 para contribuyentes especiales antes del 15 y el último día del mes en el resto de casos (`_get_period_limit`), excluyendo para especiales los documentos de la primera quincena cuando el límite ya pasó al fin de mes. El tipo de contribuyente se lee de la compañía activa (`self.env.company.taxpayer_type`), no de la compañía del documento, y todo documento en estado `cancel` o de otro tipo de movimiento queda en falso.

#### Scenario: Contribuyente especial en la primera quincena

- **WHEN** la compañía es contribuyente especial, hoy es antes del día 15 y la factura de venta tiene fecha dentro de la primera quincena del mes
- **THEN** `entry_in_period` es verdadero

#### Scenario: Documento cancelado

- **WHEN** el documento está en estado `cancel`
- **THEN** `entry_in_period` es falso

### Requirement: Advertencia de Nota de Débito de proveedor fuera del período fiscal

El wizard `account.debit.note` DEBE (MUST) exponer `l10n_ve_out_of_fiscal_period_warning` (booleano, solo advertencia -- nunca bloquea la creación), verdadero cuando entre las facturas de proveedor (`in_invoice`) seleccionadas (`move_ids`) alguna tiene su `invoice_date_display` en un mes/año distinto al de la fecha de la Nota de Débito elegida en el wizard (`date`). La comparación usa `invoice_date_display` de la factura origen -- su fecha fiscal real -- y no `date` (fecha contable, que solo se DERIVA de `invoice_date_display` vía `_get_accounting_date_source` de `l10n_ve_accountant` y puede quedar posterior si el documento se contabiliza después de emitido). Documentos de venta (`out_invoice`/`out_refund`) nunca disparan la advertencia.

#### Scenario: Nota de Débito de proveedor en el mismo período que la factura

- **WHEN** se abre el wizard de Nota de Débito sobre una factura de proveedor y la fecha elegida cae en el mismo mes/año que `invoice_date_display` de esa factura
- **THEN** `l10n_ve_out_of_fiscal_period_warning` es falso

#### Scenario: Nota de Débito de proveedor en un período distinto

- **WHEN** la fecha elegida en el wizard cae en un mes/año distinto al de `invoice_date_display` de la factura de proveedor
- **THEN** `l10n_ve_out_of_fiscal_period_warning` es verdadero y el formulario del wizard muestra un aviso, sin impedir crear la nota

#### Scenario: La advertencia ignora la fecha contable de la factura, no su fecha fiscal

- **WHEN** la factura de proveedor fue emitida (`invoice_date_display`) en un mes pero contabilizada (`date`) en otro, y la Nota de Débito se fecha en el mes de emisión
- **THEN** `l10n_ve_out_of_fiscal_period_warning` es falso, porque la comparación usa `invoice_date_display`, no `date`

### Requirement: Preservación de la tasa y de la fecha fiscal propia al crear una Nota de Débito

Al crear una Nota de Débito (`account.debit.note.create_debit`, `_prepare_default_values`), el sistema DEBE (MUST) corregir el comportamiento por defecto del núcleo (`account_debit_note`), que asigna tanto `date` como `invoice_date` a la fecha elegida en el wizard y dependen de `copy()` para heredar `invoice_date_display` de la factura origen sin cambios:

- `invoice_date` (la "Fecha de Tasa" redefinida por `l10n_ve_accountant`/`l10n_ve_invoice`, usada solo para el cálculo de tasa de cambio) DEBE quedar igual a `invoice_date` de la factura origen -- nunca a la fecha del wizard. Sin esta corrección, la nota cotiza a una tasa distinta a la de la factura que corrige/complementa, generando un diferencial cambiario espurio entre dos documentos que son la misma transacción.
- `invoice_date_display` (la fecha fiscal propia del documento, de la que `date` se deriva vía `_get_accounting_date_source`) DEBE quedar igual a la fecha elegida en el wizard (`self.date` o `move.date` como resguardo) -- nunca heredada en silencio de la factura origen.
- `date` (fecha contable) sigue como ya lo resuelve el núcleo: la fecha elegida en el wizard.

Aplica a cualquier documento facturable (`is_invoice(include_receipts=True)`), no solo a facturas de proveedor.

#### Scenario: La Nota de Débito conserva la tasa de la factura origen

- **WHEN** se crea una Nota de Débito con una fecha de wizard distinta a la fecha de la factura origen
- **THEN** `invoice_date` de la nota creada es igual a `invoice_date` de la factura origen, no a la fecha del wizard

#### Scenario: La Nota de Débito declara su propia fecha fiscal

- **WHEN** se crea una Nota de Débito con una fecha de wizard distinta a `invoice_date_display` de la factura origen
- **THEN** `invoice_date_display` de la nota creada es igual a la fecha elegida en el wizard, y `date` también

### Requirement: Próxima cuota por vencer

El campo `next_installment_date` DEBE (MUST) calcularse como el menor `date_maturity` mayor o igual a hoy entre las líneas `payment_term` del documento; sin líneas de término de pago, toma `invoice_date_due`.

#### Scenario: Factura con cuotas futuras

- **WHEN** una factura tiene líneas de término de pago con vencimientos pasados y futuros
- **THEN** `next_installment_date` es el primer vencimiento igual o posterior a hoy

### Requirement: Control de copias de la forma libre

`print_invoice_free_form` DEBE (MUST) incrementar `free_form_copy_number` en cada impresión y devolver la descarga del adjunto principal cuando ya existe, generando el reporte QWeb solo la primera vez; el adjunto principal del documento solo puede establecerse cuando `free_form_copy_number` es al menos 1 y aún no existe (`_message_set_main_attachment_id`), y el envío por correo (`action_invoice_sent`) también incrementa el contador.

#### Scenario: Reimpresión de la forma libre

- **WHEN** se vuelve a imprimir una factura que ya tiene adjunto principal
- **THEN** se descarga el mismo adjunto en lugar de regenerar el reporte

### Requirement: Dominio de los libros fiscales

El wizard `wizard.accounting.reports` DEBE (MUST) seleccionar para el libro los documentos de las compañías del alcance del libro (`report_company_ids`, ver «Alcance del libro con sucursales nativas») con estado `posted` o `cancel`, `correlative` asignado (distinto de `/` y de vacío), fecha contable dentro del rango solicitado, y tipo según el libro (`out_invoice`/`out_refund` para ventas; `in_invoice`/`in_refund`/`in_debit` para compras), ordenados por correlativo en ventas y por fecha de documento en compras; cuando todas las columnas internacionales están ocultas por configuración, el libro de compras excluye los diarios internacionales.

#### Scenario: Generación del libro de ventas

- **WHEN** se genera el libro de ventas de un período
- **THEN** solo aparecen documentos de venta publicados o anulados con número de control dentro del rango de fechas

### Requirement: Alcance del libro con sucursales nativas

El wizard `wizard.accounting.reports` DEBE (MUST) detectar las sucursales nativas de Odoo (compañías descendientes por `parent_id`) de la compañía activa que comparten su RIF —una sucursal sin RIF propio se considera el mismo contribuyente— y exponer `has_branches`. Cuando `has_branches` es verdadero, el wizard DEBE (MUST) mostrar el campo `branch_scope` con tres valores: `all` (consolidado: la matriz y todas sus sucursales del mismo RIF; valor por defecto), `main` (solo la compañía activa, excluyendo sus sucursales) y `branch` (una sucursal elegida en `branch_company_id`, obligatoria en ese caso y obligatoriamente del mismo RIF). Sin sucursales del mismo RIF el selector DEBE (MUST) permanecer oculto y el libro se genera solo con la compañía activa. Las compañías hijas con RIF distinto NO DEBEN (MUST NOT) incluirse nunca. `report_company_ids` se limita a las compañías a las que el usuario creador del wizard tiene acceso. Los libros consolidados conservan por línea el número de factura y de control de cada sede, ordenan por fecha del documento con una sola numeración de operación y calculan el resumen sobre el total consolidado; el encabezado (razón social, RIF y dirección) y la configuración de alícuotas son los de la compañía del wizard (la matriz), salvo en el alcance `branch`, donde el encabezado es el de la sucursal.

#### Scenario: Libro consolidado desde la matriz

- **WHEN** se genera el libro con la matriz activa y alcance `all`
- **THEN** aparecen los documentos de la matriz y de sus sucursales del mismo RIF, con sus números de control originales, ordenados por fecha, y las compañías con otro RIF quedan excluidas

#### Scenario: Solo la matriz o una sucursal

- **WHEN** el alcance es `main` o `branch`
- **THEN** el libro contiene únicamente los documentos de la matriz, o de la sucursal elegida, respectivamente

#### Scenario: Sucursal activa sin hijos

- **WHEN** la compañía activa es una sucursal sin sucursales propias
- **THEN** el selector de alcance no se muestra y el libro contiene solo sus documentos

### Requirement: Documento sin fecha bloquea el libro

Si un documento seleccionado para el libro no tiene `invoice_date_display`, la generación DEBE (MUST) detenerse con un error que identifica el documento y su id.

#### Scenario: Factura sin fecha de documento

- **WHEN** el libro incluye un documento sin fecha de documento
- **THEN** se lanza un error indicando el nombre y el id del documento

### Requirement: Clasificación de documentos y tipo de transacción en los libros

Cada línea del libro DEBE (MUST) clasificar el documento como FAC (facturas), NC (notas de crédito) o ND (notas de débito), tratando como ND cualquier documento cuyo diario tenga `is_debit` —el tipo se fuerza a `in_debit` en ambos libros, también en el de ventas—, llenar la columna de número correspondiente al tipo, referenciar la factura afectada (`debit_origin_id` cuando el diario es `is_debit`, `reversed_entry_id` en el resto) y asignar el tipo de transacción solo a documentos publicados (`01-REG` facturas, `02-REG` facturas de diario de débito y notas de débito, `03-REG` notas de crédito) o `03-ANU` cuando el documento está anulado.

#### Scenario: Nota de débito por diario

- **WHEN** una factura publicada pertenece a un diario con `is_debit`
- **THEN** la línea del libro la clasifica como ND con transacción `02-REG` y referencia la factura de origen

#### Scenario: Documento anulado

- **WHEN** el documento está en estado `cancel`
- **THEN** el tipo de transacción es `03-ANU`

### Requirement: Documentos anulados con montos en cero

Para documentos con estado distinto de `posted`, `_determinate_amount_taxeds` DEBE (MUST) devolver todos los montos (bases, impuestos, totales, internacionales y no deducibles) en cero, de modo que los anulados aparezcan en el libro sin importes.

#### Scenario: Factura anulada en el libro

- **WHEN** el libro incluye una factura anulada
- **THEN** su línea muestra todas las bases e impuestos en 0

### Requirement: Clasificación por alícuota según la configuración de la compañía

Los montos de cada documento DEBEN (MUST) clasificarse por alícuota (exenta, reducida 8%, general 16%, adicional 31%) comparando el `id` del grupo de impuestos de cada `tax_group` de `tax_totals` con el `tax_group_id` del impuesto configurado en la compañía para el libro correspondiente (`*_aliquot_sale`, `*_aliquot_purchase`, `*_aliquot_purchase_international`, campos de `l10n_ve_accountant`), leyendo los montos en VES desde las cadenas `formatted_base_amount_currency_ves` / `formatted_tax_amount_currency_ves` y convirtiéndolas a float con `convert_currency_to_float`; un grupo con impuesto cero se clasifica como exento cuando no hay alícuota exenta configurada, y las notas de crédito invierten el signo de bases e impuestos. En el libro de compras internacional, las alícuotas cuya columna está oculta por configuración (`not_show_*_purchase_international`) no se resuelven y sus grupos quedan sin clasificar. Los totales `amount_untaxed`/`amount_taxed` de la línea se recalculan sumando las bases (y las bases más los impuestos) ya clasificadas, no se toman del total del documento.

#### Scenario: Factura con IVA general

- **WHEN** un documento tiene un grupo de impuestos igual al de la alícuota general configurada
- **THEN** su base e impuesto se acumulan en las columnas de base imponible 16% e IVA 16% en bolívares

#### Scenario: Nota de crédito

- **WHEN** el documento es una nota de crédito
- **THEN** sus bases e impuestos aparecen con signo negativo

### Requirement: Compras internacionales en columnas separadas

Para documentos de diarios con `is_purchase_international`, el libro de compras DEBE (MUST) trasladar bases e impuestos a las columnas internacionales (dejando las nacionales en cero), usar `tax_base_for_international_purchase` y `tax_amount_for_international_purchase` del documento como base/impuesto general internacional cuando están definidos, calcular el valor total de las importaciones (`amount_import_international`) sumando las columnas internacionales visibles, y excluir del libro la línea cuando todos sus montos internacionales son cero.

#### Scenario: Factura de importación

- **WHEN** una factura pertenece al diario de compra internacional con montos gravados
- **THEN** sus bases e impuestos aparecen solo en las columnas internacionales junto con la DUA y el número de expediente

#### Scenario: Importación sin montos

- **WHEN** todos los montos internacionales del documento son cero
- **THEN** el documento no genera línea en el libro de compras

### Requirement: Columnas de crédito fiscal no deducible

Cuando la compañía activa `config_deductible_tax`, el libro de compras DEBE (MUST) agregar columnas de base, alícuota y crédito fiscal no deducible por cada alícuota no deducible configurada (`no_deductible_general/reduced/extend_aliquot_purchase`), acumulando los montos de los grupos de impuestos correspondientes.

#### Scenario: Compra con IVA no deducible

- **WHEN** un documento tiene un grupo de impuestos igual al de la alícuota general no deducible
- **THEN** su base e impuesto se acumulan en las columnas no deducibles del libro

### Requirement: Columnas de alícuotas configurables

Las columnas de alícuota reducida, adicional e internacionales de los libros DEBEN (MUST) ocultarse según los flags de la compañía (`not_show_reduced_aliquot_sale`, `not_show_extend_aliquot_sale`, `not_show_*_purchase`, `not_show_*_purchase_international`, `not_show_total_purchases_*`), construyendo dinámicamente los grupos de columnas del Excel.

#### Scenario: Alícuota reducida oculta

- **WHEN** la compañía tiene `not_show_reduced_aliquot_sale` activo
- **THEN** el libro de ventas no incluye las columnas de base, alícuota e IVA 8%

### Requirement: Resumen fiscal al pie del libro

Al final de cada libro, el sistema DEBE (MUST) generar el resumen por categoría con cuatro columnas —base e impuesto de facturas/ND y base e impuesto de notas de crédito— calculadas con `_determinate_resume_books` sobre los documentos del período (excluyendo los documentos cuya fecha contable cae fuera del rango) más dos columnas de total neto (suma de la columna de facturas y la de notas de crédito), y una fila final "Total ... del Periodo" cuyas cuatro primeras columnas se sobrescriben con fórmulas `SUM` del rango del resumen. Solo las categorías con alícuota asociada (exenta, general, reducida, adicional y sus variantes internacionales en compras) devuelven importes; las categorías sin alícuota —"Ventas de Exportación", "Ajustes a los Débitos/Créditos Fiscales de Periodos Anteriores" y la propia fila de totales— devuelven siempre cuatro ceros. Las categorías nacionales excluyen los documentos de diarios `is_purchase_international`. Si el dominio del libro no arroja documentos, la generación del resumen DEBE (MUST) fallar con "There are no moves to show".

#### Scenario: Resumen del libro de ventas

- **WHEN** se genera el libro de ventas
- **THEN** el resumen muestra por categoría la base y el débito fiscal separando facturas/ND de notas de crédito, con el total neto por fila

#### Scenario: Categoría sin alícuota asociada

- **WHEN** el resumen incluye la fila de exportación o la de ajustes de períodos anteriores
- **THEN** sus cuatro columnas de base e impuesto se emiten en cero

### Requirement: Aislamiento multi-compañía de secuencias y del wizard de libros

El módulo DEBE (MUST) instalar dos reglas de registro globales: `invoice_correlative_rule` sobre `ir.sequence` y `wizard_accounting_reports_restricted_multi_company` sobre `wizard.accounting.reports`, ambas con dominio `['|', ('company_id','=',False), ('company_id','in',company_ids)]`, de modo que las secuencias de número de control y los wizards de libros de otras compañías queden fuera del alcance del usuario. Las secuencias `invoice.correlative` (padding 5) y `series.invoice.correlative` (padding 5, inactiva) DEBEN (MUST) instalarse como datos `noupdate`.

#### Scenario: Secuencia de otra compañía

- **WHEN** un usuario consulta las secuencias sin tener activa la compañía dueña de una secuencia de número de control
- **THEN** la regla global excluye esa secuencia del resultado

#### Scenario: Instalación del módulo

- **WHEN** se instala el módulo
- **THEN** existen las secuencias `invoice.correlative` activa y `series.invoice.correlative` inactiva

### Requirement: Descarga del libro por controlador autenticado

Las rutas `/web/download_sales_book` y `/web/download_purchase_book` DEBEN (MUST) requerir usuario autenticado (`auth="user"`) y devolver el XLSX como adjunto (`Libro_de_venta.xlsx` / `Libro_de_compra.xlsx`), con la hoja protegida contra edición mediante contraseña. La URL recibe el `wizard_id` del wizard que generó el libro; el controlador DEBE (MUST) rechazar con `AccessError` el wizard inexistente, creado por otro usuario o cuya compañía no esté entre las del usuario, y generar el libro con un entorno elevado a `SUPERUSER_ID` limitado a `report_company_ids`. Se conserva el parámetro `company_id` en las llamadas a `generate_sales_book` / `generate_purchases_book` por compatibilidad con los módulos que las extienden.

#### Scenario: Descarga del libro de compras

- **WHEN** un usuario autenticado ejecuta la generación del libro de compras
- **THEN** el navegador descarga `Libro_de_compra.xlsx` generado a partir de su propio wizard (`wizard_id`)

#### Scenario: Wizard ajeno

- **WHEN** se invoca la ruta con un `company_id` distinto del de la compañía activa
- **THEN** el libro se genera para la compañía indicada en el parámetro, sin control de acceso adicional por parte del controlador
- **WHEN** se invoca la ruta con el `wizard_id` de un wizard creado por otro usuario
- **THEN** el controlador responde con un error de acceso y no genera el libro

### Requirement: Ajuste de descuento fijo en el desglose por línea en moneda de la compañía

Cuando una línea de factura usa descuento fijo (`discount_fixed`, con el campo nativo `discount` forzado a 0), el sistema DEBE (MUST) calcular el precio unitario y el monto de descuento de `company_currency_line_totals` (`l10n_ve_accountant`) usando el porcentaje de descuento equivalente exacto de `discount_fixed`, no el campo nativo `discount` -- que en este caso vale 0 y daría un precio unitario incorrecto.

#### Scenario: Línea con descuento fijo

- **WHEN** una línea de factura usa `discount_fixed` en una compañía configurada con descuento por monto fijo
- **THEN** `company_currency_line_totals` de esa línea refleja el descuento real aplicado, con `discount_type` en `'amount'`, y el precio unitario reconstruido reproduce el bruto correcto

### Requirement: Ninguna fecha de factura, nota de crédito, nota de débito o recibo puede ser futura al confirmar

El guard `_check_dates_not_in_future` DEBE (MUST) impedir confirmar cualquier documento que no sea un asiento contable puro (`move_type` distinto de `entry` -- en la práctica, `is_invoice(include_receipts=True)`: factura, nota de crédito, nota de débito o recibo, de venta o de compra) cuando `invoice_date_display` sea posterior a la fecha del día (`fields.Date.context_today`) o `invoice_date` (fecha de la tasa) sea posterior a `invoice_date_display`. `invoice_date` PUEDE (MAY) ser anterior a `invoice_date_display`. La fecha contable (`date`) NO se valida en documentos normales: core la permite a futuro a propósito (documentos que se confirman solos en su fecha). El error de validación identifica el campo y la fecha en conflicto. Tickets #15450 y #15594.

Las mismas reglas aplican a ventas y a compras. Aunque ningún ticket lo pida para compras, impedir facturas con fecha futura es el criterio correcto del producto y el comportamiento de validación no debe depender del tipo de documento. Consecuencia conocida: en una factura de proveedor con fecha de documento anterior a hoy hay que bajar la fecha de tasa (por defecto hoy) para poder confirmarla, porque su `onchange` solo sincroniza ventas.

Un asiento contable (`move_type = 'entry'`) queda fuera del alcance: no tiene `invoice_date` ni `invoice_date_display` con sentido fiscal.

El guard se ejecuta en `action_post` y también antes de los dos caminos de la interfaz que confirman con `_post` sin pasar por `action_post`: la acción "Confirm Entries" de lista y kanban (`action_validate_moves_with_confirmation`) y el botón "Confirm" del asistente `validate.account.move` (incluida la casilla "Force"). Sin ese cubrimiento, una factura con `invoice_date_display` de hoy e `invoice_date` de mañana se confirmaría desde la lista sin ningún aviso, porque el núcleo solo pide confirmación cuando `date` es futura. `_post` en sí no se bloquea: los llamadores internos directos (donación, reverso de IGTF, cron) lo hacen de forma intencional.

La validación no es un `@api.constrains` de guardado para las fechas futuras: un borrador con alguna de esas fechas en el futuro SÍ se puede crear y guardar; solo se bloquea confirmarlo mientras siga así. Sin zona horaria (cron o usuarios de integración sin `tz`), `context_today` usa UTC; entre las 20:00 y las 24:00 de Caracas puede aceptarse un documento fechado "mañana" local (limitación conocida).

Una nota de débito (`account.debit.note`) no es un modelo distinto: es un `account.move` con `debit_origin_id`, así que pasa por el mismo guard sin lógica adicional.

Notas (`reversed_entry_id` o `debit_origin_id`), ticket #15594:
- `invoice_date_display` no puede ser anterior al `invoice_date_display` del origen (con `date` como resguardo), ni posterior a hoy: se valida en los wizards, en el guard y al confirmar desde "Confirm Entries".
- `invoice_date` (tasa) DEBE ser igual al del origen al confirmar, y es de solo lectura en el formulario (ventas y compras). No aplica a las notas automáticas de diferencial cambiario, cuya tasa es la del pago (`_l10n_ve_allows_future_date()`).
- Los mensajes del guard nombran el documento, porque "Confirm Entries" valida todo el lote y lo aborta si un borrador no cumple.
- La fecha contable (`date`) de una nota NO puede ser anterior a su propio `invoice_date_display` (constraint de guardado `_check_note_accounting_date`), de modo que editarla directamente (multi-edición de la lista, edición rápida o RPC) no permite esquivar el rango del origen. `date` posterior es válido (fecha de bloqueo).

Exención: la ND/NC de diferencial cambiario (`l10n_ve_exchange_difference`) toma la fecha del pago y la ND de IGTF se confirma desde el flujo de pago; ambas se confirman con el contexto `l10n_ve_skip_future_date_check`. El contexto por sí solo no basta (se puede enviar por RPC): el guard solo lo respeta si `_l10n_ve_allows_future_date()` devuelve `True` para el documento. Ese método devuelve `False` por defecto y lo sobreescriben `l10n_ve_exchange_difference` (notas con `l10n_ve_exchange_diff_entry` y `l10n_ve_exchange_payment_id`) y `l10n_ve_igtf_note_debit` (ND con `l10n_ve_igtf_note_debit_origin`, `origin_payment_to_pay_igtf` y `debit_origin_id`). Esas marcas no se exponen en ningún formulario ni las escribe un `onchange`. La fecha de la ND de IGTF no cambia (hoy; su cálculo es en VEF).

#### Scenario: Factura de venta con invoice_date_display posterior a hoy

- **WHEN** se confirma una factura de venta cuyo `invoice_date_display` es posterior a hoy
- **THEN** se lanza un error de validación indicando que esa fecha no puede ser posterior a hoy

#### Scenario: Nota de crédito con invoice_date_display futuro

- **WHEN** se confirma una nota de crédito de venta cuyo `invoice_date_display` es posterior a hoy
- **THEN** se lanza un error de validación

#### Scenario: Fecha contable futura no se bloquea

- **WHEN** se confirma una factura de proveedor cuyo `date` (fecha contable) es posterior a hoy y `invoice_date_display` es hoy o anterior
- **THEN** la confirmación procede con normalidad

#### Scenario: Recibo de venta o de compra con fecha futura

- **WHEN** se confirma un recibo (`out_receipt`/`in_receipt`) cuyo `invoice_date_display` es posterior a hoy
- **THEN** se lanza el mismo error de validación que en una factura

#### Scenario: Nota de débito hereda el guard de su action_post

- **WHEN** se confirma una nota de débito (venta o compra) con `invoice_date_display` posterior a hoy
- **THEN** se lanza el mismo error de validación, sin código específico para notas de débito

#### Scenario: Un asiento contable puro no se valida

- **WHEN** se confirma un `account.move` con `move_type = 'entry'` y `date` posterior a hoy
- **THEN** la confirmación procede con normalidad; el guard no aplica a asientos

#### Scenario: Guardar un borrador con fecha futura no se bloquea

- **WHEN** se crea o guarda en borrador una factura, nota de crédito, nota de débito o recibo con alguna fecha futura, sin confirmarla
- **THEN** el guardado se permite; el bloqueo solo aplica al llamar `action_post`

#### Scenario: Fecha de hoy confirma sin error

- **WHEN** se confirma un documento con `invoice_date_display` hoy o anterior e `invoice_date` no posterior a `invoice_date_display`
- **THEN** la confirmación procede con normalidad

#### Scenario: Nota confirmada con fecha anterior a su origen

- **WHEN** se edita en borrador una nota de crédito o de débito con `invoice_date_display` anterior al del origen y se confirma
- **THEN** se lanza un error de validación indicando la fecha del documento original

#### Scenario: invoice_date posterior a invoice_date_display

- **WHEN** se confirma un documento cuyo `invoice_date` es posterior a su `invoice_date_display`
- **THEN** se lanza un error de validación

#### Scenario: El contexto de exención no basta

- **WHEN** se confirma una factura común con fecha futura y el contexto `l10n_ve_skip_future_date_check=True`
- **THEN** el guard sigue bloqueándola, porque `_l10n_ve_allows_future_date()` es `False`

#### Scenario: Nota automática con exención

- **WHEN** se confirma una ND/NC de diferencial cambiario o una ND de IGTF con el contexto de exención
- **THEN** el guard no la bloquea

#### Scenario: Confirm Entries no esquiva el guard

- **WHEN** se confirma desde la lista, el kanban o el asistente "Confirm Entries" (con o sin "Force") un borrador cuya fecha no cumple las reglas del guard
- **THEN** se lanza el mismo error de validación y el documento sigue en borrador

#### Scenario: Tasa de una nota distinta a la de su origen

- **WHEN** se confirma una nota de crédito o de débito cuyo `invoice_date` (tasa) es distinto al de su documento origen
- **THEN** se lanza un error de validación, también en notas de proveedor

#### Scenario: Fecha contable de una nota editada antes de su fecha de documento

- **WHEN** se edita la fecha contable (`date`) de una nota para que sea anterior a su `invoice_date_display` y se guarda
- **THEN** se lanza un error de validación y no se guarda

