# Tasks

## 0. Preparación

- [x] 0.1 Reproducido en el staging de Monfarmacia (2026-11-11, Autopago CCCT 1,
      orden "Autopago CCCT 1 - 000008"): con la tasa cargada, "Crear factura"
      responde "El cruce entre empresas está prohibido"; el contacto `jdavila`
      es de MONBODEGON
- [x] 0.2 Decisión (2026-11-11, ticket 16378): los clientes nuevos del Kiosko se
      crean en la empresa raíz de la caja, no en la sucursal

## 1. Implementación

- [x] 1.1 `controllers/orders.py`: `_ve_find_partner` filtra con
      `res.partner._check_company_domain(pos_config.company_id)`
- [x] 1.2 `controllers/orders.py`: `identify/create` crea el contacto en
      `pos_config.company_id.root_id` (`with_company`) y devuelve en `error` el
      mensaje de una `ValidationError` de la creación
- [x] 1.3 `__manifest__.py`: `19.0.1.7.1`

## 2. Pruebas

- [x] 2.1 `tests/test_kiosk_public_routes.py`: setup con otra empresa y una
      sucursal con su Kiosko; `_make_partner` crea el cliente en la empresa de
      las cajas (antes quedaba en la compañía por defecto de la base, que el
      Kiosko ya no encuentra)
- [x] 2.2 Pruebas nuevas: contacto de otra empresa ignorado (`identify` y
      `set_phone`), cédula en dos empresas, sucursal que encuentra al cliente de
      la matriz, registro desde la sucursal en la empresa raíz y control global
      de cédula que devuelve el error
- [x] 2.3 Suite del módulo en base nueva (2026-11-11, instancia `monfarmacia`,
      código de la rama): `odoo -i l10n_ve_pos_self_order
      --test-tags /l10n_ve_pos_self_order` → 101 tests, 0 fallos y 0 errores
      (2 de la máquina fiscal se saltan). Línea base en `origin/19.0`: 95
      tests, 0 fallos. Con los tests nuevos sobre el código sin el fix, fallan
      5 de los 6 (el de la sucursal pasa en ambos: cubre que el filtro incluya
      la matriz)
- [x] 2.4 Prueba funcional en el navegador sobre `monfarmacia_20261030`
      (Autopago CCCT 1, VPOS Megasoft simulado, 2026-11-11):
      - V-24757432, en MONBODEGON (id 4344, el más bajo) y en MONFARMACIA
        (27149): la orden toma el 27149 y queda facturada
        (`FAP1/2026/0001`, publicada). Antes tomaba el 4344, como en staging
      - V-6293004, solo en MONBODEGON (13722): el Kiosko muestra "Nuevo
        cliente", el registro crea el 91095 en MONFARMACIA INVERSIONES (no en
        la sucursal), el 13722 no cambia y la orden queda facturada
        (`FAP1/2026/0002`, publicada)
      - Un "Crear factura" fallido del panel del Kiosko con un cliente de otra
        empresa deja la orden pagada y pendiente de facturar (no la pasa a
        `done`)

## 3. Cierre

- [ ] 3.1 Archivar el change y volcarlo en
      `openspec/specs/pos-self-order-kiosk-identification/spec.md`
