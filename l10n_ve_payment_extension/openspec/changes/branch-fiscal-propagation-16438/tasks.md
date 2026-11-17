# Tasks

## 1. Diagnóstico

- [x] 1.1 Reproducido en una copia de la base con una factura de la
      sucursal: con la sucursal activa la línea queda en 0, con la matriz
      activa calcula.
- [x] 1.2 Confirmada la causa: `_get_islr_type_person_id()` lee el tipo de
      persona del contacto de la empresa y el de la sucursal está vacío.
- [x] 1.3 Confirmado en el core de Odoo 19 que el sync comercial de
      `res.partner` no aplica (los contactos de las sucursales no tienen
      `parent_id`) y que los campos delegados del core solo cubren campos
      de `res.company`.

## 2. Implementación

- [x] 2.1 Propagación raíz → sucursales (`_fields_sync` + helper)
- [x] 2.2 Constraint para contactos de sucursales
- [x] 2.3 `res.company.create` aplica los valores a la sucursal nueva
- [x] 2.4 Migración 19.0.2.2.9

## 3. Pruebas

- [x] 3.1 Tests nuevos `branch_fiscal_propagation`
- [ ] 3.2 Correr la suite en CI sobre la rama del PR
- [ ] 3.3 Validar en el staging de Daiko con SUCURSAL CARACAS y VALENCIA

## 4. Fuera de alcance

- [ ] 4.1 `condition_withholding_id` sigue editable en el formulario de
      compañía de las sucursales; si se cambia ahí, la constraint del
      contacto lo rechaza con un mensaje que habla del contacto.
