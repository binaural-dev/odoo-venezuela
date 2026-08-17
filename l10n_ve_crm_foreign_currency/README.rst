===================================
Binaural CRM Moneda Alterna
===================================

.. |badge1| image:: https://img.shields.io/badge/licence-LGPL--3-blue.png
    :target: http://www.gnu.org/licenses/lgpl-3.0-standalone.html
    :alt: License: LGPL-3

|badge1|

El módulo "Binaural CRM Moneda Alterna" (``l10n_ve_crm_foreign_currency``)
extiende el CRM nativo de Odoo para que los montos de ingreso y facturación
se manejen en la moneda comercial configurada (ej. USD) además de la moneda
de la compañía (ej. VES).

Parametrización
================

Este módulo **no tiene un flag de configuración para activar o desactivar
la moneda alterna**: la parametrización es la instalación misma del módulo.
Si está instalado, el CRM trabaja en moneda alterna para todas las
compañías de la base — se asume que toda compañía tiene una moneda
comercial configurada en Binaural Settings (``l10n_ve_rate``), ya que
ninguna instancia Binaural debería carecer de ella. La instalación **no**
se detiene si a alguna compañía le falta: un constraint permanente avisa al
intentar guardar una compañía sin moneda comercial configurada, pero no
bloquea la carga del módulo (necesario para que el módulo se pueda instalar
sobre bases de test/CI que no traen esa configuración por defecto).

Si en el futuro se necesita una funcionalidad de CRM que **no** dependa de
la moneda alterna (por ejemplo, para un cliente que no la usa), esa
funcionalidad debe ir en un módulo base nuevo, ``l10n_ve_crm``, del cual
este módulo pasaría a depender. Este módulo, tal como está, no debe
mezclarse con lógica de CRM que no tenga que ver con moneda alterna.

**Tabla de Contenidos**

.. contents::
   :local:

Funcionalidad
==============

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
  permiten montos en cero ni negativos) para oportunidades creadas o
  editadas manualmente. Se exceptúan los leads (no oportunidades) y los
  registros creados automáticamente por la pasarela de correo o el
  formulario del sitio web, que no tienen quién llene el monto al momento
  de crearse.
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

Migración de datos históricos
===============================

Al instalar el módulo sobre una base con oportunidades y equipos ya
existentes, un ``post_init_hook`` convierte los montos históricos (que
vivían en la moneda de la compañía) a moneda comercial, usando la tasa
vigente en la fecha de creación de cada registro.

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
