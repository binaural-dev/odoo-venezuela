# Verification Report: l10n_ve_pos_igtf Odoo 17→19 Migration

- **Change**: `l10n-ve-pos-igtf-migration`
- **Mode**: openspec
- **TDD mode**: STRICT (runtime test evidence required per scenario)
- **Verifier**: sdd-verify executor (glm-5.2)
- **Date**: 2026-07-08
- **Verdict**: **FAIL** (see §Final Verdict)

---

## Executive Summary

The compat-wrapper migration is **structurally correct and load-verified** — the module installs cleanly on Odoo 19 (`Modules loaded`, `Registry loaded in 4.390s`), all 8 import paths resolve against O19 core, all 8 compat wrappers delegate to confirmed O19 method names, the `_create_payment_moves` session-helper signatures are compatible with O19, and the OWL XPath selectors match the live O19 templates. No `install`-time crash, no missing-view-parent error, no XPath-target error.

However, under **STRICT TDD mode**, this is not sufficient. A spec scenario is compliant only when a **passing runtime test** covers it. The module ships **zero test files** (`l10n_ve_pos_igtf/tests/` does not exist) and the configured runner executed `0 post-tests`. Consequently **every behavioral scenario across all 7 specs is UNTESTED** → CRITICAL. Because more than one CRITICAL is open, the verdict is **FAIL** before warnings are even considered.

Three latent crash traps remain (O17 methods that no longer exist on O19 core nor on `l10n_ve_pos`: `get_rounding_applied()` and `get_foreign_rounding_applied()`, plus a `this.props.order` misuse in `get_max_total_with_igtf()`). They are dead code today (the built template does not render them) but they will crash the moment any UI change wires them up. They are documented in `apply-progress.md` as "pre-existing, not in scope" — but they ARE remaining O17 API patterns the migration was asked to surface, so they are recorded as WARNINGs with a follow-up recommendation.

---

## Artifacts Reviewed

| Artifact | Status |
|---|---|
| `tasks.md` | 8/8 tasks marked complete |
| `apply-progress.md` | Consistent with file contents |
| `design.md` | Architecture followed (alternative-safe path for T6) |
| `specs/frontend-imports.md` | Reviewed |
| `specs/frontend-api-wrappers.md` | Reviewed |
| `specs/frontend-display.md` | Reviewed |
| `specs/frontend-igtf-calculation.md` | Reviewed |
| `specs/frontend-payment-creation.md` | Reviewed |
| `specs/backend-payment-moves.md` | Reviewed |
| `specs/views-xml.md` | Reviewed |

**Implementation files inspected**: `order_model.js`, `payment_model.js`, `payment_screen.js`, `payment_status.js`, `payment_line.js`, `pos_payment.py`, `payment_status.xml`, `payment_lines.xml`. (Note: `payment_line.js`/`payment_lines.xml` were applied for this module's functionality but were not listed in `apply-progress.md` Files Changed; included here for full spec coverage.)

---

## Completeness Table

| Task | Title | Tasks.md | Impl. | Static | Runtime |
|------|-------|---------|-------|--------|---------|
| T1 | Imports & patch targets | [x] | ✅ | ✅ all paths resolve | ❌ no JS-load test |
| T2 | Compat wrappers on PosOrder | [x] | ✅ 8 wrappers present | ✅ delegate to verified O19 names | ❌ UNTESTED |
| T3 | Mechanical renames | [x] | ✅ `payment_method`→`payment_method_id` + `?.` guard; `cid`→`uuid`; `get_order()`→`currentOrder` | ✅ static-only (see W1/W2 for residual O17 calls) | ❌ UNTESTED |
| T4 | formatCurrency fix | [x] | ✅ no `'Product Price'` anywhere in `payment_status.js` | ✅ | ❌ UNTESTED |
| T5 | Defensive getters | [x] | ✅ `Array.from(payment_ids||[])` + `totalDue ?? ...` guards | ✅ | ❌ UNTESTED |
| T6 | Rewrite add_paymentline_without_igtf | [x] | ✅ `models["pos.payment"].create({pos_order_id, payment_method_id, amount})`; `setAmount` triggers `localToForeign` chain | ✅ static, indirect foreign chain | ❌ UNTESTED |
| T7 | _create_payment_moves | [x] | ✅ `from_pos=True`; session-helper signatures compatible | ✅ install passes | ❌ UNTESTED |
| T8 | XML views/templates | [x] | ✅ parent IDs exist, XPaths match O19 templates | ✅ (ir.ui.view validated at install; OWL template XPath matched statically) | ❌ UNTESTED at render |

All 8 tasks are checked in `tasks.md` and reflect actual code changes. Task completion is **PASS**. The CRITICAL gap is behavioral test coverage, not task completion.

---

## Build / Install Evidence

| Action | Command | Result |
|---|---|---|
| Module install on O19 | `docker exec -u odoo proj odoo -i l10n_ve_pos_igtf --test-tags /l10n_ve_pos_igtf --stop-after-init -d pos --no-http` | ✅ `Modules loaded.` → `Registry loaded in 4.390s` — no view-parent / XPath / `super()` / Python import error |
| Test execution (Strict TDD) | same as above | ❌ `0 post-tests in 0.00s, 0 queries` → **0 tests ran** (no `l10n_ve_pos_igtf/tests/` directory) |
| O19 import-path existence | `ls + grep` inside `proj` container | ✅ `@point_of_sale/app/models/pos_order`, `.../pos_payment`, `.../hooks/pos_hook`, `.../payment_screen/payment_status`, `.../payment_screen/payment_lines` all exist & export expected symbols |
| O19 view parent IDs | `grep` in O19 `point_of_sale/views` | ✅ `view_pos_pos_form`, `pos_payment_method_view_form`, `view_pos_payment_tree`, `view_pos_payment_form` all exist |

---

## Spec Compliance Matrix

Statuses: ✅ PASS (static) · ❌ UNTESTED (no runtime covering test) · ⚠️ DEVIATION

### frontend-imports.md
| Scenario | Status | Evidence |
|---|---|---|
| order_model.js loads | ✅ static / ❌ runtime | `import { PosOrder } from "@point_of_sale/app/models/pos_order"` — path exists in O19; no JS-load test |
| payment_model.js loads | ✅ static / ❌ runtime | `PosPayment` path verified |
| payment_status.js usePos | ✅ static / ❌ runtime | `@point_of_sale/app/hooks/pos_hook` exports `usePos` confirmed |
| Runtime patch verification (IGTF on order/payment instance) | ❌ UNTESTED | Runtime patch check requires a JS test — none exists |

### frontend-api-wrappers.md
| Requirement | Status | Evidence |
|---|---|---|
| `get_paymentlines()` returns `payment_ids` | ✅ static / ❌ runtime | Wrapper: `this.payment_ids ? Array.from(this.payment_ids) : []` |
| `get_total_with_tax()` returns `totalDue` | ✅ static / ❌ runtime | `Number(this.totalDue ?? 0) \|\| 0` + IGTF-aware branch |
| `get_due()` returns `remainingDue` | ✅ static / ❌ runtime | `Number(this.remainingDue ?? 0) \|\| 0` |
| `add_paymentline(method)` → `addPaymentline` | ✅ static / ❌ runtime | Wrapper calls `this.addPaymentline(...)`, which is itself an IGTF-aware override (diverts IGTF methods to `add_paymentline_without_igtf`); letter-of-spec satisfied |
| `select_paymentline(line)` → `selectPaymentline` | ✅ static / ❌ runtime | Both methods exist in O19 (verified line 510 of `pos_order.js`) |

### frontend-display.md
| Requirement | Status | Evidence |
|---|---|---|
| `igtfAmount` getter | ✅ static / ❌ runtime | `formatCurrency(this.props.order.get_igtf_amount())` |
| `biAmount` getter | ✅ static / ❌ runtime | `formatCurrency(this.props.order.get_bi_igtf())` |
| `foreignIgtfAmount` getter | ⚠️ DEVIATION / ❌ runtime | Spec mandates `foreignIgtfAmount`; impl defines `igtfForeignAmount` (foreign word order swapped). Template references `igtfForeignAmount`, so rendering works, but the spec-mandated name is absent. |
| `isIgtf` via `payment_method_id.apply_igtf` | ✅ static / ❌ runtime | `payment_line.payment_method_id?.apply_igtf` |
| `formatCurrency` O19 signature (no `'Product Price'`) | ✅ static | No `'Product Price'` anywhere; `payment_line.js` uses `formatCurrency(val, true)` which is valid O19 `hasSymbol=true` (redundant, see S2) |
| `formatIgtfAmount` works with O19 models | ✅ static / ❌ runtime | Defined in `payment_line.js` patching `PaymentScreenPaymentLines`; uses `paymentline.igtf_amount`/`foreign_igtf_amount` |

### frontend-igtf-calculation.md
| Scenario | Status | Evidence |
|---|---|---|
| Single foreign IGTF method: total 100, 3% → IGTF 3 | ❌ UNTESTED | `update_igtf` logic uses `payment_method_id?.apply_igtf` + `compute_igtf_amount`; no runtime test |
| Mixed methods: 50/50, 3% → IGTF 1.5 | ❌ UNTESTED | Same |
| Refund negative amount | ❌ UNTESTED | Same |
| `compute_igtf_amount` rounds with currency precision | ✅ static / ❌ runtime | Uses `round_pr(amount * pct/100, rounding)` |
| `get_total_with_tax()` includes IGTF (100+3=103) | ✅ static / ❌ runtime | Override returns `res + this.igtf_amount` for IGTF-payment paths |
| `get_total_without_igtf()` excludes IGTF | ✅ static / ❌ runtime | Returns `totalDue` directly |

### frontend-payment-creation.md
| Scenario | Status | Evidence |
|---|---|---|
| Create via `models["pos.payment"].create`, linked via `pos_order_id`, amount=100 (due 103 − IGTF 3) | ✅ static / ❌ runtime | `create({pos_order_id: this, payment_method_id, amount: 0})` then `setAmount(due − igtf)` |
| Non-IGTF method → amount = remaining due, standard O19 path | ✅ static / ❌ runtime | `addPaymentline` override delegates to `super.addPaymentline(...)` for non-IGTF |
| IGTF exclusion preserved: amount = `due − igtf_amount` | ✅ static / ❌ runtime | `const amountWithoutIgtf = this.get_due() - this.get_igtf_amount(); newPaymentline.setAmount(amountWithoutIgtf)` |
| Foreign amount via `order.localToForeign()` | ✅ static (indirect) / ❌ runtime | `setAmount` triggers l10n_ve_pos `setAmount` patch → `_recomputeForeignFromLocal()` → `order.localToForeign(this.amount)` — chain confirmed in `l10n_ve_pos/.../payment_model.js:42,45-48` |

### backend-payment-moves.md
| Scenario | Status | Evidence |
|---|---|---|
| `_create_payment_moves` uses O19 session API | ✅ static / ❌ runtime | `_update_amounts`, `_credit_amounts`, `_debit_amounts` signatures verified compatible (O19: `_update_amounts(self, old_amounts, amounts_to_add, date, round=True, force_company_currency=False)`, `_credit_amounts(self, partial_move_line_vals, amount, amount_converted, force_company_currency=False)`, `_debit_amounts(self, partial_move_line_vals, amount, amount_converted, force_company_currency=False)` — all call sites use positional 3-arg form) |
| POS order with IGTF payment: move balances to zero | ❌ UNTESTED | Needs accounting test |
| IGTF split: 100 receivable + 3 IGTF account; debits=credits | ❌ UNTESTED | Needs accounting test |
| `from_pos=True` prevents duplicate IGTF | ✅ static / ❌ runtime | `with_context(default_journal_id=journal.id, from_pos=True)` present (line 41) |
| Foreign currency amounts preserved on move lines | ✅ static / ❌ runtime | `foreign_debit`/`foreign_credit` keys passed to `_credit_amounts`/`_debit_amounts` |

### views-xml.md
| Scenario | Status | Evidence |
|---|---|---|
| pos_order.xml view validation (no missing parent) | ✅ PASS (install) | O19 core `view_pos_pos_form` exists; install succeeded without missing-view error |
| pos_payment_method form renders apply_igtf | ✅ static / ❌ runtime | Parent `pos_payment_method_view_form` exists |
| pos_payment tree/form render IGTF fields | ✅ static / ❌ runtime | Parents exist |
| payment_status.xml XPath matches O19 | ✅ static / ❌ runtime | O19 template has `<div class="payment-status-container ...">` matching `//div[hasclass('payment-status-container')]` |
| payment_lines.xml renders IGTF row | ✅ static / ❌ runtime | O19 template has `<t t-foreach="props.paymentLines" ...>` matching XPath; `line.include_igtf`/`line.selected` available |
| Order without IGTF → IGTF row hidden | ✅ static / ❌ runtime | `t-if="line.include_igtf"` |

---

## Correctness Table (remaining O17 patterns)

| Pattern | File:Line | Status | Note |
|---|---|---|---|
| `payment.payment_method` (no `_id`) | none | ✅ clean | All accesses use `payment_method_id?.apply_igtf` |
| `payment.cid` | none | ✅ clean | All use `payment.uuid` |
| `this.pos.get_order()` | none | ✅ clean | Replaced with `this.currentOrder` |
| `'Product Price'` literal | none | ✅ clean | Removed; `payment_line.js` uses `true` (valid `hasSymbol`) |
| `get_total_with_tax()` called as method | present in wrapper bodies | ✅ OK | Wrapper exists on same prototype (resolves) |
| `get_rounding_applied()` (no O19 method!) | `payment_status.js:54` | ⚠️ WARNING W1 | O17 API leftover |
| `get_foreign_rounding_applied()` (no O19/l10n_ve_pos method!) | `payment_status.js:67`, `order_model.js:288` | ⚠️ WARNING W2 | O17 API leftover |
| `this.props.order.*` inside an order-model method | `order_model.js:288` | ⚠️ WARNING W3 | Order instances have no `.props` (component pattern misuse) |
| Silent-trap `?.() \|\| 0` on renamed getters | none | ✅ clean | No `?.()` trap; getters use `?? 0` + `Number(...) \|\| 0` (returns 0 on NaN — acceptable defensive pattern) |

---

## Design Coherence Table

| Design decision | Implantation matches? |
|---|---|
| Compat-wrapper strategy (wrap O17 names on PosOrder) | ✅ — 8 wrappers present at design §3 |
| Subscription to l10n_ve_pos helpers (no conversion duplication) | ✅ — delegates to `localToForeign`, `get_foreign_total_with_tax`, `set_foreign_amount` |
| T6 chosen path | ✅ — design "Alternative (safer)" path: `models["pos.payment"].create + select_paymentline + setAmount(due − igtf)` |
| `_create_payment_moves` minimal adapt with `from_pos=True` | ✅ |
| Defensive getter pattern (`totalDue ?? typeof get_total_with_tax === "function" ? ... : 0`) | ✅ — applied in `payment_status.js` lines 53, 61, 75, 86 |
| `get_max_total_with_igtf()` `this.props.order` pre-existing bug (note from progress) | acknowledged in design — design does NOT fix it; flagged WARNING here |

---

## Issues

### CRITICAL

- **C1 — No behavioral test coverage (Strict TDD violation).** `l10n_ve_pos_igtf/tests/` does not exist; runner executed `0 post-tests`. Under Strict TDD every required scenario (IGTF calc 3 / 1.5 / refund; payment creation amount = due − igtf; foreign via localToForeign; create_payment_moves balances to zero + IGTF split; foreign currency preservation; view render; wrapper delegation) is **UNTESTED**. No behavioral spec requirement can be marked COMPLIANT. This is the single blocking cause of the FAIL verdict. The runner command and database (`pos`) are available, so writing tests is feasible.

### WARNING

- **W1 — `this.props.order.get_rounding_applied()` will throw at runtime** (`payment_status.js:54`, in unused `amountIGTF` getter). `get_rounding_applied` does NOT exist on O19 core, l10n_ve_pos, or this module. Currently latent (the built `payment_status.xml` does not render `amountIGTF`), but the moment any UI change renders it the POS payment screen crashes with `TypeError: ...get_rounding_applied is not a function`. Document the property as a SMALL wrapper → `this.props.order.rounding_applied` (O19 core `get rounding_applied` exists as JS getter on PosOrder? — verify at fix time).

- **W2 — `get_foreign_rounding_applied()` will throw at runtime** (`payment_status.js:67` in unused `foreignTotalDueTextWithIGTF` getter; `order_model.js:288` in `get_max_total_with_igtf`). Method does not exist in O19 core or l10n_ve_pos (l10n_ve_pos even has it commented out at `pos_order.js:587+`). Latent crash trap; remove the calls or provide a wrapper.

- **W3 — `get_max_total_with_igtf()` uses `this.props.order.*`** (`order_model.js:288`). `this` is a `PosOrder` instance, not an OWL component, so `this.props` is `undefined` → `TypeError` regardless of whether `get_foreign_rounding_applied` would exist. Latent crash trap (method unused by current templates/JS).

- **W4 — Spec naming deviation: `foreignIgtfAmount` vs `igtfForeignAmount`** (`payment_status.js:23`). Spec frontend-display.md mandates a `foreignIgtfAmount` getter; implementation defines `igtfForeignAmount`. The template renders with the impl name, so the screen works, but spec-compliance is broken. Rename to match the spec (or update the spec if the existing name is preferred).

### SUGGESTION

- **S1 — Add a final `return res;` after the for-loop** in `get_total_with_tax()` (`order_model.js:242-261`). The current control-flow relies on a structural invariant (filter non-empty ⟹ for-loop returns). Adding `return res;` after the loop makes the function total and robust against future refactors.
- **S2 — Redundant `true` second arg** in `payment_line.js:8-9`. O19 `formatCurrency(value, hasSymbol=true)` makes `formatCurrency(x, true)` identical to `formatCurrency(x)`; simplify to single-arg for clarity (out of migration scope, but matches the T4 spirit).
- **S3 — Track a follow-up task** for the three O17 API leftovers (W1/W2/W3) instead of relying on "not in scope". They are documented in `apply-progress.md` but a new task should be opened (or specs extended) so they are not inherited silently into the next change.

---

## Final Verdict: **FAIL**

Decision rationale:

1. **Tasks**: complete (8/8) — but task completion alone does not satisfy behavioral compliance under Strict TDD.
2. **Static correctness + install evidence**: strong — the module loads on O19 with no errors; import paths, target method names, view parents, XPaths, and `_create_payment_moves` signatures all validate statically. Implementation quality is high.
3. **Runtime behavioral tests**: **zero**. Strict TDD gate: "Spec scenario has no passing covering test → CRITICAL UNTESTED." Every behavioral scenario across the 7 specs is UNTESTED → multiple CRITICAL issues → **FAIL**.
4. **Latent WARNINGs (W1–W3)** would independently downgrade a PASS to PASS-WITH-WARNINGS if test coverage existed; under the present no-test condition they reinforce the FAIL.

The implementation is **good code on a wrong evidence footprint**: well-formed and load-verified, but unproven at runtime. Once test files are added (covering at minimum the IGTF calc, payment-creation, payment-moves, wrapper-delegation, and OWL-template-render scenarios) and pass, the verdict will likely flip to PASS WITH WARNINGS (pending W1–W4 fixes).