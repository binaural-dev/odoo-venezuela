## ADDED Requirements

### Requirement: pos.payment field contract respects the "empty list = all fields" core convention
`pos.payment._load_pos_data_fields` SHALL return the value from `super()`
unmodified when it is empty, instead of replacing it with an explicit
whitelist, so that fields added to `pos.payment` by other modules keep
reaching the PoS frontend.

#### Scenario: Core contract is untouched (no ancestor narrowed the list)
- **WHEN** no module up the `pos.payment` inheritance chain overrides
  `_load_pos_data_fields` with a non-empty explicit list
- **THEN** `l10n_ve_pos`'s `_load_pos_data_fields` returns an empty list too,
  and every stored field on `pos.payment` (core or added by any other
  module) reaches the PoS frontend and is a valid target for client-side
  `.update()` calls

#### Scenario: Ancestor already narrowed the list
- **WHEN** some module up the chain already returns a non-empty explicit
  field list
- **THEN** `l10n_ve_pos`'s `_load_pos_data_fields` extends that list with
  `_POS_PAYMENT_CORE_FIELDS` and the Venezuelan foreign-currency fields
  (`foreign_rate`, `foreign_amount`, `foreign_currency_id`), without
  dropping any field already present
