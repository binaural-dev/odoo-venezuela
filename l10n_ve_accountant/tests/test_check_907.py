import logging
_logger = logging.getLogger(__name__)
from odoo.tests import TransactionCase, tagged

@tagged("post_install", "-at_install", "check_invoice_907")
class CheckInvoice907(TransactionCase):
    def test_check_invoice_907(self):
        cr = self.env.cr
        cr.execute("SELECT id, name, move_type, state, invoice_date, currency_id, amount_total FROM account_move WHERE id = 907")
        row = cr.fetchone()
        if not row:
            _logger.warning("INVOICE 907 NOT FOUND")
            return

        _logger.warning("=== INVOICE 907 ===")
        _logger.warning("id=%s name=%s type=%s state=%s date=%s cur_id=%s total=%s",
                        row[0], row[1], row[2], row[3], row[4], row[5], row[6])

        cr.execute("SELECT currency_id, foreign_currency_id FROM res_company WHERE id = 1")
        c = cr.fetchone()
        _logger.warning("Company: cur_id=%s foreign_cur_id=%s", c[0], c[1])

        cr.execute("""
            SELECT id, name, display_type, currency_id, account_id,
                   debit, credit, balance,
                   foreign_debit, foreign_credit, foreign_balance,
                   amount_currency, not_foreign_recalculate,
                   foreign_inverse_rate
            FROM account_move_line
            WHERE move_id = 907
            ORDER BY id
        """)
        lines = cr.fetchall()

        _logger.warning("%-6s %-14s %-5s %-6s %16s %16s %16s %14s %14s %14s %14s %-6s %s",
                        "id", "type", "cur", "acct", "debit", "credit", "balance", "f_db", "f_cr", "f_bal", "amt_cur", "n_rec", "inv_rate")
        _logger.warning("-" * 150)
        for l in lines:
            _logger.warning("%-6s %-14s %-5s %-6s %16.2f %16.2f %16.2f %14.2f %14.2f %14.2f %14.2f %-6s %14.8f",
                            l[0], str(l[2]), str(l[3] or ''), l[4],
                            l[5], l[6], l[7], (l[8] or 0), (l[9] or 0), (l[10] or 0), (l[11] or 0),
                            str(bool(l[12])), (l[13] or 0))

        pt = [l for l in lines if l[2] == 'payment_term']
        np = [l for l in lines if l[2] != 'payment_term']
        fd_pt = sum((l[8] or 0) for l in pt)
        fc_pt = sum((l[9] or 0) for l in pt)
        fd_np = sum((l[8] or 0) for l in np)
        fc_np = sum((l[9] or 0) for l in np)

        _logger.warning("")
        _logger.warning("Non-PT (%d): f_db=%.2f f_cr=%.2f", len(np), fd_np, fc_np)
        _logger.warning("PT     (%d): f_db=%.2f f_cr=%.2f", len(pt), fd_pt, fc_pt)
        _logger.warning("ALL:         f_db=%.2f f_cr=%.2f diff=%.6f", fd_np+fd_pt, fc_np+fc_pt, (fd_np+fd_pt)-(fc_np+fc_pt))

        if pt:
            _logger.warning("")
            for p in pt:
                exp = fc_np / len(pt)
                _logger.warning("PT id=%s bal=%.2f f_db=%.2f f_cr=%.2f f_bal=%.2f expected~%.2f diff=%.6f",
                                p[0], p[7], (p[8] or 0), (p[9] or 0), (p[10] or 0), exp, abs((p[8] or 0) - exp))

            self.assertAlmostEqual(fd_pt, fc_np, places=2,
                                   msg="PT foreign_debit sum != non-PT foreign_credit")
            self.assertAlmostEqual(fd_np + fd_pt, fc_np + fc_pt, places=2,
                                   msg="Foreign imbalance")
            for p in pt:
                exp = fc_np / len(pt)
                self.assertAlmostEqual((p[8] or 0), exp, delta=0.02,
                                       msg="PT %s foreign_debit %.2f != expected %.2f" % (p[0], (p[8] or 0), exp))
            _logger.warning("*** ALL CHECKS PASSED ***")

        _logger.warning("=== CHECK COMPLETE ===")
