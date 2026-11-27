## MODIFIED Requirements

### Requirement: Numeración automática de comprobantes

En `create` el sistema DEBE (MUST) ejecutar `_set_sequence` sobre todo comprobante sin `number` **de proveedor** (todo tipo distinto de `out_invoice`, `out_refund`, `out_debit` y `out_contingence`), asignando un correlativo con formato `AAAAMM` (año y mes de `date_accounting`) seguido del siguiente valor de la secuencia de la compañía activa (o de su empresa matriz, según el requisito «Correlativo de retenciones compartido con la empresa matriz»): `retention.iva.control.number` con padding 8 para IVA (resultando 14 dígitos) y `retention.islr.control.number` con padding 5 para ISLR; el correlativo se guarda en `number` y `name`. Los comprobantes de cliente NO DEBEN (MUST NOT) tomar número de estas secuencias, porque son los correlativos de los comprobantes que la empresa emite a sus proveedores y el número del comprobante de cliente lo emite el agente de retención externo: se crean sin `number` y el usuario lo escribe antes de emitir. Además, `action_post` vuelve a invocar `_set_sequence` solo para los comprobantes de proveedor (`in_invoice`, `in_refund`, `in_debit`). La secuencia se crea automáticamente si no existe, pero para municipal la búsqueda usa el código `retention.municipal.control.number` mientras la creación registra la secuencia con el código `retention.iva.control.number` y padding 5, por lo que la búsqueda nunca la reencuentra y cada numeración municipal crea una secuencia nueva que arranca de su primer valor.

#### Scenario: Comprobante IVA de proveedor sin número

- **WHEN** se crea un comprobante de retención IVA de proveedor sin `number`
- **THEN** recibe un número de 14 dígitos compuesto por año, mes y la secuencia de 8 dígitos

#### Scenario: Comprobante de cliente creado sin número

- **WHEN** se crea un comprobante de tipo cliente (IVA, ISLR o municipal) sin `number`
- **THEN** queda en borrador sin número y la secuencia de la compañía no avanza

#### Scenario: Numeración municipal repetida

- **WHEN** se numeran dos comprobantes municipales de proveedor en una compañía sin secuencia municipal previa
- **THEN** cada uno crea una secuencia nueva registrada con el código de IVA y ambos reciben el mismo valor inicial de secuencia

### Requirement: Número obligatorio en retenciones de cliente

El número de un comprobante de tipo cliente (`out_invoice`, `out_refund`, `out_debit`) NO DEBE (MUST NOT) ser obligatorio para crearlo ni para guardarlo en borrador (los formularios IVA, ISLR y municipal no lo marcan como requerido), pero el sistema DEBE (MUST) impedir emitirlo sin `number`, ya que el número lo emite el agente de retención externo y el usuario lo escribe cuando llega. Esta validación se evalúa en `action_post` **después** de la comprobación de monto cero de las líneas y opera sobre el valor vigente del campo.

#### Scenario: Retención de cliente sin número

- **WHEN** se ejecuta `action_post` sobre una retención de cliente (IVA, ISLR o municipal) cuyo `number` está vacío
- **THEN** se lanza un `UserError` pidiendo insertar un número y la retención sigue en borrador

#### Scenario: Borrador de cliente sin número guardado desde el formulario

- **WHEN** el usuario edita y guarda en el formulario un borrador de retención de cliente sin `number`
- **THEN** se guarda sin error

#### Scenario: Retención de cliente con el número escrito

- **WHEN** se escribe el número del cliente y se emite la retención
- **THEN** se emite y la factura recibe ese número en `iva_voucher_number`, `islr_voucher_number` o `municipal_voucher_number`, sin consumir la secuencia de la compañía

### Requirement: Generación automática de retenciones al publicar la factura

Al publicar una factura (`action_post` de `account.move`), el sistema DEBE (MUST) crear automáticamente: la retención ISLR (`auto_create_islr_retention`) si `generate_islr_retention` está activo y no hay `islr_voucher_number`; la retención IVA si `generate_iva_retention` está activo y no hay `iva_voucher_number` (validando el diario IVA del flujo correspondiente, que existan impuestos aplicables y que el partner tenga `withholding_type_id`); y, solo en facturas de proveedor (`in_invoice`/`in_refund`), la retención municipal cuando hay líneas municipales no emitidas y no hay `municipal_voucher_number`. La emisión automática DEBE (MUST) ocurrir únicamente cuando `create_retentions_of_suppliers_in_draft` está desactivado **y** el `move_type` es exactamente `in_invoice`: las notas de crédito y débito de proveedor y las facturas de cliente crean la retención pero la dejan en borrador. En facturas de proveedor, en los flujos IVA e ISLR el número del comprobante se escribe en `iva_voucher_number` / `islr_voucher_number` de la factura inmediatamente después de crearlo, incluso si la retención quedó en borrador (el flujo municipal no escribe su número en esta ruta). En facturas de cliente (`out_invoice`/`out_refund`) la retención se crea en borrador sin número y la factura NO DEBE (MUST NOT) recibir `iva_voucher_number` ni `islr_voucher_number` hasta que se emita la retención con el número real; mientras la factura tenga una retención del mismo tipo (IVA o ISLR) no cancelada, el sistema NO DEBE (MUST NOT) crear otra al volver a publicar. La creación automática de ISLR exige además el diario ISLR **de proveedor** de la compañía y el `type_person_id` del partner de la factura, también cuando la factura es de cliente.

#### Scenario: Factura de proveedor con retención IVA automática

- **WHEN** se publica una factura de proveedor `in_invoice` con `generate_iva_retention` activo y la compañía no crea retenciones en borrador
- **THEN** se crea la retención IVA, se emite automáticamente y la factura recibe el número de comprobante

#### Scenario: Compañía con retenciones en borrador

- **WHEN** `create_retentions_of_suppliers_in_draft` está activo y se publica una factura de proveedor
- **THEN** la retención se crea en estado borrador sin emitirse, y la factura queda igualmente con el número de comprobante IVA o ISLR

#### Scenario: Nota de crédito de proveedor con retención marcada

- **WHEN** se publica una `in_refund` con `generate_iva_retention` activo y la compañía no crea retenciones en borrador
- **THEN** la retención IVA se crea pero NO se emite, porque la emisión automática solo aplica a `in_invoice`

#### Scenario: Factura de cliente con retención IVA marcada

- **WHEN** se publica una factura de cliente con `generate_iva_retention` activo
- **THEN** se crea una retención IVA en borrador sin número, `iva_voucher_number` queda vacío y la secuencia de la compañía no avanza

#### Scenario: Factura de cliente publicada de nuevo

- **WHEN** se vuelve a publicar una factura de cliente que ya tiene su retención en borrador sin número
- **THEN** no se crea una segunda retención

#### Scenario: Factura de cliente con retención ISLR automática sin diario de proveedor

- **WHEN** se publica una factura de cliente con `generate_islr_retention` activo y la compañía no tiene configurado el diario ISLR de proveedor
- **THEN** se lanza un `UserError` exigiendo ese diario aunque el flujo sea de cliente
