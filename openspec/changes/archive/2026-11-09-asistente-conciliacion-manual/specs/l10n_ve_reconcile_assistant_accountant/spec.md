# l10n_ve_reconcile_assistant_accountant

## Purpose

Conecta el asistente de `l10n_ve_reconcile_assistant` con la conciliación manual de Enterprise. Extiende `account.move.line.action_reconcile` de `account_accountant`. Se instala solo (`auto_install`) cuando están ambos módulos.

## Requirements

### Requirement: El botón Reconciliar abre el asistente

`action_reconcile` DEBE (MUST) abrir el asistente cuando `_l10n_ve_reconcile_classify` reporta `handled` para las líneas con saldo seleccionadas (incluidas las combinaciones que se bloquean con explicación), y DEBE (MUST) delegar en la conciliación nativa en cualquier otro caso, incluida una selección vacía o sin saldo.

#### Scenario: Pago contra factura

- **WHEN** el usuario pulsa Reconciliar con una factura y un pago seleccionados
- **THEN** se abre el asistente y no se concilia nada hasta confirmar

#### Scenario: Asientos manuales

- **WHEN** el usuario pulsa Reconciliar con un débito y un crédito manuales de la misma cuenta
- **THEN** la conciliación nativa los concilia sin abrir el asistente
