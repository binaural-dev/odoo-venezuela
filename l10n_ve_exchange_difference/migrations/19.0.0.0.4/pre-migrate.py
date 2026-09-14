"""Convierte res_partner.l10n_ve_exchange_allow_note de boolean a jsonb.

El campo siempre fue fields.Boolean en el codigo -- lo que cambio en el
commit 648fe821f (PR odoo-venezuela#1283) fue agregarle
company_dependent=True. Un campo company_dependent se guarda en Postgres
como una unica columna jsonb (mapa {company_id: valor}), sin importar su
tipo logico, y el ORM intenta migrar la columna existente con
`ALTER COLUMN ... TYPE jsonb USING columna::jsonb` -- ese cast puntual
(boolean -> jsonb) no existe en Postgres y revienta con
`psycopg2.errors.CannotCoerce`.

Politica de migracion: antes de este cambio el campo era un unico valor
global por partner (no dependia de la compañia activa). Para no alterar
el comportamiento observado en ninguna compañia existente, el valor viejo
se replica bajo la clave de TODAS las compañias actuales -- equivalente a
"lo que ya se veia, se sigue viendo igual", sea cual sea la compañia
desde la que se consulte el campo despues de la migracion.
"""

from odoo.tools.sql import column_exists, table_exists


def migrate(cr, version):
    if not table_exists(cr, "res_partner"):
        return
    if not column_exists(cr, "res_partner", "l10n_ve_exchange_allow_note"):
        return

    cr.execute(
        """
        SELECT data_type
        FROM information_schema.columns
        WHERE table_name = 'res_partner'
          AND column_name = 'l10n_ve_exchange_allow_note'
        """
    )
    row = cr.fetchone()
    if not row or row[0] == "jsonb":
        # Ya esta en el formato nuevo (instalacion limpia, o corrida
        # anterior de este mismo script) -- nada que hacer.
        return

    cr.execute(
        """
        ALTER TABLE res_partner
        RENAME COLUMN l10n_ve_exchange_allow_note
        TO l10n_ve_exchange_allow_note_old_bool
        """
    )
    cr.execute(
        """
        ALTER TABLE res_partner
        ADD COLUMN l10n_ve_exchange_allow_note jsonb
        """
    )
    cr.execute(
        """
        UPDATE res_partner p
        SET l10n_ve_exchange_allow_note = (
            SELECT jsonb_object_agg(
                c.id::text,
                to_jsonb(p.l10n_ve_exchange_allow_note_old_bool)
            )
            FROM res_company c
        )
        WHERE p.l10n_ve_exchange_allow_note_old_bool IS NOT NULL
        """
    )
    cr.execute(
        """
        ALTER TABLE res_partner
        DROP COLUMN l10n_ve_exchange_allow_note_old_bool
        """
    )
