# l10n_ve_exchange_difference

## Purpose

Documenta el diferencial cambiario de facturas y notas de CLIENTE en moneda
extranjera como Notas de Débito/Crédito fiscales reales, en vez del asiento
genérico interno que Odoo crea por defecto al conciliar. Intercepta el cálculo
nativo de Odoo (`_prepare_exchange_difference_move_vals`/
`_create_exchange_difference_moves`, núcleo `account.move.line`) para líneas
de factura/nota de cliente elegibles, y redirige el monto exacto que Odoo ya
determinó a una Nota de Débito (ganancia, diario dedicado con secuencia
propia) o Nota de Crédito (pérdida, mismo diario de venta que la factura de
origen) en vez del asiento genérico. La nota se crea y cierra de forma
síncrona, en el mismo punto de la transacción de conciliación donde Odoo crea
su propio asiento genérico, vinculada a la factura de origen y conciliada de
inmediato contra el residual. Si la conciliación factura-pago que originó la
nota se rompe, la nota (ya posteada, con secuencia fiscal real) se revierte
automáticamente -- nunca se cancela ni se borra, y desconciliarla directamente
está bloqueado. Solo aplica a facturas/notas de CLIENTE; cualquier otro caso
(facturas de proveedor, asientos misceláneos) sigue el comportamiento nativo
de Odoo sin modificar. Extiende `account.move`, `account.move.line` y
`account.partial.reconcile`. Depende de `account`, `l10n_ve_accountant`,
`od_journal_sequence`, `l10n_ve_invoice`, `l10n_ve_igtf` y
`account_invoice_pricelist`.

## Requirements

### Requirement: Una Nota de Débito se emite cuando hay ganancia cambiaria

El sistema SHALL emitir una Nota de Débito (out_invoice) vinculada a la factura
de origen, posteada en un diario dedicado con secuencia propia, y conciliada
contra el residual de diferencial, cuando la conciliación de una factura de
cliente en moneda extranjera contra un pago con tasa distinta deja un residual
positivo (lado de crédito) que representa una ganancia cambiaria.

La ND SHALL estar fechada el día del pago, no el día de la conciliación, y
SHALL incluir una línea de producto configurada en la compañía. Su numeración
(y la de cualquier ND/NC de este módulo, incluidas las reversiones) SHALL
recalcular también `payment_reference` en el mismo paso -- asignar `name`
directo, fuera del compute nativo que normalmente encadena ese recálculo por
dependencia, lo dejaría vacío para siempre en cualquier ND/NC de este módulo.

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

El diario de la factura de origen SHALL tener su propia `refund_sequence_id`
configurada antes de conciliar -- el sistema NUNCA autoprovisiona esa
secuencia en silencio sobre el diario de venta del cliente (compartido con
cualquier factura/NC de negocio normal): lanza `UserError` explícito pidiendo
configuración.

#### Scenario: Factura en USD pagada parcialmente con tasa mejor

- **GIVEN** una factura de cliente por 100 USD, contabilizada el 2026-01-01 a tasa 40.0
- **AND** se paga 100 USD el 2026-08-01 a tasa 44.0 (tasa mejor, menos pesos necesarios)
- **AND** el toggle activado
- **AND** el diario de venta de la factura ya tiene `refund_sequence_id` configurada
- **WHEN** se concilia
- **THEN** se genera una Nota de Crédito con:
  - `move_type = 'out_refund'`
  - `reversed_entry_id = <id de la factura>`
  - `date = 2026-08-01`
  - `journal_id = <diario de venta original, no dedicado>`
  - `name = <refund_sequence_id del diario, ej: NC/2026/0001>`
- **AND** la línea tiene `account_id = company.expense_currency_exchange_account_id`
  (no derivado del producto)

#### Scenario: Diario de venta sin secuencia de NC configurada

- **GIVEN** una factura de cliente en USD cuyo diario de venta NO tiene `refund_sequence_id`
- **WHEN** la conciliación contra el pago deja un residual de pérdida cambiaria
- **THEN** se lanza `UserError` explícito pidiendo configurar la secuencia de NC del diario
- **AND** no se autoprovisiona nada en silencio sobre ese diario

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
conciliación que la originó se rompe, sin importar por qué VÍA se rompe -- el
botón ✕ del widget de pagos, o cualquier otro camino que termine borrando el
`account.partial.reconcile` correspondiente (ej. `remove_move_reconcile()`,
usado directo por `l10n_ve_igtf` al cancelar un anticipo). La reversión SHALL
generar un asiento de tipo opuesto (ND genera NC reversa, y viceversa) con
`l10n_ve_exchange_original_id` apuntando al original.

La reversión nunca SHALL CANCELAR ni BORRAR la nota, porque es un documento
fiscal ya posteado con correlativo real y no puede desaparecer del registro.
La reversión SHALL numerarse con la secuencia dedicada correspondiente
(nunca con el numerador normal del diario) -- si esa secuencia no está
configurada, SHALL abortar con `UserError` en vez de consumir un correlativo
ajeno en silencio.

El usuario NO SHALL poder romper la conciliación de la nota directamente (hacer
click ✕ sobre la nota misma), solo puede romper la conciliación original
(factura <-> pago), que automáticamente revierte la nota.

#### Scenario: Romper la conciliación factura-pago revierte la ND

- **GIVEN** una factura con una ND posteada y conciliada
- **WHEN** el usuario hace click ✕ en el widget de pagos de la factura
- **THEN** el partial entre factura y pago se destruye
- **AND** la ND se revierte automáticamente (nueva NC con `l10n_ve_exchange_original_id`)
- **AND** la ND original sigue existiendo con `state = 'posted'`

#### Scenario: Romper la conciliación por una vía distinta al widget también revierte la nota

- **GIVEN** una factura con una ND posteada y conciliada contra un anticipo
- **WHEN** se cancela el anticipo por `l10n_ve_igtf` (`remove_move_reconcile()`, sin pasar por el widget)
- **THEN** la ND se revierte igual, automáticamente
- **AND** no queda huérfana (posteada, con folio consumido, pero sin revertir)

#### Scenario: Intentar romper la conciliación de la nota directamente falla

- **GIVEN** una ND posteada
- **WHEN** el usuario intenta hacer click ✕ en el partial entre la ND y la factura
- **THEN** se lanza `UserError` bloqueando la acción
- **AND** se comunica que solo se puede romper vía la conciliación original

La detección de qué nota revertir (`account.partial.reconcile.unlink()`) SHALL correr para CUALQUIER partial que se elimine en el sistema, sin cortocircuitos basados en el estado ACTUAL del toggle `l10n_ve_exchange_use_nd_nc` de ninguna compañía involucrada: una nota emitida mientras el toggle estaba activo SHALL seguir revirtiéndose correctamente aunque el toggle se desactive DESPUÉS -- de lo contrario quedaría huérfana (posteada, con folio fiscal consumido, nunca revertida). Por la misma razón, esa detección NUNCA SHALL leer un campo escalar (ej. el toggle) directamente sobre la unión de las compañías de las dos líneas del partial -- un partial entre una sucursal y su matriz (soportado por el núcleo) involucra DOS compañías distintas, y esa lectura fallaría con `ValueError: Expected singleton` antes de llegar a revisar nada.

#### Scenario: El toggle se desactiva después de emitida la nota

- **GIVEN** una factura con una ND posteada, emitida mientras el toggle estaba activo
- **WHEN** se desactiva `l10n_ve_exchange_use_nd_nc` en la compañía
- **AND** luego se rompe la conciliación factura-pago que originó la ND
- **THEN** la ND se revierte igual, automáticamente
- **AND** no queda huérfana solo porque el toggle ya no está activo

#### Scenario: Se rompe un partial entre sucursal y matriz

- **GIVEN** un partial de conciliación cuya línea de débito es de una compañía y cuya línea de crédito es de la compañía MATRIZ de esa sucursal
- **WHEN** se elimina ese partial
- **THEN** la detección de nota a revertir no lanza `ValueError`
- **AND** se completa normalmente (revirtiendo la nota si existe, sin hacer nada si no)

### Requirement: Facturas conciliadas contra Notas de Crédito sueltas del mismo cliente también generan ND/NC

El sistema SHALL generar la ND/NC de diferencial también cuando una factura se
salda contra una Nota de Crédito de cliente SUELTA (sin `debit_origin_id` ni
`reversed_entry_id`, no derivada de un pago bancario -- ej. vía el widget
"outstanding credits" de la factura), no solo contra un pago real. Ambos
documentos (`out_invoice`/`out_refund`) califican por igual como "línea de
factura de cliente" en `reconcile()`, así que ninguno de los dos puede
asumirse como "el pago" por descarte -- la nota queda vinculada a cualquiera
de los dos que Odoo determine que retuvo el residual, y a la contraparte real
capturada vía `_prepare_reconciliation_single_partial` (no una adivinanza),
nunca a sí misma.

#### Scenario: Factura saldada contra una NC suelta del mismo cliente

- **GIVEN** una factura de cliente y una Nota de Crédito de cliente separada, sin relación entre sí, ambas en USD y fechadas con tasas distintas
- **WHEN** se concilian entre sí vía el widget de créditos pendientes de la factura
- **THEN** se genera una ND/NC de diferencial vinculada a UNO de los dos documentos como factura y al OTRO como su contraparte de pago
- **AND** la nota nunca queda vinculada a sí misma como su propio pago
- **AND** la nota queda cerrada por su propia conciliación

### Requirement: Pagos agrupados o multi-pago atribuyen la ND/NC a la factura y al pago CORRECTOS

El sistema SHALL determinar la factura exacta a la que pertenece cada residual
cuando un ÚNICO pago se aplica a VARIAS facturas de cliente en una sola
reconciliación (pago agrupado), y el pago exacto contra el que se concilió
cuando una ÚNICA factura se reconcilia contra VARIAS líneas de pago en una
sola llamada. No SHALL NUNCA ADIVINAR por orden de aparición en la lista en
NINGUNO de los dos sentidos, porque dos facturas (o dos pagos) con montos
distintos pueden dar resultados incorrectos.

Se logra capturando la pareja EXACTA (factura, pago) en el momento en que Odoo
calcula el residual, stasheando el par antes de permitir que Odoo prosiga, y
usando esa pareja real -- nunca el primer candidato de la lista -- para
determinar tanto la factura como el pago de cada nota.

#### Scenario: Pago agrupado a dos facturas con montos distintos

- **GIVEN** dos facturas de cliente de 100 USD y 500 USD
- **AND** un pago único de 600 USD que cubre ambas
- **WHEN** se concilian las dos facturas contra el pago
- **THEN** se generan DOS notas de diferencial, una por factura
- **AND** la nota de 100 USD está vinculada a la factura de 100 USD
- **AND** la nota de 500 USD está vinculada a la factura de 500 USD
- **AND** no hay swap o atribución cruzada

#### Scenario: Una factura conciliada contra más de una línea de pago en la misma llamada

- **GIVEN** una factura de cliente en USD
- **AND** se concilia en un solo `.reconcile()` contra dos líneas de pago distintas
- **WHEN** el residual de diferencial cae del lado de la factura en cada partial
- **THEN** cada nota queda atribuida al pago REAL de su propio partial
- **AND** ninguna nota queda atribuida al primer pago por defecto

### Requirement: La configuración falta-parámetro falla RUIDOSO antes de crear nota

El sistema SHALL validar que existan los parámetros obligatorios ANTES de
intentar crear la ND/NC, y SHALL NUNCA caer en silencio al numerador normal
del diario ni autoprovisionar configuración fiscal sobre un diario compartido
con documentos de negocio normales. Si falta el producto, la pricelist, la
secuencia dedicada de ND, o la secuencia de NC del diario de venta, SHALL
lanzar `UserError` EXPLÍCITO y NUNCA creará ni numerará una nota incompleta.

La validación ocurre en DOS puntos:
1. Al guardar la compañía (constraint `_check_l10n_ve_exchange_use_nd_nc_requires_config`)
2. Al momento de reconciliación (defensa en profundidad en `_create_exchange_difference_note`,
   `_compute_name_by_sequence` y `_reverse_moves`)

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
`l10n_ve_exchange_diff_entry = True` para trazabilidad, pero SOLO en el propio
asiento genérico -- esa etiqueta de trazabilidad NUNCA SHALL alterar el
comportamiento de validación nativo de Odoo (ej. la fecha de la secuencia)
para esos documentos ajenos al módulo.

#### Scenario: Factura de proveedor no genera ND/NC propia

- **GIVEN** una factura de compra en moneda extranjera
- **WHEN** se concilia contra un pago con tasa distinta
- **THEN** se genera solo el asiento genérico nativo de Odoo, etiquetado para trazabilidad
- **AND** no se genera ND/NC de este módulo
- **AND** la validación nativa de fecha de secuencia de ese asiento sigue aplicando sin cambios

#### Scenario: ND de cliente nativa SÍ es elegible

- **GIVEN** una Nota de Débito de cliente nativa de Odoo (move_type=out_invoice, debit_origin_id!=False)
- **WHEN** se concilia contra un pago con diferencial cambiario
- **THEN** se genera la ND/NC de este módulo (es una factura de cliente válida)

### Requirement: El widget de Conciliación Bancaria de Enterprise queda fuera de alcance a propósito

El sistema SHALL NOT generar ND/NC cuando la conciliación de una factura de
cliente contra una línea de extracto bancario ocurre a través del widget de
Conciliación Bancaria de Odoo Enterprise (`account_accountant`). Es una
decisión de alcance CONFIRMADA por el responsable del ticket, no una
limitación pendiente de resolver: ese widget calcula y aplica su propio
ajuste de diferencial cambiario directo sobre la línea de conciliación del
extracto (`account.bank.statement.line._reconcile_payments`, sin llamar
`account.move.line.reconcile()` en ningún momento), así que nunca pasa por el
mecanismo que este módulo intercepta. La contabilidad no se ve afectada
(Odoo resuelve el diferencial por su cuenta, sin pérdida de dinero ni
descuadre) -- lo único que no ocurre es la emisión de la ND/NC fiscal real,
y eso es intencional para este flujo.

Cualquier desarrollo propio de Binaural que necesite conciliar facturas de
cliente SHALL hacerlo siempre a través de `account.move.line.reconcile()`
(nunca `_reconcile_plan()` directo) para no perder, por una vía evitable,
la emisión de la ND/NC que si aplica al flujo del ticket.

#### Scenario: Conciliación vía el dashboard de extractos bancarios de Enterprise

- **GIVEN** una factura de cliente en moneda extranjera
- **WHEN** se concilia contra una línea de extracto bancario desde el widget de Conciliación Bancaria de Enterprise
- **THEN** Odoo resuelve el diferencial cambiario con su propio mecanismo interno del widget
- **AND** no se genera ninguna ND/NC de este módulo
- **AND** esto es el comportamiento esperado, no un defecto

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
   existan antes de stashearlos. Si no existen, lanza `UserError` explícito
   (no `RuntimeError`: una excepción interna genérica no se muestra en un
   diálogo legible al usuario, aborta la transacción igual de ruidoso pero en
   silencio de cara al usuario).

#### Scenario: Firma del método cambia en futuro Odoo 19.x

- **GIVEN** Odoo 19.2 cambia la firma de `_prepare_reconciliation_single_partial`
- **WHEN** se ejecutan los tests
- **THEN** `test_odoo_core_api_compatibility` falla con TypeError
- **AND** el error es claro

#### Scenario: Keys de diccionario cambian en futuro Odoo 19.x

- **GIVEN** Odoo 19.1 renombra `debit_values['aml']` por `debit_values['line']`
- **WHEN** ocurre una reconciliación
- **THEN** el runtime guard detecta que `'aml'` no existe
- **AND** lanza `UserError` explícito ANTES de stashear None
- **AND** la reconciliación falla ruidoso, no silenciosamente
