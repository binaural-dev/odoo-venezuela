from odoo.tests import tagged, TransactionCase

@tagged("post_install", "-at_install", "product_concept")
class TestProductPaymentConcept(TransactionCase):

    def setUp(self):
        super().setUp()
      
        # 1. Creamos conceptos de pago de prueba
        self.concept_honorarios = self.env['payment.concept'].create({
            'name': 'Honorarios Profesionales',
            'status': True,
        })
        self.concept_fletes = self.env['payment.concept'].create({
            'name': 'Gastos de Transporte',
            'status': True,
        })

    def test_01_service_product_with_concept(self):
        """ CASO 1: Producto tipo SERVICIO. 
            Debe permitir asignar y mantener el concepto de pago. """
        product_service = self.env['product.template'].create({
            'name': 'Consultoría Legal',
            'type': 'service',
            'payment_concept': self.concept_honorarios.id,
        })
        
        # Forzamos el onchange manualmente (en tests los onchanges no se disparan solos)
        product_service._onchange_payment_concept()
        
        self.assertEqual(product_service.payment_concept.id, self.concept_honorarios.id, 
                         "El concepto de pago debería mantenerse para productos de tipo servicio.")

    def test_02_consu_product_resets_concept(self):
        """ CASO 2: Producto tipo BIENES.
            El onchange debe borrar el concepto de pago si se asigna. """
        product_consu = self.env['product.template'].create({
            'name': 'Resma de Papel',
            'type': 'consu',
            'payment_concept': self.concept_fletes.id,
        })
        
        # Disparamos la lógica del onchange
        product_consu._onchange_payment_concept()
        
        self.assertFalse(product_consu.payment_concept, 
                         "El concepto de pago debe resetearse a False si el producto no es un servicio.")

    def test_03_storable_product_resets_concept(self):
        """ CASO 3: Producto COMBO.
            Similar al consumible, debe limpiar el campo. """
        
        sub_product = self.env['product.product'].create({'name': 'Accesorio','type': 'consu'})

        product_stock = self.env['product.template'].create({
            'name': 'Laptop Oficina',
            'type': 'combo', 
            'payment_concept': self.concept_honorarios.id,
            'combo_ids': [(0, 0, {
                'name': 'Opciones de Laptop',
                'combo_item_ids': [(0, 0, {'product_id': sub_product.id})]
            })]
        })

        
        product_stock._onchange_payment_concept()
        
        self.assertFalse(product_stock.payment_concept, 
                         "Los productos COMBO no deben tener concepto de retención ISLR.")

   