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

- [x] 2.1 Propagación raíz → sucursales de lo que se escribió
      (`_fields_sync` + helper con `values` y `branches`)
- [x] 2.2 Constraint para contactos de sucursales
- [x] 2.3 `res.company.create` aplica los valores a la sucursal nueva
- [x] 2.4 Migración 19.0.2.2.10 (solo propaga los campos con valor en la raíz;
      conserva los de la sucursal si la raíz está vacía y deja un warning)

## 3. Pruebas

- [x] 3.1 Tests nuevos `branch_fiscal_propagation`
- [x] 3.1b Tests de los flujos ISLR de cliente (automático y manual) con la
      sucursal activa (`test_branch_islr_customer_flows.py`)
- [x] 3.1c Tests de la propagación solo de lo escrito, la sucursal nueva sin
      tocar las existentes, el vaciado en la matriz y la constraint con
      raíz vacía (`test_h` a `test_n`, incluye sucursales archivadas y alta múltiple)
- [x] 3.2 Correr la suite en CI sobre la rama del PR (verde sobre
      `3d4a1965b`)
- [ ] 3.2b Tests de la migración 19.0.2.2.10 (`test_migration_branch_fiscal.py`):
      los cinco estados raíz/sucursal en cada campo, una pérdida = un warning
      y una nota en el chatter, sucursales ya alineadas, archivadas y de varios
      niveles, varias raíces aisladas, idempotencia, resto de datos del
      contacto intactos, escritura posterior sin `ValidationError` y carpeta
      de migración no mayor a la versión del manifest
- [ ] 3.3 Validación de la migración: cubierta por la matriz de 3.2b, porque
      el resultado depende solo del valor de la raíz y de la sucursal en cada
      campo y esa matriz agota los casos. Lo que se sobrescribe queda en el
      log, en el historial y en una nota del contacto de la sucursal.
- [ ] 3.4 Antes de actualizar Daiko (paso del despliegue, no del merge): correr
      la consulta de solo lectura de la sección "Despliegue" de `proposal.md`
      y revisar las filas `se sobrescribe` de SUCURSAL CARACAS y VALENCIA

## 4. Fuera de alcance

- [ ] 4.1 `condition_withholding_id` sigue editable en el formulario de
      compañía de las sucursales; si se cambia ahí, la constraint del
      contacto lo rechaza con un mensaje que habla del contacto.
