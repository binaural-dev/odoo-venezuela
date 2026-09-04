def migrate(cr, version):
    cr.execute(
        """
        UPDATE account_move
        SET print_type = 'fiscal'
        WHERE mf_serial IS NOT NULL AND mf_serial != ''
          AND mf_invoice_number IS NOT NULL AND mf_invoice_number != ''
        """
    )
