# Spec delta: cuenta-default-diarios-banco-81735

## MODIFIED Requirements

### Requirement: Métodos de pago bancarios con cuenta obligatoria

Todo método de pago (entrante o saliente) de un diario de tipo `bank` DEBE (MUST) tener `payment_account_id` asignada. Esto se garantiza con dos constraints independientes, salvo durante la carga de plantillas contables o instalación:

- `_check_payment_method_line_accounts` de `account.journal` -- se dispara cuando cambia la relación o two2many `inbound_payment_method_line_ids`/`outbound_payment_method_line_ids` del diario (ej. al guardar el diario con líneas sin cuenta, o al vaciar la colección de un lado).
- `_check_payment_account_id_required_for_bank` de `account.payment.method.line` -- se dispara al escribir directamente sobre la línea, camino que el constrains del diario NO cubre (Odoo no reevalúa un constrains sobre un campo o2m cuando se edita un campo propio del registro hijo). Su propio `create()` rellena `payment_account_id` desde `default_account_id` del diario ANTES de validar, para que este constrains pueda ser estricto sin romper la creación de diarios banco por ningún camino (compute nativo, `_auto_link_payment_methods`, payment providers).

Un diario `bank` también DEBE (MUST) tener al menos una línea de método de pago entrante y una saliente.

#### Scenario: Diario sin líneas entrantes o salientes

- **WHEN** se vacía `inbound_payment_method_line_ids` o `outbound_payment_method_line_ids` de un diario `bank` ya guardado
- **THEN** se lanza un error indicando que el diario debe tener al menos un método de pago de ese lado

#### Scenario: Ninguna línea tiene cuenta

- **WHEN** se guarda un diario bancario donde ninguna línea de método de pago (entrante ni saliente) tiene cuenta
- **THEN** se lanza un error "All payment methods must have an assigned account."

#### Scenario: Una línea con cuenta y otra sin

- **WHEN** un diario bancario tiene una línea con cuenta asignada y otra sin, del mismo lado (entrante o saliente)
- **THEN** se lanza el mismo error -- el constrains falla si CUALQUIER línea carece de cuenta, no solo cuando todas carecen

#### Scenario: Escritura directa sobre la línea

- **WHEN** se escribe `payment_account_id = False` directamente sobre una línea de un diario `bank`, sin pasar por el campo o2m del diario
- **THEN** se lanza un error "must have an assigned account" (vía el constrains propio de `account.payment.method.line`)

#### Scenario: Diario de caja no se ve afectado

- **WHEN** se crea o edita un diario de tipo `cash` con líneas de método de pago sin cuenta
- **THEN** no se lanza ningún error -- ambos constraints están acotados a `type == 'bank'`

## ADDED Requirements

### Requirement: Cuenta bancaria obligatoria en diarios tipo banco

Todo diario de tipo `bank` DEBE (MUST) tener `default_account_id` ("Cuenta Bancaria") asignado (constraint `_check_default_account_id_required_for_bank` de `account.journal`). Esto es independiente de la propagación a los métodos de pago (ver el siguiente requirement): un diario banco sin esta cuenta no se puede guardar bajo ninguna circunstancia.

#### Scenario: Diario banco sin cuenta bancaria

- **WHEN** se crea o guarda un diario de tipo `bank` sin `default_account_id`
- **THEN** se lanza un error "Bank journals require a default account (Bank Account)."

### Requirement: Propagación automática de la cuenta bancaria a los métodos de pago

Cuando un diario de tipo `bank` tiene `default_account_id` asignado, esa cuenta DEBE (MUST) propagarse automáticamente a `payment_account_id` en todas sus líneas de método de pago (entrantes y salientes) que no tengan ya una cuenta propia (`_fill_payment_account_id_from_default` de `account.journal`), sin intervención manual del usuario. Esto aplica tanto a las líneas generadas por el compute nativo de Odoo al crear/editar el diario, como a líneas de método de pago agregadas manualmente después, vía el `default` de `payment_account_id` en `account.payment.method.line` (`_default_payment_account_id`, usa el contexto `default_journal_id`).

Editar `default_account_id` en un diario ya guardado con líneas de método de pago adicionales (más allá de las nativas) NO DEBE (MUST NOT) desvincular ni eliminar esas líneas extra, ni los pagos que ya las usan -- la propagación solo rellena cuentas vacías, nunca reconstruye las líneas desde cero.

#### Scenario: Creación del diario en una sola llamada API

- **WHEN** se crea un diario de tipo `bank` con `default_account_id` ya en los valores, sin pasar por ningún onchange
- **THEN** todas las líneas de método de pago generadas (entrantes y salientes) toman esa cuenta en `payment_account_id`

#### Scenario: Línea de método de pago agregada manualmente

- **WHEN** se crea una `account.payment.method.line` para un diario `bank` existente (con el contexto `default_journal_id` del diario)
- **THEN** la línea toma `default_account_id` del diario como su `payment_account_id`, sin que el usuario la configure a mano

#### Scenario: Edición de la cuenta bancaria no borra líneas extra

- **WHEN** se edita `default_account_id` en un diario `bank` ya guardado que tiene una línea de método de pago agregada manualmente (además de las nativas)
- **THEN** esa línea extra sigue existiendo, vinculada al mismo diario, con su nombre intacto

#### Scenario: Diario no bancario no hereda cuenta

- **WHEN** se crea una línea de método de pago para un diario de tipo distinto a `bank` (ej. `cash`)
- **THEN** `payment_account_id` queda vacío, sin tomar ninguna cuenta por defecto

### Requirement: Bloqueo de confirmación de pagos de banco sin cuenta contable

Un `account.payment` cuyo diario es de tipo `bank` y cuya línea de método de pago (`payment_method_line_id`) no tiene `payment_account_id` NO DEBE (MUST NOT) poder confirmarse (`action_post`), ni quedar con un asiento contable generado usando una cuenta genérica distinta a la configurada.

El core de Odoo, al confirmar un pago sin `outstanding_account_id`, normalmente cae en un fallback silencioso (`company.transfer_account_id` o una cuenta del chart template) cuando la app completa de Contabilidad no está instalada, o directamente omite ese fallback -- dejando el pago confirmado sin asiento y sin error -- cuando sí está instalada. `_get_outstanding_account` (override de `account.payment`) DEBE (MUST) deshabilitar ese fallback para diarios `bank` sin cuenta en su línea, dejando `outstanding_account_id` en `False`; `action_post` (override de `account.payment`) DEBE (MUST) rechazar la confirmación en ese caso con un error explícito, antes de intentar generar el asiento.

#### Scenario: Pago correctamente configurado

- **WHEN** se confirma un pago cuyo diario `bank` y método de pago tienen cuenta asignada
- **THEN** el pago genera su asiento contable normalmente

#### Scenario: Línea sin cuenta, app de Contabilidad no instalada

- **WHEN** se crea y confirma un pago contra una línea de método de pago de un diario `bank` sin `payment_account_id` (incluso si la compañía tiene `transfer_account_id` configurado, que en otro caso habría sido usado en silencio)
- **THEN** el pago se crea con `outstanding_account_id` en `False`, y `action_post` lanza un error explícito en vez de confirmar sin asiento

### Requirement: Migración de diarios banco existentes sin cuenta

Al actualizar el módulo, los diarios de tipo `bank` ya existentes cuyas líneas de método de pago no tengan `payment_account_id` DEBEN (MUST) recibir automáticamente la cuenta de `default_account_id` del propio diario (migración `19.0.1.0.28`, idempotente), para no quedar bloqueados por los constraints de este documento apenas se actualice el sistema. Los diarios que tampoco tengan `default_account_id` configurado quedan registrados en el log del servidor, sin bloquear la migración.
