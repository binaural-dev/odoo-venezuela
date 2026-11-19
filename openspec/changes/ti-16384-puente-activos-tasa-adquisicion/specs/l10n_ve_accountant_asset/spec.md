## ADDED Requirements

### Requirement: Tasa de la fecha de adquisición en las cuotas de depreciación

Cada cuota de depreciación (`account.move` con `asset_move_type == 'depreciation'`) de un activo de una compañía con moneda alterna DEBE (MUST) crearse con `manually_set_rate=True` y con `foreign_rate` y `foreign_inverse_rate` de la tasa de la fecha de adquisición del activo (`acquisition_date`), calculada con `compute_rate(use_last_rate=True)` en la compañía del activo (`account.asset._get_acquisition_rate_values`). La tasa de la cuota NO DEBE (MUST NOT) recalcularse al publicarla (manual o por el cron nativo), ni tomar la tasa de la fecha de la cuota ni la de la factura de compra del activo. Si la compañía no tiene moneda alterna no se asigna ninguna tasa. Las cuotas nacen con su fecha real y, si son futuras, con el `auto_post='at_date'` nativo; el addon no define un modo de publicación propio. Aplica solo a cuotas de tipo `depreciation`; `negative_revaluation`, `disposal` y `modify` con moneda distinta quedan fuera de alcance.

#### Scenario: Cuota con la tasa de adquisición

- **WHEN** se calcula el plan de depreciación de un activo cuya fecha de adquisición tiene tasa propia distinta de la tasa de la fecha de cada cuota
- **THEN** todas las cuotas de depreciación quedan con `manually_set_rate=True` y la tasa de la fecha de adquisición

#### Scenario: Publicación sin recalcular la tasa

- **WHEN** el cron nativo publica una cuota futura (`auto_post='at_date'`) en su fecha
- **THEN** la cuota se publica con la tasa de adquisición y su importe alterno no cambia; el cron publica solo la cuota de su fecha

#### Scenario: Activo con factura de compra

- **WHEN** el activo proviene de una factura de compra con una tasa distinta a la de adquisición
- **THEN** las cuotas usan la tasa de adquisición, no la de la factura

#### Scenario: Adquisición en fin de semana

- **WHEN** la fecha de adquisición cae en un día sin tasa cargada y existe una tasa anterior
- **THEN** las cuotas usan la última tasa anterior a la fecha de adquisición

#### Scenario: Sin ninguna tasa previa a la adquisición

- **WHEN** la fecha de adquisición es anterior a todas las tasas cargadas de la moneda alterna
- **THEN** se lanza el `UserError` "There is no rate assigned for <moneda> on <fecha>" y no se crea ninguna cuota

#### Scenario: Cuotas futuras con su fecha real

- **WHEN** el plan incluye cuotas con fecha posterior a hoy
- **THEN** quedan en borrador con su fecha real y `auto_post='at_date'`; las de fecha pasada se publican; recalcular el plan no duplica borradores

### Requirement: Importe alterno de las líneas de una cuota

El importe en moneda alterna de las líneas de una cuota de depreciación con tasa manual DEBE (MUST) ser `(debit - credit) / foreign_rate` de la cuota, redondeado con la moneda alterna de la compañía (`account.move.line._get_non_invoice_foreign_value`). NO DEBE (MUST NOT) usarse `foreign_inverse_rate` (truncado a 6 decimales en el activo) ni inferirse la orientación de la tasa: `foreign_rate` son unidades de la moneda de la compañía por unidad de la alterna, sea esta USD o VEF. Para el reverso de una cuota, la tasa se toma de la cuota original siguiendo la cadena de `reversed_entry_id`, de modo que el reverso devuelve exactamente el importe alterno original. Los asientos que no son cuotas de activo, aunque tengan tasa manual, conservan el cálculo estándar.

#### Scenario: USD con la tasa de adquisición

- **WHEN** se calcula el importe alterno de una línea de una cuota de depreciación
- **THEN** es el balance de la línea dividido entre la tasa de adquisición de la cuota, incluso para importes grandes

#### Scenario: Moneda alterna VEF en compañía USD

- **WHEN** la compañía tiene VEF como moneda alterna
- **THEN** el importe alterno también es balance dividido entre `foreign_rate`

#### Scenario: Reverso de una cuota

- **WHEN** se revierte una cuota publicada
- **THEN** el importe alterno del reverso es el de la cuota original

#### Scenario: Asiento que no es una cuota

- **WHEN** un asiento sin `asset_id` tiene tasa manual
- **THEN** su importe alterno se calcula con la tasa de su tabla, no con la lógica de depreciación

### Requirement: Protección de las cuotas publicadas al recalcular el plan

Al ejecutar `compute_depreciation_board`, las cuotas ya publicadas (`state == 'posted'`) DEBEN (MUST) conservar `manually_set_rate`, `foreign_rate` y `foreign_inverse_rate` que tenían, aunque `binaural_account_asset` (no es dependencia del addon) escriba la tasa del activo en todas las cuotas. Si el campo `foreign_rate` existe en `account.asset`, el addon DEBE (MUST) dejar en el activo la tasa de adquisición antes del `super`, para que esa escritura copie el mismo valor sea cual sea el orden del MRO. Las cuotas nuevas (borradores y las que el mismo plan acaba de publicar) que difieran de la tasa de adquisición DEBEN (MUST) corregirse. El addon NO DEBE (MUST NOT) escribir en las cuotas ni en el activo cuando la tasa ya es la correcta (a la precisión de cada campo).

#### Scenario: Recalcular con cuotas publicadas

- **WHEN** se recalcula el plan de un activo que ya tiene cuotas publicadas
- **THEN** las publicadas conservan su tasa y su importe alterno, y las nuevas llevan la tasa de adquisición

#### Scenario: Modificar el activo con cuotas publicadas

- **WHEN** se modifica el activo (`modify`) teniendo cuotas publicadas
- **THEN** las cuotas publicadas conservan su tasa

#### Scenario: binaural_account_asset instalado

- **WHEN** `binaural_account_asset` está instalado, ya sea antes o después de este addon en la cadena de herencia
- **THEN** las cuotas quedan con la tasa de adquisición y las publicadas no cambian

#### Scenario: Tasa ya correcta

- **WHEN** se recalcula el plan y las cuotas ya tienen la tasa de adquisición
- **THEN** no se escribe ninguna tasa ni se generan mensajes de tasa actualizada

### Requirement: Migración del modo de publicación personalizado

Al actualizar a 19.0.1.0.2 una base donde el addon estuvo instalado con el modo `auto_post='custom'` (19.0.1.0.0 o 19.0.1.0.1), la migración previa (`pre-10-remove_custom_auto_post`) DEBE (MUST) retirar ese modo antes de que el ORM elimine las columnas `auto_post_custom_*`: las cuotas de activo en borrador con `auto_post='custom'` pasan a `auto_post='at_date'` con `date` igual a `auto_post_custom_date` (y se actualiza `account_move_line.date`); las facturas y asientos `custom` que no son de activos pasan a `auto_post='no'` sin tocar sus fechas, dejando un warning en el log con sus ids; cualquier otra fila `custom` restante pasa a `auto_post='no'` con warning; y se borran las vistas `view_move_form_auto_post_custom` y `view_account_asset_form_publish_date`. La migración DEBE (MUST) ser idempotente y no hacer nada si la columna `auto_post_custom_date` no existe.

#### Scenario: Cuota de activo en borrador con modo custom

- **WHEN** se actualiza una base con una cuota de activo en borrador, `auto_post='custom'` y `auto_post_custom_date` definida
- **THEN** la cuota queda con `auto_post='at_date'` y su fecha real en `date`

#### Scenario: Documento custom que no es de activo

- **WHEN** la base tiene una factura o asiento con `auto_post='custom'` sin `asset_id`
- **THEN** pasa a `auto_post='no'` con sus fechas intactas y su id aparece en un warning del log

#### Scenario: Base que nunca tuvo el modo custom

- **WHEN** se actualiza una base sin la columna `auto_post_custom_date`
- **THEN** la migración no modifica nada
