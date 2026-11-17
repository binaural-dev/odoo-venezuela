from . import models
from . import wizard
from .models.res_company import INTERNAL_TRANSFER_REASON_CODES

old_module = "binaural_stock_accountant"
new_module = "l10n_ve_stock_account"
other_module = "l10n_ve_inventory_book"

def pre_init_hook(env):
    reassign_xml_ir_cron_ids(env.cr)
    reassign_xml_seq_guide_ids(env.cr)
    reassign_xml_transfer_reason_ids(env.cr)

def post_init_hook(env):
    fill_historical_transfer_reasons(env)


def fill_historical_transfer_reasons(env):
    """Give the pickings that existed before the install the reason a new one would get.

    When the module is installed on a database with pickings, _compute_allowed_reason_ids runs
    on all of them before data/transfer_reason.xml is loaded: there is no reason to pick, so
    they are left without one and with no allowed reasons. Here the reasons already exist.

    Everything _compute_allowed_reason_ids would assign is written by SQL, so that tens of
    thousands of historical pickings neither get a tracking message each nor go through the
    write() overrides of the stock modules: consignment (and is_consignment_readonly) for internal
    pickings into a consignation warehouse, the company default (or transfer between warehouses)
    for the other internal ones, sale for outgoing pickings with a sale order and self consumption
    for the ones without. Then allowed_reason_ids is recomputed on every picking, which finds
    nothing left to write, and the stored fields that follow the reason (is_consignment,
    is_dispatch_guide, is_transfer_between_warehouses) on the pickings that got one.
    partner_required is left alone on purpose: its compute assigns partners.
    """
    cr = env.cr
    env.flush_all()

    def ref_id(name):
        record = env.ref(f"l10n_ve_stock_account.{name}", raise_if_not_found=False)
        return record.id if record else None

    consignment = ref_id("transfer_reason_consignment")
    between_warehouses = ref_id("transfer_reason_transfer_between_warehouses")
    sale = ref_id("transfer_reason_sale")
    self_consumption = ref_id("transfer_reason_self_consumption")
    touched = set()

    if consignment:
        cr.execute(
            """
            UPDATE stock_picking p
               SET transfer_reason_id = %s, is_consignment_readonly = true
              FROM stock_picking_type t, stock_location l, stock_warehouse w
             WHERE t.id = p.picking_type_id AND t.code = 'internal'
               AND p.transfer_reason_id IS NULL
               AND l.id = p.location_dest_id AND w.id = l.warehouse_id
               AND w.is_consignation_warehouse IS TRUE
         RETURNING p.id
            """,
            [consignment],
        )
        touched.update(row[0] for row in cr.fetchall())
    if between_warehouses:
        cr.execute(
            """
            UPDATE stock_picking p
               SET transfer_reason_id = COALESCE(company_reason.id, %s)
              FROM stock_picking_type t, res_company c
              LEFT JOIN transfer_reason company_reason
                     ON company_reason.id = c.internal_transfer_reason_id
                    AND company_reason.code IN %s
             WHERE t.id = p.picking_type_id AND t.code = 'internal'
               AND c.id = COALESCE(p.company_id, t.company_id)
               AND p.transfer_reason_id IS NULL
         RETURNING p.id
            """,
            [between_warehouses, INTERNAL_TRANSFER_REASON_CODES],
        )
        touched.update(row[0] for row in cr.fetchall())
    for reason, with_sale in ((sale, True), (self_consumption, False)):
        if not reason:
            continue
        cr.execute(
            """
            UPDATE stock_picking p
               SET transfer_reason_id = %%s
              FROM stock_picking_type t
             WHERE t.id = p.picking_type_id AND t.code = 'outgoing'
               AND p.sale_id IS %s NULL
               AND p.transfer_reason_id IS NULL
         RETURNING p.id
            """ % ("NOT" if with_sale else ""),
            [reason],
        )
        touched.update(row[0] for row in cr.fetchall())

    Picking = env["stock.picking"].with_context(tracking_disable=True)
    pickings = Picking.search([])
    pickings.invalidate_recordset(["transfer_reason_id", "is_consignment_readonly"])
    env.add_to_compute(Picking._fields["allowed_reason_ids"], pickings)
    if touched:
        touched_pickings = Picking.browse(sorted(touched))
        for name in ("is_consignment", "is_dispatch_guide", "is_transfer_between_warehouses"):
            env.add_to_compute(Picking._fields[name], touched_pickings)
    env.flush_all()


def reassign_xml_ir_cron_ids(env):
    execute_script_sql_two(env, "ir_cron_auto_invoice_stock")

def reassign_xml_seq_guide_ids(env):
    execute_script_sql_two(env, "seq_guide_number")    
    
def reassign_xml_transfer_reason_ids(env):
    execute_script_sql_other(env, "transfer_reason_")
    
def execute_script_sql(env, xml_id_prefix):    
    env.execute(
        """
        UPDATE ir_model_data
        SET module=%s
        WHERE module=%s AND name LIKE %s
        """,
        (new_module, old_module, f"{xml_id_prefix}%"),
    ) 

def execute_script_sql_two(env, xml_id_prefix):    
    env.execute(
        """
        UPDATE ir_model_data
        SET module=%s
        WHERE module=%s AND name=%s
        """,
        (new_module, old_module, xml_id_prefix),
    ) 
    
def execute_script_sql_other(env, xml_id_prefix):    
    env.execute(
        """
        UPDATE ir_model_data
        SET module=%s
        WHERE module=%s AND name LIKE %s
        """,
        (new_module, other_module, f"{xml_id_prefix}%"),
    ) 