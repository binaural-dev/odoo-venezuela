Este modulo se encarga de agregar las siguientes configuraciones:

* Restriccion para agregar productos fuera de lo requerido en el movimiento (pick / pack / out)
* Crear factura al validar las transferencias OUT

Modelo nuevo llavado Carrito para almacenar el pick, pack, o out en curso, asi como 
tambien su codigo de barra para poder iniciar las operaciones

Modelo nuevo llamado Tiempos de Picking para almacenar los eventos de inicio, pausa, renaudar o
detener operacion de stock.picking utilizado para calcular los tiempos.

## Empleados:

* Lista de pickings activos para el Empleado
* Rol de picking (Relacionado al usuario de Odoo)
* Contraseña de supervisor (Relacionado al usuario de Odoo)

## Reglas de Nomenclatura

* Nuevo tipo llamado Carrito

##Codigo de Barra

* Validacion para no poder agregar mas productos de lo requerido en las lineas
* Validacion para en caso de tener menos cantidades de lo requerido exija clave de supervisor
* Validacion para en el momento de validar la operacion este exija la clave de supervisor

* Al momento de escanear un producto por el codigo de barra este toma las cantidades requeridas automaticamente

