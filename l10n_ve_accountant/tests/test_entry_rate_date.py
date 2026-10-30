"""Un asiento (entry) toma la tasa de su fecha contable (`date`), no la de "hoy".

`_compute_rate_for_documents` usa `date` para los asientos (`entry`),
pero el `create` de `account.move` consultaba ademas la tasa de `invoice_date or hoy`:
en un asiento `invoice_date` esta vacio, asi que un asiento con fecha pasada o futura
(p. ej. depreciacion) fallaba si hoy no tenia tasa aunque la de su `date` existiera.
"""

from datetime import date

from odoo.tests import TransactionCase, tagged

from .common_tz_boundary import CARACAS_DAY, USD_PER_VEF_INVERSE, TzBoundaryMixin, freeze_time


@tagged("post_install", "-at_install", "l10n_ve_accountant_entry_rate_date")
class TestEntryRateDate(TzBoundaryMixin, TransactionCase):
    def setUp(self):
        super().setUp()
        self._setup_tz_boundary()
        self.journal = self.env["account.journal"].search(
            [("type", "=", "general"), ("company_id", "=", self.company.id)], limit=1
        ) or self.env["account.journal"].sudo().create(
            {"name": "TZ Entry", "code": "TZENT", "type": "general", "company_id": self.company.id}
        )

    def test_entry_with_past_date_uses_its_own_date_rate(self):
        """Hoy (20-mar) no tiene tasa; el asiento del 10-mar si: debe tomar la del 10."""
        with freeze_time("2026-03-20 15:00:00"):
            move = self.env["account.move"].create(
                {"move_type": "entry", "journal_id": self.journal.id, "date": CARACAS_DAY}
            )
            self.assertAlmostEqual(move.foreign_rate, USD_PER_VEF_INVERSE, places=4)

    def test_entry_date_without_rate_still_raises(self):
        """La fecha explicita del asiento no se corrige: sin tasa en `date` se bloquea."""
        from odoo.exceptions import UserError

        with freeze_time("2026-03-10 15:00:00"), self.assertRaisesRegex(
            UserError, "There is no rate assigned"
        ):
            self.env["account.move"].create(
                {"move_type": "entry", "journal_id": self.journal.id, "date": date(2026, 3, 12)}
            )
