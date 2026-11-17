"""Propagate the fiscal fields of each root company partner to its branches.

What: copies type_person_id, withholding_type_id and taxpayer_type from the partner of every
    root company to the partners of all its branches, overwriting whatever they had.

Why: customer ISLR retentions of a branch did not compute because the branch partner had those
    fields empty. They are now inherited from the root company and locked on branches.

If it does not run: existing branches keep their old values and the constraint on branch
    partners fails the next time one of those fields is written on them.

How to revert: not possible, the previous values of the branches are only kept in the warnings
    logged by the migration (and in the tracking of each contact).

A warning is logged for every branch value that differs from the root and is overwritten.

Task: ticket 16438
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Company = env["res.company"].with_context(active_test=False)
    for root in Company.search([("parent_id", "!=", False)]).root_id:
        partner = root.partner_id
        branches = Company.search([("id", "child_of", root.id), ("id", "!=", root.id)])
        for branch in branches:
            for fname in partner._l10n_ve_branch_synced_fields():
                value = branch.partner_id[fname]
                if value and value != partner[fname]:
                    _logger.warning(
                        "Branch %s: %s '%s' is overwritten with the value of root %s ('%s').",
                        branch.name,
                        fname,
                        getattr(value, "display_name", value),
                        root.name,
                        getattr(partner[fname], "display_name", partner[fname]) or "",
                    )
        partner._l10n_ve_propagate_fiscal_fields_to_branches()
