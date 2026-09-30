"""Da a cada contacto las cuentas de anticipo que usaba su compañía en 17.

Qué: crea res_partner.default_advance_customer_account_id y default_advance_supplier_account_id
    antes que el ORM y las llena desde res_company.advance_customer_account_id /
    advance_supplier_account_id:

    1. Contacto con compañía: las de su compañía.
    2. Contacto compartido (sin compañía): las de la única compañía que las tenga configuradas.
    3. Si hay varias, las de la compañía donde tuvo anticipos en 17, siempre que sea una sola.
    El resto queda vacío y se lista en el reporte de migración.

Por qué: en 17 un anticipo tomaba siempre la cuenta de la compañía. En 19 la toma del contacto
    (account_payment._compute_destination_account_id), y con el contacto sin cuenta
    res.partner._check_igtf_apply_improved devuelve False: el anticipo no aplica IGTF ni va a la
    cuenta de anticipo. Los dos campos son nuevos en 19, con default=env.company.<cuenta>. Al crear
    la columna, el ORM calcula ese default una sola vez, con la compañía principal, y se lo pone a
    todos los contactos. En 19_proalca_run15 la compañía principal no tiene cuentas de anticipo, y
    los 3.360 contactos quedaron vacíos, también los de las compañías 2, 3 y 4, que sí las tienen.
    En un cliente cuya compañía principal sí las tenga, todos los contactos quedarían con las
    cuentas de esa compañía, aunque sean de otra.

    El campo no es company_dependent: un contacto compartido que se use en dos compañías con
    anticipos sólo puede tener una cuenta. Eso es del diseño de 19, no de la migración, y esos
    casos van al reporte.

Qué pasa si no corre: los anticipos de los clientes migrados dejan de aplicar IGTF y de ir a la
    cuenta de anticipo, o van a la cuenta de otra compañía.

Cómo revertirlo: vaciar los dos campos en los contactos. Las cuentas de la compañía no se tocan.

Tarea: https://binaural.odoo.com/odoo/action-1963/4199/action-345/82849
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

        # 1. contacto con compañía
        cr.execute(
            f"""
            UPDATE res_partner p
               SET {partner_col} = c.{company_col}
              FROM res_company c
             WHERE p.company_id = c.id
               AND c.{company_col} IS NOT NULL
            """
        )
        # 2. contacto compartido y una sola compañía con la cuenta configurada
        cr.execute(f"SELECT array_agg(DISTINCT {company_col}) FROM res_company WHERE {company_col} IS NOT NULL")
        accounts = cr.fetchone()[0] or []
        if len(accounts) == 1:
            cr.execute(
                f"UPDATE res_partner SET {partner_col} = %s WHERE company_id IS NULL AND {partner_col} IS NULL",
                [accounts[0]],
            )
        elif util.column_exists(cr, "account_payment", "is_advance_payment"):
            # 3. contacto compartido: la compañía donde tuvo anticipos en 17, si es una sola
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
                unresolved.append(f"{pending} contactos compartidos ({partner_type})")

    if unresolved:
        util.add_to_migration_reports(
            "Anticipos: 19 toma la cuenta de anticipo del contacto y no de la compañía. Quedaron sin "
            f"cuenta, por tener anticipos en más de una compañía: {', '.join(unresolved)}. Sin cuenta, "
            "sus anticipos no aplican IGTF. Asignarla en la ficha del contacto.",
            category="Binaural · Contabilidad",
        )
