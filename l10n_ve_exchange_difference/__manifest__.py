{
    'name': 'Venezuela - Diferencial cambiario como Notas de Débito/Crédito',
    'version': '1.0',
    'category': 'Accounting/Localizations',
    'summary': 'Document exchange-rate differences on customer invoices as real fiscal Debit/Credit Notes',
    'description': """
Módulo de localización venezolana que documenta el diferencial cambiario de
facturas de cliente como Notas de Débito/Crédito fiscales reales, en vez del
asiento contable genérico e interno que crea Odoo por defecto.

Cómo funciona:

- Al conciliar una factura de cliente en moneda extranjera contra un pago con
  una tasa de cambio distinta, se omite el asiento automático de diferencial
  de Odoo (`no_exchange_difference`, la misma llave que usa Odoo
  internamente), dejando el residual abierto.
- El monto exacto del diferencial se calcula a partir del monto realmente
  emparejado en la conciliación (`account.partial.reconcile`) y la tasa
  propia de cada línea -- nunca del residual completo de la línea (que puede
  incluir montos ajenos al diferencial si el pago es por un importe distinto
  al de la factura).
- Ese monto se documenta con una Nota de Débito (ganancia) o Nota de Crédito
  (pérdida) real, con correlativo fiscal en el diario dedicado, vinculada a
  la factura de origen y conciliada de inmediato contra el residual.
- Si la conciliación factura-pago que originó la nota se rompe, la nota (ya
  posteada, con correlativo fiscal) se revierte automáticamente -- nunca se
  cancela ni se borra. Desconciliar la nota directamente está bloqueado.
- Solo aplica a facturas/notas de crédito de CLIENTE. Cualquier otro caso
  (facturas de proveedor, asientos manuales) sigue el comportamiento nativo
  de Odoo sin modificaciones.

Configuración:

- Activable por compañía (`Ajustes > Contabilidad`).
- Producto dedicado (con impuesto exento) para la línea de la ND/NC.
- Diario de venta dedicado, con su propia secuencia para las Notas de
  Débito.
    """,
    'author': 'Binaural',
    'depends': ['account', 'l10n_ve_accountant', 'od_journal_sequence', 'l10n_ve_invoice', 'l10n_ve_igtf'],
    'data': [
        'views/account_journal_views.xml',
        'views/account_move_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
