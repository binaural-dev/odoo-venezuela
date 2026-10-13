# Spec delta: exchange-difference-note (ticket 15726)

## ADDED Requirements

### Requirement: Las ND/NC de diferencial no llevan montos en moneda alterna

Las líneas de una ND/NC de diferencial cambiario (`l10n_ve_exchange_diff_entry`,
`out_invoice`/`out_refund`) SHALL tener `foreign_debit`, `foreign_credit` y
`foreign_balance` en 0.0, igual que el asiento de diferencial nativo. Se
garantiza al crear y al escribir, incluso si otro flujo escribe `foreign_balance`
directamente.

#### Scenario: Emitir una ND de diferencial

- **WHEN** se emite una ND por diferencial cambiario
- **THEN** sus apuntes SHALL tener los tres montos alternos en 0.0

#### Scenario: Notas ya emitidas

- **WHEN** se actualiza el módulo
- **THEN** las notas ya emitidas SHALL NOT modificarse (no hay migración; se corrigen manualmente si se reportan)

### Requirement: Las ND/NC de diferencial no vuelven a borrador

Una ND/NC de diferencial y su reverso automático SHALL NOT poder volver a
borrador. Extra no pedido en el ticket, detectado al probar: la nota la genera
la conciliación; romperla la revierte automáticamente, y esa es la vía de
corrección. Una factura normal SHALL poder volver a borrador.

#### Scenario: Volver a borrador una ND o su reverso

- **WHEN** se intenta pasar a borrador la nota o su reverso
- **THEN** el sistema SHALL lanzar un error

#### Scenario: Factura normal

- **WHEN** se pasa a borrador una factura que no es nota de diferencial
- **THEN** el sistema SHALL permitirlo
