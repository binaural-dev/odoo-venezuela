## MODIFIED Requirements

### Requirement: Cálculo automático de la tasa según la fecha del documento

El sistema DEBE (MUST) calcular `foreign_rate` y `foreign_inverse_rate` de cada `account.move` invocando `res.currency.rate.compute_rate` sobre la moneda alterna del documento (`foreign_currency_id`) con la fecha de tasa del documento: `invoice_date` ("Rate Date") para todas las facturas, ventas y compras por igual, con `date` como respaldo si está vacía; los asientos (`entry`) usan siempre `date`, porque su `invoice_date` solo trae el "hoy" por defecto; si ninguna está definida usa la fecha actual del usuario (`context_today`). La regla es la misma para todos los tipos de documento: `_compute_rate_for_documents` recibe solo los documentos, sin distinguir ventas de compras. El recálculo (`_compute_rate`) DEBE (MUST) depender tanto de `invoice_date` como de `date`, porque `date` es el respaldo cuando `invoice_date` está vacía: editar únicamente `date` en un documento sin `invoice_date` DEBE (MUST) recalcular la tasa, mientras que en un documento con `invoice_date` (por ejemplo una compra) cambiar solo `date` NO DEBE (MUST NOT) moverla. `foreign_rate` y `foreign_inverse_rate` NO TIENEN (MUST NOT) un `default=` propio: se calculan siempre con la fecha del documento, incluso en la creación (`create`) de cualquier tipo, `in_invoice` incluido. Los documentos con `manually_set_rate` activo y con tasa ya fijada quedan excluidos del recálculo; uno marcado manual sin tasa se calcula. Ticket #16148. `compute_rate` se invoca con la compañía del documento (`move.company_id`) y exige la tasa de la fecha exacta (sin usar la más cercana, anterior ni posterior) a las facturas, notas de crédito/débito, recibos y asientos de pago (`origin_payment_id`): si esa fecha no tiene tasa cargada, la creación o contabilización del documento se bloquea con un `UserError` que indica la moneda y la fecha. El hook `_is_exact_rate_required()` define ese grupo (`l10n_ve_accountant/models/account_move.py:1209`).

El resto de asientos (`entry` sin `origin_payment_id`: manuales, valoración de inventario, extractos bancarios, depreciaciones, diferencia cambiaria) DEBEN (MUST) invocar `compute_rate` con `use_last_rate=True`: si su fecha no tiene tasa (fin de semana, feriado o fecha futura) usan la última tasa anterior a esa fecha, y solo se bloquean con el mismo `UserError` si no existe NINGUNA tasa anterior. La tasa así calculada queda fija desde que se guarda el asiento (no se recalcula al cargarse luego la tasa de su fecha). Los asientos de diferencia cambiaria (`l10n_ve_exchange_foreign_diff_entry`) quedan a propósito en el grupo no exacto, porque sus líneas no usan la tasa de cabecera (`_skip_foreign_compute`) y un reverso o una conciliación en un día sin tasa no debe fallar. Los pagos quedan fuera de este alcance y siguen exigiendo tasa exacta. Ticket #16384.

En `create`, un documento con `manually_set_rate` consulta la tasa del día solo para decidir si publica el mensaje de chatter de tasa distinta; esa consulta NO DEBE (MUST NOT) lanzar error: una factura o un asiento con tasa manual en una fecha sin tasa se crea sin bloquearse y, si no hay tasa de referencia, no publica el mensaje.

#### Scenario: Factura de venta

- **WHEN** se establece o cambia la fecha de factura de un documento de venta sin tasa manual
- **THEN** `foreign_rate` y `foreign_inverse_rate` se recalculan con la tasa vigente a esa fecha

#### Scenario: Factura de compra con la fecha de tasa editada

- **WHEN** se edita `invoice_date` (Rate Date) en un documento de compra (`in_invoice`) sin tasa manual, incluso restablecido a borrador desde el formulario
- **THEN** `foreign_rate` y `foreign_inverse_rate` se recalculan con la tasa vigente a esa fecha, igual que en una factura de venta, y al guardar el formulario queda esa tasa

#### Scenario: Factura de compra con solo la fecha contable editada

- **WHEN** se edita únicamente `date` (sin tocar `invoice_date`) en un documento de compra con `invoice_date` definida, sin tasa manual
- **THEN** `foreign_rate` y `foreign_inverse_rate` conservan la tasa de `invoice_date`

#### Scenario: Asiento sin fecha de tasa con solo la fecha contable editada

- **WHEN** se edita `date` en un asiento (`entry`), o en un documento sin `invoice_date`, sin tasa manual
- **THEN** `foreign_rate` y `foreign_inverse_rate` se recalculan con la tasa vigente a la nueva `date`

#### Scenario: Factura de proveedor o de cliente creada con fecha pasada

- **WHEN** se crea un documento `in_invoice` u `out_invoice` (por código o desde el formulario) con `invoice_date` pasada y sin tasa manual
- **THEN** el documento toma la tasa de esa fecha y no la de hoy

#### Scenario: Tasa fijada manualmente

- **WHEN** un documento tiene `manually_set_rate` en verdadero
- **THEN** el recálculo automático no modifica su tasa

#### Scenario: Tasa manual sin valor útil

- **WHEN** un documento tiene `manually_set_rate` en verdadero pero su `foreign_rate` es cero, o un residuo menor a la precisión `Tasa` (6 decimales)
- **THEN** se trata como "sin tasa" y se calcula por la Rate Date; la comparación contra la tasa vigente para avisar un cambio manual usa esa misma precisión

#### Scenario: Documento con fecha sin tasa cargada

- **WHEN** se crea o contabiliza un documento cuya fecha de tasa no tiene registro de tasa para la moneda alterna, aunque existan tasas de otras fechas
- **THEN** se lanza un `UserError` "There is no rate assigned for <moneda> on <fecha>" y, una vez cargada la tasa de esa fecha, el mismo documento se contabiliza con ella

#### Scenario: Cambio de la tasa después de contabilizar

- **WHEN** se modifica el registro de tasa de la fecha de un documento ya contabilizado y luego se recalcula y cancela el documento
- **THEN** el asiento sigue cuadrado (débito igual a crédito)

#### Scenario: Asiento en fin de semana

- **WHEN** se crea un asiento (`entry`, sin pago de origen) con fecha de sábado o domingo sin tasa cargada y existe la tasa del viernes
- **THEN** el asiento toma la tasa del viernes y sus líneas en moneda alterna son coherentes con esa tasa

#### Scenario: Asiento con fecha futura

- **WHEN** se crea un asiento con una fecha posterior a la última tasa cargada
- **THEN** el asiento toma la tasa más reciente existente

#### Scenario: Asiento sin tasa previa

- **WHEN** se crea un asiento con una fecha anterior a todas las tasas cargadas
- **THEN** se lanza el `UserError` "There is no rate assigned for <moneda> on <fecha>"

#### Scenario: Tasa fija al guardar

- **WHEN** un asiento tomó la última tasa anterior y después se carga la tasa de su fecha
- **THEN** el asiento conserva la tasa con la que se guardó; no se recalcula

#### Scenario: La factura sigue exigiendo tasa exacta

- **WHEN** se crea una factura, nota de crédito/débito o recibo (`is_invoice(include_receipts=True)`) con fecha de tasa sin registro, aunque existan tasas anteriores, sin tasa manual
- **THEN** se lanza el `UserError` de tasa no asignada; no se usa la última tasa anterior

#### Scenario: El asiento de pago sigue exigiendo tasa exacta

- **WHEN** se crea un asiento con `origin_payment_id` en una fecha sin tasa exacta
- **THEN** se lanza el `UserError` de tasa no asignada, mientras que el mismo asiento sin `origin_payment_id` usa la última tasa anterior

#### Scenario: Diferencia cambiaria con tasa no exacta

- **WHEN** se crea un asiento de diferencia cambiaria (`l10n_ve_exchange_foreign_diff_entry`) en una fecha sin tasa y existe una tasa anterior
- **THEN** se crea con la última tasa anterior y no se bloquea

#### Scenario: Tasa manual en una fecha sin tasa

- **WHEN** se crea una factura o un asiento con `manually_set_rate` y tasa manual en una fecha sin tasa cargada
- **THEN** el documento se crea sin lanzar error, conserva la tasa manual y no publica el mensaje de tasa distinta si no hay tasa de referencia

#### Scenario: Búsqueda de la tasa en la compañía del documento

- **WHEN** se crea un asiento de una compañía distinta de la activa de la sesión
- **THEN** la tasa se busca en la compañía del asiento (y su raíz), no en la compañía activa
