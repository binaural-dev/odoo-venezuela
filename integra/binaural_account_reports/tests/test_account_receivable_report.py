from odoo import fields, Command
from odoo.tests import tagged
from .common import TestAccountReportsCommonBinaural
from odoo.addons.account_reports.tests.test_aged_receivable_report import TestAgedReceivableReport
import logging

_logger = logging.getLogger(__name__)


@tagged(
    "post_install",
    "-at_install",
    "account_reports",
    "account_receivable_report",
    "base_vef_report",
)
class TestAccountReceivableReportBinauralBaseVef(TestAccountReportsCommonBinaural):
    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(
            chart_template_ref=chart_template_ref,
            base_currency_ref="base.VEF",
            foreign_currency_ref="base.USD",
        )
        _logger.warning(
            "Account moves before test: %s",
            cls.env["account.move"].search([]).read(["foreign_rate"]),
        )
        cls.foreign_currency.rate_ids.unlink()
        cls.foreign_currency.rate_ids = [
            Command.create({"name": "2016-01-01", "inverse_company_rate": 25}),
        ]

        cls.partner_category_a = cls.env["res.partner.category"].create({"name": "partner_categ_a"})
        cls.partner_category_b = cls.env["res.partner.category"].create({"name": "partner_categ_b"})

        cls.partner_a = cls.env["res.partner"].create(
            {
                "name": "partner_a",
                "company_id": False,
                "category_id": [
                    Command.set([cls.partner_category_a.id, cls.partner_category_b.id])
                ],
            }
        )
        cls.partner_b = cls.env["res.partner"].create(
            {
                "name": "partner_b",
                "company_id": False,
                "category_id": [Command.set([cls.partner_category_a.id])],
            }
        )

        receivable_1 = cls.company_data["default_account_receivable"]
        receivable_2 = cls.company_data["default_account_receivable"].copy()
        receivable_3 = cls.company_data["default_account_receivable"].copy()
        receivable_4 = cls.company_data_2["default_account_receivable"]
        receivable_5 = cls.company_data_2["default_account_receivable"].copy()
        receivable_6 = cls.company_data_2["default_account_receivable"].copy()
        misc_1 = cls.company_data["default_account_revenue"]
        misc_2 = cls.company_data_2["default_account_revenue"]

        # Test will use the following dates:
        # As of                  2017-02-01
        # 1 - 30:   2017-01-31 - 2017-01-02
        # 31 - 60:  2017-01-01 - 2016-12-03
        # 61 - 90:  2016-12-02 - 2016-11-03
        # 91 - 120: 2016-11-02 - 2016-10-04
        # Older:    2016-10-03

        # ==== Journal entries in company_1 for partner_a ====

        move_1 = cls.env["account.move"].create(
            {
                "move_type": "entry",
                "date": fields.Date.from_string("2016-11-03"),
                "journal_id": cls.company_data["default_journal_sale"].id,
                "line_ids": [
                    # 1000.0 in 61 - 90.
                    Command.create(
                        {
                            "debit": 1000.0,
                            "credit": 0.0,
                            "date_maturity": False,
                            "account_id": receivable_1.id,
                            "partner_id": cls.partner_a.id,
                        }
                    ),
                    # -800.0 in 31 - 60
                    Command.create(
                        {
                            "debit": 0.0,
                            "credit": 800.0,
                            "date_maturity": "2017-01-01",
                            "account_id": receivable_2.id,
                            "partner_id": cls.partner_a.id,
                        }
                    ),
                    # Ignored line.
                    Command.create(
                        {
                            "debit": 0.0,
                            "credit": 200.0,
                            "date_maturity": False,
                            "account_id": misc_1.id,
                            "partner_id": cls.partner_a.id,
                        }
                    ),
                ],
            }
        )

        move_2 = cls.env["account.move"].create(
            {
                "move_type": "entry",
                "date": fields.Date.from_string("2016-10-05"),
                "journal_id": cls.company_data["default_journal_sale"].id,
                "line_ids": [
                    # -200.0 in 61 - 90
                    Command.create(
                        {
                            "debit": 0.0,
                            "credit": 200.0,
                            "date_maturity": "2016-12-02",
                            "account_id": receivable_1.id,
                            "partner_id": cls.partner_a.id,
                        }
                    ),
                    # -300.0 in 31 - 60
                    Command.create(
                        {
                            "debit": 0.0,
                            "credit": 300.0,
                            "date_maturity": "2016-12-03",
                            "account_id": receivable_1.id,
                            "partner_id": cls.partner_a.id,
                        }
                    ),
                    # 1000.0 in 91 - 120
                    Command.create(
                        {
                            "debit": 1000.0,
                            "credit": 0.0,
                            "date_maturity": False,
                            "account_id": receivable_2.id,
                            "partner_id": cls.partner_a.id,
                        }
                    ),
                    # 100.0 in all dates
                    Command.create(
                        {
                            "debit": 100.0,
                            "credit": 0.0,
                            "date_maturity": "2017-02-01",
                            "account_id": receivable_3.id,
                            "partner_id": cls.partner_a.id,
                        }
                    ),
                    Command.create(
                        {
                            "debit": 100.0,
                            "credit": 0.0,
                            "date_maturity": "2017-01-02",
                            "account_id": receivable_3.id,
                            "partner_id": cls.partner_a.id,
                        }
                    ),
                    Command.create(
                        {
                            "debit": 100.0,
                            "credit": 0.0,
                            "date_maturity": "2016-12-03",
                            "account_id": receivable_3.id,
                            "partner_id": cls.partner_a.id,
                        }
                    ),
                    Command.create(
                        {
                            "debit": 100.0,
                            "credit": 0.0,
                            "date_maturity": "2016-11-03",
                            "account_id": receivable_3.id,
                            "partner_id": cls.partner_a.id,
                        }
                    ),
                    Command.create(
                        {
                            "debit": 100.0,
                            "credit": 0.0,
                            "date_maturity": "2016-10-04",
                            "account_id": receivable_3.id,
                            "partner_id": cls.partner_a.id,
                        }
                    ),
                    Command.create(
                        {
                            "debit": 100.0,
                            "credit": 0.0,
                            "date_maturity": "2016-01-01",
                            "account_id": receivable_3.id,
                            "partner_id": cls.partner_a.id,
                        }
                    ),
                    # Ignored line.
                    Command.create(
                        {
                            "debit": 0.0,
                            "credit": 1100.0,
                            "date_maturity": "2016-10-05",
                            "account_id": misc_1.id,
                            "partner_id": cls.partner_a.id,
                        }
                    ),
                ],
            }
        )
        (move_1 + move_2).action_post()
        (move_1 + move_2).line_ids.filtered(
            lambda line: line.account_id == receivable_1
        ).reconcile()
        (move_1 + move_2).line_ids.filtered(
            lambda line: line.account_id == receivable_2
        ).reconcile()

        # ==== Journal entries in company_2 for partner_b ====

        move_3 = cls.env["account.move"].create(
            {
                "move_type": "entry",
                "date": fields.Date.from_string("2016-11-03"),
                "journal_id": cls.company_data_2["default_journal_sale"].id,
                "line_ids": [
                    # 1000.0 in 61 - 90.
                    Command.create(
                        {
                            "debit": 1000.0,
                            "credit": 0.0,
                            "date_maturity": False,
                            "account_id": receivable_4.id,
                            "partner_id": cls.partner_b.id,
                        }
                    ),
                    # -200.0 in 31 - 60
                    Command.create(
                        {
                            "debit": 0.0,
                            "credit": 800.0,
                            "date_maturity": "2017-01-01",
                            "account_id": receivable_5.id,
                            "partner_id": cls.partner_b.id,
                        }
                    ),
                    # Ignored line.
                    Command.create(
                        {
                            "debit": 0.0,
                            "credit": 200.0,
                            "date_maturity": False,
                            "account_id": misc_2.id,
                            "partner_id": cls.partner_b.id,
                        }
                    ),
                ],
            }
        )

        move_4 = cls.env["account.move"].create(
            {
                "move_type": "entry",
                "date": fields.Date.from_string("2016-10-05"),
                "journal_id": cls.company_data_2["default_journal_sale"].id,
                "line_ids": [
                    # -200.0 in 61 - 90
                    Command.create(
                        {
                            "debit": 0.0,
                            "credit": 200.0,
                            "date_maturity": "2016-12-02",
                            "account_id": receivable_4.id,
                            "partner_id": cls.partner_b.id,
                        }
                    ),
                    # -300.0 in 31 - 60
                    Command.create(
                        {
                            "debit": 0.0,
                            "credit": 300.0,
                            "date_maturity": "2016-12-03",
                            "account_id": receivable_4.id,
                            "partner_id": cls.partner_b.id,
                        }
                    ),
                    # 1000.0 in 91 - 120
                    Command.create(
                        {
                            "debit": 1000.0,
                            "credit": 0.0,
                            "date_maturity": False,
                            "account_id": receivable_5.id,
                            "partner_id": cls.partner_b.id,
                        }
                    ),
                    # 100.0 in all dates
                    Command.create(
                        {
                            "debit": 100.0,
                            "credit": 0.0,
                            "date_maturity": "2017-02-01",
                            "account_id": receivable_6.id,
                            "partner_id": cls.partner_b.id,
                        }
                    ),
                    Command.create(
                        {
                            "debit": 100.0,
                            "credit": 0.0,
                            "date_maturity": "2017-01-02",
                            "account_id": receivable_6.id,
                            "partner_id": cls.partner_b.id,
                        }
                    ),
                    Command.create(
                        {
                            "debit": 100.0,
                            "credit": 0.0,
                            "date_maturity": "2016-12-03",
                            "account_id": receivable_6.id,
                            "partner_id": cls.partner_b.id,
                        }
                    ),
                    Command.create(
                        {
                            "debit": 100.0,
                            "credit": 0.0,
                            "date_maturity": "2016-11-03",
                            "account_id": receivable_6.id,
                            "partner_id": cls.partner_b.id,
                        }
                    ),
                    Command.create(
                        {
                            "debit": 100.0,
                            "credit": 0.0,
                            "date_maturity": "2016-10-04",
                            "account_id": receivable_6.id,
                            "partner_id": cls.partner_b.id,
                        }
                    ),
                    Command.create(
                        {
                            "debit": 100.0,
                            "credit": 0.0,
                            "date_maturity": "2016-01-01",
                            "account_id": receivable_6.id,
                            "partner_id": cls.partner_b.id,
                        }
                    ),
                    # Ignored line.
                    Command.create(
                        {
                            "debit": 0.0,
                            "credit": 1100.0,
                            "date_maturity": False,
                            "account_id": misc_2.id,
                            "partner_id": cls.partner_b.id,
                        }
                    ),
                ],
            }
        )
        _logger.warning(
            "Move 3 lines: %s",
            move_3.line_ids.read(
                ["debit", "credit", "foreign_inverse_rate", "foreign_debit", "foreign_credit"]
            ),
        )
        _logger.warning(
            "Move 4 lines: %s",
            move_4.line_ids.read(
                ["debit", "credit", "foreign_inverse_rate", "foreign_debit", "foreign_credit"]
            ),
        )
        (move_3 + move_4).action_post()
        reconcile_1 = (
            (move_3 + move_4)
            .line_ids.filtered(lambda line: line.account_id == receivable_4)
            .reconcile()
        )
        reconcile_2 = (
            (move_3 + move_4)
            .line_ids.filtered(lambda line: line.account_id == receivable_5)
            .reconcile()
        )
        _logger.warning(
            "Reconcile 1: %s",
            [
                {
                    "amount": partial["amount"],
                    "debit_move_id": (
                        cls.env["account.move.line"]
                        .browse(partial["debit_move_id"][0])
                        .read(["name", "foreign_inverse_rate"])
                    ),
                    "credit_move_id": (
                        cls.env["account.move.line"]
                        .browse(partial["credit_move_id"][0])
                        .read(["name", "foreign_inverse_rate"])
                    ),
                }
                for partial in reconcile_1["partials"].read([])
            ],
        )
        _logger.warning(
            "Reconcile 2: %s",
            [
                {
                    "amount": partial["amount"],
                    "debit_move_id": (
                        cls.env["account.move.line"]
                        .browse(partial["debit_move_id"][0])
                        .read(["name", "foreign_inverse_rate"])
                    ),
                    "credit_move_id": (
                        cls.env["account.move.line"]
                        .browse(partial["credit_move_id"][0])
                        .read(["name", "foreign_inverse_rate"])
                    ),
                }
                for partial in reconcile_2["partials"].read([])
            ],
        )
        cls.env["res.currency"].search(
            [("name", "!=", "USD"), ("name", "!=", "VEF")]
        ).active = False
        cls.env.companies = cls.company_data["company"] + cls.company_data_2["company"]
        cls.report = cls.env.ref("account_reports.aged_receivable_report").with_context(
            usd_report=True
        )
        cls.prefix_line_id = f'{cls._get_basic_line_dict_id_from_report_line_ref("account_reports.aged_receivable_line")}|'

    def test_aged_receivable_report_base_vef(self):
        """
        Test the aged receivable report with the base.VEF currency when it is the base currency of
        the company.
        """
        options = self._generate_options(
            self.report,
            fields.Date.from_string("2017-02-01"),
            fields.Date.from_string("2017-02-01"),
        )
        partner_a_line_id = self.env["account.report"]._get_generic_line_id(
            "res.partner", self.partner_a.id, markup=f"{self.prefix_line_id}groupby:partner_id"
        )
        options["unfolded_lines"] = [partner_a_line_id]

        report_lines = self.report._get_lines(options)
        sorted_report_lines = self.report._sort_lines(report_lines, options)

        # self.assertLinesValues(
        #     # pylint: disable=C0326
        #     sorted_report_lines,
        #     #   Name                    Due Date   Not Due On      1 - 30     31 - 60     61 - 90    91 - 120       Older        Total
        #     [   0,                                 1,       4,          5,          6,          7,          8,          9,          10],
        #     [
        #         ('Aged Receivable',               '',      '',         '',      150.0,      150.0,      150.0,      900.0,       450.0),
        #         ('partner_a',                     '',      '',         '',      100.0,      100.0,      100.0,      600.0,       300.0),
        #         ('INV/2016/00002',      '01/01/2016',      '121030',   '',         '',         '',         '',         '',          ''),
        #         ('INV/2016/00002',      '10/04/2016',      '121030',   '',         '',         '',         '',         '',       100.0),
        #         ('INV/2016/00002',      '10/05/2016',      '121020',   '',         '',         '',         '',         '',       200.0),
        #         ('INV/2016/00001',      '11/03/2016',      '121000',   '',         '',         '',         '',         500.0,       ''),
        #         ('INV/2016/00002',      '11/03/2016',      '121030',   '',         '',         '',         '',      100.0,          ''),
        #         ('INV/2016/00002',      '12/03/2016',      '121030',   '',         '',         '',      100.0,         '',          ''),
        #         ('INV/2016/00002',      '01/02/2017',      '121030',   '',         '',      100.0,         '',         '',          ''),
        #         ('INV/2016/00002',      '02/01/2017',      '121030',   '',      100.0,         '',         '',         '',          ''),
        #         ('Total partner_a',               '',            '',   '',      100.0,       100.0,     100.0,      600.0,       300.0),
        #         ('partner_b',                     '',            '',   '',       50.0,        50.0,      50.0,      300.0,       150.0),
        #         ('Total Aged Receivable',         '',            '',   '',      150.0,       150.0,     150.0,      900.0,       450.0),
        #     ],
        # )


        self.assertLinesValues(
            sorted_report_lines,
            #   Name                    Due Date   Not Due On      1 - 30     31 - 60     61 - 90    91 - 120       Older        Total
            [   0,                                 1,       4,          5,          6,          7,          8,          9,          10],
            [
                ('Aged Receivable',               '',      '',         '',        6.0,        6.0,        6.0,        36.0,       18.0),
                ('partner_a',                     '',      '',         '',        4.0,        4.0,        4.0,        24.0,       12.0),
                ('INV/2016/00002',      '01/01/2016',      '121030',   '',         '',         '',         '',         '',          ''),
                ('INV/2016/00002',      '10/04/2016',      '121030',   '',         '',         '',         '',         '',         4.0),
                ('INV/2016/00002',      '10/05/2016',      '121020',   '',         '',         '',         '',         '',         8,0),
                ('INV/2016/00001',      '11/03/2016',      '121000',   '',         '',         '',         '',       20.0,          ''),
                ('INV/2016/00002',      '11/03/2016',      '121030',   '',         '',         '',         '',        4.0,          ''),
                ('INV/2016/00002',      '12/03/2016',      '121030',   '',         '',         '',        4.0,         '',          ''),
                ('INV/2016/00002',      '01/02/2017',      '121030',   '',         '',        4.0,         '',         '',          ''),
                ('INV/2016/00002',      '02/01/2017',      '121030',   '',        4.0,         '',         '',         '',          ''),
                ('Total partner_a',               '',            '',   '',        4.0,        4.0,        4.0,       24.0,        12.0),
                ('partner_b',                     '',            '',   '',        2.0,        2.0,        2.0,       12.0,         6.0),
                ('Total Aged Receivable',         '',            '',   '',        6.0,        6.0,        6.0,       36.0,        18.0),
            ],
            currency_map={i+1: {'currency': self.env.company.currency_foreign_id} for i in range(0, 12)},
        )

#         # Sort 61 - 90 decreasing.
#         options['order_column'] = -7
#         self.assertLinesValues(
#             # pylint: disable=C0326
#             report._sort_lines(sorted_report_lines, options),
#             #   Name                    Due Date   Not Due On      1 - 30     31 - 60     61 - 90    91 - 120       Older        Total
#             [   0,                                 1,       4,          5,          6,          7,          8,          9,          10],
#             [
#                 ('Aged Receivable',               '',   150.0,      150.0,      150.0,      900.0,      450.0,      150.0,      1950.0),
#                 ('partner_a',                     '',   100.0,      100.0,      100.0,      600.0,      300.0,      100.0,      1300.0),
#                 ('INV/2016/00001',      '11/03/2016',      '',         '',         '',      500.0,         '',         '',          ''),
#                 ('INV/2016/00002',      '11/03/2016',      '',         '',         '',      100.0,         '',         '',          ''),
#                 ('INV/2016/00002',      '01/01/2016',      '',         '',         '',         '',         '',      100.0,          ''),
#                 ('INV/2016/00002',      '10/04/2016',      '',         '',         '',         '',      100.0,         '',          ''),
#                 ('INV/2016/00002',      '10/05/2016',      '',         '',         '',         '',      200.0,         '',          ''),
#                 ('INV/2016/00002',      '12/03/2016',      '',         '',      100.0,         '',         '',         '',          ''),
#                 ('INV/2016/00002',      '01/02/2017',      '',      100.0,         '',         '',         '',         '',          ''),
#                 ('INV/2016/00002',      '02/01/2017',   100.0,         '',         '',         '',         '',         '',          ''),
#                 ('Total partner_a',               '',   100.0,      100.0,      100.0,      600.0,      300.0,      100.0,      1300.0),
#                 ('partner_b',                     '',    50.0,       50.0,       50.0,      300.0,      150.0,       50.0,       650.0),
#                 ('Total Aged Receivable',         '',   150.0,      150.0,      150.0,      900.0,      450.0,      150.0,      1950.0),
#             ],
#             currency_map={i+1: {'currency': self.env.company.currency_id} for i in range(1, 13)},
#         )

#         # Sort 61 - 90 increasing.
#         options['order_column'] = 7
#         self.assertLinesValues(
#             # pylint: disable=C0326
#             report._sort_lines(sorted_report_lines, options),
#             #   Name                    Due Date    Not Due On      1 - 30     31 - 60      61 - 90    91 - 120       Older        Total
#             [   0,                                 1,        4,          5,          6,           7,          8,          9,          10],
#             [
#                 ('Aged Receivable',               '',    150.0,      150.0,      150.0,       900.0,      450.0,      150.0,      1950.0),
#                 ('partner_b',                     '',     50.0,       50.0,       50.0,       300.0,      150.0,       50.0,       650.0),
#                 ('partner_a',                     '',    100.0,      100.0,      100.0,       600.0,      300.0,      100.0,      1300.0),
#                 ('INV/2016/00002',      '01/01/2016',       '',         '',         '',          '',         '',      100.0,          ''),
#                 ('INV/2016/00002',      '10/04/2016',       '',         '',         '',          '',      100.0,         '',          ''),
#                 ('INV/2016/00002',      '10/05/2016',       '',         '',         '',          '',      200.0,         '',          ''),
#                 ('INV/2016/00002',      '12/03/2016',       '',         '',      100.0,          '',         '',         '',          ''),
#                 ('INV/2016/00002',      '01/02/2017',       '',      100.0,         '',          '',         '',         '',          ''),
#                 ('INV/2016/00002',      '02/01/2017',    100.0,         '',         '',          '',         '',         '',          ''),
#                 ('INV/2016/00002',      '11/03/2016',       '',         '',         '',       100.0,         '',         '',          ''),
#                 ('INV/2016/00001',      '11/03/2016',       '',         '',         '',       500.0,         '',         '',          ''),
#                 ('Total partner_a',               '',    100.0,      100.0,      100.0,       600.0,      300.0,      100.0,      1300.0),
#                 ('Total Aged Receivable',         '',    150.0,      150.0,      150.0,       900.0,      450.0,      150.0,      1950.0),
#             ],
#             currency_map={i+1: {'currency': self.env.company.currency_id} for i in range(1, 13)},
#         )
