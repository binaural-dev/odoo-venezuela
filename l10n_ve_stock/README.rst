=====================
Venezuela - Inventario
=====================

.. image:: static/description/icon.png
   :alt: Venezuela Inventory

Descripción
===========

Este módulo amplía el inventario nativo de Odoo para la localización
venezolana. Complementa a los módulos ``l10n_ve_*`` aportando flujos y
validaciones adicionales que son habituales en el país.

Características principales
===========================

* Control de códigos de barras con soporte multicompañía.
* Validaciones sobre precios de productos (no negativos ni cero).
* Configuración de ubicaciones físicas y almacenes principales.
* Control de impuestos únicos por producto.
* Reportes de valoración de inventario y etiquetas de empaque.
* Grupos de seguridad para restringir operaciones de inventario.

Uso
===

1. Instala el módulo desde la aplicación de Apps o a través del comando
   de actualización en tu instancia ``docker-odoo``.
2. Configura los parámetros adicionales en ``Inventario → Configuración``
   (almacén principal, ubicaciones físicas, cantidad libre, etc.).
3. Opera las transferencias de inventario normalmente; las validaciones y
   restricciones se aplican automáticamente.

Pruebas
=======

Ejecuta las pruebas automáticas desde el entorno ``docker-odoo``:

.. code-block:: bash

   scripts/odoo-test <instancia> -d <base_de_pruebas> -m l10n_ve_stock

Soporte
=======

Para reportar incidencias o solicitar mejoras abre un issue en el
repositorio ``binaural-dev/odoo-venezuela``.
