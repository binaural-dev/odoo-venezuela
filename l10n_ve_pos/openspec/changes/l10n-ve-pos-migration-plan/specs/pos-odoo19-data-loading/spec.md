# POS Odoo 19 Data Loading Specification

## Purpose

Define how `l10n_ve_pos` migrates its Odoo 17 session-data loading overrides to Odoo 19 `load_data` / `_load_pos_data_*` patterns.

## Requirements

### Requirement: Inventory and map all custom session loaders

The migration plan MUST list every `l10n_ve_pos` override of `load_pos_data`, `_loader_params_*`, `_get_pos_ui_*`, and `_pos_ui_models_to_load`, and map each to the corresponding Odoo 19 API.

#### Scenario: Loader inventory is complete

- GIVEN the gap-analysis section of the migration plan
- WHEN a reviewer compares it with `src/odoo-venezuela/l10n_ve_pos/models/pos_session.py`
- THEN every old loader method is present with a source file reference and an Odoo 19 replacement

#### Scenario: No loader is left unmapped

- GIVEN the mapping table
- WHEN the reviewer searches for `load_pos_data` or `_loader_params_`
- THEN no occurrence appears without a mapped Odoo 19 equivalent

### Requirement: Preserve custom fields, domains, and contexts

The plan MUST map every custom field, domain, and context added by the old loaders to `_load_pos_data_fields`, `_load_pos_data_domain`, `_load_pos_data_read`, `_load_pos_data_search_read`, or `load_data` extra keys.

Custom additions include, at minimum:
- `prefix_vats` extra key in `load_pos_data`
- `pos.payment`: `foreign_rate`
- `pos.payment.method`: `is_foreign_currency`
- `account.tax`: `type_tax_use`
- `res.partner`: `prefix_vat`, `city_id`
- `res.currency`: domain filter, `inverse_rate`
- `product.product`: `free_qty`, `qty_available`, `warehouse` context
- `res.company`: explicit field list

#### Scenario: Field coverage is verified

- GIVEN the field mapping table
- WHEN the reviewer checks each custom addition against the Odoo 17 source
- THEN each addition has a target Odoo 19 hook and no addition is omitted

#### Scenario: Domain and context are preserved

- GIVEN a multi-currency POS config
- WHEN the migration design is reviewed
- THEN the plan keeps the `res.currency` domain restriction and the product warehouse context

### Requirement: Schedule data loading as Slice 1

The plan MUST schedule data-loading migration before order/payment serialization and frontend re-enablement because those slices consume the loaded data.

#### Scenario: Dependency order is explicit

- GIVEN the task list in `tasks.md`
- WHEN the reviewer inspects slice dependencies
- THEN Slice 1 (data loading) has no incoming dependency from later slices and is marked as blocking them

### Requirement: Define a data-loading verification scenario

The plan MUST specify a test that opens a POS session and asserts each custom data element is present in the frontend payload.

#### Scenario: Happy path payload verification

- GIVEN a POS session loaded with the migrated module
- WHEN the frontend requests initial data
- THEN the response contains `prefix_vats`, `foreign_rate`, `is_foreign_currency`, `inverse_rate`, and the other mapped custom fields

#### Scenario: Limited products loading edge case

- GIVEN a config with limited product loading enabled
- WHEN the product list is loaded
- THEN `free_qty`, `qty_available`, and the warehouse context still behave as in Odoo 17
