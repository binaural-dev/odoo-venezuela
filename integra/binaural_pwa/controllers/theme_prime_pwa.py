import json
from odoo import _, http
from odoo.addons.theme_prime.controllers.main import ThemePrimePWA
from odoo.http import request

import logging
_logger = logging.getLogger(__name__)

class BinThemePrimePWA(ThemePrimePWA):

    def get_default_manifest_json(self, website_id, website):
        manifest_data = {"fake": 1}

        if not (website and website.id == website_id and website.dr_pwa_activated):
            return manifest_data

        manifest_data = {
            "name": website.dr_pwa_name,
            "short_name": website.dr_pwa_short_name,
            "display": "standalone",
            "background_color": website.dr_pwa_background_color,
            "theme_color": website.dr_pwa_theme_color,
            "id": website.dr_pwa_start_url,
            "start_url": website.dr_pwa_start_url,
            "scope": "/",
            "icons": [{
                "src": "/web/image/website/%s/dr_pwa_icon_192/192x192" % website.id,
                "sizes": "192x192",
                "type": "image/png",
            }, {
                "src": "/web/image/website/%s/dr_pwa_icon_512/512x512" % website.id,
                "sizes": "512x512",
                "type": "image/png",
            }]
        }

        if website.dr_pwa_shortcuts:
            manifest_data['shortcuts'] = [
                {
                    "name": shortcut.name,
                    "short_name": shortcut.short_name or '',
                    "description": shortcut.description or '',
                    "url": shortcut.url,
                    "icons": [{"src": "/web/image/dr.pwa.shortcuts/%s/icon/192x192" % shortcut.id, "sizes": "192x192"}]
                } for shortcut in website.dr_pwa_shortcuts
            ]

        return manifest_data

    @http.route('/pwa/<int:website_id>/manifest.json', type="json", auth="public", website=True)
    def get_pwa_manifest(self, website_id, **kargs):
        website = request.website
        manifest_data = self.get_default_manifest_json(website_id, website)

        custom_manifest = website.company_id.custom_manifest

        try:
            json_custom_manifest = json.loads(custom_manifest)

            manifest_data = json_custom_manifest

            website.sudo().company_id.write({"custom_manifest": json.dumps(manifest_data)})

        except:
            website.sudo().company_id.write({"custom_manifest": json.dumps(manifest_data)})

        return request.make_response(
            data=json.dumps(manifest_data),
            headers=[('Content-Type', 'application/json')]
        )
    

    @http.route('/.well-known/assetlinks.json', type='http', auth='public', website=True)
    def get_pwa_assetlinks_json(self, **kargs):
        website = request.website
        assetlinks_data = [
            {
                "relation": ["delegate_permission/common.handle_all_urls"],
                "target": {
                    "namespace": "android_app",
                    "package_name": _("ADD PACKAGE NAME HERE (Android Unique Identifier)"),
                    "sha256_cert_fingerprints": [_("ADD FINGERPRINT HERE")]
                }
            }
        ]

        assetlink = website.company_id.assetlink

        try:
            json_assetlink = json.loads(assetlink)

            assetlinks_data = json_assetlink

            website.sudo().company_id.write({"assetlink": json.dumps(assetlinks_data)})
        except:
            website.sudo().company_id.write({"assetlink": json.dumps(assetlinks_data)})

        return request.make_response(
            data=json.dumps(assetlinks_data),
            headers=[('Content-Type', 'application/json')]
        )