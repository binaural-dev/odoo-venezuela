from odoo import models, fields, api, _

class PosConfigInherit(models.Model):
    _inherit = "pos.config"

    # Campos de configuración de la máquina fiscal (Web Serial API)
    serial_machine = fields.Char(
        string="Serial de Máquina Fiscal",
        help="Serial de la impresora fiscal conectada (se llena automáticamente)"
    )
    
    flag_21 = fields.Selection(
        [
            ('00', 'Estándar (8+2 enteros, 5+3 cantidad)'),
            ('01', 'Precisión decimal (7+3 enteros, 5+3 cantidad)'),
            ('02', 'Alta precisión (6+4 enteros, 5+3 cantidad)'),
            ('30', 'Montos grandes (14+2 enteros, 14+3 cantidad)')
        ],
        string="Flag 21 - Formato de Números",
        default='00',
        required=True,
        help="Determina el formato de números en la impresora fiscal TFHKA.\n"
             "00 = Estándar (la mayoría de impresoras)\n"
             "30 = Para montos muy grandes (empresas grandes)"
    )
    
    traditional_line = fields.Boolean(
        string="Línea Tradicional",
        default=False,
        help="Activar si la impresora usa formato de línea tradicional"
    )
    
    has_cashbox = fields.Boolean(
        string="Tiene Gaveta de Efectivo",
        default=True,
        help="Si está activado, la gaveta se abrirá automáticamente al cobrar en efectivo"
    )
    
    # Campos de configuración general
    access_button_mf = fields.Boolean(
        string="Mostrar Botón de Conexión MF",
        default=True
    )
    
    message_in_head = fields.Boolean(
        string="Mensaje en Encabezado",
        default=False
    )

    enable_auto_sync = fields.Boolean(
        string="Habilitar Sincronización Automática",
        default=True,
        help="Si está activo, sincroniza automáticamente pedidos offline en segundo plano"
    )

    auto_sync_interval = fields.Integer(
        string="Intervalo de Sincronización (segundos)",
        default=60,
        help="Intervalo en segundos para sincronizar pedidos offline con Odoo"
    )
    
    mf_skip_invoice_pdf = fields.Boolean(
        string="Omitir PDF de Factura",
        default=True,
        help="Si está activo, no genera ni descarga el PDF de la factura al validar un pedido fiscal"
    )
    
    @api.model
    def _load_pos_data_fields(self, config):
        """Exponer campos de configuración fiscal al frontend POS"""
        fields_list = list(super()._load_pos_data_fields(config))
        # Si el core devuelve [] significa "todos los campos"
        if not fields_list:
            return fields_list
        
        fiscal_fields = [
            'serial_machine',
            'flag_21',
            'traditional_line',
            'has_cashbox',
            'access_button_mf',
            'message_in_head',
            'enable_auto_sync',
            'auto_sync_interval',
            'mf_skip_invoice_pdf',
        ]
        
        for field_name in fiscal_fields:
            if field_name not in fields_list:
                fields_list.append(field_name)
        
        return fields_list
