from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_invoice_digital", "tfhka_serie")
class TestTfhkaSerie(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")

    def test_01_sync_creates_new_series(self):
        numberings = [
            {"serie": "A", "prefijo": "A-", "estado": "True"},
            {"serie": "B", "prefijo": "B-", "estado": "True"},
        ]

        self.env["tfhka.serie"]._sync_from_tfhka(self.company, numberings)

        series = self.env["tfhka.serie"].search([("company_id", "=", self.company.id)])
        self.assertEqual(set(series.mapped("name")), {"A", "B"})

    def test_02_sync_updates_existing_series(self):
        serie = self.env["tfhka.serie"].create({
            "name": "A",
            "company_id": self.company.id,
            "prefix": "OLD-",
            "status": "agotada",
        })

        self.env["tfhka.serie"]._sync_from_tfhka(
            self.company, [{"serie": "A", "prefijo": "A-", "estado": "True"}]
        )

        self.assertEqual(serie.prefix, "A-")
        self.assertEqual(serie.status, "True")
        # No crea un duplicado -- actualiza el registro existente.
        self.assertEqual(
            self.env["tfhka.serie"].search_count([("name", "=", "A"), ("company_id", "=", self.company.id)]),
            1,
        )

    def test_03_sync_ignores_no_aplica_and_empty_series(self):
        numberings = [
            {"serie": "NO APLICA", "prefijo": "00", "estado": "True"},
            {"serie": "", "prefijo": "", "estado": "True"},
            {"serie": None, "prefijo": "", "estado": "True"},
        ]

        self.env["tfhka.serie"]._sync_from_tfhka(self.company, numberings)

        self.assertFalse(self.env["tfhka.serie"].search([("company_id", "=", self.company.id)]))

    def test_04_sync_dedupes_same_serie_across_document_types(self):
        # TFHKA puede devolver la misma serie varias veces (una fila por
        # tipo de documento, cada una con su propio rango) -- el modelo no
        # rastrea esos rangos por tipo, solo el nombre/prefijo/estado de la
        # serie como tal, así que debe quedar un único registro.
        numberings = [
            {"serie": "A", "tipoDocumento": "01", "prefijo": "A-", "estado": "True"},
            {"serie": "A", "tipoDocumento": "03", "prefijo": "A-", "estado": "True"},
        ]

        self.env["tfhka.serie"]._sync_from_tfhka(self.company, numberings)

        self.assertEqual(
            self.env["tfhka.serie"].search_count([("name", "=", "A"), ("company_id", "=", self.company.id)]),
            1,
        )

    def test_05_sync_empty_numberings_does_nothing(self):
        self.env["tfhka.serie"]._sync_from_tfhka(self.company, [])

        self.assertFalse(self.env["tfhka.serie"].search([("company_id", "=", self.company.id)]))
