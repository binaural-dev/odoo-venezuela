## ADDED Requirements

### Requirement: Cola de digitalización TFHKA con cron unificado

`account.move`, `account.retention` y `stock.picking` DEBEN (MUST) heredar el modelo abstracto
`tfhka.digitalization.mixin`, que agrega el campo `tfhka_digitalization_state` (`none / queued /
processing / success / error / data_error / not_applicable`) y `tfhka_queued_at`. Confirmar o
publicar un documento elegible DEBE (MUST) únicamente encolarlo (`_tfhka_enqueue_digitalization`,
un `write` de campo sin llamada HTTP) y NO DEBE (MUST NOT) emitirlo inline en ese mismo request. Un
cron unificado (`_tfhka_cron_process_queue_multi`, corriendo cada minuto sobre `account.move`,
`account.retention` y `stock.picking`) es el único punto que llama a TFHKA: por cada modelo procesa
los documentos en estado `queued` en orden `tfhka_queued_at asc, id asc` (FIFO, más antiguo
primero), intercalando un documento de cada modelo por vuelta en vez de agotar la cola de un modelo
antes de pasar al siguiente. Para un modelo dado, NUNCA DEBE (MUST NOT) haber más de un documento en
`processing` ni más de uno en `error`/`data_error` a la vez: si el modelo ya tiene un documento en
`error` o `data_error`, el cron NO DEBE (MUST NOT) procesar el resto de su cola hasta que ese
documento se resuelva (reintento exitoso), sin afectar la cola de los otros modelos. Si la
digitalización de un documento falla por el error de negocio de límite de tasa de TFHKA, el sistema
DEBE (MUST) reintentar una única vez tras esperar `RATE_LIMIT_RETRY_WAIT` segundos antes de marcarlo
`error`.

#### Scenario: Confirmar una factura la encola, no la emite

- **WHEN** se publica una factura elegible para digitalización
- **THEN** queda en estado `queued` y la publicación se completa sin haber llamado a la API de TFHKA

#### Scenario: Un modelo con error no bloquea a los demás

- **WHEN** `account.move` tiene un documento en `error` y `account.retention` tiene documentos
  `queued` sin errores propios
- **THEN** el cron sigue digitalizando la cola de `account.retention` en esa misma corrida, mientras
  la de `account.move` permanece detenida

#### Scenario: Reintento por límite de tasa

- **WHEN** TFHKA responde con su error de negocio de límite de tasa al digitalizar un documento
- **THEN** el sistema espera y reintenta una vez esa misma llamada antes de decidir éxito o error

### Requirement: Recuperación de digitalizaciones interrumpidas

Al inicio de cada corrida del cron, por cada modelo, el sistema DEBE (MUST) buscar documentos en
`processing` (solo puede haberlos si una corrida anterior fue interrumpida a mitad de una llamada,
p. ej. por `limit_time_cron`) y resolverlos antes de tocar la cola de `queued`, en orden `date_state
asc` (el más antiguo primero). Para cada uno DEBE (MUST) buscar en `tfhka.api.log` una llamada
exitosa a `/Emision` posterior al inicio de ese intento: si existe, DEBE (MUST) reconstruir el
resultado exitoso a partir de esa respuesta ya registrada (sin reenviar el documento, evitando un
duplicado) y marcarlo `success`; si no existe y ya pasó el período de gracia de un minuto, DEBE
(MUST) marcarlo `error` indicando que no hay confirmación de que TFHKA lo haya recibido; si aún no
pasó ese período, DEBE (MUST) dejarlo intacto en `processing` y detener por completo el
procesamiento de ese modelo en esta corrida (ni siquiera evalúa la cola de `queued`), porque el
intento puede seguir genuinamente en curso.

#### Scenario: Interrupción con respuesta ya recibida por TFHKA

- **WHEN** el cron muere mientras un documento está en `processing`, pero TFHKA sí procesó la
  emisión antes del corte (hay un log exitoso posterior al inicio del intento)
- **THEN** la siguiente corrida marca el documento `success` a partir del log, sin reenviarlo

#### Scenario: Interrupción sin respuesta tras el período de gracia

- **WHEN** un documento lleva más de un minuto en `processing` y no hay ningún log exitoso posterior
  al inicio del intento
- **THEN** se marca `error` con un mensaje que advierte verificar con TFHKA antes de reintentar

### Requirement: Estado `not_applicable` para facturas fuera de alcance de digitalización

Al encolar tras publicar (`_tfhka_enqueue_eligible_for_digitalization`), una factura de cliente
(`out_invoice`/`out_refund`) en una compañía con `invoice_digital_tfhka` activo cuyo diario NO tenga
`digital_invoice` DEBE (MUST) marcarse `not_applicable` en vez de quedar en `none` indefinidamente
(indistinguible de "todavía no publicada"). Una factura ya digitalizada NUNCA DEBE (MUST NOT)
marcarse `not_applicable`, y este marcado NO DEBE (MUST NOT) depender de si la compañía usa el modo
"digitalización con pago" (`digitalization_with_payment_tfhka`) -- ese modo solo cambia cómo se
encola una factura elegible, no si un diario no digital sigue siendo un caso sin salida.

#### Scenario: Factura en diario no digital

- **WHEN** se publica una factura de cliente en una compañía con TFHKA activo, cuyo diario no tiene
  facturación digital habilitada
- **THEN** la factura queda en `tfhka_digitalization_state = 'not_applicable'`, no en `'none'` ni en
  la cola

### Requirement: Alerta de documentos bloqueados para usuarios internos

El sistema DEBE (MUST) exponer, para usuarios internos únicamente y respetando los derechos de
acceso y las reglas de registro normales (sin `sudo()`), la lista de documentos de
`account.move`/`account.retention`/`stock.picking` cuyo `tfhka_digitalization_state` esté en
`error` o `data_error`, acotada a las compañías de la sesión actual, para el banner mostrado en toda
página (`views/tfhka_digitalization_alert.xml`). Para un usuario no interno (portal/público) el
método DEBE (MUST) devolver una lista vacía sin ejecutar ninguna búsqueda.

#### Scenario: Usuario interno con documentos bloqueados

- **WHEN** un usuario interno con acceso a la compañía de una factura en `error` visita cualquier
  página
- **THEN** el banner lista esa factura, enlazando a su registro

#### Scenario: Usuario portal

- **WHEN** un usuario portal/público carga una página
- **THEN** no se ejecuta ninguna búsqueda de documentos bloqueados y el banner no muestra nada

## MODIFIED Requirements

### Requirement: Emisión digital de facturas, notas de débito y notas de crédito

Al publicar una factura de cliente, nota de débito o nota de crédito elegible (diario con
`digital_invoice`, compañía con `invoice_digital_tfhka` activo, no ya digitalizada, y sin el modo
"digitalización con pago"), el sistema DEBE (MUST) únicamente encolarla
(`_tfhka_enqueue_eligible_for_digitalization`); la emisión real contra `/Emision` ocurre
exclusivamente en el cron de la cola (ver "Cola de digitalización TFHKA con cron unificado"), nunca
en el request de publicación. El método `generate_document_digital` de `account.move` sigue
determinando el tipo de documento (`01` factura de cliente, `03` con `debit_origin_id`, `02` con
`reversed_entry_id`) y, tras una emisión exitosa del cron, marca `is_digitalized`, asigna al
`correlative` el `numeroControl` devuelto por TFHKA y registra un mensaje en el chatter -- eso no
cambia, solo el momento y quién dispara la llamada.

#### Scenario: Factura de cliente digitalizada

- **WHEN** el cron digitaliza una factura de cliente previamente encolada y la API responde con
  éxito
- **THEN** la factura queda con `is_digitalized = True`, su `correlative` es el número de control
  devuelto y se publica un mensaje de confirmación en el chatter

#### Scenario: Compañía sin facturación digital activa

- **WHEN** se publica una factura con `invoice_digital_tfhka` desactivado
- **THEN** no se encola ningún documento y nada se emite

### Requirement: Emisión digital de comprobantes de retención IVA e ISLR

Al publicar un comprobante de retención elegible en el flujo automático, o al usar el botón manual,
el sistema DEBE (MUST) únicamente encolarlo; la emisión real contra `/Emision` ocurre
exclusivamente en el cron de la cola. El método `generate_document_digital` de `account.retention`
sigue construyendo el tipo de documento (`05` IVA / `06` ISLR) y delegando en
`tfhka.retention.service.send_retention`, que arma sujeto retenido, totales y detalle por línea
exactamente igual que antes; tras el éxito el cron marca `is_digitalized`, guarda el `numeroControl`
en `control_number_tfhka` y registra el mensaje en el chatter. Una retención ya digitalizada DEBE
(MUST) rechazarse con error al intentar reenviarla, salvo que la compañía tenga
`invoice_digital_tfhka` desactivado, caso en el que el método retorna sin validar nada.

#### Scenario: Retención ya digitalizada

- **WHEN** se intenta encolar o reenviar una retención con `is_digitalized = True` en una compañía
  con facturación digital activa
- **THEN** se lanza un `UserError` indicando que el documento ya fue digitalizado

#### Scenario: Emisión exitosa de retención IVA

- **WHEN** el cron digitaliza una retención IVA previamente encolada y la API acepta la emisión
- **THEN** la retención queda digitalizada con su número de control TFHKA registrado

#### Scenario: Facturación digital desactivada

- **WHEN** se invoca la emisión digital de una retención con `invoice_digital_tfhka` desactivado
- **THEN** el método retorna sin llamar a la API y sin lanzar el error de documento ya digitalizado

### Requirement: Digitalización automática de guías de despacho

Al validar un `stock.picking` (`button_validate`) elegible (compañía con `invoice_digital_tfhka`
activo, guía de despacho, no digitalizada, no es recepción), el sistema DEBE (MUST) únicamente
encolarlo; la emisión real como documento tipo `04` ocurre exclusivamente en el cron de la cola,
comparando en ese momento el siguiente número de TFHKA contra el `number_next_actual` de la
secuencia `guide.number` de la compañía y aplicando el mismo criterio de `sequence_validation_tfhka`
que antes. Tras el éxito el cron guarda `control_number_tfhka`, marca `is_digitalized` y ejecuta
`_set_guide_number`, que sigue asignando `guide_number` solo si el picking tiene
`dispatch_guide_controls` (a un picking ya digitalizado, si la facturación digital está activa;
directamente, si no lo está).

#### Scenario: Validación de una entrega con guía

- **WHEN** se valida un picking de salida marcado como guía de despacho, con
  `dispatch_guide_controls`, en una compañía con facturación digital activa
- **THEN** el picking queda `queued`, y el cron lo digitaliza como tipo `04`, dejándolo con número
  de control y número de guía asignados

#### Scenario: Picking digitalizado sin controles de guía

- **WHEN** el cron digitaliza con éxito un picking que no tiene `dispatch_guide_controls`
- **THEN** queda con `is_digitalized` y `control_number_tfhka`, pero sin `guide_number` asignado

### Requirement: Alerta confirmable de secuencia en retenciones

En la digitalización de un comprobante de retención (disparada por el cron de la cola, nunca
inline), el número a comparar DEBE (MUST) obtenerse como `int(number[6:])`, es decir el correlativo
del comprobante sin su prefijo `AAAAMM` de seis caracteres; la consulta de numeración y de último
documento del comprobante se hacen siempre sin serie (`serie: ""`, tramo "NO APLICA"). Si ese
correlativo no coincide con el siguiente número de TFHKA, la validación de secuencia de la compañía
está activa y el contexto `account_retention_alert` no está presente, el sistema DEBE (MUST) lanzar
`TfhkaSequenceMismatchError` en vez de emitir -- como corre en el cron, sin un humano presente que
pueda contestar un wizard en el acto, el mixin clasifica esa excepción como `data_error` y detiene
ahí la cola de retenciones. El botón manual `account.retention.action_tfhka_review_sequence_mismatch`
(visible cuando el estado es `data_error`) DEBE (MUST) recalcular esa misma brecha de forma
sincrónica (sin emitir nada) y abrir el wizard `account.retention.alert.wizard` con el mensaje;
solo si el usuario confirma (`action_confirm`), la retención se reencola con
`tfhka_auto_accept_sequence_mismatch = True`, y el contexto `account_retention_alert` hace que el
siguiente intento del cron omita la comparación y digitalice, registrando en el chatter que la
diferencia de secuencia fue aceptada además del mensaje de digitalización.

#### Scenario: Secuencia desincronizada detenida en el cron

- **WHEN** el cron intenta digitalizar una retención cuya secuencia no coincide con la de TFHKA, sin
  `tfhka_auto_accept_sequence_mismatch`
- **THEN** la retención queda en `data_error`, con `is_digitalized` en `False` y sin haberse enviado
  nada a TFHKA

#### Scenario: Usuario revisa y confirma la diferencia

- **WHEN** un usuario abre `action_tfhka_review_sequence_mismatch` sobre una retención en
  `data_error` por mismatch de secuencia y confirma el wizard
- **THEN** la retención vuelve a `queued`, y el siguiente tick del cron la emite exitosamente
  registrando en el chatter la aceptación de la diferencia

#### Scenario: Comparación del correlativo sin prefijo de período

- **WHEN** el comprobante tiene `number = "20250800000123"` y TFHKA reporta como siguiente el
  documento 123
- **THEN** no se lanza `TfhkaSequenceMismatchError`, porque la comparación se hace contra `123` (los
  caracteres a partir del séptimo) y no contra el número completo

## REMOVED Requirements

### Requirement: Bloqueo de publicación con documentos sin digitalizar del mismo diario

**Razón**: la cola de digitalización procesa en orden FIFO por modelo y se detiene por completo en
el primer documento en `error`/`data_error` de ese modelo (ver "Cola de digitalización TFHKA con
cron unificado"), por lo que ningún documento posterior de un mismo diario puede llegar a
digitalizarse antes que uno anterior sin digitalizar todavía -- la misma garantía que este guard
existía para dar, sin bloquear la publicación en sí. Mantener el guard de publicación además
entraba en conflicto con encolar (en vez de emitir inline): bloquear la publicación por un documento
que solo está *pendiente en la cola* (no fallido) habría impedido publicar documentos legítimos a la
espera de su turno del cron.
