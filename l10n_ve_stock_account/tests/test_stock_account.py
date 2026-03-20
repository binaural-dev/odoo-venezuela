# -*- coding: utf-8 -*-
import logging
from odoo.tests import TransactionCase, tagged
from odoo import Command
from odoo.fields import Datetime
from datetime import timedelta

_logger = logging.getLogger(__name__)

@tagged('post_install', '-at_install')
class TestStockMoveDispatchGuideVES(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # --- 1. Configuración de Monedas ---
        cls.currency_usd = cls.env.ref('base.USD')
        cls.currency_usd.active = True
        
        cls.currency_vef = cls.env.ref('base.VEF')
        cls.currency_vef.active = True

        # --- 2. Compañía ---
        cls.company = cls.env.company
        cls.company.write({
            'currency_id': cls.currency_vef.id,
            'foreign_currency_id': cls.currency_usd.id,
            'indexed_dispatch_guide': False,
        })
        cls.env.company.currency_id = cls.currency_vef

        # --- 3. Fechas ---
        cls.dt_now = Datetime.now()
        cls.date_done = cls.dt_now.date() 
        cls.dt_past = cls.dt_now - timedelta(days=10)
        cls.date_order = cls.dt_past.date() 

        if cls.currency_usd.rate_ids:
            cls.currency_usd.rate_ids.unlink()

        # --- CREACIÓN DE RATES ---
        cls.env['res.currency.rate'].create({
            'name': cls.date_order, 
            'rate': 1 / 50.0,
            'currency_id': cls.currency_usd.id,
            'company_id': cls.company.id,
        })
        
        cls.env['res.currency.rate'].create({
            'name': cls.date_done, 
            'rate': 1 / 60.0,
            'currency_id': cls.currency_usd.id,
            'company_id': cls.company.id,
        })

        # --- 4. Datos Maestros ---
        cls.partner = cls.env['res.partner'].create({'name': 'Cliente Test'})
        cls.product = cls.env['product.product'].create({
            'name': 'Producto Test', 
            'type': 'consu', 
            'lst_price': 100.0,
            'taxes_id': [Command.clear()],           
            'supplier_taxes_id': [Command.clear()], 
        })

        cls.pricelist_usd = cls.env['product.pricelist'].create({
            'name': 'Tarifa USD',
            'currency_id': cls.currency_usd.id,
            'company_id': cls.company.id,
        })
        
        cls.pricelist_ves = cls.env['product.pricelist'].create({
            'name': 'Tarifa VES',
            'currency_id': cls.currency_vef.id,
            'company_id': cls.company.id,
        })

        # =========================================================
        # ESCENARIO A: Venta en USD (Usando la Pricelist)
        # =========================================================
        cls.so_usd = cls.env['sale.order'].create({
            'name': 'SO-USD',
            'partner_id': cls.partner.id,
            'pricelist_id': cls.pricelist_usd.id,
            'date_order': cls.dt_past, 
            'order_line': [Command.create({
                'product_id': cls.product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
                'tax_ids': [Command.clear()], 
            })]
        })
        
        cls.so_usd.action_confirm()
        cls.so_usd.write({'date_order': cls.dt_past}) 
        
        cls.move_usd = cls.so_usd.picking_ids.move_ids[0]
        cls.so_usd.picking_ids.write({'date_done': cls.dt_now})

        # =========================================================
        # ESCENARIO B: Venta en VES
        # =========================================================
        cls.so_ves = cls.env['sale.order'].create({
            'name': 'SO-VES',
            'partner_id': cls.partner.id,
            'currency_id': cls.currency_vef.id,
            'pricelist_id': cls.pricelist_ves.id,
            'date_order': cls.dt_past,
            'order_line': [Command.create({
                'product_id': cls.product.id,
                'product_uom_qty': 1,
                'price_unit': 500.0,
                'tax_ids': [Command.clear()], 
            })]
        })
        cls.so_ves.action_confirm()
        cls.so_ves.write({'date_order': cls.dt_past})
        
        cls.move_ves = cls.so_ves.picking_ids.move_ids[0]
        cls.so_ves.picking_ids.write({'date_done': cls.dt_now})

    def test_01_same_currency_vef(self):
        """ Escenario B: Si la venta es en VES, retorna 500 """
        price = self.move_ves.price_unit_ves_for_dispatch_guide()
        self.assertEqual(price, 500.0)

    def test_02_conversion_date_order_false(self):
        """ 
        Escenario A: USD, Config False -> Tasa Orden (Pasado: 50.0)
        Debe tomar cls.dt_past -> rate 50.0
        """
        self.company.write({'indexed_dispatch_guide': False})
        
        # Verificación visual en log si falla
        _logger.info(f"Test 02 Dates -> SO Date: {self.so_usd.date_order} | Picking Date: {self.so_usd.picking_ids.date_done}")
        
        price = self.move_usd.price_unit_ves_for_dispatch_guide()
        
        # 100 * 50 = 5000
        self.assertAlmostEqual(price, 5000.0, delta=1.0, 
            msg=f"Falló conversión por Fecha Orden. SO Date es {self.so_usd.date_order}")

    def test_03_conversion_date_done_true(self):
        """ 
        Escenario A: USD, Config True -> Tasa Picking (Ahora: 60.0)
        Debe tomar cls.dt_now -> rate 60.0
        """
        self.company.write({'indexed_dispatch_guide': True})
        
        price = self.move_usd.price_unit_ves_for_dispatch_guide()
        
        # 100 * 60 = 6000
        self.assertAlmostEqual(price, 6000.0, delta=1.0, 
            msg="Falló conversión por Fecha Picking")