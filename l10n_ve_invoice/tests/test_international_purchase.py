from odoo.tests.common import TransactionCase

class TestAccountMoveInternational(TransactionCase):
    def setUp(self):
        super().setUp()
        self.journal_intl = self.env['account.journal'].create({
            'name': 'International Journal',
            'type': 'purchase',
            'code': 'INTL',
            'is_purchase_international': True,
        })
        self.journal_local = self.env['account.journal'].create({
            'name': 'Local Journal',
            'type': 'purchase',
            'code': 'LOC',
            'is_purchase_international': False,
        })

    def test_is_purchase_international_related(self):
        move_intl = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'journal_id': self.journal_intl.id,
            'date': '2023-01-01',
        })
        self.assertTrue(move_intl.is_purchase_international, "Move should be international when journal is international")

        move_local = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'journal_id': self.journal_local.id,
            'date': '2023-01-01',
        })
        self.assertFalse(move_local.is_purchase_international, "Move should not be international when journal is not")
