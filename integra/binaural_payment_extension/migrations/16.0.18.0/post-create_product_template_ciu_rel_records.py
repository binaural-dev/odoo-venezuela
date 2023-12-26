def migrate(cr, installed_version):
    cr.execute(
        """
        DELETE FROM product_template_ciu_rel;
    """
    )
    cr.execute(
        """
        INSERT INTO product_template_ciu_rel (product_template_id, ciu_id)
        SELECT id, temp_ciu_id FROM product_template WHERE temp_ciu_id IS NOT NULL
    """
    )
    cr.execute("ALTER TABLE product_template DROP COLUMN temp_ciu_id")
