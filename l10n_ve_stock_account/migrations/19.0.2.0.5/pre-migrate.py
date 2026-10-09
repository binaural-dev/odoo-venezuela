import logging

from lxml import etree
from psycopg2.extras import Json

_logger = logging.getLogger(__name__)

_XMLID_MODULE = "l10n_ve_stock_account"
_XMLID_NAME = "l10n_ve_stock_inherit_l10n_ve_stock_account"
_STALE_DIV_ID = "l10n_ve_settings_hide_disc_field_dispatch_guide"

# View that v17 shipped and v19 no longer declares. Its only content is an xpath
# on //div[@id='l10n_ve_stock_block_limit_product_qty_out'], a div that
# l10n_ve_stock declared in 17 and that does not exist in 19 either. Since it stays
# in the database without any data file rewriting it, it breaks the validation of
# the res.config.settings tree as soon as any sibling view is loaded:
#
#   ParseError: Element '<xpath expr="//div[@id='l10n_ve_stock_block_
#   limit_product_qty_out']">' cannot be located in parent view
#
# and that aborts the registry loading, i.e. the whole migration.
_ORPHAN_XMLID_NAME = "res_config_settings_view_form_stock_inherit"


def _strip_stale_div(arch):
    if not arch or _STALE_DIV_ID not in arch:
        return arch
    root = etree.fromstring(arch)
    for node in root.xpath(f'.//div[@id="{_STALE_DIV_ID}"]'):
        node.getparent().remove(node)
    return etree.tostring(root, encoding="unicode")


def _drop_orphan_view(cr):
    """Deletes the view that v19 no longer declares, before anything is validated.

    Odoo cleans up on its own the records whose xmlid disappeared from the module,
    but that pass runs at the END of the whole update; the validation that breaks
    happens much earlier. It has to be removed by hand and in time.

    Through raw SQL and not the ORM, for the same reason the docstring of
    migrate() explains: at this point res.config.settings has not finished
    building its fields yet and any ORM operation on ir.ui.view triggers
    _check_xml() against an incomplete model.
    """
    cr.execute(
        """
        SELECT v.id, d.id
        FROM ir_ui_view v
        JOIN ir_model_data d ON d.model = 'ir.ui.view' AND d.res_id = v.id
        WHERE d.module = %s AND d.name = %s
        """,
        (_XMLID_MODULE, _ORPHAN_XMLID_NAME),
    )
    row = cr.fetchone()
    if not row:
        _logger.info("  %s.%s does not exist, nothing to delete", _XMLID_MODULE, _ORPHAN_XMLID_NAME)
        return
    view_id, data_id = row

    # If someone inherited from it, those children would be left hanging from a
    # nonexistent parent. They are counted and deleted too.
    cr.execute("SELECT id FROM ir_ui_view WHERE inherit_id = %s", (view_id,))
    child_view_ids = [r[0] for r in cr.fetchall()]
    if child_view_ids:
        _logger.warning("  %s.%s had %s inherited view(s) (%s): they are deleted with it",
                        _XMLID_MODULE, _ORPHAN_XMLID_NAME, len(child_view_ids), child_view_ids)
        cr.execute("DELETE FROM ir_model_data WHERE model = 'ir.ui.view' AND res_id = ANY(%s)",
                   (child_view_ids,))
        cr.execute("DELETE FROM ir_ui_view WHERE id = ANY(%s)", (child_view_ids,))

    cr.execute("DELETE FROM ir_model_data WHERE id = %s", (data_id,))
    cr.execute("DELETE FROM ir_ui_view WHERE id = %s", (view_id,))
    _logger.info("  Deleted the orphan view %s.%s (id %s): v19 no longer declares it and its "
                 "anchor does not exist either", _XMLID_MODULE, _ORPHAN_XMLID_NAME, view_id)


def migrate(cr, version):
    """Strip the removed hide_disc_field_dispatch_guide field from the
    still-installed (pre-upgrade) arch_db of this view before the module's
    own data files load.

    Without this, updating past this version can fail: the model is already
    reloaded without the field by the time this view (a sibling in the same
    views/res_config_setting_views.xml) gets its own arch_db rewritten, and
    Odoo revalidates the combined res.config.settings view against the
    not-yet-updated stale arch in between.

    This is done via raw SQL, not env['ir.ui.view'].write(): a pre-migrate
    script for this module runs while res.config.settings hasn't finished
    assembling all of its fields yet, so an ORM write() here triggers
    ir.ui.view._check_xml()/_validate_view() against an incomplete model and
    fails on unrelated, perfectly valid fields (e.g. indexed_dispatch_guide).
    Raw SQL updates arch_db without going through that validation.
    """
    _drop_orphan_view(cr)

    cr.execute(
        """
        SELECT v.id, v.arch_db
        FROM ir_ui_view v
        JOIN ir_model_data d ON d.model = 'ir.ui.view' AND d.res_id = v.id
        WHERE d.module = %s AND d.name = %s
        """,
        (_XMLID_MODULE, _XMLID_NAME),
    )
    row = cr.fetchone()
    if not row:
        return
    view_id, arch_db = row

    if isinstance(arch_db, dict):
        new_arch_db = {lang: _strip_stale_div(arch) for lang, arch in arch_db.items()}
        if new_arch_db == arch_db:
            return
        cr.execute(
            "UPDATE ir_ui_view SET arch_db = %s WHERE id = %s",
            (Json(new_arch_db), view_id),
        )
    else:
        new_arch = _strip_stale_div(arch_db)
        if new_arch == arch_db:
            return
        cr.execute(
            "UPDATE ir_ui_view SET arch_db = %s WHERE id = %s",
            (new_arch, view_id),
        )
