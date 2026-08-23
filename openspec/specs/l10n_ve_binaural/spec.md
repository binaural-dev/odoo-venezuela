# l10n_ve_binaural

## Purpose

Plan de cuentas venezolano de Binaural ("Venezuela - Binaural"): registra la plantilla contable `ve_binaural` en el motor de plantillas de `account` (`account.chart.template`) y aporta como data de plantilla el catálogo de cuentas, los grupos de impuestos y los impuestos de IVA venezolanos (CSV en `data/template/`), con nombres traducidos al español (`name@es`). Depende únicamente de `account`. Incluye una compañía demo venezolana (`demo/demo_company.xml`).

## Requirements

### Requirement: Plantilla contable ve_binaural

El sistema DEBE (MUST) registrar en `account.chart.template` la plantilla `ve_binaural` ("Venezuela - Binaural") con `code_digits = 7` y con las cuentas por defecto: cuentas por cobrar `1122001`, cuentas por pagar `2122001`, gasto por categoría `7151001` e ingreso por categoría `5111001` (decorador `@template("ve_binaural")` en `_get_ve_binaural_template_data`).

#### Scenario: Selección de la plantilla

- **WHEN** una compañía instala la plantilla contable `ve_binaural`
- **THEN** el plan se genera con códigos de 7 dígitos y esas cuentas quedan como propiedades por defecto de cobrar/pagar/ingreso/gasto

### Requirement: Configuración de la compañía al cargar la plantilla

La data de plantilla para `res.company` (`_get_ve_binaural_res_company`) DEBE (MUST) configurar la compañía con: país fiscal `base.ve`, prefijos de cuentas bancarias `1113`, de caja `1111` y de transferencia `1129003`, cuenta por cobrar de POS `1122003`, cuentas de diferencial cambiario ganancia `9212003` y pérdida `9113006`, e impuestos por defecto de venta `tax1sale` y de compra `tax1purchase` (IVA 16%).

#### Scenario: Compañía venezolana recién configurada

- **WHEN** se carga la plantilla `ve_binaural` en una compañía
- **THEN** la compañía queda con país fiscal Venezuela, los prefijos de cuentas de banco/caja/transferencia indicados y el IVA 16% como impuesto por defecto de ventas y compras

### Requirement: Catálogo de cuentas con traducción al español

La plantilla DEBE (MUST) cargar el catálogo de cuentas desde `data/template/account.account-ve.csv` (266 cuentas), donde cada cuenta define código de 7 dígitos, `account_type`, flag `reconcile` y nombre en inglés con su traducción en español (`name@es`).

#### Scenario: Cuentas generadas

- **WHEN** se instala la plantilla en una compañía con idioma español
- **THEN** las cuentas del catálogo se crean con su código de 7 dígitos y el nombre traducido del CSV

### Requirement: Impuestos de IVA venezolanos

La plantilla DEBE (MUST) cargar cuatro grupos de impuestos con país Venezuela (IVA 0%, 8%, 16% y 31%) y ocho impuestos porcentuales (`amount_type = percent`) —exento, 8%, 16% y 31%, cada uno en versión venta y compra— cuyas líneas de repartición de impuesto apuntan a la cuenta `2172003` en ventas y `1151004` en compras, quedando los impuestos exentos (0%) sin cuenta de repartición.

#### Scenario: IVA de ventas 16%

- **WHEN** se instala la plantilla y se factura con el impuesto `tax1sale`
- **THEN** el impuesto calcula 16% y su repartición registra el IVA en la cuenta con código `2172003`

#### Scenario: IVA de compras

- **WHEN** se usa un impuesto de compra de la plantilla distinto del exento
- **THEN** la repartición del impuesto apunta a la cuenta con código `1151004`
