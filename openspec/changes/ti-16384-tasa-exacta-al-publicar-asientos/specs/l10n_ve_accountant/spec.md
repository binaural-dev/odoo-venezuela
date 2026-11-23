## MODIFIED Requirements

### Requirement: Cálculo automático de la tasa según la fecha del documento

El sistema DEBE (MUST) calcular `foreign_rate` y `foreign_inverse_rate` de cada `account.move` invocando `res.currency.rate.compute_rate` sobre la moneda alterna del documento (`foreign_currency_id`) con la fecha de tasa del documento: `invoice_date` ("Rate Date") para todas las facturas, ventas y compras por igual, con `date` como respaldo si está vacía; los asientos (`entry`) usan siempre `date`, porque su `invoice_date` solo trae el "hoy" por defecto; si ninguna está definida usa la fecha actual del usuario (`context_today`). La regla es la misma para todos los tipos de documento: `_compute_rate_for_documents` recibe solo los documentos, sin distinguir ventas de compras. El recálculo (`_compute_rate`) DEBE (MUST) depender tanto de `invoice_date` como de `date`, porque `date` es el respaldo cuando `invoice_date` está vacía: editar únicamente `date` en un documento sin `invoice_date` DEBE (MUST) recalcular la tasa, mientras que en un documento con `invoice_date` (por ejemplo una compra) cambiar solo `date` NO DEBE (MUST NOT) moverla. `foreign_rate` y `foreign_inverse_rate` NO TIENEN (MUST NOT) un `default=` propio: se calculan siempre con la fecha del documento, incluso en la creación (`create`) de cualquier tipo, `in_invoice` incluido. Los documentos con `manually_set_rate` activo y con tasa ya fijada quedan excluidos del recálculo; uno marcado manual sin tasa se calcula. Ticket #16148. Facturas, notas de crédito/débito, recibos (`is_invoice(include_receipts=True)`) y asientos de pago (`origin_payment_id`) DEBEN (MUST) exigir siempre la tasa de la fecha exacta (sin usar la más cercana, anterior ni posterior): si esa fecha no tiene tasa cargada, la creación del documento se bloquea con un `UserError` que indica la moneda y la fecha. Esto incluye una factura con `manually_set_rate` en una fecha sin tasa: `create` consulta la tasa del día para decidir si publica el mensaje de chatter de tasa distinta y esa consulta lanza si no existe, como en `maintenance-19.0`. Ticket #16384.

Un asiento manual (`move_type == 'entry'` no generado por otro proceso; hook `_is_rate_deferrable()`) DEBE (MUST) poder crearse en borrador aunque su fecha sea futura o no tenga tasa: queda con `foreign_rate` y `foreign_inverse_rate` en 0 y no lanza error. AL PUBLICARSE (`_post`, ya sea por el botón, por el cron `_autopost_draft_entries` o por código) el sistema DEBE (MUST) recalcular la tasa exacta de `date` y forzar el recálculo de `foreign_debit` y `foreign_credit` de sus líneas; si no existe la tasa exacta lanza `UserError` y el asiento queda en borrador (en el cron queda con `auto_post='no'` y el core avisa en el chatter; ya no se publica solo aunque se cargue la tasa después). La tasa se busca con la compañía del asiento (`with_company(move.company_id)`) solo en `_post`, porque el cron corre con la compañía del usuario del cron. `_post(soft=True)` NO DEBE (MUST NOT) recalcular los asientos de fecha futura (solo los programa). NO DEBE (MUST NOT) recalcularse la tasa manual ya cargada (`manually_set_rate` con tasa, p. ej. las cuotas de depreciación de activos) ni la de un asiento ya publicado alguna vez (`posted_before`) que conserve tasa; sí se recalcula si `manually_set_rate` está marcado con tasa 0 (p. ej. un duplicado o una copia recurrente). Mientras está en borrador sin tasa, los montos en moneda alterna del asiento son provisionales (el core usa la última tasa disponible) y se corrigen al publicar.

NO DEBEN (MUST NOT) ser diferibles, y exigen la tasa exacta al crearse: los asientos de pago (`origin_payment_id`), de extractos bancarios (`statement_line_id` o contexto `is_statement_line`), de inventario (`stock_move_ids`), de sesión de PdV (`pos_session_ids`), los reversos (`reversed_entry_id`: heredan la tasa del original aunque su fecha no tenga tasa) y los de diferencia cambiaria (`l10n_ve_exchange_foreign_diff_entry` o diario de diferencia cambiaria de la compañía, cuyas líneas no usan la tasa de cabecera, `_skip_foreign_compute`). Como el core vincula los asientos de inventario y de PdV después de crearlos, al crearse son diferibles; los cubre la red de seguridad: tras `_post`, un `entry` publicado con moneda alterna y sin tasa DEBE (MUST) lanzar `UserError` y revertir la transacción (se excluye la diferencia cambiaria). El formulario de un asiento diferible DEBE (MUST) mostrar un aviso no bloqueante (`@api.onchange("date")`) cuando la fecha no tiene tasa.

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

- **WHEN** se crea una factura, nota o recibo cuya fecha de tasa no tiene registro de tasa para la moneda alterna, aunque existan tasas de otras fechas
- **THEN** se lanza un `UserError` "There is no rate assigned for <moneda> on <fecha>" y, una vez cargada la tasa de esa fecha, el mismo documento se crea con ella

#### Scenario: Cambio de la tasa después de contabilizar

- **WHEN** se modifica el registro de tasa de la fecha de un documento ya contabilizado y luego se recalcula y cancela el documento
- **THEN** el asiento sigue cuadrado (débito igual a crédito)

#### Scenario: Asiento manual con fecha futura o sin tasa

- **WHEN** se crea un asiento manual (`entry`) con una fecha futura o sin tasa cargada
- **THEN** se crea en borrador con `foreign_rate` en 0 y sin lanzar error

#### Scenario: Publicar el asiento sin tasa

- **WHEN** se publica un asiento manual cuya fecha no tiene tasa exacta
- **THEN** se lanza un `UserError` y el asiento sigue en borrador

#### Scenario: Publicar el asiento con la tasa cargada

- **WHEN** se carga la tasa de la fecha de un asiento manual en borrador y se publica
- **THEN** el asiento toma la tasa exacta de su fecha y `foreign_debit`/`foreign_credit` de sus líneas se recalculan con ella

#### Scenario: Tasa manual no se recalcula al publicar

- **WHEN** se publica un asiento con `manually_set_rate` y tasa distinta de 0 (p. ej. una cuota de depreciación)
- **THEN** conserva su tasa manual

#### Scenario: Tasa manual marcada con tasa 0

- **WHEN** se publica un asiento con `manually_set_rate` marcado y `foreign_rate` en 0 (p. ej. un duplicado)
- **THEN** se calcula la tasa exacta de su fecha como a cualquier asiento diferible

#### Scenario: Publicación programada de un asiento futuro

- **WHEN** se invoca `_post(soft=True)` sobre un asiento con fecha futura
- **THEN** solo se programa (`auto_post='at_date'`) y no se recalcula su tasa

#### Scenario: El cron con un asiento sin tasa

- **WHEN** el cron `_autopost_draft_entries` procesa un asiento programado cuya fecha no tiene tasa y otro que sí la tiene
- **THEN** publica el segundo; el primero queda en borrador con `auto_post='no'` (y aviso en el chatter) y no se publica solo aunque se cargue la tasa después

#### Scenario: Asiento ya publicado alguna vez

- **WHEN** se vuelve a publicar un asiento que ya se publicó antes (`posted_before`) y conserva su tasa
- **THEN** conserva la tasa con la que se confirmó

#### Scenario: Reverso de un asiento

- **WHEN** se revierte un asiento publicado en una fecha sin tasa
- **THEN** el reverso hereda la tasa del original y no lanza error

#### Scenario: Red de seguridad

- **WHEN** un `entry` con moneda alterna queda publicado sin tasa (p. ej. un asiento de inventario o de PdV, o un cambio de fecha por periodo bloqueado)
- **THEN** se lanza un `UserError` y se revierte la transacción; los asientos de diferencia cambiaria se excluyen

#### Scenario: La factura exige tasa exacta, también con tasa manual

- **WHEN** se crea una factura, nota de crédito/débito o recibo con fecha de tasa sin registro, aunque existan tasas anteriores, con o sin tasa manual
- **THEN** se lanza el `UserError` de tasa no asignada

#### Scenario: Asientos que no son diferibles

- **WHEN** se crea un asiento de pago (`origin_payment_id`), de extracto bancario, de inventario con movimientos de stock, de sesión de PdV o de diferencia cambiaria en una fecha sin tasa exacta
- **THEN** se lanza el `UserError` de tasa no asignada, mientras que el mismo asiento sin ese vínculo (manual) se crea en borrador

#### Scenario: Aviso en el formulario

- **WHEN** se edita la fecha de un asiento manual y esa fecha no tiene tasa
- **THEN** se muestra un aviso no bloqueante de que la tasa se calculará al publicar; si la tasa existe no se muestra nada

#### Scenario: Compañía sin moneda alterna

- **WHEN** se crea y publica un asiento en una compañía sin moneda alterna
- **THEN** no se calcula ni se exige ninguna tasa
