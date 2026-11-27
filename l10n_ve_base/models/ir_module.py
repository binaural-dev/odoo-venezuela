from collections.abc import Iterable

from odoo import api, fields, models

MIGRATED_KEY = "binaural_migrated"


class IrModule(models.Model):
    _inherit = "ir.module.module"

    binaural = fields.Boolean(default=False)
    migration_state = fields.Selection(
        [("migrated", "Migrated"), ("pending", "Pending migration")],
        compute="_compute_migration_state",
        search="_search_migration_state",
        help="Migrated: the manifest of the module says it is migrated to this version of Odoo "
        "(key binaural_migrated). Pending migration: a module that is not from Odoo and cannot be "
        "installed in this version yet.",
    )

    @api.depends("name", "state", "author")
    def _compute_migration_state(self):
        """
        The manifest is read when the screen asks for it, not when the list of modules is updated:
        marking a module as migrated shows on the screen without updating anything.
        """
        for module in self:
            if module._is_from_odoo():
                module.migration_state = False
            elif self.get_module_info(module.name).get(MIGRATED_KEY):
                module.migration_state = "migrated"
            elif module.state == "uninstallable":
                module.migration_state = "pending"
            else:
                module.migration_state = False

    def _is_from_odoo(self):
        """Odoo's own modules (community and enterprise) never carry a tag."""
        self.ensure_one()
        return (self.author or "").startswith("Odoo S")

    def _search_migration_state(self, operator, value):
        """
        Only the modules that are not from Odoo can carry a tag, so only their manifests are read:
        the modules of Odoo, most of the list, are left out by their author first. Odoo keeps the
        manifests in memory (``Manifest._get_manifest_from_addons`` is cached per process), so a
        search does not read them from disk again.
        """
        if operator not in ("in", "not in", "=", "!="):
            return NotImplemented
        values = set(value) if isinstance(value, Iterable) and not isinstance(value, str) else {value}
        modules = self.with_context(active_test=False).search([])
        candidates = modules.filtered(lambda module: not module._is_from_odoo())
        tagged = candidates.filtered("migration_state")
        if any(not state for state in values):
            # Untagged modules are asked for: every module except the tagged ones not asked for.
            ids = tagged.filtered(lambda module: module.migration_state not in values).ids
            inside = False
        else:
            ids = tagged.filtered(lambda module: module.migration_state in values).ids
            inside = True
        if operator in ("not in", "!="):
            inside = not inside
        return [("id", "in" if inside else "not in", ids)]
