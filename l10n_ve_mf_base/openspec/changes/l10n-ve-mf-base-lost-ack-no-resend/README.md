# l10n-ve-mf-base-lost-ack-no-resend

El driver TFHKA ya no reenvía a ciegas un ítem, descuento o pago cuando no llega el ACK: consulta S2 para saber si la máquina fiscal lo registró, y anula con "7" (no con "9") cuando no se puede saber. Ticket #15814.
