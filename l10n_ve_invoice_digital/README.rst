=====================
Venezuela - Facturación Digital
=====================

.. |badge1| image:: https://img.shields.io/badge/licence-LGPL--3-blue.png
    :target: http://www.gnu.org/licenses/lgpl-3.0-standalone.html
    :alt: License: LGPL-3

|badge1|

Módulo de Facturación Digital para Venezuela. Integración con The Factory HKA (TFHKA)
para emitir facturas, notas de débito, notas de crédito y retenciones electrónicas
en cumplimiento con las regulaciones del SENIAT.

**Tabla de Contenidos**

.. contents::
   :local:

Configuración
=============

1. Vaya a *Facturación / Contabilidad > Configuración > Ajustes*.
2. En la sección *Venezuela - Facturación Digital*, configure la URL del endpoint TFHKA,
   credenciales, series y numeraciones por defecto.
3. En cada diario, asigne el código de forma de pago requerido por TFHKA.
4. Para facturas multi-moneda, active la casilla *Factura multi-moneda* en la factura
   y seleccione la moneda extranjera.

Uso
===

Para digitalizar una factura:

1. Vaya a *Facturación > Clientes > Facturas*.
2. Abra o cree una factura validada.
3. Haga clic en el botón *Generar Documento Digital*.
4. Si el documento se emite exitosamente, la factura quedará marcada como digitalizada.

Problemas conocidos / Hoja de ruta
==================================

* Máximo 5 formas de pago por documento digital.

Gestión de errores
==================

Los errores se gestionan en `GitHub Issues <https://github.com/binauraldev/odoo-venezuela/issues>`_.

Créditos
========

Autor/es
~~~~~~~~

* Binauraldev

Mantenedor/es
~~~~~~~~~~~~~

Este módulo es mantenido por Binaural.

.. image:: https://binauraldev.com/wp-content/uploads/2022/01/logo-binaural.png
   :alt: Binaural dev
   :target: https://binauraldev.com/
