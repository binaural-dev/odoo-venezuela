## MODIFIED Requirements

### Requirement: Productos de una Nota de Crédito restringidos a la factura origen
El sistema DEBE (MUST) impedir **publicar** una Nota de Crédito (`out_refund`/`in_refund`) con `reversed_entry_id` que incluya un producto **Almacenable o Consumible** que no esté presente en las líneas de producto de la factura que revierte, salvo que la Nota de Crédito esté eximida (ver `Requirement: Exención de la validación por registro`). Un producto de tipo **Servicio** ajeno a la factura origen SIEMPRE se permite (queda sujeto al tope agregado del `Requirement` de monto total de servicios ajenos). La validación NO se ejecuta al crear ni al editar el borrador.

#### Scenario: Producto presente en la factura origen
- **WHEN** se publica una Nota de Crédito cuyas líneas de producto son un subconjunto de los productos de su factura origen
- **THEN** la Nota de Crédito se publica sin error

#### Scenario: Producto Almacenable/Consumible ajeno a la factura origen
- **WHEN** se publica una Nota de Crédito con un producto de tipo Almacenable o Consumible que la factura origen nunca facturó
- **THEN** el sistema rechaza la publicación con un `ValidationError` indicando el producto y la factura origen

#### Scenario: Producto tipo Servicio ajeno a la factura origen
- **WHEN** se publica una Nota de Crédito con un producto de tipo Servicio que la factura origen nunca facturó
- **THEN** la Nota de Crédito se publica sin error, siempre que el monto total acreditado no supere el total facturado en el origen

#### Scenario: Edición de una línea en borrador
- **WHEN** se modifica el `product_id` o el monto de una línea de una Nota de Crédito en borrador, dejándola fuera de lo permitido
- **THEN** la edición se guarda, y el `ValidationError` se lanza al intentar publicarla

#### Scenario: Línea sin producto
- **WHEN** se publica una Nota de Crédito con una línea de producto sin `product_id`
- **THEN** el sistema rechaza la publicación con un `ValidationError`

### Requirement: Monto acreditado por producto no puede superar lo facturado en el origen, contando todas las Notas de Crédito
El sistema DEBE (MUST) impedir publicar una Nota de Crédito cuando, para un mismo producto, el monto acreditado acumulado entre ella y las demás Notas de Crédito contra el mismo origen que estén **publicadas, o se publiquen en la misma operación**, supere el monto facturado por ese producto en la factura origen, usando la precisión de redondeo de la moneda del documento. Las Notas de Crédito en borrador que no se están publicando no cuentan.

#### Scenario: Nota de crédito parcial, sin otras Notas de Crédito previas
- **WHEN** el monto acreditado por un producto es menor o igual al facturado por ese producto en el origen y no existen otras Notas de Crédito publicadas contra ese origen
- **THEN** la Nota de Crédito se publica sin error

#### Scenario: Nota de crédito que excede el monto facturado por sí sola
- **WHEN** el monto acreditado por un producto en una sola Nota de Crédito ya supera el monto facturado por ese producto en la factura origen
- **THEN** el sistema rechaza la publicación con un `ValidationError` indicando el producto, los montos y la factura origen

#### Scenario: Segunda Nota de Crédito que, sumada a una publicada, excede el origen
- **WHEN** una primera Nota de Crédito por un producto ya está publicada dentro del monto facturado, y se intenta publicar una segunda para el mismo producto y origen cuyo monto, sumado al de la primera, supera lo facturado
- **THEN** el sistema rechaza la segunda con un `ValidationError`, indicando el monto ya acreditado por otras Notas de Crédito

#### Scenario: Dos Notas de Crédito publicadas en la misma operación
- **WHEN** se publican juntas dos Notas de Crédito en borrador contra el mismo origen que, sumadas, superan lo facturado
- **THEN** el sistema rechaza la publicación con un `ValidationError`

#### Scenario: Un borrador olvidado no bloquea
- **WHEN** existe una Nota de Crédito en borrador que por sí sola excede el origen, y se publica otra Nota de Crédito que respeta el tope
- **THEN** la segunda se publica sin error; el borrador solo se valida cuando se intente publicar

#### Scenario: Diferencias de redondeo no bloquean la Nota de Crédito
- **WHEN** el monto acreditado (incluyendo otras Notas de Crédito) difiere del monto facturado solo por un arrastre de punto flotante menor a la precisión de la moneda
- **THEN** la Nota de Crédito se publica sin error

### Requirement: Monto total de servicios ajenos al origen no puede superar lo facturado en el origen
El sistema DEBE (MUST) impedir publicar una Nota de Crédito cuando la suma de lo acreditado por productos de tipo Servicio ajenos a la factura origen, más lo acreditado por productos presentes en el origen, más lo acreditado por las demás Notas de Crédito contra el mismo origen **publicadas o publicándose en la misma operación**, supere el total facturado (todas las líneas de producto) en la factura origen.

#### Scenario: Servicio ajeno dentro del total facturado
- **WHEN** el monto de un producto de Servicio ajeno al origen, sumado a lo demás acreditado, no supera el total facturado en el origen
- **THEN** la Nota de Crédito se publica sin error

#### Scenario: Servicio ajeno que excede el total facturado
- **WHEN** el monto acreditado total (incluyendo el servicio ajeno y las Notas de Crédito publicadas) supera el total facturado en el origen
- **THEN** el sistema rechaza la publicación con un `ValidationError` indicando los montos y la factura origen

## ADDED Requirements

### Requirement: Borrador editable desde el asistente de reversión
El asistente "Nota de Crédito" > "Revertir" (`account.move.reversal.refund_moves`) DEBE (MUST) poder crear el borrador de la Nota de Crédito con el monto completo de la factura aunque, sumado a Notas de Crédito ya publicadas, exceda lo facturado, de modo que el usuario pueda reducirlo antes de publicar.

#### Scenario: Segunda Nota de Crédito parcial sobre la misma factura
- **WHEN** una factura ya tiene una Nota de Crédito parcial publicada y el usuario usa "Revertir" de nuevo
- **THEN** se crea el borrador con las cantidades completas de la factura, sin error

#### Scenario: Publicar el borrador sin reducirlo
- **WHEN** el usuario publica ese borrador sin reducir cantidades ni montos
- **THEN** el sistema rechaza la publicación con el `ValidationError` de monto acreditado

#### Scenario: Publicar el borrador reducido
- **WHEN** el usuario reduce la cantidad del borrador de modo que el acumulado no supere lo facturado, y lo publica
- **THEN** la Nota de Crédito se publica sin error

### Requirement: Exención de la validación por registro
La validación DEBE (MUST) consultar, por cada Nota de Crédito, el método `_l10n_ve_skip_refund_origin_validation()`, que por defecto devuelve verdadero solo si la clave de contexto `l10n_ve_skip_refund_origin_validation` está activa **al publicar**. Los módulos que generan Notas de Crédito con un producto propio PUEDEN (MAY) sobrescribirlo para eximirlas por un campo guardado.

#### Scenario: Clave de contexto activa al publicar
- **WHEN** una Nota de Crédito con un producto ajeno a la factura origen se publica con el contexto `l10n_ve_skip_refund_origin_validation=True`
- **THEN** la validación de producto y monto no se ejecuta

#### Scenario: Clave de contexto solo al crear
- **WHEN** la Nota de Crédito se creó con la clave de contexto, pero se publica en una llamada posterior sin ella, y ningún módulo la exime por el hook
- **THEN** la validación se ejecuta al publicar
