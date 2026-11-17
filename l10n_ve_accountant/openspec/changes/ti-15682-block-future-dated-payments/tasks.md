## 1. Implementación

- [x] 1.1 Constraint `_check_date_not_in_future` en `account.payment`.
- [x] 1.2 Constraint `_check_payment_date_not_in_future` en `account.payment.register`.
- [x] 1.3 Traducción `es_VE` y bump de versión.

## 2. Tests

- [x] 2.1 `tests/test_payment_future_date.py`: pago de hoy y pasado permitidos; futuro rechazado al crear y al
  escribir; asistente con hoy crea el pago y con fecha futura se rechaza; usa la zona horaria del usuario.

## 3. Verificación manual

- [ ] 3.1 Reproducir los pasos del ticket: registrar un pago con fecha de mañana desde el formulario de pagos y
  desde el asistente de registrar pago.
