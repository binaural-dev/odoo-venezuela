## MODIFIED Requirements

### Requirement: Cálculo automático de la tasa según la fecha del documento

El sistema DEBE (MUST) calcular `foreign_rate` y `foreign_inverse_rate` de cada `account.move` invocando `res.currency.rate.compute_rate` sobre la moneda alterna del documento (`foreign_currency_id`) con la fecha del documento: para documentos de venta usa `invoice_date` y para el resto (compras, asientos) usa `date`; si la fecha no está definida usa la fecha actual en la zona horaria del usuario (`fields.Date.context_today`), nunca la fecha UTC del servidor: en Venezuela (UTC-4), a partir de las 8 pm la fecha UTC ya es la del día siguiente, que todavía no tiene tasa cargada. Las fechas explícitas del documento (`invoice_date`, `date`) se usan tal cual, sin ajuste de zona horaria. El recálculo (`_compute_rate`) DEBE (MUST) depender tanto de `invoice_date` como de `date`, precisamente porque el propio método lee uno u otro campo según el tipo de documento: si dependiera solo de `invoice_date`, editar únicamente `date` en un documento de compra (o cualquier documento que no sea de venta) nunca dispararía el recompute, dejando `foreign_rate`/`foreign_inverse_rate` obsoletos respecto a la fecha realmente usada para buscarlos. En la creación del asiento se omite para los documentos `in_invoice`, que conservan la tasa por defecto calculada a la fecha de hoy del usuario. Los documentos con `manually_set_rate` activo quedan excluidos del recálculo. `compute_rate` busca la tasa únicamente en la fecha exacta del documento (sin usar la más cercana, anterior ni posterior): si esa fecha no tiene tasa cargada, la creación o contabilización del documento se bloquea con un `UserError` que indica la moneda y la fecha.

#### Scenario: Factura de venta

- **WHEN** se establece o cambia la fecha de factura de un documento de venta sin tasa manual
- **THEN** `foreign_rate` y `foreign_inverse_rate` se recalculan con la tasa vigente a esa fecha

#### Scenario: Factura de compra con solo la fecha contable editada

- **WHEN** se edita únicamente `date` (sin tocar `invoice_date`) en un documento que no es de venta (por ejemplo `in_invoice`), sin tasa manual
- **THEN** `foreign_rate` y `foreign_inverse_rate` se recalculan con la tasa vigente a la nueva `date`, en vez de quedar congelados con la tasa de la fecha anterior

#### Scenario: Factura de proveedor recién creada

- **WHEN** se crea un documento `in_invoice`
- **THEN** la creación no dispara el recálculo de tasa y el documento conserva la tasa por defecto de la fecha actual

#### Scenario: Tasa fijada manualmente

- **WHEN** un documento tiene `manually_set_rate` en verdadero
- **THEN** el recálculo automático no modifica su tasa

#### Scenario: Documento con fecha sin tasa cargada

- **WHEN** se crea o contabiliza un documento cuya fecha de tasa no tiene registro de tasa para la moneda alterna, aunque existan tasas de otras fechas
- **THEN** se lanza un `UserError` "There is no rate assigned for <moneda> on <fecha>" y, una vez cargada la tasa de esa fecha, el mismo documento se contabiliza con ella

#### Scenario: Cambio de la tasa después de contabilizar

- **WHEN** se modifica el registro de tasa de la fecha de un documento ya contabilizado y luego se recalcula y cancela el documento
- **THEN** el asiento sigue cuadrado (débito igual a crédito)

#### Scenario: Documento sin fecha creado después de las 8 pm

- **WHEN** a las 9 pm (hora de Caracas, ya el día siguiente en UTC) se crea una factura de venta en borrador sin `invoice_date`, y solo existe la tasa del día local
- **THEN** `foreign_rate` y `foreign_inverse_rate` toman la tasa del día local y no se lanza el `UserError` de tasa no asignada para el día siguiente

#### Scenario: Fecha explícita del documento después de las 8 pm

- **WHEN** a las 9 pm (hora de Caracas) se crea un documento con `invoice_date` igual al día siguiente, sin tasa cargada para ese día
- **THEN** la fecha no se corrige y se lanza el `UserError` de tasa no asignada para esa fecha
