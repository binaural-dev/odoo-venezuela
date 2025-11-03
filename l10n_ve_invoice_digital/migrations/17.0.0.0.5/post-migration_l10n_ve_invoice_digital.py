# migrations/17.0.2.0.0/post-migration.py
from odoo.api import Environment, SUPERUSER_ID


def migrate(cr, version):
    env = Environment(cr, SUPERUSER_ID, {})

    cr.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'account_journal' AND column_name = 'payment_method_code_legacy'
        LIMIT 1
    """
    )
    if not cr.fetchone():
        return

    cr.execute(
        """
        SELECT DISTINCT TRIM(payment_method_code_legacy)
        FROM account_journal
        WHERE payment_method_code_legacy IS NOT NULL
          AND TRIM(payment_method_code_legacy) <> ''
    """
    )
    codes = [r[0] for r in cr.fetchall()]

    Method = env["payment.method.tfhka"]
    if codes:
        existing = {
            m.code: m.id
            for m in Method.search([("code", "in", [c.strip() for c in codes])])
        }
        to_create = []
        for code in codes:
            code = code.strip()
            if code and code not in existing:
                to_create.append({"code": code, "name": code})
        if to_create:
            created = Method.create(to_create)
            for m in created:
                existing[m.code] = m.id

    cr.execute(
        """
        UPDATE account_journal aj
        SET payment_method_code = pm.id
        FROM payment_method_tfhka pm
        WHERE TRIM(aj.payment_method_code_legacy) = pm.code
          AND aj.payment_method_code IS NULL
          AND aj.payment_method_code_legacy IS NOT NULL
          AND TRIM(aj.payment_method_code_legacy) <> ''
    """
    )

    env.cr.execute("SELECT id FROM payment_method_tfhka WHERE code = '03' LIMIT 1")
    row = env.cr.fetchone()
    if row:
        default_id = row[0]
        env.cr.execute(
            """
            UPDATE account_journal
            SET payment_method_code = %s
            WHERE payment_method_code IS NULL
        """,
            (default_id,),
        )

    cr.execute("ALTER TABLE account_journal DROP COLUMN payment_method_code_legacy")
