===============
Binaural CRM
===============

.. |badge1| image:: https://img.shields.io/badge/licence-LGPL--3-blue.png
    :target: http://www.gnu.org/licenses/lgpl-3.0-standalone.html
    :alt: License: LGPL-3

|badge1|

El módulo "Binaural CRM" es un módulo nuevo pensado como la **base sobre la
que se construirán los próximos desarrollos de CRM** de Binaural: aquí van a
vivir todas las adaptaciones, ajustes y funcionalidades propias que se
agreguen sobre el CRM nativo de Odoo para los clientes venezolanos.

Actualmente incluye la primera funcionalidad desarrollada sobre esta base:
el manejo de moneda alterna (comercial) en CRM.

**Tabla de Contenidos**

.. contents::
   :local:

Moneda alterna en CRM
======================

Este módulo depende de "Binaural Tasa de Cambio" (``l10n_ve_rate``) para
extender el CRM de Odoo de forma que los montos de ingreso y facturación se
manejen en la moneda comercial configurada (ej. USD) además de la moneda de
la compañía (ej. VES).

Oportunidades (``crm.lead``)
-----------------------------

- El **Ingreso Esperado** y el **Ingreso Recurrente** se ingresan
  directamente en la moneda comercial. Ese valor es fijo: nunca se
  recalcula por cambios de tasa.
- El equivalente en la moneda de la compañía se calcula automáticamente,
  usando siempre la tasa de cambio vigente en el momento de la consulta.
- Disponible en el formulario de la oportunidad, en el mini-formulario de
  creación rápida del kanban, y en la tarjeta del kanban de Pipeline.
- El monto en moneda comercial debe ser estrictamente positivo (no se
  permiten montos en cero ni negativos).
- Los cambios sobre el monto en moneda comercial quedan registrados en el
  historial (chatter) de la oportunidad.

Equipos de venta (``crm.team``)
---------------------------------

- El **Objetivo de Facturación** mensual se define en moneda comercial.
- El monto facturado del mes y su equivalente en moneda de la compañía se
  calculan automáticamente, disponibles en el formulario del equipo y en el
  dashboard kanban de equipos de venta.

Reportes
---------

- **Pronóstico**: kanban, lista, gráfico y pivote muestran los montos
  ponderados por probabilidad en moneda comercial.
- **Análisis de Flujo**: pivote, gráfico y lista muestran el ingreso
  esperado en moneda comercial.

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
