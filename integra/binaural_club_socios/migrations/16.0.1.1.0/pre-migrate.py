from odoo import api, Command, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """DROP FUNCTION IF EXISTS get_members_pending_debt(bigint,bigint,date);

            DROP FUNCTION IF EXISTS get_members_pending_debts() CASCADE;
        """
    )
