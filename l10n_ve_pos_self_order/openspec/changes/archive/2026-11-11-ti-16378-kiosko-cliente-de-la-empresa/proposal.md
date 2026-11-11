# Fix: el Kiosko solo identifica clientes que su caja puede facturar (ti 16378)

## Why

Ticket 16378 (referencia #16416, Monfarmacia): en el Autopago CCCT 1 del
staging (11/11/2026) el cliente se identificó por cédula, pagó con Megasoft y
la orden quedó **pagada sin factura** (y sin factura fiscal), aunque la
pantalla dijo "Transacción exitosa". Al crear la factura desde el panel Debug,
Odoo respondió: *"Borrador de factura (Autopago CCCT 1 - 000008)" pertenece a
la empresa "MONFARMACIA CCCT" mientras que "Contacto" (partner_id: 'jdavila')
pertenece a otra empresa. El cruce entre empresas está prohibido.*

`l10n_ve_contact` le pone compañía a cada contacto (`_default_company_id`), así
que en una base con varias empresas la misma cédula puede existir en otra. La
búsqueda por cédula del Kiosko (`_ve_find_partner`, usada por `identify`,
`identify/create` y `set_phone`) buscaba con `sudo()` sin filtrar por compañía
y tomaba el contacto de otra empresa (MONBODEGON), que la factura de la caja
(MONFARMACIA CCCT, sucursal de MONFARMACIA INVERSIONES) rechaza.

En el staging de Monfarmacia hay 69.270 cédulas con contacto: 6.275 existen
solo en MONBODEGON y en otras 3.194 el Kiosko escogía el de MONBODEGON aunque
existiera el de MONFARMACIA (≈ 14 % de los clientes pagarían sin factura).

Además, el cliente que se registraba en el Kiosko quedaba en la compañía de la
caja (la sucursal), así que las demás cajas de la empresa no podían
facturarle.

## What Changes

- `controllers/orders.py`, `_ve_find_partner`: busca la cédula solo entre los
  contactos que la factura de la caja acepta, con
  `res.partner._check_company_domain(pos_config.company_id)` (compañía de la
  caja, sus matrices y compartidos). Si la cédula solo existe en otra empresa,
  el Kiosko la trata como cliente nuevo y pide registrarse.
- `controllers/orders.py`, `identify/create`: el cliente nuevo se crea en la
  compañía raíz de la caja (`company_id.root_id`, con `with_company` para que
  el control de cédula duplicada de `l10n_ve_contact` mire esa compañía). Sin
  sucursales, la raíz es la compañía de la caja (sin cambio).
- `controllers/orders.py`, `identify/create`: si la creación la rechaza una
  validación (p. ej. el control GLOBAL de cédula duplicada de
  `l10n_ve_contact` con una cédula de otra empresa), la ruta devuelve el
  mensaje de la validación en `error` en vez de un error de servidor.

## Non-goals

- Corregir los contactos existentes o las órdenes ya pagadas con un contacto de
  otra empresa: se arreglan a mano (cambiar la compañía del contacto y "Crear
  factura").
- Compartir contactos entre empresas (`binaural_partner_multi_company`,
  en integra-addons): si está instalado, la búsqueda lo respeta
  porque usa la misma regla `_check_company_domain`.

## Capabilities

### Modified Capabilities

- `pos-self-order-kiosk-identification`: la búsqueda por cédula se limita a
  los contactos que la caja puede facturar y el registro crea el contacto en
  la compañía raíz.

## Impact

- **Módulo**: `l10n_ve_pos_self_order` (`controllers/orders.py` y
  `tests/test_kiosk_public_routes.py`). Versión `19.0.1.7.0` → `19.0.1.7.1`.
- **Despliegue**: `-u l10n_ve_pos_self_order` (o reinicio: el cambio es solo
  Python). Sin cambio de esquema ni de datos.
- **Comportamiento visible**: un cliente cuya cédula solo existe en otra empresa
  ve el formulario de registro una vez en el Kiosko.
