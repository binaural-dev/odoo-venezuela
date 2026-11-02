from . import models

import logging

_logger = logging.getLogger(__name__)

old_module = "binaural_filter_partner"
new_module = "l10n_ve_filter_partner"


def pre_init_hook(env):
    """Reassign ir.model.data entries from binaural_filter_partner to l10n_ve_filter_partner.

    Accepts either an Environment-like object (with .cr) or a bare cursor.
    Updates ir_model_data.module to preserve existing bindings under the new module.

    Runs on a fresh install of this module (see odoo/modules/loading.py: pre_init_hook only
    fires for update_operation == 'install'). Raises on failure instead of logging and
    continuing: a silent failure here leaves a base "installed" with orphaned XMLIDs bound to
    a module that no longer exists, and nothing would ever flag that state again.
    """
    cr = getattr(env, "cr", env)
    _logger.info(
        "Running pre_init_hook for l10n_ve_filter_partner: reassigning data from %s to %s",
        old_module,
        new_module,
    )
    reassign_filter_partner_data_ids(cr)


def reassign_filter_partner_data_ids(cr):
    cr.execute("SELECT count(*) FROM ir_model_data WHERE module = %s", (old_module,))
    (before_cnt,) = cr.fetchone()
    if not before_cnt:
        _logger.info("No ir_model_data rows found under module '%s', nothing to reassign", old_module)
        return

    cr.execute(
        """
        UPDATE ir_model_data
        SET module=%s
        WHERE module=%s
        """,
        (new_module, old_module),
    )

    cr.execute("SELECT count(*) FROM ir_model_data WHERE module = %s", (old_module,))
    (remaining_cnt,) = cr.fetchone()
    if remaining_cnt:
        raise RuntimeError(
            "Failed to reassign ir_model_data.module from '%s' to '%s': %s row(s) still remain "
            "under '%s' after the UPDATE" % (old_module, new_module, remaining_cnt, old_module)
        )

    _logger.info(
        "Reassigned %s ir_model_data row(s) from module '%s' to '%s'",
        before_cnt,
        old_module,
        new_module,
    )
