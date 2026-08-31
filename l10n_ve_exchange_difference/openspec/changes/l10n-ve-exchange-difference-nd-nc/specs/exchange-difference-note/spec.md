# Spec delta: exchange-difference-note

## ADDED Requirements

### Requirement: Una Nota de Débito se emite cuando hay ganancia cambiaria

El sistema SHALL emitir una Nota de Débito (out_invoice) vinculada a la factura
de origen, posteada en un diario dedicado con secuencia propia, y conciliada
contra el residual de diferencial, cuando la conciliación de una factura de
cliente en moneda extranjera contra un pago con tasa distinta deja un residual
positivo (lado de crédito) que representa una ganancia cambiaria.

La ND SHALL estar fechada el día del pago, no el día de la conciliación, y 
SHALL incluir una línea de producto configurada en la compañía.

#### Scenario: Factura en USD pagada parcialmente con tasa peor

- **GIVEN** una factura de cliente por 100 USD, contabilizada el 2026-01-01 a tasa 40.0 (VEF/USD)
- **AND** se paga 100 USD el 2026-08-01 a tasa 36.0 (VEF/USD)
- **AND** el toggle `l10n_ve_exchange_use_nd_nc` está activado en la compañía
- **WHEN** se concilia la factura contra el pago
- **THEN** se genera una Nota de Débito con:
  - `move_type = 'out_invoice'`
  - `debit_origin_id = <id de la factura>`
  - `date = 2026-08-01` (día del pago, no hoy)
  - `journal_id = <diario dedicado con is_debit=True>`
  - `name = <secuencia dedicada NDDIFT/2026/0001>`
- **AND** la línea de la ND incluye `product_id = <producto configurado>`
- **AND** la línea está conciliada contra el residual de la factura

#### Scenario: Factura en VEF pagada con tasa distintos si hay otros movimientos

- **GIVEN** una factura en moneda de compañía (VEF) pero con líneas cuya
  conversión extranjera deja un residual de redondeo
- **AND** el pago es en moneda extranjera
- **WHEN** se concilia
- **THEN** se genera ND por el redondeo (Odoo nativo también lo hace)

### Requirement: Una Nota de Crédito se emite cuando hay pérdida cambiaria

El sistema SHALL emitir una Nota de Crédito (out_refund) vinculada a la factura
de origen, posteada en el MISMO diario de venta que la factura de origen (no un
diario dedicado -- Odoo numera NC con `refund_sequence_id`), y conciliada contra
el residual, cuando la conciliación deja un residual negativo (lado de débito)
que representa una pérdida cambiaria.

La NC SHALL usar la cuenta de PÉRDIDA cambiaria de la compañía (no la de ingreso
del producto), porque `is_sale_document()` de Odoo trata `out_refund` igual que
`out_invoice` al resolver la cuenta de la línea.

#### Scenario: Factura en USD pagada parcialmente con tasa mejor

- **GIVEN** una factura de cliente por 100 USD, contabilizada el 2026-01-01 a tasa 40.0
- **AND** se paga 100 USD el 2026-08-01 a tasa 44.0 (tasa mejor, menos pesos necesarios)
- **AND** el toggle activado
- **WHEN** se concilia
- **THEN** se genera una Nota de Crédito con:
  - `move_type = 'out_refund'`
  - `reversed_entry_id = <id de la factura>`
  - `date = 2026-08-01`
  - `journal_id = <diario de venta original, no dedicado>`
  - `name = <refund_sequence_id del diario, ej: NC/2026/0001>`
- **AND** la línea tiene `account_id = company.expense_currency_exchange_account_id`
  (no derivado del producto)

### Requirement: ND/NC no se duplican en conciliaciones simultáneas

El sistema SHALL crear como máximo UNA Nota de Débito/Crédito por pareja (factura, pago).
Si dos reconciliaciones casi simultáneas del mismo (factura, pago) se ejecutan,
solo la primera crea la nota; la segunda detecta que ya existe y la reutiliza.

El guard anti-duplicado SHALL excluir notas ya revertidas (campo `reversal_move_ids`
no vacío), porque revertir una nota no la cancela, solo la marca como "tiene reversión".
Sin esta exclusión, re-conciliar tras romper y reasignar el mismo pago encontraría
la ND vieja revertida y saldría sin crear una nueva ni conciliar nada.

#### Scenario: Dos conciliaciones casi simultáneas del mismo par invoice-payment

- **GIVEN** una factura y un pago en la misma transacción de base de datos
- **AND** dos threads/procesos intentan conciliar el mismo (factura, pago)
- **WHEN** la segunda conciliación busca una ND existente
- **THEN** encuentra la creada por la primera
- **AND** no crea una segunda

#### Scenario: Re-conciliación después de romper y reasignar

- **GIVEN** una factura con una ND ya emitida y revertida
- **AND** se rompe la conciliación original
- **AND** se reasigna el MISMO pago a la factura
- **WHEN** se concilia de nuevo
- **THEN** se crea una NUEVA ND (no reutiliza la revertida)
- **AND** la ND revertida sigue existiendo (nunca se cancela)

### Requirement: La reversión de la conciliación revierte (no cancela) la ND/NC

El sistema SHALL REVERTIR (generar un asiento de reversal) la ND/NC si la
conciliación que la originó se rompe (usuario hace click en el botón ✕ del
widget de pagos). La reversión SHALL generar un asiento de tipo opuesto (ND
genera NC reversa, y viceversa) con `reversed_entry_id` apuntando al original.

La reversión nunca SHALL CANCELAR ni BORRAR la nota, porque es un documento
fiscal ya posteado con correlativo real y no puede desaparecer del registro.

El usuario NO SHALL poder romper la conciliación de la nota directamente (hacer
click ✕ sobre la nota misma), solo puede romper la conciliación original
(factura <-> pago), que automáticamente revierte la nota.

#### Scenario: Romper la conciliación factura-pago revierte la ND

- **GIVEN** una factura con una ND posteada y conciliada
- **WHEN** el usuario hace click ✕ en el widget de pagos de la factura
- **THEN** el partial entre factura y pago se destruye
- **AND** la ND se revierte automáticamente (nueva NC con `reversed_entry_id`)
- **AND** la ND original sigue existiendo con `state = 'posted'`

#### Scenario: Intentar romper la conciliación de la nota directamente falla

- **GIVEN** una ND posteada
- **WHEN** el usuario intenta hacer click ✕ en el partial entre la ND y la factura
- **THEN** se lanza `UserError` bloqueando la acción
- **AND** se comunica que solo se puede romper vía la conciliación original

### Requirement: Pagos agrupados atribuyen la ND/NC a la factura CORRECTA

El sistema SHALL determinar la factura exacta a la que pertenece cada residual
cuando un ÚNICO pago se aplica a VARIAS facturas de cliente en una sola
reconciliación (pago agrupado). No SHALL NUNCA ADIVINAR por orden de aparición
en la lista, porque dos facturas con montos distintos pueden dar resultados
incorrectos (un pago de 500 aplicado a facturas de 100 y 500 USD podría
atribuir la nota de diferencial a la de 100 cuando corresponde a la de 500).

Se logra capturando la pareja EXACTA (factura, pago) en el momento en que Odoo
calcula el residual, stasheando el par antes de permitir que Odoo prosiga.

#### Scenario: Pago agrupado a dos facturas con montos distintos

- **GIVEN** dos facturas de cliente de 100 USD y 500 USD
- **AND** un pago único de 600 USD que cubre ambas
- **WHEN** se concilian las dos facturas contra el pago
- **THEN** se generan DOS notas de diferencial, una por factura
- **AND** la nota de 100 USD está vinculada a la factura de 100 USD
- **AND** la nota de 500 USD está vinculada a la factura de 500 USD
- **AND** no hay swap o atribución cruzada

### Requirement: La configuración falta-parámetro falla RUIDOSO antes de crear nota

El sistema SHALL validar que existan los parámetros obligatorios ANTES de
intentar crear la ND/NC. Si falta el producto, la pricelist, o (para ND) el
diario dedicado con secuencia, SHALL lanzar `UserError` EXPLÍCITO y NUNCA creará
una nota incompleta.

La validación ocurre en DOS puntos:
1. Al guardar la compañía (constraint `_check_l10n_ve_exchange_use_nd_nc_requires_config`)
2. Al momento de reconciliación (defensa en profundidad en `_create_exchange_difference_note`)

#### Scenario: Toggle activado sin producto configurado

- **GIVEN** una compañía con `l10n_ve_exchange_use_nd_nc = True`
- **AND** sin `l10n_ve_exchange_note_product_id` seteado
- **WHEN** el usuario intenta guardar la compañía
- **THEN** falla con `ValidationError` explícito
- **AND** no permite guardarse

#### Scenario: Configuración incompleta descubierta en tiempo de reconciliación

- **GIVEN** la compañía se guardó con configuración completa
- **AND** alguien después removió el producto configurado
- **WHEN** ocurre una conciliación que triggers la ND/NC
- **THEN** falla con `UserError` ANTES de crear el asiento
- **AND** se detalla qué falta

### Requirement: La ND/NC solo aplica a facturas de CLIENTE elegibles

El sistema SHALL crear ND/NC SOLO para:
- `out_invoice` y `out_refund` (incluye ND de cliente nativas de Odoo)
- SIN `debit_origin_id` (no es ND/débito de otro documento)
- SIN `reversed_entry_id` (no es NC reversal de otro documento)
- SIN `l10n_ve_igtf_note_debit_origin` (no es ND generada por `l10n_ve_igtf`)

Cualquier otro documento (factura de proveedor, ND de proveedor, NC de negocio,
asiento misceláneo, etc.) sigue el comportamiento nativo de Odoo.

El asiento genérico nativo que Odoo genera igual se etiqueta con
`l10n_ve_exchange_diff_entry = True` para trazabilidad en cualquier caso.

#### Scenario: Factura de proveedor no genera ND/NC propia

- **GIVEN** una factura de compra en moneda extranjera
- **WHEN** se concilia contra un pago con tasa distinta
- **THEN** se genera solo el asiento genérico nativo de Odoo
- **AND** no se genera ND/NC de este módulo

#### Scenario: ND de cliente nativa SÍ es elegible

- **GIVEN** una Nota de Débito de cliente nativa de Odoo (move_type=out_invoice, debit_origin_id!=False)
- **WHEN** se concilia contra un pago con diferencial cambiario
- **THEN** se genera la ND/NC de este módulo (es una factura de cliente válida)

### Requirement: Compatibilidad con `l10n_ve_igtf`

El sistema SHALL funcionar correctamente cuando `l10n_ve_igtf` está también
activado. Ambos módulos son independientes y se aplican sobre la misma
conciliación sin interferencia.

- ND/NC de este módulo SÍ llevan el `l10n_ve_exchange_diff_entry` tag
- ND de IGTF (`l10n_ve_igtf_note_debit_origin`) SÍ están excluidas de generar
  ND/NC de este módulo (guard en `reconcile()`)

#### Scenario: Factura con diferencial cambiario + IGTF

- **GIVEN** una factura de cliente en USD con diferencial cambiario + IGTF
- **WHEN** se concilia con un pago
- **THEN** se genera una ND/NC de diferencial cambiario
- **AND** también se calcula/aplica IGTF
- **AND** ambas se aplican correctamente sin duplicación ni error

### Requirement: Acoplamiento a API interna se detecta en test + runtime

El módulo está acoplado al método INTERNO `_prepare_reconciliation_single_partial`
de Odoo 19.0-20260710. Si Odoo cambia este método (firma o keys de diccionario),
el error SHALL DETECTARSE RÁPIDAMENTE, no en silencio meses después.

Se logra con:
1. **Test de compatibilidad (`test_odoo_core_api_compatibility`):** Verifica
   que la firma y los parámetros sean exactamente los esperados.
2. **Runtime guard:** Verifica que `debit_values['aml']` y `credit_values['aml']`
   existan antes de stashearlos. Si no existen, lanza `RuntimeError` explícito.

#### Scenario: Firma del método cambia en futuro Odoo 19.x

- **GIVEN** Odoo 19.2 cambia la firma de `_prepare_reconciliation_single_partial`
- **WHEN** se ejecutan los tests
- **THEN** `test_odoo_core_api_compatibility` falla con TypeError
- **AND** el error es claro

#### Scenario: Keys de diccionario cambian en futuro Odoo 19.x

- **GIVEN** Odoo 19.1 renombra `debit_values['aml']` por `debit_values['line']`
- **WHEN** ocurre una reconciliación
- **THEN** el runtime guard detecta que `'aml'` no existe
- **AND** lanza `RuntimeError` explícito ANTES de stashear None
- **AND** la reconciliación falla ruidoso, no silenciosamente
