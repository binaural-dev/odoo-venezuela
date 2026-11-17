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

    The reasons are written by SQL, the same ones the compute gives a new picking: consignment
    for internal pickings into a consignation warehouse, the company default (or transfer
    between warehouses) for the other internal ones, and sale for outgoing pickings with a sale
    order. By SQL so that tens of thousands of historical pickings do not get a tracking message
    each, nor go through the write() overrides of the stock modules. Then allowed_reason_ids is
    recomputed, without tracking: that compute gives the outgoing pickings without a sale order
    their first allowed reason (self consumption), as it does on a new one.
    """
    cr = env.cr

    def ref_id(name):
        record = env.ref(f"l10n_ve_stock_account.{name}", raise_if_not_found=False)
        return record.id if record else None

    consignment = ref_id("transfer_reason_consignment")
    between_warehouses = ref_id("transfer_reason_transfer_between_warehouses")
    sale = ref_id("transfer_reason_sale")

    if consignment:
        cr.execute(
            """
            UPDATE stock_picking p
               SET transfer_reason_id = %s
              FROM stock_picking_type t, stock_location l, stock_warehouse w
             WHERE t.id = p.picking_type_id AND t.code = 'internal'
               AND p.transfer_reason_id IS NULL
               AND l.id = p.location_dest_id AND w.id = l.warehouse_id
               AND w.is_consignation_warehouse IS TRUE
            """,
            [consignment],
        )
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
            """,
            [between_warehouses, INTERNAL_TRANSFER_REASON_CODES],
        )
    if sale:
        cr.execute(
            """
            UPDATE stock_picking p
               SET transfer_reason_id = %s
              FROM stock_picking_type t
             WHERE t.id = p.picking_type_id AND t.code = 'outgoing'
               AND p.sale_id IS NOT NULL
               AND p.transfer_reason_id IS NULL
            """,
            [sale],
        )

    pickings = env["stock.picking"].with_context(tracking_disable=True).search([])
    pickings.invalidate_recordset(["transfer_reason_id"])
    env.add_to_compute(pickings._fields["allowed_reason_ids"], pickings)
    pickings.flush_recordset()


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