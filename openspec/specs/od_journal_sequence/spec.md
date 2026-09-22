# od_journal_sequence

## Purpose

Módulo de terceros vendorizado ("Journal Sequence For Odoo 18", licencia OPL-1) que restaura la numeración de asientos por secuencia configurable en cada diario: cada `account.journal` lleva una secuencia de asientos (`ir.sequence`) y opcionalmente una de notas de crédito, y el nombre del asiento se asigna desde esa secuencia al publicarse, desactivando la numeración nativa de Odoo basada en el último nombre. Extiende `account.journal` y `account.move`. Depende de `account`.

## Requirements

### Requirement: Secuencia automática al crear un diario

Al crear un `account.journal` sin `sequence_id`, el sistema DEBE (MUST) crear automáticamente una `ir.sequence` (vía `_prepare_sequence`) con implementación `no_gap`, prefijo `<CODIGO>/%(range_year)s/` (código del diario en mayúsculas), `padding` 4, `use_date_range` activo y la compañía del diario (o la compañía activa en su defecto). El campo `sequence_id` es requerido en el diario.

#### Scenario: Creación de un diario nuevo

- **WHEN** se crea un diario con código `VEN` sin indicar secuencia
- **THEN** el diario queda con una secuencia `no_gap` de prefijo `VEN/%(range_year)s/`, padding 4 y rangos por fecha

### Requirement: Secuencia de notas de crédito para diarios de venta y compra

Al crear un `account.journal` de tipo `sale` o `purchase` con `refund_sequence` activo y sin `refund_sequence_id`, el sistema DEBE (MUST) crear automáticamente una secuencia de reembolso con prefijo `R<CODIGO>/%(range_year)s/` y asignarla en `refund_sequence_id`.

#### Scenario: Diario de venta con secuencia de reembolso

- **WHEN** se crea un diario de tipo `sale` con `refund_sequence` activo y código `VEN`
- **THEN** el diario queda con una secuencia de notas de crédito de prefijo `RVEN/%(range_year)s/`

### Requirement: Numeración del asiento desde la secuencia del diario al publicar

El nombre (`name`) de un `account.move` DEBE (MUST) calcularse (`_compute_name_by_sequence`) tomando el siguiente número de la secuencia del diario cuando el asiento pasa a estado `posted` y su nombre está vacío o es `/`: usa `refund_sequence_id` si el movimiento es `out_refund` o `in_refund` en un diario `sale`/`purchase` con `refund_sequence` activo, y `sequence_id` en cualquier otro caso; la secuencia se consume con la fecha del asiento (`move.date`) como `sequence_date`, de modo que el rango de fechas aplicado corresponde a esa fecha.

#### Scenario: Publicación de una factura

- **WHEN** se publica una factura sin nombre asignado en un diario con secuencia
- **THEN** el nombre se toma del siguiente número de `sequence_id` usando la fecha del asiento para el rango

#### Scenario: Publicación de una nota de crédito

- **WHEN** se publica una nota de crédito (`out_refund`) en un diario de venta con `refund_sequence` y `refund_sequence_id` configurados
- **THEN** el nombre se toma de la secuencia de reembolso del diario

#### Scenario: Asiento ya numerado

- **WHEN** se recalcula el nombre de un asiento que ya tiene un nombre distinto de `/`
- **THEN** el nombre existente se conserva sin consumir la secuencia

### Requirement: Secuencias de asiento y de reembolso distintas

El sistema DEBE (MUST) impedir, vía constraint sobre `sequence_id` y `refund_sequence_id` de `account.journal`, que un diario use la misma secuencia como secuencia de asientos y como secuencia de notas de crédito.

#### Scenario: Misma secuencia en ambos campos

- **WHEN** se asigna a un diario la misma `ir.sequence` en `sequence_id` y `refund_sequence_id`
- **THEN** se lanza un error de validación indicando que el diario usa la misma secuencia para ambos propósitos

### Requirement: Compañía obligatoria en las secuencias del diario

El sistema DEBE (MUST) impedir, vía constraint en `account.journal`, que la secuencia de asientos o la de notas de crédito de un diario sea una `ir.sequence` sin compañía (`company_id`) establecida.

#### Scenario: Secuencia sin compañía

- **WHEN** se configura en un diario una secuencia cuyo `company_id` está vacío
- **THEN** se lanza un error de validación indicando que la compañía no está establecida en la secuencia

### Requirement: Próximo número configurable desde el diario

Los campos `sequence_number_next` y `refund_sequence_number_next` de `account.journal` DEBEN (MUST) mostrar el próximo número de la secuencia vigente (`_get_current_sequence`) y, al escribirse, actualizar el `number_next` de esa secuencia (con `sudo()`); `refund_sequence_number_next` solo opera cuando el diario tiene `refund_sequence` activo, y ambos muestran `1` cuando no hay secuencia aplicable.

#### Scenario: Ajuste del próximo número

- **WHEN** un usuario escribe un valor en "Next Number" del formulario del diario
- **THEN** la secuencia vigente del diario queda con ese valor como próximo número

### Requirement: Generación de secuencias para diarios existentes al instalar

El hook post-instalación (`create_journal_sequences`) DEBE (MUST) crear y asignar una secuencia de asientos a todos los diarios existentes (incluidos los archivados), y adicionalmente una secuencia de reembolso a los diarios `sale`/`purchase` con `refund_sequence` activo, usando el mismo formato de `_prepare_sequence`.

#### Scenario: Instalación del módulo

- **WHEN** se instala el módulo en una base con diarios existentes
- **THEN** cada diario queda con su `sequence_id` creada, y los de venta/compra con reembolso también con su `refund_sequence_id`

### Requirement: Número de asiento no editable y resecuenciación nativa deshabilitada

El sistema DEBE (MUST) impedir la renumeración manual de asientos: el campo `name` se muestra de solo lectura en el formulario de `account.move`, y la regla de acceso nativa del asistente de resecuenciación (`account.resequence.wizard`) se sobrescribe (xml id `account.access_account_resequence`) revocando todos los permisos al grupo `account.group_account_manager`.

#### Scenario: Intento de renumerar manualmente

- **WHEN** un contador abre un asiento e intenta editar su número o usar el asistente nativo de resecuenciación
- **THEN** el campo `name` es de solo lectura y el asistente de resecuenciación no es accesible

### Requirement: Desactivación de la validación nativa de coherencia nombre-fecha

El sistema DEBE (MUST) anular la validación estándar `_constrains_date_sequence` de `account.move` (retorna `True` sin validar), de modo que la fecha del asiento no se restringe por el patrón de fecha contenido en su nombre.

#### Scenario: Asiento con nombre que no coincide con la fecha

- **WHEN** se guarda un asiento cuyo nombre contiene un año o mes distinto al de su fecha
- **THEN** no se lanza el error nativo de coherencia entre nombre y fecha
