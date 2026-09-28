# Tasks

## 1. Espejar la config de impuestos en la línea foránea

- [x] 1.1 `orderline.xml`: el monto en divisa usa
      `get_foreign_price_with_tax()` cuando `iface_tax_included === 'total'`,
      y `get_foreign_price_without_tax()` en caso contrario

## 2. Verificación manual (navegador, 2doce)

- [ ] 2.1 PdV con "impuesto separado" (`subtotal`): la línea en divisa muestra
      SIN impuesto y cuadra con la columna local
- [ ] 2.2 PdV con "impuesto incluido" (`total`): sin cambios

## 3. OpenSpec

- [x] 3.1 `openspec validate --changes`
