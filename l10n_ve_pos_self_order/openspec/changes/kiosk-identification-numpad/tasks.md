# Tasks

## 1. Teclado numérico en pantalla

- [x] 1.1 `identification_page.js`: getter `numpadKeys` (grid 3×4: 1-9,
      retroceso, 0, limpiar)
- [x] 1.2 `identification_page.js`: handler `onNumpadKey(value)` que actualiza
      `state.vat` (dígito / retroceso / limpiar) y limpia `state.error`
- [x] 1.3 `identification_page.xml`: renderizar el numpad debajo del campo en el
      paso `identify` con `t-foreach` sobre `numpadKeys`
- [x] 1.4 `identification_page.scss`: `.o_ve_numpad` (grid centrado) y
      `.o_ve_numpad_key` / `.o_ve_numpad_action`

## 2. Reubicación de la acción primaria al pie

- [x] 2.1 Eliminar el botón "Continuar"/"Crear" de ancho completo del centro
- [x] 2.2 Añadir la acción primaria al pie, a la derecha, misma altura que
      "Atrás" (izquierda), conmutando etiqueta/acción por paso

## 3. Verificación manual (navegador)

- [x] 3.1 Upgrade del módulo y probar en el Kiosko: teclear la cédula con el
      numpad, retroceso y limpiar; "Continuar" identifica; "Atrás" vuelve; el
      paso "crear" (cédula no encontrada) mantiene la acción en el pie
- [x] 3.2 Confirmar el layout táctil (Atrás izq / Continuar der a la misma
      altura) y que el campo sigue admitiendo teclado físico

## 4. OpenSpec

- [x] 4.1 `openspec change validate kiosk-identification-numpad` → válido
