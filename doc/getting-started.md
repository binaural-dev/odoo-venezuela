
# INSTALACION Y CONFIGURACION

Esta guía de instalación está basada en SO Debian 11, sin embargo puedes instalarlo en los diferentes SO.

## Dependencias

 - [Docker](https://docs.docker.com/engine/install/debian/)
 - [docker-compose](https://computingforgeeks.com/install-docker-and-docker-compose-on-debian/)
 - [Odoo Enterprise](https://github.com/odoo/enterprise)
 - [Git](https://git-scm.com/book/es/v2/Inicio---Sobre-el-Control-de-Versiones-Instalaci%C3%B3n-de-Git)

## Environment

### .env

Antes de correr el ambiente se debe crear en el ruta principal el archivo `.env` con base en el template [.env_example](../.env_example) para configurar las variables de entorno, asi como el puerto, el nombre del contenedor y versiones de Odoo.

### odoo.conf

Se debe configurar el archivo `config/odoo.conf` dependiendo de la configuracion del proyecto.

En la linea `addons_path` se deben colocar las carpetas en donde esten colocados los modulos, en caso de haber mas carpetas, se deben añadir aca, asi como en el `docker-compose`.

```bash
addons_path = /mnt/extra-addons, /mnt/integra-addons, /mnt/custom-addons, /mnt/third-party-addons
```

En la linea `admin_passwd` es para la contraseña para la administracion de bases de datos, en caso de ya tener una puedes se eliminarla o colocar a mano la contraseña. (No es necesaria para arrancar integra, ya que al no tenerla odoo te proporcionara un input al correrlo para que puedas ingresar la contraseña).

### docker-compose.yml

Antes de correr el ambiente se debe crear en el ruta principal el archivo `.docker-compose.yml` con base en el template [docker-compose_example.yml](../docker-compose_example.yml)

dentro del apartado `volumes:` se deben colocar las carpetas en donde esten colocados los modulos, en caso de haber mas carpetas, se deben añadir aca, asi como en el `odoo.conf`

```bash
    - odoo-web:/var/lib/odoo
    - ./config:/etc/odoo
    - ./enterprise:/mnt/extra-addons
    - ./integra:/mnt/integra-addons
    - ./custom:/mnt/custom-addons
    - ./third-party:/mnt/third-party-addons
```

**SE DEBE TENER EN SINCRONIA LAS CARPETAS EN LAS RUTAS, EN EL ODOO.CONF Y DOCKER-COMPOSE.YML!**


## Enterprise version
Tambien en la ruta principal se debe colocar el repositorio de Odoo Enterprise en la rama de , por lo que las rutas deberian verse de la siguiente manera:

```bash
/integra
    /config
    /custom
    /integra
    /third-party
    /enterprise
```


## Como correr el contenedor

#### Docker build
Luego de haber configurado las variables de entorno, nos permitira realizar el build, para instalar la version de odoo mas reciente y poder arrancar el proyecto
```bash
docker-compose build
```
En caso de ya tener una imagen del contenedor puedes realizar, para volver a descargar las dependencias y borrar la ya existente

```bash
docker-compose build --no-cache
```

#### Docker up

Para arrancar el contenedor, puedes hacerlo con el comando
```bash
docker-compose up
```

y si quieres correrlo en segundo plano con 

```bash
docker-compose up -d
```

En caso de reiniciarlo puedes hacerlo con
```bash
docker-compose restart
```

#### Docker down

Para apagar el contenedor
```bash
docker-compose down
```

Y en caso de eliminar el volumen y **borrar todos los datos de las BASES DE DATOS**
```bash
docker-compose down -v
```
