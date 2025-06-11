from odoo import api, fields, models

import logging

_logger = logging.getLogger(__name__)

class ResCompany(models.Model):
    _inherit = "res.company"

    subsidiary = fields.Boolean(
        string="Subsidiary",
        readonly=False,
    )

    analytical_accounts_subsidiary = fields.Boolean(
        string="Use Analytical Accounts as Subsidiary",
        readonly=False,
    )

    analytical_accounts_cost_subsidiary = fields.Boolean(
        string="Using Analytical Accounts as Cost Center and Subsidiary",
        readonly=False,
    )
    
    def _set_subsidiary_in_records(self):
        if not self.subsidiary:
            return
        env = self.env

        # Iterar por cada compañía activa
        company_id = self.id  # Extraemos el id de la tupla

        # Obtener una sucursal para la compañía actual
        env.cr.execute("""
            SELECT id FROM account_analytic_account 
            WHERE is_subsidiary = True 
            AND active = True 
            AND company_id = %s
            LIMIT 1
        """, (company_id,))
        
        subsidiary = env.cr.fetchone()
        
        # Si no existe una sucursal para la compañía, saltamos esta iteración
        if not subsidiary:
            return

        subsidiary_id = subsidiary[0]  # Extraemos el id de la sucursal

        # Queries de actualización
        queries = self._get_queries_to_set_subsidiary()

        # Ejecutar todas las queries para la compañía y la sucursal correspondientes
        
        for query in queries:
            _logger.warning("____________________________________________")
            _logger.warning(query)
            # Para las otras tablas con solo 2 parámetros (subsidiary_id y company_id)
            env.cr.execute(query, (subsidiary_id, company_id))

        # Actualizar usuarios que no tengan sucursales asignadas, filtrando por compañía
        res_users_ids = env["res.users"].search([("subsidiary_ids", "=", False), ("company_id", "=", company_id)]).ids

        select_query = """
            SELECT 1 FROM account_analytic_account_res_users_rel 
            WHERE res_users_id = %s AND account_analytic_account_id = %s;
        """
        insert_query = """
            INSERT INTO account_analytic_account_res_users_rel (res_users_id, account_analytic_account_id)
            VALUES (%s, %s);
        """

        # Verificar si el usuario ya tiene una sucursal asignada, de no tenerla, asignar la correspondiente
        for user_id in res_users_ids:
            env.cr.execute(select_query, (user_id, subsidiary_id))
            if not env.cr.fetchone():
                env.cr.execute(insert_query, (user_id, subsidiary_id))

    def _get_queries_to_set_subsidiary(self):
        queries = [
            "UPDATE sale_order SET subsidiary_id = %s WHERE subsidiary_id IS NULL AND company_id = %s",
            "UPDATE purchase_order SET account_analytic_id = %s WHERE account_analytic_id IS NULL AND company_id = %s",
            "UPDATE res_users SET subsidiary_id = %s WHERE subsidiary_id IS NULL AND company_id = %s",
            "UPDATE account_move SET account_analytic_id = %s WHERE account_analytic_id IS NULL AND company_id = %s",
            """
            UPDATE account_payment 
            SET account_analytic_id = %s 
            WHERE account_analytic_id IS NULL 
            AND move_id IN (
                SELECT id FROM account_move WHERE company_id = %s
            );
            """,
        ]
        return queries 