def migrate(cr, installed_version):
    cr.execute("ALTER TABLE product_template ADD COLUMN temp_ciu_id int")
    cr.execute("UPDATE product_template SET temp_ciu_id=ciu_id")
