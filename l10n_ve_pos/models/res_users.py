from odoo import models, api


class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model
    def _load_pos_data_read(self, records, config):
        """Odoo 19 loader contract: the core loader only sends ``all_group_ids``
        to compute ``_role`` and then deletes it (see point_of_sale's
        ``res_users.py``), so ``groups_id`` never reaches the frontend. Expose
        the two custom Venezuelan permissions as booleans computed here,
        following the same pattern as ``_role``.

        Keys MUST start with a single underscore: the PoS frontend's
        ``related_models`` layer only keeps dict keys that are either a
        declared ORM field (``_load_pos_data_fields``) or match
        ``key[0] === "_" && key[1] !== "_"`` (its "extraFields" escape
        hatch, used by core for ``_role``) — see
        ``_sanitizeRawData``/``createExtraField`` in
        point_of_sale's ``related_models/index.js``. A plain key like
        ``can_change_qty_on_pos_order`` is silently dropped client-side.
        """
        read_records = super()._load_pos_data_read(records, config)
        if read_records:
            user = records[0]
            read_records[0]['_can_change_qty_on_pos_order'] = user.has_group(
                'l10n_ve_pos.group_change_qty_on_pos_order'
            )
            read_records[0]['_can_change_price_on_pos_order'] = user.has_group(
                'l10n_ve_pos.group_change_price_on_pos_order'
            )
        return read_records
