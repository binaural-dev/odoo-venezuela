## Decisiones

**En el módulo base, no en un puente.** El fallo es de `l10n_ve_account_mf` (decide por
la moneda de la compañía) y no depende del PdV ni de multimoneda.

**El monto del asiento manda.** La MF arma el ítem como unitario (2 decimales) ×
cantidad; el asiento valora la línea completa sin redondear el unitario (5 × $ 2,32 a
803,34 = 9.318,74; 5 × 1.863,75 = 9.318,75). Se manda el unitario redondeado hacia arriba
y un `q-` por el exceso (`_mf_company_item`, espejo de `mfCompanyItem` del puente del
PdV), para que la MF imprima lo mismo que el asiento.

**Impuesto incluido o excluido.** Las facturas en Bs mandan `price_unit` tal cual y el
impuesto de Odoo se configura alineado con el tipo de tasa de la MF. En otra moneda se
manda lo equivalente: base (`balance`) con impuesto excluido, total con IVA
(`price_total` × tasa de la factura) con impuesto incluido. Con todos los impuestos
incluidos la última línea absorbe el redondeo para que los ítems sumen el total de la
factura en la moneda de la compañía.

**Tasa.** La del propio asiento: `abs(amount_total_signed) / amount_total`.

**Pagos a la tasa de la factura.** El documento fiscal es uno solo y va a la tasa de la
factura; un pago a otra tasa genera diferencia en cambio en contabilidad, que no es un
medio de pago y no se envía (antes se mandaba como un pago "01").
