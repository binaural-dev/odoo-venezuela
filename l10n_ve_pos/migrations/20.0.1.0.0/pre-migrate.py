"""Plan the merge of the cash payment methods of a register (ADR-023).

Odoo 19 kept one payment method per currency ("Efectivo Bs.", "Efectivo $",
"Efectivo EUR"), each flagged ``is_foreign_currency`` with its own
``cross_journal`` / ``cross_account_journal``. Odoo 20 admits a single cash
method per register that takes every currency (``currency_ids``), so the
settings by currency live in ``pos.payment.method.currency`` and the payments
of the old methods move to the surviving one.

This step runs before the module is loaded, while the Odoo 19 columns are
still there, and only writes the plan to ``l10n_ve_pos_method_merge``: what
moves where and with which currency, plus the ``apply_igtf`` flag the old
method had (``l10n_ve_pos_igtf`` reads that table, to put the flag on the
currency settings, and drops it). ``post-migrate.py`` applies it.
"""


def _columns(cr, table):
    cr.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
        (table,),
    )
    return {row[0] for row in cr.fetchall()}


def migrate(cr, version):
    if not version:
        return
    columns = _columns(cr, "pos_payment_method")
    if "is_foreign_currency" not in columns:
        return
    igtf = "m.apply_igtf" if "apply_igtf" in columns else "FALSE"
    cr.execute(
        """
        CREATE TABLE IF NOT EXISTS l10n_ve_pos_method_merge (
            id SERIAL PRIMARY KEY,
            config_id INTEGER,
            keeper_id INTEGER NOT NULL,
            old_id INTEGER NOT NULL,
            currency_id INTEGER,
            cross_journal INTEGER,
            cross_account_journal INTEGER,
            apply_igtf BOOLEAN DEFAULT FALSE,
            done BOOLEAN DEFAULT FALSE
        )
        """
    )
    cr.execute("DELETE FROM l10n_ve_pos_method_merge WHERE NOT done")
    cr.execute(
        f"""
        SELECT rel.pos_config_id,
               m.id,
               m.sequence,
               j.type,
               COALESCE(m.is_foreign_currency, FALSE),
               m.cross_journal,
               m.cross_account_journal,
               COALESCE({igtf}, FALSE),
               COALESCE(cj.currency_id, comp.foreign_currency_id),
               COALESCE(m.company_id, cfg.company_id)
          FROM pos_payment_method m
          JOIN pos_config_pos_payment_method_rel rel
            ON rel.pos_payment_method_id = m.id
          JOIN pos_config cfg ON cfg.id = rel.pos_config_id
          JOIN res_company comp ON comp.id = COALESCE(m.company_id, cfg.company_id)
          LEFT JOIN account_journal j ON j.id = m.journal_id
          LEFT JOIN account_journal cj ON cj.id = m.cross_journal
         ORDER BY rel.pos_config_id, m.sequence, m.id
        """
    )
    by_config = {}
    for row in cr.fetchall():
        by_config.setdefault(row[0], []).append(row)
    rows = []
    for config_id, methods in by_config.items():
        cash = [m for m in methods if m[3] == "cash"]
        keeper = None
        if cash:
            keeper = next((m for m in cash if not m[4]), cash[0])
        for method in methods:
            (_cfg, method_id, _seq, jtype, is_foreign, cross, cross_account,
             apply_igtf, currency, _company) = method
            if jtype == "cash":
                if method_id == keeper[1] and not is_foreign:
                    continue
                rows.append((
                    config_id, keeper[1], method_id,
                    currency if is_foreign else None,
                    cross, cross_account, apply_igtf,
                ))
            elif is_foreign and jtype == "bank":
                rows.append((
                    config_id, method_id, method_id,
                    currency, cross, cross_account, apply_igtf,
                ))
    if rows:
        cr.executemany(
            """
            INSERT INTO l10n_ve_pos_method_merge
                (config_id, keeper_id, old_id, currency_id, cross_journal,
                 cross_account_journal, apply_igtf)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            rows,
        )
