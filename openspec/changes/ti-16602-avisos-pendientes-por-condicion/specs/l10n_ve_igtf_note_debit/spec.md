## ADDED Requirements

### Requirement: Aviso de notas de débito IGTF pendientes después de los avisos de pendientes

Cuando el documento tiene notas de débito de IGTF pendientes (`has_pending_igtf_debit_note`), el formulario de `account.move` DEBE (MUST) mostrar el aviso "You have pending IGTF notes to pay" inmediatamente después del bloque de avisos de pendientes (detrás del aviso de `in_refund`, el último de los cuatro). Su posición NO DEBE (MUST NOT) depender de cuántos avisos `alert-info` agreguen otros módulos antes.

#### Scenario: Factura con nota de débito de IGTF pendiente y aviso de tasa

- **WHEN** se abre una factura con una nota de débito de IGTF pendiente, creada desde una orden que fija la tasa
- **THEN** se ven el aviso de tasa, el aviso de pendientes y, a continuación, el aviso de notas de débito IGTF pendientes
