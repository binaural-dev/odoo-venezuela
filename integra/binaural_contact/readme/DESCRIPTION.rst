#Binaural Contactos

Este modulo se encarga de agregar el tipo de documento en la ficha del contacto.


Campos agregados a modelos existentes
"""""""""""""""""""""""""""""""""""""

* Contactos (res.partner).

  * prefix_vat: Tipos de documento venezolano (V, E, P, J, G, C)

Funcionalidades
"""""""""""""""

* Al agregar el tipo de documento y se introduce el número del documento, este consultara los nombres y apellidos en la plataforma del CNE y agregarlos en la ficha por registrar.

Validaciones
""""""""""""

* La consulta en el CNE solo se realizara cuando el tipo de documento sea V o E y se agrega el numero de documento.
* Solo aceptara dígitos el número de documento.
