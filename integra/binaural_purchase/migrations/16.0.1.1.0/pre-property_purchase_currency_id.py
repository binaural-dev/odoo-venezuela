def migrate(cr, installed_version):
    cr.execute(
        """
        DELETE FROM ir_property WHERE name = 'property_purchase_currency_id';
    """
    )
