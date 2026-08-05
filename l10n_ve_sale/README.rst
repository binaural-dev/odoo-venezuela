=====================
Venezuela - Ventas
=====================

.. image:: static/description/icon.png
   :alt: Venezuela Sales

Descripción
===========

Este módulo amplía las ventas nativas de Odoo para la localización
venezolana. Complementa a los módulos ``l10n_ve_*`` aportando flujos y
validaciones adicionales que son habituales en el país.

Características principales
===========================

* Control de tasas y monedas extranjeras dentro de las órdenes de venta.
* Validaciones sobre límites de crédito, facturas vencidas y estados de
  pago antes de confirmar el presupuesto.
* Integración con la configuración venezolana de stock, impuestos y
  guías de despacho.
* Ajustes en la generación de facturas para evitar redondeos residuales
  y dividir documentos según los límites configurados.

Uso
===

1. Instala el módulo desde la aplicación de Apps o a través del comando
   de actualización en tu instancia ``docker-odoo``.
2. Configura los parámetros adicionales en ``Ventas → Configuración``
   (tasas manuales, límites de crédito, cantidad máxima a facturar, etc.).
3. Opera las órdenes de venta normalmente; las validaciones y
   recomputaciones se ejecutan automáticamente.

Pruebas
=======

Ejecuta las pruebas automáticas desde el entorno ``docker-odoo``:

.. code-block:: bash

   scripts/odoo-test <instancia> -d <base_de_pruebas> -m l10n_ve_sale

Soporte
=======

Para reportar incidencias o solicitar mejoras abre un issue en el
repositorio ``binaural-dev/odoo-venezuela``.
