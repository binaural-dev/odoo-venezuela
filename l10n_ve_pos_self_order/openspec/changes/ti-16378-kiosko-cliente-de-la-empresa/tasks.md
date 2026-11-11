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
- [ ] 2.3 Suite del módulo en base nueva
- [ ] 2.4 Prueba funcional en una copia de Monfarmacia (Autopago CCCT 1):
      cédula solo en MONBODEGON, cédula en las dos empresas y cliente de
      MONFARMACIA; pago y factura publicada

## 3. Cierre

- [ ] 3.1 Archivar el change y volcarlo en
      `openspec/specs/pos-self-order-kiosk-identification/spec.md`
