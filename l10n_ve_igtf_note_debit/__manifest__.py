{
    "name": "Venezuela - IGTF Nota de Débito Automática",
    "summary": "Genera automáticamente una Nota de Débito Fiscal para la percepción de IGTF, "
               "como alternativa opt-in a la línea contable embebida del módulo base.",
    "license": "LGPL-3",
    "description": """
    Venezuela - IGTF Nota de Débito Automática
    ===========================================
    Este módulo AGREGA un flujo alterno de percepción de IGTF sobre el existente en
    `l10n_ve_igtf`: en vez de contabilizar el IGTF como una línea dentro del mismo
    asiento de pago/anticipo (flujo histórico "inline"), genera un documento fiscal
    independiente -- una Nota de Débito, vía `account_debit_note` -- vinculada a la
    factura de origen, con su propio número de control (Forma Libre), conforme a las
    Providencias SENIAT 0071/0102.

    Principio de diseño:
    ---------------------
    * NO reemplaza el flujo existente. Es 100% opt-in por compañía
      (`igtf_note_debit_mode`), por lo que clientes que ya operan con el flujo
      de línea embebida NO se ven afectados y sus asientos históricos no se tocan.
    * Basado en Providencias SENIAT 0071 / 0102 (IGTF como documento de ajuste
      por cobrar, no como línea de producto ordinaria en la factura).

    Cómo funciona (con el modo activado):
    --------------------------------------
    * Registro de pago (wizard estándar): si el pago aplica IGTF, se puede elegir
      si el IGTF va incluido en el mismo pago o se cobra aparte (checkbox
      "Incluir IGTF en el pago"); el wizard muestra el desglose Importe + IGTF =
      Total a pagar cuando corresponde. Al confirmar, se genera la ND por el
      monto exacto de IGTF.
    * Cobro de la ND: si el IGTF va incluido en el pago, se concilia directo
      contra el residual sobrante del mismo pago; si no, se crea automáticamente
      un pago aparte en VEF y se concilia contra la ND.
    * Anticipos: al cruzar un anticipo contra una factura, el asiento de cruce se
      arma SIN la línea embebida de IGTF -- el IGTF correspondiente se calcula
      aparte y se cobra vía ND.
    * Conciliación manual (pago directo, no anticipo, vía el widget de líneas
      salientes de la factura): separa la porción que corresponde a la factura
      de la que corresponde al IGTF mediante una conciliación parcial, sin crear
      asientos intermedios, con soporte para pago y factura en monedas distintas.
    * La "Base imponible del IGTF" y el monto de IGTF mostrados en la factura
      reconocen tanto la línea embebida como la ND independiente.
    * Si el pago que originó una ND se desconcilia/cancela, se genera
      automáticamente una Nota de Crédito en Forma Libre que la reversa.
    """,
    "author": "binaural-dev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Accounting",
    "version": "19.0.1.0.1",

    "depends": [
        "l10n_ve_igtf",
        "account_debit_note",
    ],
    "data": [
        "views/res_config_settings_views.xml",
        "wizard/account_payment_register_views.xml",
        "views/account_move_views.xml",
    ],
    "application": False,
    "auto_install": False,
}