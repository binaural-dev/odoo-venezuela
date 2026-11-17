"""`block_invoice_display_date_upper_than_date` pasa a ser True por defecto:
activa el bloqueo (fecha contable de compras no menor a la fecha de la
factura) en las companias existentes."""


def migrate(cr, version):
    cr.execute(
        "UPDATE res_company SET block_invoice_display_date_upper_than_date = TRUE"
    )
