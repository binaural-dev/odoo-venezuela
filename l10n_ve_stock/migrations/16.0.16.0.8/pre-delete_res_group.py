def migrate(cr, installed_version):
    cr.execute(
        """
        DELETE from ir_model_data where module = 'l10n_ve_stock' and name ilike 'group_hide_add_new_product_in_dispatch'
        """
    )
    
    cr.execute(
        """
        DELETE from res_groups where name ->> 'en_US' ilike 'Hide Add New Product In Dispatch';
        """
    )
