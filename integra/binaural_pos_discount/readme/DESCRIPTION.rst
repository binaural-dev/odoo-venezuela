#Binaural POS Descuentos

Este modulo se encarga de la creacion del nuevo boton de descuento en el POS. Este reemplaza los descuentos existentes en las líneas de la orden de venta con un descuento personalizado 
basado en el porcentaje proporcionado, con tasa alterna.


Este añade los siguientes campos:

##Configuraciones:

* Se configura el Boton Descuento para almacenar el precio alterno al momento de hacer descuentos. Donde busca la orden de venta actual en el punto de venta y el producto de descuento configurado en la instancia de Odoo. 
* Se agrupan las líneas de la orden de venta por grupo de impuestos. Para cada grupo de impuestos, se calcula el monto base para aplicar el descuento. También se calcula el monto base en moneda extranjera si corresponde.
* Se soporta el caso de uso de productos con más de un impuesto.

----------------------------------------

#Interfaz de POS

* Boton Descuento que almacena el precio alterno al momento de hacer descuentos.

