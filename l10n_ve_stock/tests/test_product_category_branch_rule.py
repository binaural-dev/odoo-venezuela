from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestProductCategoryBranchRule(TransactionCase):
    """La regla de categorias de producto deja ver las de la compania padre desde una sucursal."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Company = cls.env["res.company"]
        # una base con sucursal real se reutiliza: crear una compania ahi depende de su plan contable
        branch = Company.search([("parent_id", "!=", False)], limit=1)
        if branch:
            cls.parent, cls.branch = branch.parent_id, branch
        else:
            cls.parent = cls.env.company
            cls.branch = Company.create({"name": "Sucursal de prueba", "parent_id": cls.parent.id})
        cls.other = Company.search(
            [("parent_id", "=", False), ("id", "not in", (cls.parent | cls.branch).ids)], limit=1
        ) or Company.create({"name": "Otra persona juridica"})
        Category = cls.env["product.category"]
        cls.cat_parent = Category.create({"name": "Cat padre", "company_id": cls.parent.id})
        cls.cat_branch = Category.create({"name": "Cat sucursal", "company_id": cls.branch.id})
        cls.cat_other = Category.create({"name": "Cat otra empresa", "company_id": cls.other.id})
        cls.cat_shared = Category.create({"name": "Cat compartida", "company_id": False})
        cls.cats = cls.cat_parent | cls.cat_branch | cls.cat_other | cls.cat_shared
        cls.user = cls.env["res.users"].create(
            {
                "name": "Usuario sucursal",
                "login": "usuario_sucursal_categoria",
                "company_id": cls.branch.id,
                "company_ids": [(6, 0, (cls.parent | cls.branch | cls.other).ids)],
                "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
            }
        )

    def _visible(self, company_ids):
        env = self.env(user=self.user, context=dict(self.env.context, allowed_company_ids=company_ids))
        return env["product.category"].search([("id", "in", self.cats.ids)])

    def test_branch_sees_parent_categories(self):
        # Scenario: con solo la sucursal activa se ven las categorias de la padre, las propias y las compartidas
        visible = self._visible([self.branch.id])
        self.assertEqual(visible, self.cat_parent | self.cat_branch | self.cat_shared)

    def test_branch_does_not_see_other_company_group(self):
        # Scenario: las categorias de otra compania raiz (otro RIF) siguen sin verse
        self.assertNotIn(self.cat_other, self._visible([self.branch.id]))

    def test_parent_does_not_see_branch_categories(self):
        # Scenario: la regla es unidireccional: la padre no ve las categorias de la sucursal
        visible = self._visible([self.parent.id])
        self.assertEqual(visible, self.cat_parent | self.cat_shared)
