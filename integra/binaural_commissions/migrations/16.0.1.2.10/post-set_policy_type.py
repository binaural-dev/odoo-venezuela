def migrate(cr, installed_version):
    # send policy_type Selection to policy_type_id Model
    cr.execute(
        """
        UPDATE commission_policy as cp
        SET policy_type_id = 
            (
                SELECT id 
                FROM commission_policy_type 
                WHERE policy_type = cp.policy_type 
                LIMIT 1 
            ),sequence = 
            (
                SELECT sequence 
                FROM commission_policy_type 
                WHERE policy_type = cp.policy_type 
                LIMIT 1 
            )
        WHERE policy_type IS NOT NULL;
       """
    )

    cr.execute(
        """
        UPDATE commission_policy_line_image as cpli
        SET policy_type_id = 
            (
                SELECT id 
                FROM commission_policy_type 
                WHERE policy_type = cpli.policy_type 
                LIMIT 1 
            )
        WHERE policy_type IS NOT NULL;
    """
    )
