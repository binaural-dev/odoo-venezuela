# l10n_binaural

## Purpose

Plantilla de plan de cuentas "de servicio" de Binaural para Venezuela ("Venezuela - Plan de cuentas"): según su manifest, carga cuentas contables, grupos de impuestos e impuestos (CSV de plantilla `account.account-binaural`, `account.tax.group-binaural`, `account.tax-binaural`), además de datos de moneda, productos, contactos y diarios para una empresa de servicios. Depende de `base`, `account`, `account_accountant`, `stock`, `sale` y `contacts`.

Nota de estado (rama actual): del módulo solo queda el `__manifest__.py`. No hay `__init__.py`, no hay `models/` con fuentes (solo restos de `__pycache__` de un `ir_module.py` borrado), no hay ninguna carpeta `data/` y ningún método decorado con `@template(...)` que registre la plantilla en `account.chart.template`. El manifest tampoco declara `installable`, por lo que el módulo sigue apareciendo como instalable en la lista de aplicaciones.

## Requirements

### Requirement: Declaración de la carga del plan de cuentas de servicio

El manifest del módulo DEBE (MUST) declarar, en su clave `data` y en este orden: `data/res_currency_data.xml`, `data/template/account.account-binaural.csv`, `data/template/account.tax.group-binaural.csv`, `data/template/account.tax-binaural.csv`, `data/product_template_data.xml`, `data/res_partner_data.xml` y `data/account_journal_data.xml`, con dependencias sobre `base`, `account`, `account_accountant`, `stock`, `sale` y `contacts`.

#### Scenario: Lectura del manifest

- **WHEN** Odoo indexa el módulo y lee su `__manifest__.py`
- **THEN** el módulo aparece con ese nombre, categoría "Accounting/Localizations/Account Charts" y esa lista de dependencias y de archivos de datos

### Requirement: El módulo no es instalable en esta rama

Dado que ninguno de los archivos declarados en `data` existe en el árbol, una instalación real DEBE (MUST) fallar al intentar cargar el primer archivo declarado (`data/res_currency_data.xml`), sin crear cuentas, impuestos, productos, contactos ni diarios.

#### Scenario: Intento de instalación

- **WHEN** se intenta instalar `l10n_binaural` en una base de datos
- **THEN** la instalación aborta porque el archivo de datos declarado no existe, y no se carga ningún plan de cuentas de servicio
