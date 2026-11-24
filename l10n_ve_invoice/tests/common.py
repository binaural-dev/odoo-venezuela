from unittest.mock import patch

from odoo.tests import TransactionCase


class ForeignRateTransactionCase(TransactionCase):
    """TransactionCase for tests that create and post invoices without caring
    about the exchange rate.

    ``compute_rate`` only uses the rate dated exactly on the document date, so
    a test that creates documents on arbitrary dates (today, fixed or relative
    ones) fails with "There is no rate assigned" in a clean database. Here a
    missing rate resolves to 1.0 / 1.0 instead of raising; a rate that does
    exist is still used as is, and the rate lookup itself is covered by the
    tests of ``l10n_ve_rate``.
    """

    def setUp(self):
        super().setUp()
        rate_model = type(self.env["res.currency.rate"])
        original = rate_model.compute_rate

        def compute_rate(model, foreign_currency_id, rate_date=None, raise_if_not_found=True):
            values = original(model, foreign_currency_id, rate_date, raise_if_not_found=False)
            if values or not raise_if_not_found:
                return values
            return {"foreign_rate": 1.0, "foreign_inverse_rate": 1.0}

        patcher = patch.object(rate_model, "compute_rate", compute_rate)
        patcher.start()
        self.addCleanup(patcher.stop)
