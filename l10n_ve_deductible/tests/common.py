import re
from contextlib import contextmanager

from odoo import Command, fields
from odoo.tests import Form, TransactionCase, tagged


def ensure_ve_base(env):
    """Tests run on a VEF base / USD alternate DB: do nothing when it already
    is, otherwise set the missing currencies (valid only while the company has
    no journal items, i.e. on a clean database)."""
    vef, usd = env.ref("base.VEF"), env.ref("base.USD")
    (vef | usd).write({"active": True})
    company = env.company
    vals = {}
    if company.currency_id != vef:
        vals["currency_id"] = vef.id
    if company.foreign_currency_id != usd:
        vals["foreign_currency_id"] = usd.id
    if vals:
        company.write(vals)
    return vef, usd


def set_usd_rate(env, rate, date=None, company=None):
    """1 VEF = 1 (company currency); `rate` is the VEF-based rate of USD."""
    date = date or fields.Date.today()
    company = company or env.company
    Rate = env["res.currency.rate"]
    Rate.search([("name", "=", date), ("company_id", "=", company.id)]).unlink()
    for currency, value in ((env.ref("base.VEF"), 1.0), (env.ref("base.USD"), rate)):
        Rate.create({"name": date, "currency_id": currency.id, "rate": value, "company_id": company.id})


class AssertMixin:
    @contextmanager
    def assertRaisesMsg(self, exception, text):
        """`assertRaises` (which rolls the failed statement back through a
        savepoint) plus a check that the message contains `text`."""
        with self.assertRaises(exception) as caught:
            yield
        self.assertIn(text, str(caught.exception))


@tagged("post_install", "-at_install", "l10n_ve_deductible")
class DeductibleCase(AssertMixin, TransactionCase):
    """Base of the deductible tests: VEF base / USD alternate, recent rates
    (1 USD = 857.88 / 857.00 VEF) and documents of `MOVE_TYPE`. A subclass that
    only sets `MOVE_TYPE` re-runs every test on the other side (Odoo only runs
    inherited tests when `allow_inherited_tests_method` is set)."""

    allow_inherited_tests_method = True
    MOVE_TYPE = "in_invoice"
    RATES = (0.00116565386887513, 0.001166853246500782)
    METHODS = ("round_per_line", "round_globally")
    LINES = [(10.3333, 3), (7.1249, 7), (0.9999, 13), (123.4567, 1), (3.3333, 9)]
    PERCENT = {"is_deductible": True, "global_deductible_type": "percent", "global_deductible_percent": 12.5}
    AMOUNT = {"is_deductible": True, "global_deductible_type": "amount", "global_deductible_amount": 77.77}

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ensure_ve_base(cls.env)
        cls.env.ref("product.decimal_price").digits = 4
        cls.vef, cls.usd = cls.env.ref("base.VEF"), cls.env.ref("base.USD")
        # documents are dated with the server date: the date of the notes (user
        # timezone) must be the same one, whatever the hour the tests run at
        cls.env.user.tz = "UTC"
        cls.company = cls.env.company
        cls.company.write({"use_deductible": True, "deductible_scope": "both", "discount_type": "percent"})
        set_usd_rate(cls.env, cls.RATES[0])
        cls.partner = cls.env["res.partner"].create({"name": "Contacto Deducible", "company_id": False})
        cls.taxes = {cls.company: cls._make_taxes(cls.company)}
        cls.product = cls.env["product.product"].create(
            {
                "name": "Producto Deducible",
                "taxes_id": [Command.set(cls.taxes[cls.company]["sale"]["exempt"].ids)],
                "supplier_taxes_id": [Command.set(cls.taxes[cls.company]["purchase"]["exempt"].ids)],
            }
        )

    @classmethod
    def _make_taxes(cls, company):
        """{sale|purchase: {exempt, general, fixed, included}} of a company."""
        kinds = {
            "exempt": {"amount_type": "percent", "amount": 0.0},
            "general": {"amount_type": "percent", "amount": 16.0},
            "fixed": {"amount_type": "fixed", "amount": 0.0},
            "included": {"amount_type": "percent", "amount": 0.0, "price_include_override": "tax_included"},
        }
        return {
            use: {
                kind: cls.env["account.tax"].with_company(company).create(
                    {"name": f"{kind} {use}", "type_tax_use": use, "company_id": company.id, **vals}
                )
                for kind, vals in kinds.items()
            }
            for use in ("sale", "purchase")
        }

    def tax(self, kind="exempt", move_type=None, company=None):
        """Tax of `kind` for the side (sale / purchase) of the document type."""
        use = "sale" if (move_type or self.MOVE_TYPE).startswith("out_") else "purchase"
        return self.taxes[company or self.company][use][kind]

    def _doc(self, lines=None, currency=None, move_type=None, tax=None, line_extra=None, company=None, **vals):
        """A document of `move_type` with `lines` [(price, qty)] (or explicit
        `invoice_line_ids`), in `currency` (USD by default) and `company`."""
        move_type = move_type or self.MOVE_TYPE
        if "invoice_line_ids" not in vals:
            tax = tax or self.tax(move_type=move_type, company=company)
            vals["invoice_line_ids"] = [
                Command.create(
                    {
                        "product_id": self.product.id,
                        "name": f"L{index}",
                        "quantity": qty,
                        "price_unit": price,
                        "tax_ids": [Command.set(tax.ids)],
                        **(line_extra or {}),
                    }
                )
                for index, (price, qty) in enumerate(lines or self.LINES)
            ]
        company = company or self.company
        return self.env["account.move"].with_company(company).create(
            {
                "move_type": move_type,
                "company_id": company.id,
                "partner_id": self.partner.id,
                "currency_id": (currency or self.usd).id,
                "invoice_date": fields.Date.today(),
                **vals,
            }
        )

    def _combos(self):
        """(rounding method, document currency); sets the company method."""
        for method in self.METHODS:
            for currency in (self.usd, self.vef):
                self.company.tax_calculation_rounding_method = method
                yield method, currency

    def _post(self, docs):
        """Confirm: customer documents ask for a confirmation by default."""
        docs.with_context(move_action_post_alert=True).action_post()
        return docs

    def _account_type(self):
        return "asset_receivable" if self.MOVE_TYPE.startswith("out_") else "liability_payable"

    def _pay(self, doc):
        """Register the payment of a posted document in a bank journal."""
        journal = self.env["account.journal"].search(
            [("type", "=", "bank"), ("company_id", "=", self.company.id)], limit=1
        )
        account = self.env["account.account"].search(
            [("account_type", "in", ("asset_cash", "asset_current")), ("company_ids", "in", self.company.ids)],
            limit=1,
        )
        (journal.inbound_payment_method_line_ids | journal.outbound_payment_method_line_ids).write(
            {"payment_account_id": account.id}
        )
        self.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=doc.ids
        ).create({"journal_id": journal.id}).action_create_payments()

    def _reverse(self, doc, cancel=True):
        """Credit note through the standard wizard (reverse and cancel, or a
        draft credit note). Returns the credit note and the replacement."""
        wizard = self.env["account.move.reversal"].with_context(
            active_model="account.move", active_ids=doc.ids
        ).create({"journal_id": doc.journal_id.id, "date": fields.Date.today()})
        action = wizard.modify_moves() if cancel else wizard.refund_moves()
        replacement = self.env["account.move"].browse(action["res_id"]) if cancel else doc.browse()
        return doc.reversal_move_ids, replacement

    def _debit(self, doc, copy_lines):
        """Debit note through the standard wizard."""
        wizard = self.env["account.debit.note"].with_context(
            active_model="account.move", active_ids=doc.ids
        ).create({"copy_lines": copy_lines, "date": fields.Date.today()})
        return doc.browse(wizard.create_debit()["res_id"])

    @staticmethod
    def _number(text):
        """The number inside a formatted monetary text ('$ 1,234.50')."""
        return float(re.search(r"-?\d[\d,]*\.?\d*", text).group().replace(",", ""))

    @staticmethod
    def _snapshot(doc):
        """Every figure that must be identical between two equivalent documents."""
        lines = doc.invoice_line_ids.sorted("id")
        totals = doc.tax_totals
        by_line = doc.company_currency_line_totals or {}
        entries = [by_line.get(str(line.id), {}) for line in lines]
        return {
            "amount_untaxed": doc.amount_untaxed,
            "amount_total": doc.amount_total,
            "amount_total_signed": doc.amount_total_signed,
            "price_subtotal": lines.mapped("price_subtotal"),
            "price_total": lines.mapped("price_total"),
            "balance": lines.mapped("balance"),
            "amount_currency": lines.mapped("amount_currency"),
            "foreign_subtotal": lines.mapped("foreign_subtotal"),
            "foreign_price_total": lines.mapped("foreign_price_total"),
            "company_subtotal": [entry.get("subtotal") for entry in entries],
            "company_price_unit": [entry.get("price_unit") for entry in entries],
            "company_discount": [entry.get("discount_amount") for entry in entries],
            "widget_base_ves": totals.get("base_amount"),
            "widget_base": totals.get("base_amount_currency"),
            "widget_total": totals.get("total_amount_currency"),
            "widget_total_foreign": totals.get("total_amount_foreign_currency"),
            "journal": sorted(doc.line_ids.mapped("balance")),
            "journal_currency": sorted(doc.line_ids.mapped("amount_currency")),
        }

    def _assert_same(self, doc, reference):
        """Exactly the same figures, field by field."""
        mine, other = self._snapshot(doc), self._snapshot(reference)
        for key, value in mine.items():
            self.assertEqual(value, other[key], key)

    def _new_form(self, currency, mode=None, value=None, lines=None):
        """Form of a new document, with lines and optionally the deductible."""
        form = Form(self.env["account.move"].with_context(default_move_type=self.MOVE_TYPE))
        form.partner_id = self.partner
        form.invoice_date = fields.Date.today()
        form.currency_id = currency
        for price, qty in lines or []:
            self._form_line(form, price, qty)
        if mode:
            form.is_deductible = True
            form.global_deductible_type = mode
            self._set_form_value(form, mode, value)
        return form

    @staticmethod
    def _set_form_value(form, mode, value):
        """Value of the deductible in the field of its type."""
        setattr(form, "global_deductible_amount" if mode == "amount" else "global_deductible_percent", value)

    def _form_line(self, form, price, qty):
        """New line; the price is set last because Odoo re-prices a vendor
        line when its quantity changes."""
        with form.invoice_line_ids.new() as line:
            line.product_id = self.product
            line.quantity = qty
            line.price_unit = price
