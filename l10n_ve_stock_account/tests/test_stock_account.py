from odoo.tests.common import TransactionCase

@tagged("post_install", "-at_install", "l10n_ve_stock_account")
class TestL10nVeStockAccount(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.sequence_model = cls.env['ir.sequence']
        cls.picking_type_out = cls.env.ref('stock.picking_type_out')
        cls.location_src = cls.env.ref('stock.stock_location_stock')
        cls.location_dest = cls.env.ref('stock.stock_location_customers')

        cls.transfer_reason_donation = cls.env.ref(
            'l10n_ve_stock_account.transfer_reason_donation'
        )
        cls.transfer_reason_self_consumption = cls.env.ref(
            'l10n_ve_stock_account.transfer_reason_self_consumption'
        )
        cls.transfer_reason_other_causes = cls.env.ref(
            'l10n_ve_stock_account.transfer_reason_other_causes'
        )
        cls.transfer_reason_repair = cls.env.ref(
            'l10n_ve_stock_account.transfer_reason_repair'
        )
        cls.transfer_reason_external_storage = cls.env.ref(
            'l10n_ve_stock_account.transfer_reason_external_storage'
        )

        cls.journal = cls.env['account.journal'].search(
            [('type', '=', 'general'), ('company_id', '=', cls.company.id)],
            limit=1,
        )
        if not cls.journal:
            raise cls.skipTest('No general journal available for tests')

        accounts = cls.env['account.account'].search(
            [('deprecated', '=', False), ('company_id', '=', cls.company.id)],
            limit=2,
        )
        if len(accounts) < 2:
            raise cls.skipTest('Not enough accounts available for tests')
        cls.account_debit, cls.account_credit = accounts[:2]

    def _create_basic_picking(self, values=None):
        picking_vals = {
            'name': 'TEST/0001',
            'company_id': self.company.id,
            'picking_type_id': self.picking_type_out.id,
            'location_id': self.location_src.id,
            'location_dest_id': self.location_dest.id,
        }
        if values:
            picking_vals.update(values)
        return self.env['stock.picking'].create(picking_vals)

    def _create_balanced_move(self):
        return self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal.id,
            'line_ids': [
                (0, 0, {
                    'name': 'debit line',
                    'debit': 100.0,
                    'credit': 0.0,
                    'account_id': self.account_debit.id,
                }),
                (0, 0, {
                    'name': 'credit line',
                    'debit': 0.0,
                    'credit': 100.0,
                    'account_id': self.account_credit.id,
                }),
            ],
        })

    def test_compute_guide_number_concatenates_values(self):
        picking_1 = self._create_basic_picking({'guide_number': 'GUIDE0001'})
        picking_2 = self._create_basic_picking({'guide_number': 'GUIDE0002'})

        move = self._create_balanced_move()
        move.write({'picking_ids': [(6, 0, (picking_1 | picking_2).ids)]})

        move._compute_guide_number()

        self.assertEqual(move.guide_number, 'GUIDE0001/GUIDE0002')

    def test_get_sequence_creates_missing_sequence(self):
        self.sequence_model.search([
            ('code', '=', 'guide.number'),
            ('company_id', '=', self.company.id),
        ]).unlink()

        picking = self._create_basic_picking()
        next_number = picking.get_sequence_guide_num()

        self.assertTrue(next_number.startswith('GUIDE'))

        new_sequence = self.sequence_model.search([
            ('code', '=', 'guide.number'),
            ('company_id', '=', self.company.id),
        ], limit=1)
        self.assertTrue(new_sequence)

    def test_allowed_reason_ids_outgoing_without_sale(self):
        picking = self._create_basic_picking({
            'transfer_reason_id': self.transfer_reason_donation.id,
        })

        picking._compute_allowed_reason_ids()

        allowed_codes = set(picking.allowed_reason_ids.mapped('code'))
        self.assertSetEqual(
            allowed_codes,
            {
                'self_consumption',
                'other_causes',
                'repair_improvement',
                'external_storage',
            },
        )

        self.assertEqual(
            picking.transfer_reason_id, self.transfer_reason_self_consumption
        )