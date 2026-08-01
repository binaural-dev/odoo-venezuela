def migrate(cr, version):
    cr.execute("UPDATE res_company SET unique_tax = TRUE")
