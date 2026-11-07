from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestFeesRetentionAccumulated(TransactionCase):
    """Tier lookup of accumulated tariffs (Tarifa 2, Decreto 1.808 art. 9)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        tax_unit = cls.env["tax.unit"].create({"name": "UT test", "value": 0.43, "status": True})
        # Same limits as the shipped data (start 2001 / 3001 leave a gap with `start`)
        cls.tariff = cls.env["fees.retention"].create(
            {
                "name": "T-2 test",
                "accumulated_rate": True,
                "tax_unit_ids": tax_unit.id,
                "accumulated_rate_ids": [
                    (0, 0, {"name": "T1", "start": 0.0, "stop": 2000.0, "percentage": 15.0}),
                    (0, 0, {"name": "T2", "start": 2001.0, "stop": 3000.0, "percentage": 22.0, "subtract_ut": 140.0}),
                    (0, 0, {"name": "T3", "start": 3001.0, "stop": 0.0, "percentage": 34.0, "subtract_ut": 500.0}),
                ],
            }
        )

    def test_every_base_gets_a_tier(self):
        cases = [
            (0.0, 15.0),
            (1999.988, 15.0),
            (2000.0, 15.0),
            (2000.009, 22.0),  # ticket: 955.56 Bs
            (2000.512, 22.0),  # ticket: 955.80 Bs
            (2000.993, 22.0),  # ticket: 956.03 Bs
            (2001.014, 22.0),  # ticket: 956.04 Bs
            (3000.0, 22.0),
            (3000.5, 34.0),
            (3001.5, 34.0),
            (1_000_000.0, 34.0),
        ]
        for base_ut, percentage in cases:
            with self.subTest(base_ut=base_ut):
                tier = self.tariff.get_accumulated_rate(base_ut)
                self.assertEqual(tier.percentage, percentage)

    def test_negative_base_has_no_tier(self):
        self.assertFalse(self.tariff.get_accumulated_rate(-1.0))

    def test_constraint_rejects_tier_without_upper_limit(self):
        with self.assertRaises(ValidationError):
            self.tariff.accumulated_rate_ids[0].stop = 0.0

    def test_constraint_rejects_decreasing_limits(self):
        with self.assertRaises(ValidationError):
            self.tariff.accumulated_rate_ids.filtered(lambda t: t.name == "T2").stop = 1500.0
