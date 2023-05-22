
# Estándares de codigo

En esta sección se ilustrarà la manera en que se debe desarrollar en integra, siendo esta basada en los estándares de [Odoo OCA](https://github.com/OCA).



### ORGANIZACIÓN DE DIRECTORIOS

- `./integra` Esta carpeta es utilizada únicamente para el desarrollo de módulos propios de integración, siendo esta la base para todos los forks. **IMPORTANTE: En caso de estar en un fork y requerir una modificacion en integra no se debe hacer directamente en el fork**
- `./third-party` Esta carpeta esta destinada, a modulos no propios de integra asi como modulos de la tienda de odoo
- `./custom` Esta carpeta esta destinada a modulos de personalizaciones de forks, incluyendo modulos de terceros propios del fork.


### Modulos

En caso de ser un modulo de binaural se debe inicializar con `binaural_`

Ejemplo:

```
binaural_invoice
```

