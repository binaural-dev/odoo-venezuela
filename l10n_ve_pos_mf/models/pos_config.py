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
