from odoo import models, fields

class ResCompany(models.Model):
    _inherit = "res.company"

    custom_manifest = fields.Text(help="Open the url /pwa/1/manifest.json then use the content as template")
    
    assetlink = fields.Text(help="Generate using PWA Builder and search inside the .zip generate the assetslinks.json file and pase the content here.")
