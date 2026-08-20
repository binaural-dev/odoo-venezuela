=========================================================
Venezuela - Reporte de Lista de Precios Multi-Lista
=========================================================

.. |badge1| image:: https://img.shields.io/badge/licence-LGPL--3-blue.png
    :target: http://www.gnu.org/licenses/lgpl-3.0-standalone.html
    :alt: License: LGPL-3

|badge1|

El módulo "Venezuela - Reporte de Lista de Precios Multi-Lista"
(``l10n_ve_sale_price_list``) extiende el reporte nativo "Imprimir lista de
precios" de Odoo (menú **Ventas/Inventario → Productos → Imprimir lista de
precios**) para poder comparar **varias listas de precios a la vez, en
columnas**, en vez de ver una sola lista con distintas cantidades (que es
el comportamiento nativo de Odoo).

**Tabla de Contenidos**

.. contents::
   :local:

Funcionalidad
==============

Varias listas de precios en columnas
--------------------------------------

- El reporte nativo muestra **una** lista de precios × varias cantidades.
  Este módulo lo invierte: muestra **varias listas de precios** en
  columnas, con cantidad fija = 1.
- Desde la barra de acciones del reporte se pueden agregar/quitar listas de
  precios dinámicamente (selector desplegable + botón "+"), mostrándose
  como etiquetas (con una "✕" para quitarlas) sobre la tabla.
- El reporte puede abrirse vacío (sin ninguna lista) o con una selección
  precargada por defecto — ver "Preselección por compañía" abajo.

Preselección por compañía / sucursal
--------------------------------------

Al abrir el reporte, se precargan automáticamente:

- Las listas de precio cuya **compañía** (campo ``company_id`` de
  ``product.pricelist``) coincide con la compañía en la que está logueado
  el usuario en ese momento (la compañía "activa" del selector de
  compañías, arriba a la derecha).
- Las listas de precio **sin compañía asignada** (``company_id`` vacío),
  ya que esas se consideran compartidas por todas las compañías.

**Importante para sucursales**: si el usuario está logueado en una
compañía **padre** (matriz), solo se precargan las listas asignadas
exactamente a esa compañía padre — **no** las de sus compañías hijas
(sucursales). Esto es una comparación exacta de ``company_id``, no una
búsqueda jerárquica. Si una sucursal necesita ver sus propias listas por
defecto, el usuario debe iniciar sesión en esa sucursal (o cambiar la
compañía activa desde el selector de compañías de Odoo) antes de abrir el
reporte.

Esta preselección es solo el punto de partida: el usuario puede seguir
agregando o quitando listas de cualquier compañía manualmente desde el
selector, sin ninguna restricción.

Identificación de compañía en el nombre de la lista
-----------------------------------------------------

Para que sea fácil distinguir a qué compañía/sucursal pertenece cada lista
(tanto en el selector del reporte como en cualquier otro lugar de Odoo
donde se muestre una lista de precios — ej. el menú de configuración de
Listas de Precios, formularios, etc.), este módulo extiende el nombre
para mostrar la compañía entre paréntesis:

- Con compañía asignada: ``Costo Alterno (USD) (Sucursal Caracas)``
- Sin compañía asignada (compartida): ``Default (VEF)`` (sin cambios,
  igual que el comportamiento nativo de Odoo)

Rendimiento: paginación y cálculo por lote
---------------------------------------------

Al seleccionar catálogos grandes (cientos de productos) junto con varias
listas de precios, calcular el precio producto por producto y lista por
lista puede volverse muy lento (problema clásico de "N+1 consultas": con
``n`` productos y ``m`` listas, el enfoque ingenuo hace ``n × m`` consultas
a la base de datos). Este módulo lo resuelve así:

- **Cálculo por lote**: el precio de cada lista se calcula en **una sola
  consulta** para todos los productos de la página actual (usando
  ``product.pricelist._get_products_price``), en vez de una consulta por
  cada combinación de producto y lista.
- **Paginación en pantalla**: la vista HTML del reporte muestra 20
  productos a la vez, con controles de página (◀ Página X/Y ▶) en la barra
  de acciones. Esto evita que el navegador tenga que renderizar cientos de
  filas de golpe.
- **La exportación a PDF siempre incluye todos los productos
  seleccionados**, ignorando la página en la que se esté parado en
  pantalla — la paginación es puramente una optimización de la vista
  previa en pantalla, no afecta lo que se imprime/exporta.

Uso
====

1. Ir a **Inventario/Ventas → Productos**, seleccionar los productos a
   incluir (o entrar sin selección para elegirlos desde el propio
   reporte) y usar la acción **Imprimir lista de precios**.
2. El reporte abre con las listas de precio de la compañía activa (y las
   sin compañía) ya precargadas como etiquetas.
3. Agregar o quitar listas de precios con el selector y el botón "+" /
   la "✕" de cada etiqueta.
4. Navegar entre páginas de productos con los controles de paginación,
   si el catálogo seleccionado supera los 20 productos.
5. Usar el botón **Print** para exportar el reporte completo (todos los
   productos seleccionados, todas las listas activas) a PDF.

Configuración
==============

Este módulo **no requiere configuración adicional para funcionar** más
allá de tener las listas de precio (``product.pricelist``) creadas con su
``company_id`` correctamente asignado:

- Para que una lista aparezca precargada por defecto solo en una sucursal
  específica, asignarle esa compañía en el campo **Compañía** de la lista
  de precios (Ventas/Facturación → Configuración → Listas de Precios).
- Para que una lista esté disponible/precargada en todas las compañías,
  dejar el campo **Compañía** vacío.
- No hace falta ningún grupo de seguridad ni permiso especial: cualquier
  usuario con acceso al reporte nativo de lista de precios puede usar
  esta versión extendida.

Créditos
========

Autor/es
--------

* Binauraldev

Mantenedor/es
-------------

Este módulo es mantenido por Binaural.

.. image:: https://binauraldev.com/wp-content/uploads/2022/01/logo-binaural.png
   :alt: Binaural dev
   :target: https://binauraldev.com/
