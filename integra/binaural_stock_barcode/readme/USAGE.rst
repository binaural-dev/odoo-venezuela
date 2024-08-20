## Restriccion para agregar productos fuera de lo requerido

Se ingresa en el modulo Inventario > Configuracion > Tipos de operaciones > 
Barcode App > "Restringir agregar cantidades excedentes"

En caso de ser Verdero, al momento de escanear un elemento en el modulo de Codigo de barra en operaciones
no te permitira agregar productos que no esten ya establecidos o agregar mas de lo indicado


# Flujo de codigos de Barra:

1. Se inicia Con un presupuesto y al confirmarlo, este genera un PICK y un OUT. 
2. Al Pick se le asigna automaticamente un Empleado que no tenga asignado un pick o este en proceso.
3. El Empleado Pick entra en el modulo de Codigo de barras
4. Escanea el codigo de barra del carrito (Este asigna al carrito el PICK que tenga asignado)
5. Se escanea los productos
5.1 En caso de que no tenga las cantidades suficientes necesitara clave del supervisor para
continuar (en caso de que este activa esa configuracion)
5.2. En caso de que desee validar con cantidades insuficientes o sin algun producto necesitara 
clave de supervisor para continuar (en caso de que este activa esa configuracion)
6. Validar
7. Se escanea el Codigo de barras del carrito para continuar con el OUT, este hace el mismo 
   procedimiento
