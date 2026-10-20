# Slice C1 — Accumulator Data-Key Map

**Spec**: `pos-odoo19-session-accounting/spec.md` (Requirements: "Model before/after data structures" + "Preserve foreign amount accumulation").
**Migration context**: `l10n_ve_pos/models/pos_session.py::_accumulate_amounts` and `::_update_amounts`.
**Odoo 19 native reference**: `/home/binaural19/odoo/addons/point_of_sale/models/pos_session.py:840-1011` (`_accumulate_amounts`) and `:1486-1545` (`_update_amounts`).

---

## 1. Scope of the data dict

`_accumulate_amounts(data)` receives an input `data` dict (carrying
`bank_payment_method_diffs` from `_create_account_move`) and returns the same
dict **augmented** with the per-bucket receivable / tax / stock accumulators
that the move-creation pipeline (C2) consumes.

The return value is the only contract for the C2 methods:

| Consumer (C2) | Bucket keys it reads |
|---------------|----------------------|
| `_create_bank_payment_moves` | `combine_receivables_bank`, `split_receivables_bank` |
| `_create_cash_statement_lines_and_cash_move_lines` | `split_receivables_cash`, `combine_receivables_cash` |
| `_create_invoice_receivable_lines` | `combine_invoice_receivables`, `split_invoice_receivables` |
| `_create_non_reconciliable_move_lines` | `taxes`, `sales`, `stock_expense`, `rounding_difference` |
| `_create_stock_valuation_lines` | `stock_valuation`, `stock_return` |
| `_reconcile_account_move_lines` | `combine_inv_payment_receivable_lines`, `split_inv_payment_receivable_lines` |

**Migration rule**: every key above is the Odoo 19 contract. We MUST NOT drop,
rename, or alias them. The Venezuelan foreign-currency extension is purely
**additive** — we add a `foreign_amount` key inside each receivable bucket and
nothing else.

---

## 2. Per-bucket dict shape

### 2.1 Odoo 19 base contract (per-entry dict)

For every entry in `split_receivables_*`, `combine_receivables_*`,
`split_invoice_receivables`, `combine_invoice_receivables`:

| Key | Type | Source | Semantics |
|-----|------|--------|-----------|
| `amount` | float | `payment.amount` aggregated | Amount in the **session currency** |
| `amount_converted` | float | computed by `_update_amounts` from `amount` and the conversion rate at `date` | Amount in the **company currency** |

For `taxes` and `sales`, additional keys are present:

| Key | Type | Source |
|-----|------|--------|
| `base_amount` | float | only `taxes` |
| `base_amount_converted` | float | only `taxes` |
| `quantity` | float | only `sales` when `config_id._is_quantities_set()` |
| `move_line_id` | int | only `sales` (set by `_create_non_reconciliable_move_lines`) |

The base helper that materializes these is:

```python
# Odoo 19: pos_session.py:847
amounts = lambda: {'amount': 0.0, 'amount_converted': 0.0}
tax_amounts = lambda: {'amount': 0.0, 'amount_converted': 0.0, 'base_amount': 0.0, 'base_amount_converted': 0.0}
```

### 2.2 l10n_ve_pos extension

For every receivable entry, we add a third key:

| Key | Type | Source | Semantics |
|-----|------|--------|-----------|
| `foreign_amount` | float | `payment.foreign_amount` aggregated (per `payment` key for `split_*`; per `payment_method` for `combine_*`) | Amount in the **foreign currency** (e.g. VEF) |

`foreign_amount` is purely additive — `_update_amounts` adds it without
touching `amount` or `amount_converted` (they are computed by `super()`).

### 2.3 Before/after comparison

| Concept | Odoo 17 (legacy) | Odoo 19 (current) | l10n_ve_pos delta |
|---------|------------------|-------------------|-------------------|
| Per-entry dict keys | `{'amount': X}` (no `amount_converted`) | `{'amount': X, 'amount_converted': Y}` | + `{'foreign_amount': Z}` |
| Currency of `amount` | session currency | session currency | unchanged |
| Currency of `amount_converted` | N/A | company currency | unchanged |
| Currency of `foreign_amount` | N/A | N/A | foreign currency |
| Order iteration | `self.order_ids` | `self._get_closed_orders()` | **MUST follow Odoo 19** to avoid draft/cancel pollution |
| Receivable split logic | keyed by `payment` (split) / `payment_method` (combine) | identical | identical |
| Invoice-receivable split logic | only invoiced orders | identical | identical |
| `combine_inv_payment_receivable_lines` | not exposed (C2 derives it) | populated by super | **do not re-derive** (super already populates) |

---

## 3. Risk hotspots

1. **Default-dict key creation**: Odoo 19 uses `defaultdict(amounts)` for every
   bucket. Reading a non-existent key CREATES a fresh `{'amount': 0.0,
   'amount_converted': 0.0}` entry. l10n_ve_pos must NOT re-iterate the source
   orders to recompute `amount` / `amount_converted` (super already did it);
   iterating again and re-calling `_update_amounts` with `{"amount": 0, ...}`
   is the only safe way to add `foreign_amount` without corrupting the
   Odoo 19 base totals.

2. **`_update_amounts` round contract**: it ALWAYS returns
   `{'amount': ..., 'amount_converted': ...}`. l10n_ve_pos extends the return
   dict with `foreign_amount`. Removing or renaming the Odoo 19 keys would
   silently corrupt the C2 move-creation step.

3. **`_get_closed_orders()` vs `self.order_ids`**: super filters out `draft`
   and `cancel` orders. If l10n_ve_pos iterates over `self.order_ids`
   instead, it will try to add `foreign_amount` for orders that have no
   entries in super's accumulators (no risk of corruption because the key
   won't exist in the dict, but the `foreign_amount` will never reach the
   bucket and will be silently lost for draft orders that are later paid —
   which is the only state under which `_accumulate_amounts` is called).

---

## 4. Migration checklist (for any new C1/C2 reviewer)

Use this as a smoke check when reviewing any new accumulator or move-creation
slice:

- [ ] Every receivable bucket (`split_*` / `combine_*` for bank, cash,
      invoice receivables) carries `amount`, `amount_converted`, AND
      `foreign_amount`.
- [ ] No bucket carries a renamed Odoo 19 key.
- [ ] `foreign_amount` is computed against the same source as the matching
      `amount` entry (the same `payment` or `payment_method` key).
- [ ] The Odoo 19 super is called FIRST; the l10n_ve_pos extension runs on
      the dict super produced.
- [ ] The C2 methods consume `data` returned by `_accumulate_amounts` (not
      a re-derived dict).

---

## 5. Migration evidence

| Odoo 19 native decision | Reference | Why we need this slice |
|------------------------|-----------|------------------------|
| Odoo 19 buckets are `defaultdict` with `{'amount', 'amount_converted'}` | `pos_session.py:847-857` (the `amounts` lambda) | Confirm the base shape; our `foreign_amount` must be additive only |
| Odoo 19 super iterates `self._get_closed_orders()` | `pos_session.py:870` | Avoid draft/cancel pollution when re-iterating in our override |
| `_update_amounts` returns a NEW dict with `amount` / `amount_converted` always present | `pos_session.py:1486-1545` | Our override must extend (not replace) the return dict |
| Receivable buckets are populated by `defaultdict`, not from a manual `data.get(...)` | `pos_session.py:849-857` | Confirms `data.get('split_receivables_bank')` is the safe lookup pattern (it returns the same `defaultdict` instance) |
