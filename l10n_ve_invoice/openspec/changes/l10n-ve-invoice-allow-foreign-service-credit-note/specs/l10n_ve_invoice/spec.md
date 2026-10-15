## MODIFIED Requirements

### Requirement: Productos de una Nota de Crédito restringidos a la factura origen
El sistema DEBE (MUST) impedir que una Nota de Crédito (`out_refund`/`in_refund`) con `reversed_entry_id` incluya un producto **Almacenable o Consumible** que no esté presente en las líneas de producto de la factura que revierte, salvo que la creación se realice con la clave de contexto `l10n_ve_skip_refund_origin_validation` activa. Un producto de tipo **Servicio** ajeno a la factura origen SIEMPRE se permite (queda sujeto al tope agregado del `Requirement` siguiente), sin necesidad del bypass.

#### Scenario: Producto presente en la factura origen
- **WHEN** se crea o edita una Nota de Crédito cuyas líneas de producto son un subconjunto de los productos de su factura origen
- **THEN** la Nota de Crédito se guarda sin error

#### Scenario: Producto Almacenable/Consumible ajeno a la factura origen
- **WHEN** se crea o edita una Nota de Crédito agregando un producto de tipo Almacenable o Consumible que la factura origen nunca facturó
- **THEN** el sistema rechaza la operación con un `ValidationError` indicando el producto y la factura origen

#### Scenario: Producto tipo Servicio ajeno a la factura origen
- **WHEN** se crea o edita una Nota de Crédito agregando un producto de tipo Servicio que la factura origen nunca facturó
- **THEN** el sistema permite la operación sin error, siempre que el monto total acreditado no supere el total facturado en el origen

#### Scenario: Edición directa de una línea ya creada
- **WHEN** se modifica el `product_id` de una línea de una Nota de Crédito ya existente, sin pasar por el `write()` del documento padre
- **THEN** la validación se ejecuta igual y rechaza el producto Almacenable/Consumible ajeno

#### Scenario: Bypass explícito para módulos automáticos
- **WHEN** un módulo crea la Nota de Crédito con el contexto `l10n_ve_skip_refund_origin_validation=True`
- **THEN** la validación de producto y monto no se ejecuta, cualquiera sea el producto usado

## ADDED Requirements

### Requirement: Monto total de servicios ajenos al origen no puede superar lo facturado en el origen
El sistema DEBE (MUST) impedir que la suma de lo acreditado por productos de tipo Servicio ajenos a la factura origen, más lo acreditado por productos presentes en el origen, más lo ya acreditado por todas las demás Notas de Crédito no canceladas contra el mismo origen, supere el total facturado (todas las líneas de producto) en la factura origen.

#### Scenario: Servicio ajeno dentro del total facturado
- **WHEN** el monto de un producto de Servicio ajeno al origen, sumado a lo demás acreditado en la Nota de Crédito y a lo ya acreditado por otras Notas de Crédito, no supera el total facturado en el origen
- **THEN** la Nota de Crédito se guarda sin error

#### Scenario: Servicio ajeno que por sí solo excede el total facturado
- **WHEN** el monto de un único producto de Servicio ajeno al origen ya supera el total facturado en el origen
- **THEN** el sistema rechaza la operación con un `ValidationError` indicando los montos y la factura origen

#### Scenario: Servicio ajeno exactamente en el límite del total facturado
- **WHEN** el monto acreditado total (incluyendo el servicio ajeno) es exactamente igual al total facturado en el origen
- **THEN** la Nota de Crédito se guarda sin error

#### Scenario: Mezcla de producto del origen y servicio ajeno que juntos exceden el total
- **WHEN** una Nota de Crédito combina un producto presente en el origen con un producto de Servicio ajeno, y la suma de ambos supera el total facturado en el origen
- **THEN** el sistema rechaza la operación, aunque cada línea individualmente no exceda su propio tope por producto

#### Scenario: Varias Notas de Crédito hermanas consumen el total antes que la de servicio
- **WHEN** una primera Nota de Crédito ya acreditó parte del total facturado con un producto presente en el origen, y una segunda Nota de Crédito intenta acreditar con un producto de Servicio ajeno un monto que, sumado a lo ya acreditado, supera el total facturado
- **THEN** el sistema rechaza la segunda Nota de Crédito
