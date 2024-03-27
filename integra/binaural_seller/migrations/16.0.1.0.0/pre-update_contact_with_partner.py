def migrate(cr, installed_version):
    cr.execute(
        """
        SELECT res_id from ir_model_data where name = 'hr_employee_1' and module = 'binaural_seller';
        """
    )
    base_employee_id = cr.fetchone()[0]

    cr.execute(
        """
        SELECT rp.name, rp.id
        FROM res_partner rp
        LEFT JOIN hr_employee_res_partner_rel rel ON rp.id = rel.res_partner_id
        WHERE rel.res_partner_id IS NULL;
        """
    )
    partners_without_employee = cr.fetchall()

    for partner in partners_without_employee:
        partner_name, partner_id = partner
        cr.execute(
            """
            INSERT INTO hr_employee_res_partner_rel (res_partner_id, hr_employee_id)
            VALUES (%s, %s);
            """,
            (partner_id, base_employee_id)
        )
