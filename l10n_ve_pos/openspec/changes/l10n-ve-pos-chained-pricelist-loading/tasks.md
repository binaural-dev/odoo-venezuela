# Tasks — l10n-ve-pos-chained-pricelist-loading

## Diagnóstico

- [x] Reproducir el síntoma en la base del cliente (`dosdoce`): 1,16 Bs en todo
      el catálogo.
- [x] Descartar el servidor: `_get_product_price` sobre la cadena da
      2,00 USD → 1,7340 EUR → 1.493,26 Bs. Ventas/facturación no afectadas.
- [x] Descartar que `getPrice()` en JS convierta mal: tiene dos bloques
      `needsCurrencyConversion` simétricos (hacia la moneda de la lista antes de
      aplicar la regla, de vuelta a la del PdV después). **No parchear.**
- [x] Medir el payload real con `pos.session.load_data([])`: 2 listas, 2 items,
      cero items de `BASE USD`.
- [x] Ubicar la causa: `product.pricelist._load_pos_data_domain` del core
      resuelve las listas base un solo nivel.
- [x] Ubicar el segundo hueco: `get_pos_ui_product_pricelist_item_by_product`
      restringe a `_get_available_pricelists()`, donde las listas base no pueden
      estar por el constraint de moneda de `pos.config`.

## Implementación

- [x] `models/product_pricelist.py`: `_pos_expand_base_pricelists()` (cierre
      transitivo, tolerante a ciclos).
- [x] `models/product_pricelist.py`: `_load_pos_data_domain()` extendido, sin
      depender de la forma del dominio del core.
- [x] `models/product_pricelist.py`: `_pos_warn_absolute_amounts_in_chain()`
      para que la limitación de monedas no falle en silencio.
- [x] `models/pos_session.py`: override de
      `get_pos_ui_product_pricelist_item_by_product()` que suma los items y las
      listas base que el core excluye.
- [x] `models/__init__.py`: registrar `product_pricelist`.

## Pruebas

- [x] `tests/test_pos_pricelist_chain_loading.py` (slice_b), cadena de 3 niveles
      Bs → EUR → USD:
  - [x] el cierre transitivo alcanza los 3 eslabones
  - [x] una lista sin cadena devuelve solo a sí misma (el override no cambia
        nada en instalaciones sin listas encadenadas)
  - [x] el ORM rechaza los ciclos, así que nunca llegan al loader (el guard
        `seen` es defensa en profundidad, no manejo de un caso soportado)
  - [x] la carga inicial incluye la lista base de 2do nivel
  - [x] la carga inicial incluye los items `fixed` de la lista base
  - [x] la carga on-demand incluye items y registros de las listas base
  - [x] el precio de la cadena difiere de `list_price` y coincide con el
        servidor (test de discriminación: si el escenario diera lo mismo por
        casualidad, no probaría nada)
- [x] Verificación contra la base del cliente: simular `getPrice()` usando solo
      el payload del loader y comparar con el servidor → 16/16 coinciden.
- [ ] Correr la suite completa de `l10n_ve_pos` para descartar regresiones en
      los otros slices.
- [ ] Verificar en el navegador con la caja del cliente (abrir sesión y
      confirmar que los productos muestran el precio de la lista).

## Pendiente / seguimiento

- [ ] Decidir si la carga de monedas debe cubrir la cadena completa. Hoy
      `res_currency.py` restringe a compañía + PdV + divisa a propósito; es
      inocuo para reglas porcentuales pero bloquea recargos absolutos en listas
      intermedias. Ver "Limitación conocida" en `proposal.md`.
- [ ] Revisar si `point_of_sale.limited_product_count` en la instancia del
      cliente debe volver a un valor de rendimiento razonable (estaba en 10).
