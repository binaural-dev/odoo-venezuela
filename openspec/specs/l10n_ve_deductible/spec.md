# l10n_ve_deductible

## Purpose

Descuento global "deducible" para facturas de proveedor (porcentaje o monto fijo) con impuestos exentos. Se activa por compañía desde Ajustes (`res.company.use_deductible`, bloque "Deducibles") y, ya activo, la factura de proveedor muestra, en la pestaña de líneas y justo debajo de "Términos y condiciones" (`narration`), el booleano `is_deductible`, el tipo (`global_deductible_type`: porcentaje o monto fijo), el valor (`global_deductible_percent` o `global_deductible_amount`) y, solo en modo porcentaje, un monto referencial (`global_deductible_reference_amount`) con lo que ese porcentaje representa. En modo monto fijo el importe que se resta a cada línea se guarda en `account.move.line.global_deductible_line_amount` (solo lectura, visible solo en ese modo); de él (o del porcentaje de la factura en modo porcentaje) sale `account.move.line.global_deductible_discount_percent` (Float almacenado, sin redondeo a propósito) que se inyecta en el cálculo de impuestos como si fuera el descuento nativo, sin escribir sobre `discount` ni `discount_fixed`. Depende de `l10n_ve_accountant` y de `l10n_ve_invoice` (de donde sale `discount_fixed`, que el módulo oculta y valida) y se auto-instala cuando ambos están instalados: la dependencia de `l10n_ve_invoice` es intencional. Extiende en `l10n_ve_accountant` los ganchos `_get_base_line_sync_extra_fields()` (para que `_sync_tax_lines` vigile el campo nuevo) y `_get_effective_discount_percent()` (para las líneas con impuesto de precio incluido, cuyo apunte se reconstruye a mano).

## Requirements

### Requirement: Activación por compañía y alcance

El deducible DEBE (MUST) poder usarse solo si la compañía tiene `use_deductible` activo y solo en facturas de proveedor (`in_invoice`); las notas de crédito de proveedor (`in_refund`) lo admiten únicamente cuando revierten una factura deducible. Cualquier otro tipo de documento, o una compañía con la opción apagada, DEBE (MUST) producir un `ValidationError` aunque se intente por RPC o importación.

#### Scenario: Compañía con la opción apagada

- **WHEN** se crea una factura de proveedor con `is_deductible = True` en una compañía con `use_deductible` apagado
- **THEN** se lanza un error de validación y la factura no se guarda

### Requirement: Solo líneas con impuesto exento y sin descuento previo

Una factura con `is_deductible` DEBE (MUST) tener todas las líneas de producto con impuestos exentos (los configurados como alícuota exenta de compra de la compañía, o impuestos en porcentaje al 0 %; un impuesto exento con precio incluido también se admite) y sin `discount` ni `discount_fixed`. Al activar el booleano, el `onchange` DEBE (MUST) mostrar una advertencia y dejar el deducible apagado si hay líneas inválidas; al agregar luego una línea inválida DEBE (MUST) advertir y el guardado DEBE (MUST) fallar. Las columnas de descuento nativas DEBEN (MUST) ocultarse y quedar de solo lectura mientras la factura es deducible.

#### Scenario: Línea gravada

- **WHEN** se activa el deducible en una factura con una línea con IVA 16 %
- **THEN** aparece la advertencia, `is_deductible` queda en falso y, si se intenta por servidor, se lanza un `ValidationError`

### Requirement: Límites del valor deducible

En modo porcentaje, el valor DEBE (MUST) ser mayor que 0 y menor que 100. En modo monto, DEBE (MUST) ser mayor que 0 y menor que el total original (suma de `price_unit * quantity` de las líneas de producto), porque no se puede deducir el 100 % de una factura. Estas reglas DEBEN (MUST) reevaluarse cuando cambian precios, cantidades o líneas.

#### Scenario: Bajar precios hasta alcanzar el monto

- **WHEN** con un deducible de 15 se bajan los precios de dos líneas de 10 a 5
- **THEN** se lanza un error de validación porque el monto ya no es menor que el total original

### Requirement: Reparto equivalente al descuento nativo y a `discount_fixed`

En modo porcentaje todas las líneas DEBEN (MUST) recibir el mismo porcentaje exacto. En modo monto cada línea DEBE (MUST) recibir y guardar en `global_deductible_line_amount` un importe proporcional a su subtotal bruto, expresado en la moneda del documento (campo `Monetary`) y repartido por mayor residuo en centavos sin que ninguna línea alcance su propio subtotal, y su porcentaje equivalente DEBE (MUST) calcularse como `(importe / bruto) * 100`, igual que `discount_fixed`. La suma de los importes de las líneas DEBE (MUST) ser siempre exactamente el monto ingresado en la factura, el importe de cada línea DEBE (MUST) ser menor que su subtotal bruto, y el campo es de solo lectura: cualquier escritura que rompa la suma produce un `ValidationError`. Con los mismos importes, los resultados (subtotales y totales por línea, totales de la factura, apuntes contables, montos en moneda alterna, totales del widget y de `company_currency_line_totals`) DEBEN (MUST) coincidir exactamente con los del descuento nativo (%) y con los de `discount_fixed`, con ambos métodos de redondeo de impuestos y con facturas en la moneda base (VEF) o en la alterna (USD).

#### Scenario: Suma de los importes por línea

- **WHEN** una factura tiene un deducible fijo de 77,77 y varias líneas con precios de 4 decimales
- **THEN** la suma de `global_deductible_line_amount` de las líneas es exactamente 77,77, también tras cambiar precios o agregar líneas

#### Scenario: Paridad con el descuento nativo

- **WHEN** se compara una factura deducible al 12,5 % con la misma factura con `discount = 12.5` en cada línea, en `round_per_line` y en `round_globally`
- **THEN** todas las cifras comparadas son idénticas

### Requirement: Desactivar, ajustar y reversar

Al desactivar `is_deductible` DEBE (MUST) revertirse todo (tipo, porcentaje, monto y descuento por línea). Mientras está activo, cambiar precios o cantidades o agregar líneas DEBE (MUST) redistribuir el deducible. El deducible DEBE (MUST) poder cambiarse solo en borrador. Al reversar una factura deducible, la nota de crédito DEBE (MUST) conservar el mismo deducible; al duplicar una factura NO se copia.

#### Scenario: Nota de crédito

- **WHEN** se reversa y cancela una factura deducible confirmada
- **THEN** la nota de crédito es deducible, tiene el mismo total y subtotales por línea y la factura queda saldada

### Requirement: El deducible vive en las notas

Las notas creadas a partir de una factura deducible DEBEN (MUST) conservar el mismo deducible (tipo y valor): la nota de crédito (el deducible solo se puede activar en ella por reversión), la factura de reemplazo de "reversar y modificar" y la nota de débito cuando se copian las líneas (sin líneas copiadas la nota de débito empieza sin deducible, porque no hay líneas sobre las que deducir). Duplicar una factura NO copia el deducible.

#### Scenario: Nota de débito con líneas copiadas

- **WHEN** se crea una nota de débito con "copiar líneas" desde una factura deducible confirmada
- **THEN** la nota es deducible con el mismo tipo y valor, y con los mismos totales y apuntes que la factura

### Requirement: Multicompañía

La activación (`use_deductible`), la alícuota exenta de compra y todas las validaciones DEBEN (MUST) usar la compañía de la factura, nunca la compañía en la que esté trabajando el usuario; la pantalla de Ajustes DEBE (MUST) editar solo la compañía actual. Con dos compañías, el mismo documento da las mismas cifras en ambas.

#### Scenario: Una compañía con la opción apagada

- **WHEN** la compañía A tiene `use_deductible` activo y la B apagado, y se intenta una factura deducible en cada una
- **THEN** la de A se crea y la de B falla con un error de validación, sin importar la compañía activa del usuario

### Requirement: Consistencia al vuelo en el formulario

Mientras se edita la factura en el formulario, después de CADA cambio (activar el deducible, cambiar su tipo o valor, editar un precio o una cantidad, agregar o quitar un producto) lo que muestra el formulario DEBE (MUST) ser exactamente lo que daría una factura creada directamente con las mismas líneas y el mismo deducible: totales de la factura, subtotal de cada línea, y, en modo monto, el importe de cada línea con la suma igual al monto ingresado. Para ello el `onchange` de la factura asigna explícitamente `global_deductible_line_amount` y `global_deductible_discount_percent` en cada línea (los campos calculados almacenados no se refrescan solos desde un cambio de la factura en el formulario).

#### Scenario: Agregar un producto con el deducible activo

- **WHEN** con un deducible fijo de 20 se agrega una línea nueva y luego se edita su precio y su cantidad
- **THEN** los subtotales de todas las líneas, el total y los importes por línea mostrados coinciden con los de una factura creada directamente, y los importes suman 20

### Requirement: Filas del widget `tax_totals` y reportes

Con `is_deductible` activo, los tres widgets de totales (moneda del documento, alterna y Bs) y el reporte de forma libre DEBEN (MUST) mostrar antes del subtotal las filas "Subtotal sin deducible" (monto base más deducible) y "Deducible". El deducible DEBE (MUST) mostrarse como la conversión exacta del monto deducible a cada moneda y no como la suma de importes redondeados por línea; el reporte de forma libre DEBE (MUST) mostrar además la columna "Desc.%" con el porcentaje deducible de cada línea, y el detalle de facturas (`detailed_amounts`) DEBE (MUST) calcular bruto, descuento y neto con el deducible.

#### Scenario: Factura en USD con base VEF

- **WHEN** una factura en USD tiene un deducible de 77,77 y la tasa es 1 USD = 38 VEF
- **THEN** el widget en Bs muestra un deducible de 2.955,26 y "Subtotal sin deducible − Deducible" es igual al total en Bs
