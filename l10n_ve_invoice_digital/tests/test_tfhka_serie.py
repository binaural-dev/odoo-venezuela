from odoo.exceptions import AccessError
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

    def test_03_sync_includes_no_aplica_but_ignores_empty_series(self):
        # "NO APLICA" se sincroniza como una serie más (un diario puede
        # elegirla explícitamente para decir "sin serie") -- lo único que se
        # descarta es una serie realmente vacía/sin nombre.
        numberings = [
            {"serie": "NO APLICA", "titulo": "NUMERACIÓN DE 1 A 100000", "tipoDocumento": "TODOS",
             "prefijo": "00", "desde": "1", "hasta": "100000", "correlativo": "2672", "estado": "True"},
            {"serie": "", "prefijo": "", "estado": "True"},
            {"serie": None, "prefijo": "", "estado": "True"},
        ]

        self.env["tfhka.serie"]._sync_from_tfhka(self.company, numberings)

        series = self.env["tfhka.serie"].search([("company_id", "=", self.company.id)])
        self.assertEqual(series.mapped("name"), ["NO APLICA"])

    def test_03b_sync_stores_full_numbering_detail(self):
        numberings = [
            {"serie": "NO APLICA", "titulo": "NUMERACIÓN DE 1 A 100000", "tipoDocumento": "TODOS",
             "prefijo": "00", "desde": "1", "hasta": "100000", "correlativo": "2672", "estado": "True"},
        ]

        self.env["tfhka.serie"]._sync_from_tfhka(self.company, numberings)

        serie = self.env["tfhka.serie"].search([("name", "=", "NO APLICA"), ("company_id", "=", self.company.id)])
        self.assertEqual(serie.title, "NUMERACIÓN DE 1 A 100000")
        self.assertEqual(serie.document_type, "TODOS")
        self.assertEqual(serie.prefix, "00")
        self.assertEqual(serie.number_from, "1")
        self.assertEqual(serie.number_to, "100000")
        self.assertEqual(serie.correlative, "2672")
        self.assertEqual(serie.status, "True")

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

    # ------------------------------------------------------------------
    # Solo lectura para todos: la sincronización (que usa sudo()) es la
    # única forma de crear/editar una serie, nunca un usuario a mano.
    # ------------------------------------------------------------------

    def _create_user(self, login, group_xmlid):
        return self.env["res.users"].create({
            "name": login,
            "login": login,
            "group_ids": [(6, 0, [self.env.ref(group_xmlid).id])],
        })

    def test_06_regular_user_cannot_create_serie(self):
        user = self._create_user("tfhka_serie_user_test", "base.group_user")
        with self.assertRaises(AccessError):
            self.env["tfhka.serie"].with_user(user).create({
                "name": "A", "company_id": self.company.id,
            })

    def test_07_regular_user_cannot_write_serie(self):
        serie = self.env["tfhka.serie"].create({"name": "A", "company_id": self.company.id})
        user = self._create_user("tfhka_serie_user_test2", "base.group_user")
        with self.assertRaises(AccessError):
            serie.with_user(user).write({"prefix": "X-"})

    def test_08_regular_user_cannot_unlink_serie(self):
        serie = self.env["tfhka.serie"].create({"name": "A", "company_id": self.company.id})
        user = self._create_user("tfhka_serie_user_test3", "base.group_user")
        with self.assertRaises(AccessError):
            serie.with_user(user).unlink()

    def test_09_tfhka_admin_also_cannot_write_serie(self):
        # El grupo administrativo propio del módulo tampoco puede -- la
        # única forma de cambiar una serie es que vuelva a sincronizarse.
        serie = self.env["tfhka.serie"].create({"name": "A", "company_id": self.company.id})
        admin_user = self._create_user(
            "tfhka_serie_admin_test", "l10n_ve_invoice_digital.group_l10n_ve_invoice_digital_admin"
        )
        with self.assertRaises(AccessError):
            serie.with_user(admin_user).write({"prefix": "X-"})
