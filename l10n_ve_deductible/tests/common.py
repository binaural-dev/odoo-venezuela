from contextlib import contextmanager

from odoo import fields


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
    vef, usd = env.ref("base.VEF"), env.ref("base.USD")
    Rate = env["res.currency.rate"]
    Rate.search([("name", "=", date), ("company_id", "=", company.id)]).unlink()
    Rate.create({"name": date, "currency_id": vef.id, "rate": 1.0,
                 "company_id": company.id})
    Rate.create({"name": date, "currency_id": usd.id, "rate": rate,
                 "company_id": company.id})


class AssertMixin:
    @contextmanager
    def assertRaisesMsg(self, exception, text):
        """`assertRaises` (which rolls the failed statement back through a
        savepoint) plus a check that the message contains `text`."""
        with self.assertRaises(exception) as caught:
            yield
        self.assertIn(text, str(caught.exception))
