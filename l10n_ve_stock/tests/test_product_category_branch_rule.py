from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestProductCategoryBranchRule(TransactionCase):
    """Requirement "Categorías de producto multi-compañía": una compañía ve las categorías
    propias, las de sus ancestros y las que no tienen compañía; nada más.

    Se crean siempre las compañías del escenario (padre, dos sucursales, una sub-sucursal y
    una persona jurídica aparte) para que la prueba no dependa de los datos de la base.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Company = cls.env["res.company"]
        cls.parent = Company.create({"name": "Padre (test categorias)"})
        cls.branch = Company.create({"name": "Sucursal 1 (test categorias)", "parent_id": cls.parent.id})
        cls.sister = Company.create({"name": "Sucursal 2 (test categorias)", "parent_id": cls.parent.id})
        cls.grandchild = Company.create({"name": "Sub-sucursal 1.1 (test categorias)", "parent_id": cls.branch.id})
        cls.other = Company.create({"name": "Otra persona juridica (test categorias)"})
        companies = cls.parent | cls.branch | cls.sister | cls.grandchild | cls.other
        Category = cls.env["product.category"]
        cls.category_of = {company: Category.create({"name": f"Cat {company.name}", "company_id": company.id}) for company in companies}
        cls.shared = Category.create({"name": "Cat compartida (test categorias)", "company_id": False})
        cls.all_categories = Category.browse([c.id for c in cls.category_of.values()] + [cls.shared.id])
        cls.user = cls.env["res.users"].create(
            {
                "name": "Usuario categorias",
                "login": "usuario_categorias_sucursal",
                "company_id": cls.branch.id,
                "company_ids": [(6, 0, companies.ids)],
                "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
            }
        )

    def _visible_companies(self, active_companies):
        """Compañías cuyas categorías ve el usuario con solo `active_companies` activas
        (más 'shared' si ve la categoría sin compañía)."""
        env = self.env(user=self.user, context=dict(self.env.context, allowed_company_ids=active_companies.ids))
        visible = env["product.category"].search([("id", "in", self.all_categories.ids)])
        names = {company.name for company, category in self.category_of.items() if category in visible}
        if self.shared in visible:
            names.add("shared")
        return names

    def _expected(self, *companies):
        return {company.name for company in companies} | {"shared"}

    def test_branch_sees_parent_own_and_shared(self):
        # Scenario: La sucursal ve las categorías de su compañía padre
        self.assertEqual(self._visible_companies(self.branch), self._expected(self.parent, self.branch))

    def test_grandchild_sees_all_its_ancestors(self):
        # Scenario: Una sub-sucursal ve las de todos sus ancestros
        self.assertEqual(
            self._visible_companies(self.grandchild),
            self._expected(self.parent, self.branch, self.grandchild),
        )

    def test_sister_branches_do_not_see_each_other(self):
        # Scenario: Una sucursal hermana no ve las categorías de la otra
        self.assertEqual(self._visible_companies(self.sister), self._expected(self.parent, self.sister))
        self.assertNotIn(self.branch.name, self._visible_companies(self.sister))

    def test_parent_does_not_see_branch_categories(self):
        # Scenario: La compañía padre no ve las categorías de sus sucursales
        self.assertEqual(self._visible_companies(self.parent), self._expected(self.parent))

    def test_other_company_group_is_isolated(self):
        # Scenario: Una categoría de otra compañía raíz no aparece
        self.assertEqual(self._visible_companies(self.other), self._expected(self.other))
        self.assertNotIn(self.other.name, self._visible_companies(self.branch))

    def test_several_active_companies_add_up(self):
        # Scenario: Con varias compañías activas se suman sus ámbitos
        self.assertEqual(
            self._visible_companies(self.branch | self.sister),
            self._expected(self.parent, self.branch, self.sister),
        )
