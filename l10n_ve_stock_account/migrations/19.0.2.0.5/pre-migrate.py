import logging

from lxml import etree
from psycopg2.extras import Json

_logger = logging.getLogger(__name__)

_XMLID_MODULE = "l10n_ve_stock_account"
_XMLID_NAME = "l10n_ve_stock_inherit_l10n_ve_stock_account"
_STALE_DIV_ID = "l10n_ve_settings_hide_disc_field_dispatch_guide"

# Vista que v17 traia y v19 ya no declara. Su unico contenido es un xpath
# sobre //div[@id='l10n_ve_stock_block_limit_product_qty_out'], un div que
# l10n_ve_stock declaraba en 17 y en 19 tampoco existe. Al quedarse en la BD
# sin que ningun archivo de datos la reescriba, revienta la validacion del
# arbol de res.config.settings en cuanto se carga cualquier vista hermana:
#
#   ParseError: El elemento "<xpath expr="//div[@id='l10n_ve_stock_block_
#   limit_product_qty_out']">" no se puede localizar en la vista principal
#
# y eso aborta la carga del registro, o sea la migracion entera.
_ORPHAN_XMLID_NAME = "res_config_settings_view_form_stock_inherit"


def _strip_stale_div(arch):
    if not arch or _STALE_DIV_ID not in arch:
        return arch
    root = etree.fromstring(arch)
    for node in root.xpath(f'.//div[@id="{_STALE_DIV_ID}"]'):
        node.getparent().remove(node)
    return etree.tostring(root, encoding="unicode")


def _drop_orphan_view(cr):
    """Borra la vista que v19 ya no declara, antes de que valide nada.

    Odoo limpia solo los registros cuyo xmlid desaparecio del modulo, pero esa
    pasada corre al FINAL de toda la actualizacion; la validacion que revienta
    ocurre mucho antes. Hay que quitarla a mano y a tiempo.

    Por SQL crudo y no por el ORM, por el mismo motivo que explica el docstring
    de migrate(): en este punto res.config.settings todavia no termino de armar
    sus campos y cualquier operacion del ORM sobre ir.ui.view dispara
    _check_xml() contra un modelo incompleto.
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
        _logger.info("  %s.%s no existe, nada que borrar", _XMLID_MODULE, _ORPHAN_XMLID_NAME)
        return
    view_id, data_id = row

    # Si alguien heredo de ella, esas hijas quedarian colgando de un padre
    # inexistente. Se cuentan y se borran tambien.
    cr.execute("SELECT id FROM ir_ui_view WHERE inherit_id = %s", (view_id,))
    hijas = [r[0] for r in cr.fetchall()]
    if hijas:
        _logger.warning("  %s.%s tenia %s vista(s) heredada(s) (%s): se borran con ella",
                        _XMLID_MODULE, _ORPHAN_XMLID_NAME, len(hijas), hijas)
        cr.execute("DELETE FROM ir_model_data WHERE model = 'ir.ui.view' AND res_id = ANY(%s)",
                   (hijas,))
        cr.execute("DELETE FROM ir_ui_view WHERE id = ANY(%s)", (hijas,))

    cr.execute("DELETE FROM ir_model_data WHERE id = %s", (data_id,))
    cr.execute("DELETE FROM ir_ui_view WHERE id = %s", (view_id,))
    _logger.info("  Borrada la vista huerfana %s.%s (id %s): v19 ya no la declara y su "
                 "ancla tampoco existe", _XMLID_MODULE, _ORPHAN_XMLID_NAME, view_id)


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
