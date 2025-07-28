from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError
from unittest.mock import patch, MagicMock

import logging

_logger = logging.getLogger(__name__)

@tagged('l10n_ve_invoice_digital', 'invoice digital') 
class TestAccountMoveApiCalls(TransactionCase):

    def setUp(self):
        super().setUp()
        Account = self.env["account.account"]
        Journal = self.env["account.journal"]

        # ───────────────────────────────────────────────────── monedas
        self.company = self.env.ref("base.main_company")
        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")

        self.company.write(
            {
                "username_tfhka": "usuario_prueba",
                "password_tfhka": "clave_prueba",
                "url_tfhka": "https://api.tfhka.com",
                "token_auth_tfhka": "token_fake",
                "invoice_digital_tfhka": True,
                "sequence_validation_tfhka": True,
                "currency_id": self.currency_usd.id,
                "currency_foreign_id": self.currency_vef.id,
            }
        )
        
    def test_01_generate_token_tfhka_username_empty(self):
        self.company.username_tfhka = False
        with self.assertRaises(UserError):
            self.company.generate_token_tfhka()
        _logger.info("Test passed: Username for TFHKA is empty, UserError raised as expected.")

    def test_02_generate_token_tfhka_password_empty(self):
        self.company.password_tfhka = False
        with self.assertRaises(UserError):
            self.company.generate_token_tfhka()
        _logger.info("Test passed: Password for TFHKA is empty, UserError raised as expected.")

    def test_03_generate_token_tfhka_url_empty(self):
        self.company.url_tfhka = False
        with self.assertRaises(UserError):
            self.company.generate_token_tfhka()
        _logger.info("Test passed: URL for TFHKA is empty, UserError raised as expected.")
    
    @patch('requests.post')
    def test_04_generate_token_tfhka_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "codigo": 200,
            "mensaje": "Token generado exitosamente",
            "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCIsImN0eSI6IkpXVCJ9.eyJleHAiOjE3NDk4Mzc0MTYsImlhdCI6MTc0OTc5NDIxNiwiaXNzIjoiSi0zMTIxNzExOTciLCJjb250ZXh0Ijp7IklkIjoxMiwiRW50ZXJwcmlzZSI6IkJJTkFVUkFMIEMuQS4iLCJSSUYiOiJKLTI5NTMyMTk2MSIsImlBbWIiOjIsIlVzZXIiOiJlbGZkZHVxbnNvenNfdGZoa2EifX0.rWF7VDRT_6AL8Jdkb3XU227lKpBG5mY7GpQSZPC7VWE",
            "expiracion": "2025-06-13T17:56:56.959092Z"
        }
        mock_post.return_value = mock_response

        self.company.generate_token_tfhka()
        _logger.info("Test passed: Token generated successfully for TFHKA.")

    @patch('requests.post')
    def test_05_generate_token_tfhka_invalid_credentials(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "codigo": 403,
            "mensaje": "Usuario/Clave incorrectos",
            "expiracion": "0001-01-01T00:00:00"
        }
        mock_post.return_value = mock_response
        with self.assertRaises(UserError):
                self.company.generate_token_tfhka()
        _logger.info("Test passed: Invalid credentials for TFHKA, UserError raised as expected.")
