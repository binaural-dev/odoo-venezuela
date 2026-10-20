## ADDED Requirements

### Requirement: Productos de una Nota de Crédito restringidos a la factura origen
El sistema DEBE (MUST) impedir que una Nota de Crédito (`out_refund`/`in_refund`) con `reversed_entry_id` incluya un producto que no esté presente en las líneas de producto de la factura que revierte, salvo que la creación se realice con la clave de contexto `l10n_ve_skip_refund_origin_validation` activa.

#### Scenario: Producto presente en la factura origen
- **WHEN** se crea o edita una Nota de Crédito cuyas líneas de producto son un subconjunto de los productos de su factura origen
- **THEN** la Nota de Crédito se guarda sin error

#### Scenario: Producto ajeno a la factura origen
- **WHEN** se crea o edita una Nota de Crédito agregando un producto que la factura origen nunca facturó
- **THEN** el sistema rechaza la operación con un `ValidationError` indicando el producto y la factura origen

#### Scenario: Edición directa de una línea ya creada
- **WHEN** se modifica el `product_id` de una línea de una Nota de Crédito ya existente, sin pasar por el `write()` del documento padre
- **THEN** la validación se ejecuta igual y rechaza el producto ajeno

#### Scenario: Bypass explícito para módulos automáticos
- **WHEN** un módulo crea la Nota de Crédito con el contexto `l10n_ve_skip_refund_origin_validation=True`
- **THEN** la validación de producto y monto no se ejecuta, cualquiera sea el producto usado

### Requirement: Monto acreditado por producto no puede superar lo facturado en el origen, contando todas las Notas de Crédito
El sistema DEBE (MUST) impedir que, para un mismo producto, el monto acreditado acumulado entre la Nota de Crédito que se está guardando y todas las demás Notas de Crédito no canceladas contra el mismo origen supere el monto facturado por ese producto en la factura origen, usando la precisión de redondeo de la moneda del documento.

#### Scenario: Nota de crédito parcial, sin otras Notas de Crédito previas
- **WHEN** el monto acreditado por un producto es menor o igual al facturado por ese producto en el origen y no existen otras Notas de Crédito contra ese origen
- **THEN** la Nota de Crédito se guarda sin error

#### Scenario: Nota de crédito que excede el monto facturado por sí sola
- **WHEN** el monto acreditado por un producto en una sola Nota de Crédito ya supera el monto facturado por ese producto en la factura origen
- **THEN** el sistema rechaza la operación con un `ValidationError` indicando el producto, los montos y la factura origen

#### Scenario: Dos Notas de Crédito parciales que juntas exceden el origen
- **WHEN** una primera Nota de Crédito por un producto queda dentro del monto facturado, y se intenta crear una segunda Nota de Crédito para el mismo producto y origen cuyo monto, sumado al de la primera, supera lo facturado
- **THEN** el sistema rechaza la segunda Nota de Crédito con un `ValidationError`, indicando el monto ya acreditado por otras Notas de Crédito

#### Scenario: Diferencias de redondeo no bloquean la Nota de Crédito
- **WHEN** el monto acreditado (incluyendo otras Notas de Crédito) difiere del monto facturado solo por un arrastre de punto flotante menor a la precisión de la moneda
- **THEN** la Nota de Crédito se guarda sin error
