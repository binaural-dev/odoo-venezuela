from lxml import etree
from psycopg2.extras import Json

_XMLID_MODULE = "l10n_ve_stock_account"
_XMLID_NAME = "l10n_ve_stock_inherit_l10n_ve_stock_account"
_STALE_DIV_ID = "l10n_ve_settings_hide_disc_field_dispatch_guide"


def _strip_stale_div(arch):
    if not arch or _STALE_DIV_ID not in arch:
        return arch
    root = etree.fromstring(arch)
    for node in root.xpath(f'.//div[@id="{_STALE_DIV_ID}"]'):
        node.getparent().remove(node)
    return etree.tostring(root, encoding="unicode")


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
