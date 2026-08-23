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

### Requirement: Solo documentos confirmados se imprimen

`ir.actions.report` DEBE (MUST) filtrar las impresiones (PDF y HTML) de `account.move` a documentos en estado `posted` y las de `sale.order` a órdenes no borrador, lanzando un error cuando ningún documento seleccionado cumple la condición.

#### Scenario: Imprimir factura en borrador

- **WHEN** se solicita el PDF de una factura no publicada
- **THEN** se lanza un error indicando que solo se imprimen documentos publicados

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

El wizard `wizard.accounting.reports` DEBE (MUST) seleccionar para el libro los documentos de la compañía con estado `posted` o `cancel`, `correlative` asignado (distinto de `/` y de vacío), fecha contable dentro del rango solicitado, y tipo según el libro (`out_invoice`/`out_refund` para ventas; `in_invoice`/`in_refund`/`in_debit` para compras), ordenados por correlativo en ventas y por fecha de documento en compras; cuando todas las columnas internacionales están ocultas por configuración, el libro de compras excluye los diarios internacionales.

#### Scenario: Generación del libro de ventas

- **WHEN** se genera el libro de ventas de un período
- **THEN** solo aparecen documentos de venta publicados o anulados con número de control dentro del rango de fechas

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

Las rutas `/web/download_sales_book` y `/web/download_purchase_book` DEBEN (MUST) requerir usuario autenticado (`auth="user"`) y devolver el XLSX como adjunto (`Libro_de_venta.xlsx` / `Libro_de_compra.xlsx`), con la hoja protegida contra edición mediante contraseña. La lectura se hace con un entorno elevado a `SUPERUSER_ID`: se toma el último registro `wizard.accounting.reports` creado en la base —sin filtrar por usuario ni por compañía— y se le escribe como `company_id` el parámetro `company_id` de la URL (1 por defecto) antes de generar el libro, de modo que el contenido depende de ese parámetro y no de la compañía activa del usuario.

#### Scenario: Descarga del libro de compras

- **WHEN** un usuario autenticado ejecuta la generación del libro de compras
- **THEN** el navegador descarga `Libro_de_compra.xlsx` generado a partir del último wizard creado, con la compañía indicada en el parámetro `company_id`

#### Scenario: Parámetro de compañía en la URL

- **WHEN** se invoca la ruta con un `company_id` distinto del de la compañía activa
- **THEN** el libro se genera para la compañía indicada en el parámetro, sin control de acceso adicional por parte del controlador
