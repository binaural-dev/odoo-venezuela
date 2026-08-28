# l10n_ve_binaural

## Purpose

Plan de cuentas venezolano de Binaural ("Venezuela - Binaural"): registra la plantilla contable `ve_binaural` en el motor de plantillas de `account` (`account.chart.template`) mediante el decorador `@template` y aporta como data de plantilla el catálogo de cuentas, los grupos de impuestos y los impuestos de IVA venezolanos (CSV en `data/template/`), con nombres traducidos al español (`name@es`). Depende únicamente de `account` y declara `countries: ["ve"]`.

Nota de estado (rama actual): el módulo es una copia renombrada del `l10n_ve` oficial y quedaron referencias al nombre viejo. (1) Los CSV se llaman `account.account-ve.csv`, `account.tax.group-ve.csv` y `account.tax-ve.csv` —sufijo `ve`—, mientras que el código de plantilla que registran los decoradores es `ve_binaural`; el manifest no tiene clave `data`, así que esos CSV solo pueden llegar al sistema por el cargador de plantillas, que los busca por `<modelo>-<código_de_plantilla>.csv`. (2) `demo/demo_company.xml` referencia xml_ids del módulo inexistente `l10n_ve` (`l10n_ve.demo_company_ve`) y llama `account.chart.template.try_loading` con el código `ve`, no `ve_binaural`, por lo que la data demo no carga esta plantilla.

## Requirements

### Requirement: Plantilla contable ve_binaural

El sistema DEBE (MUST) registrar en `account.chart.template`, vía `@template("ve_binaural")` sobre `_get_ve_binaural_template_data`, la plantilla `ve_binaural` con nombre traducible "Venezuela - Binaural", `code_digits` = `"7"` (cadena) y las cuentas por defecto expresadas como xml_ids de plantilla: `property_account_receivable_id` = `account_activa_account_1122001`, `property_account_payable_id` = `account_activa_account_2122001`, `property_account_expense_categ_id` = `account_activa_account_7151001` y `property_account_income_categ_id` = `account_activa_account_5111001`.

#### Scenario: Selección de la plantilla

- **WHEN** una compañía carga la plantilla contable `ve_binaural`
- **THEN** el plan se genera con códigos de 7 dígitos y las cuentas 1122001 / 2122001 / 7151001 / 5111001 quedan como propiedades por defecto de cobrar / pagar / gasto / ingreso

### Requirement: Configuración de la compañía al cargar la plantilla

La data de plantilla para `res.company` (`_get_ve_binaural_res_company`) DEBE (MUST) devolver un único diccionario indexado por `self.env.company.id` —es decir, configura solo la compañía activa en el momento de la carga— con: país fiscal `base.ve`, `bank_account_code_prefix` `1113`, `cash_account_code_prefix` `1111`, `transfer_account_code_prefix` `1129003`, cuenta por cobrar de POS `1122003`, cuenta de ganancia por diferencial cambiario `9212003`, cuenta de pérdida por diferencial cambiario `9113006`, e impuestos por defecto de venta `tax1sale` y de compra `tax1purchase` (IVA 16%).

#### Scenario: Compañía venezolana recién configurada

- **WHEN** se carga la plantilla `ve_binaural` estando activa la compañía a configurar
- **THEN** esa compañía queda con país fiscal Venezuela, los prefijos de cuentas de banco/caja/transferencia indicados y el IVA 16% como impuesto por defecto de ventas y compras

### Requirement: Catálogo de cuentas con traducción al español

La plantilla DEBE (MUST) aportar el catálogo de cuentas en `data/template/account.account-ve.csv` con 266 cuentas, todas con código de 7 dígitos, `reconcile = True` sin excepción, nombre en inglés y traducción en `name@es`, y xml_id con el patrón `account_activa_account_<código>`. La tipificación es mayoritariamente `asset_current` (233 cuentas) frente a 10 `asset_receivable`, 7 `liability_payable`, 5 `income`, 5 `asset_fixed`, 4 `equity` y 2 `expense`; el catálogo no incluye ninguna cuenta de tipo `equity_unaffected`.

#### Scenario: Cuentas generadas

- **WHEN** se carga el catálogo en una compañía con idioma español
- **THEN** las cuentas se crean con su código de 7 dígitos, marcadas como conciliables y con el nombre traducido del CSV

#### Scenario: Cierre fiscal sobre este plan

- **WHEN** un proceso que exige una cuenta `equity_unaffected` (por ejemplo el cierre fiscal venezolano) busca la cuenta de resultados acumulados
- **THEN** no la encuentra en el catálogo de la plantilla y depende de que Odoo o el usuario la creen aparte

### Requirement: Impuestos de IVA venezolanos

La plantilla DEBE (MUST) aportar cuatro grupos de impuestos con `country_id` = `base.ve` (`tax_group_iva_0`, `_8`, `_16`, `_31`) y ocho impuestos `amount_type = percent` —`tax0sale`/`tax0purchase` (0% exento), `tax1sale`/`tax1purchase` (16%), `tax2sale`/`tax2purchase` (8%) y `tax3sale`/`tax3purchase` (31%)—, cada uno con cuatro líneas de repartición (`base` y `tax`, para `invoice` y `refund`). Las líneas de tipo `tax` apuntan a `account_activa_account_2172003` en los impuestos de venta y a `account_activa_account_1151004` en los de compra; los exentos y todas las líneas de tipo `base` quedan sin cuenta. Ambas cuentas de repartición están tipificadas como `asset_current` en el catálogo, incluida la de IVA débito fiscal (`2172003`), que no es una cuenta de pasivo.

#### Scenario: IVA de ventas 16%

- **WHEN** se factura con el impuesto `tax1sale` de la plantilla
- **THEN** el impuesto calcula 16% y sus líneas de repartición de tipo `tax` (factura y rectificativa) registran el IVA en la cuenta con código `2172003`

#### Scenario: IVA de compras

- **WHEN** se usa un impuesto de compra de la plantilla distinto del exento
- **THEN** las líneas de repartición de tipo `tax` apuntan a la cuenta con código `1151004`

#### Scenario: Impuesto exento

- **WHEN** se usa `tax0sale` o `tax0purchase`
- **THEN** el impuesto calcula 0% y ninguna de sus cuatro líneas de repartición lleva cuenta
