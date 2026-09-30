"""Give each partner the advance accounts its company used in v17.

What: creates res_partner.default_advance_customer_account_id and default_advance_supplier_account_id
    before the ORM does and fills them from res_company.advance_customer_account_id /
    advance_supplier_account_id:

    1. Partner with a company: that company's accounts.
    2. Shared partner (no company): the accounts of the only company that has them configured.
    3. If several do, the accounts of the company where it had advance payments in v17, as long as
       it is a single one.
    The rest stay empty and are listed in the migration report.

Why: in v17 an advance payment always took the company's account. In v19 it takes the partner's
    (account_payment._compute_destination_account_id), and with no account on the partner
    res.partner._check_igtf_apply_improved returns False: the advance neither applies IGTF nor goes
    to the advance account. Both fields are new in v19, with default=env.company.<account>. When it
    creates the column, the ORM computes that default once, with the main company, and writes it on
    every partner. In 19_proalca_run15 the main company has no advance accounts, and all 3,360
    partners were left empty, including those of companies 2, 3 and 4, which do have them. On a
    client whose main company does have them, every partner would get that company's accounts, even
    partners of another company.

    The field is not company_dependent: a shared partner used by two companies with advance payments
    can only hold one account. That comes from the v19 design, not from the migration, and those
    cases go to the report.

If it does not run: the advance payments of migrated clients stop applying IGTF and stop going to
    the advance account, or go to another company's account.

How to revert: empty both fields on the partners. The company accounts are not touched.

Task: https://binaural.odoo.com/odoo/action-1963/4199/action-345/82849
"""

from odoo.upgrade import util

PAIRS = (
    ("default_advance_customer_account_id", "advance_customer_account_id", "customer"),
    ("default_advance_supplier_account_id", "advance_supplier_account_id", "supplier"),
)


def migrate(cr, version):
    if not version or not version.startswith("17."):
        return

    unresolved = []
    for partner_col, company_col, partner_type in PAIRS:
        if not util.column_exists(cr, "res_company", company_col):
            continue
        created = util.create_column(
            cr, "res_partner", partner_col, "int4", fk_table="account_account", on_delete_action="SET NULL"
        )
        if not created:
            continue

        # 1. partner with a company
        cr.execute(
            f"""
            UPDATE res_partner p
               SET {partner_col} = c.{company_col}
              FROM res_company c
             WHERE p.company_id = c.id
               AND c.{company_col} IS NOT NULL
            """
        )
        # 2. shared partner and a single company with the account configured
        cr.execute(f"SELECT array_agg(DISTINCT {company_col}) FROM res_company WHERE {company_col} IS NOT NULL")
        accounts = cr.fetchone()[0] or []
        if len(accounts) == 1:
            cr.execute(
                f"UPDATE res_partner SET {partner_col} = %s WHERE company_id IS NULL AND {partner_col} IS NULL",
                [accounts[0]],
            )
        elif util.column_exists(cr, "account_payment", "is_advance_payment"):
            # 3. shared partner: the company where it had advance payments in v17, if only one
            cr.execute(
                f"""
                WITH usage AS (
                    SELECT pay.partner_id, min(m.company_id) AS company_id
                      FROM account_payment pay
                      JOIN account_move m ON m.id = pay.move_id
                     WHERE pay.is_advance_payment IS TRUE
                       AND pay.partner_type = %s
                  GROUP BY pay.partner_id
                    HAVING count(DISTINCT m.company_id) = 1
                )
                UPDATE res_partner p
                   SET {partner_col} = c.{company_col}
                  FROM usage u
                  JOIN res_company c ON c.id = u.company_id
                 WHERE p.id = u.partner_id
                   AND p.company_id IS NULL
                   AND p.{partner_col} IS NULL
                   AND c.{company_col} IS NOT NULL
                """,
                [partner_type],
            )
        if len(accounts) > 1 and util.column_exists(cr, "account_payment", "is_advance_payment"):
            cr.execute(
                f"""
                SELECT count(*) FROM res_partner p
                 WHERE p.company_id IS NULL AND p.{partner_col} IS NULL
                   AND EXISTS (SELECT 1 FROM account_payment pay
                                WHERE pay.partner_id = p.id AND pay.is_advance_payment IS TRUE
                                  AND pay.partner_type = %s)
                """,
                [partner_type],
            )
            (pending,) = cr.fetchone()
            if pending:
                unresolved.append(f"{pending} shared partners ({partner_type})")

    if unresolved:
        util.add_to_migration_reports(
            "Advance payments: v19 takes the advance account from the partner, not from the company. "
            f"Left without an account, because they had advance payments in more than one company: "
            f"{', '.join(unresolved)}. Without an account their advance payments do not apply IGTF. "
            "Set it on the partner form.",
            category="Binaural · Accounting",
        )
