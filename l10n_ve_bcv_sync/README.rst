=========================================
Venezuela - BCV Sync (Receptor de tasas)
=========================================

.. |badge1| image:: https://img.shields.io/badge/licence-LGPL--3-blue.png
    :target: http://www.gnu.org/licenses/lgpl-3.0-standalone.html
    :alt: License: LGPL-3

|badge1|

Expone ``POST /api/tasas-bcv``, el endpoint que consume **BCV Sync** (un
servicio externo, fuera de este repo, que scrapea bcv.org.ve y hace POST a
cada instancia Odoo configurada). Este modulo es solo el lado **receptor**;
el contrato completo del payload/respuesta esta documentado en
``ODOO_INTEGRATION.md`` del repo de BCV Sync.

Como se utiliza
===============

1. En el panel de BCV Sync, se genera una API Key para el cliente y se
   configura la URL de esta instancia.
2. En Odoo: **Ajustes > General Settings**, seccion de sincronizacion de
   tasa BCV, pegar exactamente la misma API Key en el campo
   ``BCV Sync API Key`` de la compania correspondiente.
3. A partir de ahi, cada POST autenticado de BCV Sync actualiza
   ``res.currency.rate`` para las monedas reconocidas.

Decisiones de diseno
=====================

**Alcance de la API Key: por compania.**
``can_update_habil_days`` (de ``l10n_ve_currency_rate_live``) ya es un ajuste
por compania, y el propio contrato de BCV Sync dice "un cliente = una URL +
una API key propia" -- una instancia Odoo multi-compania puede necesitar
distinguir el remitente por compania, asi que ``bcv_sync_api_key`` sigue la
misma granularidad. Se guarda en texto plano en un ``Char`` (patron ya usado
en este mismo grupo de repos, ej. ``splynx_api_key`` en
``binaural_splynx``); no hay cifrado a nivel de campo porque Odoo no lo
ofrece nativamente y no es el modelo de amenaza que este endpoint intenta
resolver -- el acceso de lectura al campo ya esta restringido a
``base.group_system``.

**Comparacion en tiempo constante.** La busqueda de la compania por token
(``res.company._bcv_sync_get_company_by_token``) recorre todas las
companias con key configurada y usa ``hmac.compare_digest`` contra cada una,
en vez de comparar con ``==`` o cortar en el primer match encontrado por
igualdad de texto plano.

**Controlador ``type="http"``, no ``type="json"``.** Se necesita devolver
codigos de estado especificos (``401``/``400``/``2xx``) con un body JSON
propio; el envoltorio JSON-RPC de ``type="json"`` no da ese control fino.
``auth="public"`` porque la autenticacion es el Bearer token propio, no una
sesion de usuario de Odoo; ``csrf=False`` porque es una llamada
servidor-a-servidor sin cookies.

**Persistencia en ``res.currency.rate`` -- asume moneda contable = VEF.**
BCV publica cada tasa como "unidades de VEF por 1 unidad de la moneda
extranjera" (ej. ``791.6667`` VEF por 1 USD). Ese numero coincide,
byte a byte, con el campo nativo de Odoo ``inverse_company_rate``
("unidades de la moneda de la compania por 1 unidad de esta moneda") **si y
solo si** la moneda contable de la compania es VEF -- que es la
configuracion estandar/esperada para libros contables venezolanos. Por eso
``_bcv_sync_process_tasas`` verifica ``company.currency_id.name == "VEF"``
antes de escribir nada, y si no se cumple omite todo el payload (con un
warning) en vez de escribir un numero financiero incorrecto.

Esto es deliberadamente **independiente** del esquema "legacy" de
``l10n_ve_rate``/``l10n_ve_currency_rate_live``, donde algunas companias
usan USD como moneda contable y VEF como moneda "foreign" (``currency_foreign_id``).
Ese esquema sigue intacto y sin cambios; simplemente no es el que este
modulo alimenta. Si una compania de ese tipo necesita esta integracion, hace
falta una conversion cruzada adicional (usar el ``USD`` del mismo payload
como pivote) que queda fuera de alcance de esta primera version.

La clave de upsert es ``(currency_id, company_id, name)`` -- la misma
restriccion ``unique_name_per_day`` nativa de ``res.currency.rate`` -- por lo
que reintentos automaticos de BCV Sync con el mismo payload nunca duplican
un registro, solo lo actualizan (idempotencia).

**Reuso, no reimplementacion, de la logica de "dia habil".** La decision de
si una ``fecha_valor`` corresponde aplicarse "hoy" (incluyendo el caso de
sabado/domingo con la tasa adelantada del viernes o del proximo dia habil)
usa tal cual ``res.company._is_valid_rate_date`` y el campo
``can_update_habil_days``, ambos de ``l10n_ve_currency_rate_live``. No se
toca ese modulo; solo se desactiva su cron
(``currency_rate_live.ir_cron_currency_update``) desde
``data/cron_data.xml`` de este modulo, porque BCV Sync reemplaza esa fuente
de la tasa (push en vez de scraping/cron).

Creditos
========

Autor/es
~~~~~~~~

* Binauraldev

Mantenedor/es
~~~~~~~~~~~~~

Este modulo es mantenido por Binaural.

.. image:: https://binauraldev.com/wp-content/uploads/2022/01/logo-binaural.png
   :alt: Binaural dev
   :target: https://binauraldev.com/
