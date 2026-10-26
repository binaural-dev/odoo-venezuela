# l10n_ve_deductible

## Purpose

Descuento global "deducible" (porcentaje o monto fijo) para facturas de proveedor y de cliente, con o sin impuestos. Se activa por compañía desde Ajustes (`res.company.use_deductible`, bloque "Deducibles") y la opción `deductible_scope` decide en qué documentos se ofrece: facturas de proveedor (`vendor`), facturas de cliente (`customer`, por defecto) o ambas (`both`).

Donde está habilitado, el documento muestra en la pestaña de líneas, justo debajo de "Términos y condiciones" (`narration`): el booleano `is_deductible`, el tipo (`global_deductible_type`: porcentaje o monto fijo), el valor (`global_deductible_percent` o `global_deductible_amount`) y, solo en modo porcentaje, un monto referencial (`global_deductible_reference_amount`). En modo monto fijo el importe que se resta a cada línea se guarda en `account.move.line.global_deductible_line_amount` (monetario, editable en documentos en borrador, visible solo en ese modo); de él, o del porcentaje del documento en modo porcentaje, sale `account.move.line.global_deductible_discount_percent` (Float almacenado, sin redondeo a propósito, de solo lectura; en modo monto fijo es solo un valor interno que usa el cálculo de impuestos y no se muestra; en modo porcentaje se ve como columna «Deducido (%)» con el porcentaje del documento).

El módulo no escribe sobre `discount` ni `discount_fixed`: el porcentaje se enchufa en `_get_effective_discount_percent()`, el gancho que `l10n_ve_accountant` usa para el cálculo de impuestos, el subtotal en moneda alterna, los totales en moneda de la compañía, el detalle de importes y el apunte de las líneas con precio incluido. Depende de `l10n_ve_accountant` y de `l10n_ve_invoice` (de donde sale `discount_fixed`, que el módulo oculta y valida) y se auto-instala cuando ambos están instalados; la dependencia de `l10n_ve_invoice` es intencional. Extiende además `_get_base_line_sync_extra_fields()` para que `_sync_tax_lines` vigile el campo nuevo.

Fuera de alcance: las máquinas fiscales y la factura digital no leen el deducible (usan `discount`); si se contemplan, se hacen en un módulo aparte.

## Requirements

### Requirement: Activación por compañía y alcance

El deducible DEBE (MUST) poder usarse solo si la compañía tiene `use_deductible` activo y el tipo de documento coincide con `deductible_scope`. Las notas de crédito (`in_refund`, `out_refund`) lo admiten únicamente cuando revierten un documento deducible. Cualquier otro tipo de documento (por ejemplo recibos), o un tipo no habilitado por la compañía, DEBE (MUST) producir un `ValidationError` aunque se intente por RPC o importación.

La validación de que el tipo esté habilitado se hace solo al activar el deducible (al crear un documento ya deducible o al marcar `is_deductible`), de modo que un documento que ya era deducible sigue usable si después se apaga la opción o se cambia el alcance: se puede seguir editando, y la nota de crédito, la nota de débito con líneas copiadas y la factura de reemplazo de "reversar y modificar" heredan el deducible de su origen sin importar el alcance actual. Activarlo en un documento que no lo era sí exige el tipo habilitado.

#### Scenario: Alcance solo proveedor

- **WHEN** la compañía tiene `deductible_scope = vendor` y se crea una factura de cliente con `is_deductible = True`
- **THEN** se lanza un error de validación y la factura no se guarda, mientras que una factura de proveedor sí se crea

#### Scenario: Compañía con la opción apagada

- **WHEN** se crea una factura de proveedor o de cliente con `is_deductible = True` en una compañía con `use_deductible` apagado
- **THEN** se lanza un error de validación y el documento no se guarda

### Requirement: Líneas sin descuento previo

Un documento con `is_deductible` DEBE (MUST) tener todas las líneas de producto sin `discount` ni `discount_fixed`; el deducible NO se limita a líneas con impuestos exentos: acepta cualquier impuesto y este se calcula sobre la base resultante tras el deducible. Al activar el booleano, el `onchange` DEBE (MUST) mostrar una advertencia y dejar el deducible apagado si hay líneas con descuento; al agregar luego una línea con descuento DEBE (MUST) advertir y el guardado DEBE (MUST) fallar. Las columnas de descuento nativas DEBEN (MUST) ocultarse y quedar de solo lectura mientras el documento es deducible.

#### Scenario: Línea gravada

- **WHEN** se activa el deducible en un documento con una línea con IVA 16 %
- **THEN** el deducible se activa sin advertencia y el IVA se calcula sobre la base tras el deducible

#### Scenario: Línea con descuento previo

- **WHEN** se activa el deducible en un documento con una línea con descuento
- **THEN** aparece la advertencia, `is_deductible` queda en falso y, si se intenta por servidor, se lanza un `ValidationError`

### Requirement: Límites del valor deducible

En modo porcentaje, el valor DEBE (MUST) ser mayor que 0 y menor que 100. En modo monto, DEBE (MUST) ser mayor que 0 y menor que el total original (suma de `price_unit * quantity` de las líneas de producto), porque no se puede deducir el 100 % de un documento. Estas reglas DEBEN (MUST) reevaluarse cuando cambian precios, cantidades o líneas.

#### Scenario: Bajar precios hasta alcanzar el monto

- **WHEN** con un deducible de 15 se bajan los precios de dos líneas de 10 a 5
- **THEN** se lanza un error de validación porque el monto ya no es menor que el total original

### Requirement: Reparto equivalente al descuento nativo y a `discount_fixed`

En modo porcentaje todas las líneas DEBEN (MUST) recibir el mismo porcentaje exacto. En modo monto cada línea con importe bruto mayor que 0 DEBE (MUST) recibir y guardar en `global_deductible_line_amount` un importe propuesto proporcional a su subtotal bruto, en la moneda del documento, repartido por mayor residuo en centavos sin que ninguna línea alcance su propio subtotal; su porcentaje equivalente DEBE (MUST) calcularse como `(importe / bruto) * 100`, igual que `discount_fixed`. El usuario PUEDE (MAY) escribir a mano el importe de una línea (documentos en borrador): la línea queda marcada en `global_deductible_manual`, conserva su importe y lo que resta del monto del documento se reparte, con el mismo algoritmo, entre las líneas no marcadas; cambiar el tipo o el valor del documento vuelve a proponer todos los importes. La suma de los importes de las líneas DEBE (MUST) ser exactamente el monto ingresado y ninguna línea puede alcanzar su propio subtotal: ambas reglas producen un `ValidationError`. La suma se valida sobre el documento (al guardarlo con sus líneas y al publicarlo) y no línea por línea, porque las líneas de un documento se escriben una a una. Una nota de crédito o de débito con líneas copiadas conserva los importes escritos a mano. Con los mismos importes por línea, las cifras del documento (subtotales y totales, apuntes, montos en moneda alterna, totales del widget y de `company_currency_line_totals`) DEBEN (MUST) coincidir exactamente con las del descuento nativo (%) y con las de `discount_fixed`, con ambos métodos de redondeo de impuestos y con documentos en la moneda base (VEF) o en la alterna (USD).

Las líneas con importe bruto menor o igual que 0 no participan del reparto en modo monto, pero sí cuentan en el total original que limita el monto; en modo porcentaje reciben el mismo porcentaje que las demás.

#### Scenario: Suma de los importes por línea

- **WHEN** un documento tiene un deducible fijo de 77,77 y varias líneas con precios de 4 decimales
- **THEN** la suma de `global_deductible_line_amount` de las líneas es exactamente 77,77, también tras cambiar precios o agregar líneas

#### Scenario: Importe escrito a mano en una línea

- **WHEN** un documento con un deducible fijo de 60 y tres líneas de 100, 200 y 300 tiene el importe de la primera línea escrito a mano en 30
- **THEN** la primera línea conserva 30, queda marcada como escrita a mano y el resto (30) se reparte entre las otras dos (12 y 18); el porcentaje interno de cada línea se actualiza y la suma sigue siendo 60

#### Scenario: Importes escritos a mano que no suman el monto

- **WHEN** se guardan o se publican importes por línea cuya suma es distinta del monto del deducible, o una línea con un importe igual o mayor a su subtotal
- **THEN** se lanza un `ValidationError` y el documento no se guarda ni se publica

#### Scenario: Paridad con el descuento nativo

- **WHEN** se compara un documento deducible al 12,5 % con el mismo documento con `discount = 12.5` en cada línea, en `round_per_line` y en `round_globally`
- **THEN** todas las cifras comparadas son idénticas

### Requirement: Desactivar, ajustar y reversar

Al desactivar `is_deductible` DEBEN (MUST) ponerse en cero el porcentaje, el monto y los importes y porcentajes por línea (el tipo conserva su valor). Mientras está activo, cambiar precios o cantidades o agregar líneas DEBE (MUST) redistribuir el deducible. El deducible DEBE (MUST) poder cambiarse solo en borrador. Duplicar un documento NO copia el deducible.

#### Scenario: Desactivar

- **WHEN** se desmarca `is_deductible` en un borrador con un deducible por monto
- **THEN** el monto y los importes por línea quedan en cero y el documento da exactamente las mismas cifras que uno sin deducible

### Requirement: El deducible vive en las notas

Las notas creadas a partir de un documento deducible DEBEN (MUST) conservar el mismo deducible (tipo y valor): la nota de crédito (el deducible solo se puede activar en ella por reversión; su tipo y valor siguen editables en borrador), la factura de reemplazo de "reversar y modificar" y la nota de débito cuando se copian las líneas (sin líneas copiadas la nota de débito empieza sin deducible, porque no hay líneas sobre las que deducir).

#### Scenario: Nota de crédito

- **WHEN** se reversa y cancela un documento deducible confirmado
- **THEN** la nota de crédito es deducible, tiene el mismo total y subtotales por línea y el documento queda saldado

#### Scenario: Nota de débito con líneas copiadas

- **WHEN** se crea una nota de débito con "copiar líneas" desde un documento deducible confirmado
- **THEN** la nota es deducible con el mismo tipo y valor, y con los mismos totales y apuntes que el documento

### Requirement: Multicompañía

La activación (`use_deductible`), el alcance (`deductible_scope`), y todas las validaciones DEBEN (MUST) usar la compañía del documento, nunca la compañía en la que esté trabajando el usuario; la pantalla de Ajustes DEBE (MUST) editar solo la compañía actual. Con dos compañías, el mismo documento da las mismas cifras en ambas.

#### Scenario: Una compañía con la opción apagada

- **WHEN** la compañía A tiene `use_deductible` activo y la B apagado, y se intenta un documento deducible en cada una
- **THEN** el de A se crea y el de B falla con un error de validación, sin importar la compañía activa del usuario

### Requirement: Consistencia al vuelo en el formulario

Mientras se edita el documento en el formulario, después de CADA cambio (activar el deducible, cambiar su tipo o valor, editar un precio o una cantidad, agregar o quitar un producto) lo que muestra el formulario DEBE (MUST) ser exactamente lo que daría un documento creado directamente con las mismas líneas y el mismo deducible: totales, subtotal de cada línea y, en modo monto, el importe de cada línea con la suma igual al monto ingresado. Para ello el `onchange` del documento asigna explícitamente `global_deductible_line_amount` y `global_deductible_discount_percent` en cada línea, porque los campos calculados almacenados no se refrescan solos desde un cambio del documento en el formulario.

#### Scenario: Agregar un producto con el deducible activo

- **WHEN** con un deducible fijo de 20 se agrega una línea nueva y luego se edita su precio y su cantidad
- **THEN** los subtotales de todas las líneas, el total y los importes por línea mostrados coinciden con los de un documento creado directamente, y los importes suman 20

### Requirement: Ubicación y visibilidad de los campos

La sección del deducible DEBE (MUST) ir en el grupo de "Términos y condiciones" (`narration`) de la pestaña de líneas, justo después de ese campo y a la izquierda de los totales, con `narration` ocupando las dos columnas del grupo (`colspan=2`) para que las etiquetas y los valores queden alineados; ningún campo del deducible va en el encabezado. El booleano se ofrece si el tipo está habilitado (o si el documento ya es deducible, para poder desmarcarlo) y es de solo lectura en notas de crédito y fuera de borrador; el tipo y el valor se muestran solo con el deducible activo y son de solo lectura fuera de borrador; el porcentaje solo en tipo porcentaje, el monto solo en tipo monto y el monto referencial solo en tipo porcentaje. La columna `global_deductible_line_amount` (etiqueta "Deducido") va justo después de `discount` en la lista de líneas, de solo lectura y solo con el deducible activo en modo monto. En Ajustes, el bloque "Deducibles" muestra el alcance solo cuando `use_deductible` está activo.

#### Scenario: Documento de proveedor con deducible fijo

- **WHEN** se abre un borrador de factura de proveedor con deducible por monto fijo
- **THEN** debajo de "Términos y condiciones" aparecen el booleano, el tipo y el monto alineados, sin monto referencial, y la lista de líneas muestra la columna "Deducido" con el importe de cada línea

### Requirement: Filas del widget `tax_totals` y reportes

Con `is_deductible` activo, los tres widgets de totales (moneda del documento, alterna y Bs) y el reporte de forma libre DEBEN (MUST) mostrar antes del subtotal las filas "Subtotal sin deducible" (monto base más deducible) y "Deducible". El deducible DEBE (MUST) mostrarse como la conversión exacta del monto deducible a cada moneda y no como la suma de importes redondeados por línea; el reporte de forma libre DEBE (MUST) mostrar además la columna "Desc.%" con el porcentaje deducible de cada línea, y el detalle de importes (`detailed_amounts`) DEBE (MUST) calcular bruto, descuento y neto con el deducible.

"Subtotal sin deducible" se calcula como la base contabilizada más el deducible; en modo porcentaje con `round_per_line` puede diferir en unos centavos del total que el mismo documento tendría sin deducible.

#### Scenario: Documento en USD con base VEF

- **WHEN** un documento en USD tiene un deducible de 77,77 y la tasa de ese día es 1 USD = 38 VEF
- **THEN** el widget en Bs muestra un deducible de 2.955,26 y "Subtotal sin deducible − Deducible" es igual al subtotal contabilizado en Bs

### Requirement: Limitaciones conocidas

El deducible no genera los apuntes de asignación de descuento que Odoo crea a partir de `discount` cuando la compañía configura las cuentas `account_discount_*_allocation_id`; `discount_fixed` comparte esa limitación.

#### Scenario: Compañía con cuentas de asignación de descuento

- **WHEN** la compañía usa cuentas de asignación de descuento y un documento tiene un descuento nativo
- **THEN** Odoo genera apuntes de asignación que un documento con deducible equivalente no genera
