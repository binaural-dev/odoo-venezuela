#Binaural POS Descuentos

Este modulo se encarga de la creacion del boton de descuento en el POS. Se define un nuevo botón de descuento que reemplaza los descuentos existentes en las líneas de la orden de venta con un descuento personalizado 
basado en el porcentaje proporcionado.


Este añade los siguientes campos:

##Configuraciones:

* Se configura el Boton Descuento para almacenar el precio alterno al momento de hacer descuentos. Donde busca la orden de venta actual en el punto de venta y el producto de descuento configurado en la instancia de Odoo. 
* Se eliminan los descuentos existentes en las líneas de la orden de venta que corresponden al producto de descuento.
* Se agrupan las líneas de la orden de venta por grupo de impuestos. Para cada grupo de impuestos, se calcula el monto base para aplicar el descuento. También se calcula el monto base en moneda extranjera si corresponde.
* Se soporta el caso de uso de productos con más de un impuesto.
* Se añade el precio establecido manualmente para evitar el recálculo al cambiar de cliente.


## Validaciones

* Se calcula el descuento como un porcentaje del monto base y se verifica si es negativo. Si lo ses, agrega una línea de producto de descuento si el descuento es menor que cero.

----------------------------------------

#Interfaz de POS

* Boton Descuento que almacena el precio alterno al momento de hacer descuentos.

