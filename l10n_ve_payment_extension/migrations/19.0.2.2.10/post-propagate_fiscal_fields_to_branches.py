"""Propagate the fiscal fields of each root company partner to its branches.

What: copies type_person_id, withholding_type_id and taxpayer_type from the partner of every
    root company to the partners of all its branches, overwriting whatever they had. A field
    that is empty on the root is not copied: the value of the branches is left untouched.

Why: customer ISLR retentions of a branch did not compute because the branch partner had those
    fields empty. They are now inherited from the root company and locked on branches.

If it does not run: existing branches keep their old values and the constraint on branch
    partners fails the next time one of those fields is written on them.

How to revert: there is no automatic revert. The previous value of every overwritten field is
    kept in a note on the chatter of the branch contact, in the warnings logged by the migration
    and in the tracking of the contact, so it can be restored by hand.

A warning is logged for every branch value that differs from the root and is overwritten, and
for every branch that keeps a value because the root has that field empty. In that last case
the branch keeps the value configured by hand, so it is not lost: a field empty on the root is
neither copied, nor compared by the constraint on branch partners, nor overwritten later by the
propagation of other fields. Configure the root company contact to unify it.

Task: ticket 16438
"""

import logging

from markupsafe import Markup

from odoo import SUPERUSER_ID, api
from odoo.tools import html_escape

_logger = logging.getLogger(__name__)


def _display(value):
    return getattr(value, "display_name", value) or ""


def _overwritten_note(partner, root, overwritten):
    lines = "".join(
        "<li>%s: %s &rarr; %s</li>"
        % (
            html_escape(partner._fields[fname]._description_string(partner.env)),
            html_escape(str(_display(old))),
            html_escape(str(_display(new))),
        )
        for fname, old, new in overwritten
    )
    return Markup(
        "<p>Migration 19.0.2.2.10 (ticket 16438) overwrote these fiscal fields with the values "
        "of the root company %s (previous value &rarr; new value):</p><ul>%s</ul>"
    ) % (root.name, Markup(lines))


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Company = env["res.company"].with_context(active_test=False)
    for root in Company.search([("parent_id", "!=", False)]).root_id:
        partner = root.partner_id
        synced = partner._l10n_ve_branch_synced_fields()
        with_value = [fname for fname in synced if partner[fname]]
        branches = Company.search([("id", "child_of", root.id), ("id", "!=", root.id)])
        for branch in branches:
            overwritten = []
            for fname in synced:
                value = branch.partner_id[fname]
                if not value:
                    continue
                if fname not in with_value:
                    _logger.warning(
                        "Branch %s: %s '%s' is kept because root %s has it empty. Configure the "
                        "root company contact to unify it.",
                        branch.name,
                        fname,
                        getattr(value, "display_name", value),
                        root.name,
                    )
                elif value != partner[fname]:
                    overwritten.append((fname, value, partner[fname]))
                    _logger.warning(
                        "Branch %s: %s '%s' is overwritten with the value of root %s ('%s').",
                        branch.name,
                        fname,
                        getattr(value, "display_name", value),
                        root.name,
                        getattr(partner[fname], "display_name", partner[fname]),
                    )
            if overwritten:
                branch.partner_id.message_post(
                    body=_overwritten_note(partner, root, overwritten),
                    subtype_xmlid="mail.mt_note",
                )
        partner._l10n_ve_propagate_fiscal_fields_to_branches(
            partner._l10n_ve_root_fiscal_values(), branches=branches
        )
