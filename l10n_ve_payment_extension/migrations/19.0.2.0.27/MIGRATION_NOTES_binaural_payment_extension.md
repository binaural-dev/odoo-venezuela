# l10n_ve_payment_extension: riesgo de arquitectura en la línea NO homologada, sin corrección automática

============================================================================
LÍNEA NO HOMOLOGADA (rama 17.0 de integra-addons, binaural_payment_extension)
============================================================================

Del inventario campo por campo (ver `INVENTARIO_MODULOS_NO_HOMOLOGADOS.md`,
sección `binaural_payment_extension`):

La tabla `tax_unit` es estructuralmente compatible entre `binaural_payment_extension`
v17 y `l10n_ve_accountant`/`l10n_ve_payment_extension` v19 (mismos campos
`name`, `value`, `status`) -- el backfill de `available_date` que ya hace
`l10n_ve_payment_extension/migrations/19.0.2.0.26/post-migrate.py` es
correcto y reutilizable tal cual para esta línea también. **No se toca en
esta carpeta.**

El problema real **no es de nombres de columna, es de dependencias**:

`l10n_ve_payment_extension` depende de `l10n_ve_accountant`, que a su vez
depende de `l10n_ve_base`, `l10n_ve_rate`, `l10n_ve_contact`,
`account_reports`, `account_invoice_pricelist`,
`account_invoice_pricelist_sale`, `account_debit_note`. Un cliente de la
línea `binaural_payment_extension` **nunca tuvo instalado ningún
`l10n_ve_*`** -- instalar `l10n_ve_payment_extension` tal cual no es
opcional, arrastra por dependencia dura todo ese stack de la línea
homologada.

Esto no es algo que un script de migración de datos pueda decidir por sí
solo: instalar todo el stack homologado sobre un cliente no homologado es
una decisión de producto/arquitectura (¿se acepta el arrastre completo, o
se necesita un módulo `l10n_ve_payment_extension` "ligero" sin la
dependencia de `l10n_ve_accountant` para esta línea?).

Riesgo adicional detectado, independiente de la decisión anterior: tanto
`l10n_ve_accountant/data/tax_unit_data.xml` como
`l10n_ve_payment_extension/data/tax_unit_data.xml` crean, con
`noupdate="1"`, un registro `tax.unit` con el mismo `name`/`value`
(`"0,40"` / `0.4`) que ya trae un cliente migrado desde
`binaural_payment_extension/data/tax_unit_data.xml` (mismo valor, XML-ID
distinto). Si se instalan ambos módulos v19 sobre una base migrada, se
generan filas duplicadas de `tax.unit` para el mismo valor de UT.

## Decisión pendiente (no tomada en este documento)

1. ¿Se acepta que un cliente no homologado termine con todo el stack
   `l10n_ve_accountant`/`l10n_ve_base`/`l10n_ve_rate`/`l10n_ve_contact`
   instalado al migrar sus retenciones, o se requiere un módulo propio
   sin esa dependencia?
2. Si se acepta el stack completo: antes de la instalación hay que
   deduplicar manualmente (o con un script dedicado, no escrito aquí) el
   `tax.unit` de valor `0.4` que coincide entre los datos `noupdate` de
   ambos módulos y el ya migrado del cliente.

Hasta que eso se decida, **no se debe instalar `l10n_ve_payment_extension`
sobre una base que viene de `binaural_payment_extension` sin revisar antes
el punto 1**.
