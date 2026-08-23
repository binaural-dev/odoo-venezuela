# l10n_binaural

## Purpose

Plantilla de plan de cuentas "de servicio" de Binaural para Venezuela ("Venezuela - Plan de cuentas"): según su manifest, carga cuentas contables, grupos de impuestos e impuestos (CSV de plantilla `account.account-binaural`, `account.tax.group-binaural`, `account.tax-binaural`), además de datos de moneda, productos, contactos y diarios para una empresa de servicios. Depende de `base`, `account`, `account_accountant`, `stock`, `sale` y `contacts`.

Nota de estado: en esta rama del repositorio el módulo solo contiene su `__manifest__.py`; los archivos de datos que el manifest declara (carpeta `data/`) y el código Python (`models/`) no están presentes en las fuentes, por lo que su contenido no puede documentarse aquí.

## Requirements

### Requirement: Declaración de la carga del plan de cuentas de servicio

El manifest del módulo DEBE (MUST) declarar, en su clave `data`, la carga en orden de: datos de moneda (`data/res_currency_data.xml`), la plantilla de cuentas (`data/template/account.account-binaural.csv`), los grupos de impuestos (`account.tax.group-binaural.csv`), los impuestos (`account.tax-binaural.csv`), y los datos de productos, contactos y diarios (`product_template_data.xml`, `res_partner_data.xml`, `account_journal_data.xml`), con dependencias sobre `base`, `account`, `account_accountant`, `stock`, `sale` y `contacts`.

#### Scenario: Instalación del módulo

- **WHEN** se instala `l10n_binaural` en una base de datos
- **THEN** Odoo procesa los archivos de datos declarados en el manifest en ese orden, tras instalar los módulos de los que depende
