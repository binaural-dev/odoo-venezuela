## MODIFIED Requirements

### Requirement: Base imponible del IGTF en modo nota de débito

La copia de `compute_bi_igtf` de `l10n_ve_igtf_note_debit` DEBE (MUST) usar la misma compuerta que `l10n_ve_igtf` (`_igtf_base_is_computable`) y NO DEBE (MUST NOT) decidir con `payment_state`: la base y el tope se calculan con saldo abierto, o con la factura publicada, no revertida y con conciliaciones. Una factura revertida sigue con los campos en cero.

#### Scenario: Factura pagada con `payment_state` desactualizado

- **WHEN** se recalcula la base de una factura con saldo cero, publicada y conciliada, cuyo `payment_state` aún figura `not_paid`
- **THEN** `bi_igtf` y `igtf_top_aply` se calculan y no quedan en cero

#### Scenario: Factura revertida

- **WHEN** se recalcula la base de una factura con `payment_state` `reversed`
- **THEN** los campos quedan en cero
