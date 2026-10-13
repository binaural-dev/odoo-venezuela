"""Las ND/NC por diferencial cambiario no deben llevar montos en moneda
alterna (igual que el asiento de diferencial nativo): se ponen en 0.0 los
valores alternos de las lineas de las notas ya emitidas."""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE account_move_line aml
           SET foreign_debit = 0.0,
               foreign_credit = 0.0,
               foreign_balance = 0.0
          FROM account_move am
         WHERE am.id = aml.move_id
           AND am.l10n_ve_exchange_diff_entry
           AND am.move_type IN ('out_invoice', 'out_refund')
        """
    )
