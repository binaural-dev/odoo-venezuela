El módulo Binaural Importaciones es una extension del módulo "Costes en Destino". 
Agrega funcionalidades adicionales relacionadas con el costo de importación de productos.

## Características principales

* Permite seleccionar la moneda extranjera para el cálculo del costo.
* Agrega campos de tasa de cambio y para el cálculo del costo en moneda extranjera
* Permite asociar el costo de importación a una o varias órdenes de compra.
* Permite calcular el costo de importación basado en diferentes métodos de distribución, incluyendo por cantidad, por peso, por volumen y por porcentaje.
* Actualiza el costo estándar más reciente del producto al validar el costo de importación.
* Se crea configuracion Usar misma cuenta de valoración de inventario en todas las categorias. 


## Funcionalidades adicionales

* Agrega vista de detalles para visualizar el ajuste de valorización agrupado por coste en destino.
* Agrega campo de costo por unidad de producto en ordenes de compra.
* Agrega metodo de division por porcentaje, su objetivo es distribuir el precio total de la importacion entre todos los productos en la orden de compra.
* Agrega campo de factor el cual representa el porcentaje de ese producto dentro del costo total de importación.
* Permite visualizar los ajustes de valorizacion con los valores de la moneda extranjera configurada previamente.
* Se agrega asiento de Importacion en cuanto el metodo de division sea por porcentaje y su configuracion este encendida 
    Cuenta de valoración de inventario    xxxx
    Cuenta contable del servicio 1	             xxxx
    Cuenta contable del servicio 2	             xxxx


