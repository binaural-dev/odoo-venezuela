
# Estándares de codigo 🎯

En esta sección se ilustrarà la manera en que se debe desarrollar en integra, siendo esta basada en los estándares de [Odoo OCA](https://github.com/OCA).



### ORGANIZACIÓN DE DIRECTORIOS 🗂

- `./integra` Esta carpeta es utilizada únicamente para el desarrollo de módulos propios de integración, siendo esta la base para todos los forks. **IMPORTANTE: En caso de estar en un fork y requerir una modificacion en integra no se debe hacer directamente en el fork**
- `./third-party` Esta carpeta esta destinada, a modulos no propios de integra asi como modulos de la tienda de odoo
- `./custom` Esta carpeta esta destinada a modulos de personalizaciones de forks, incluyendo modulos de terceros propios del fork.


### Módulos 📦

Al momento de heredar o crear un modelo de debe seguirse los [Estandares de Odoo](https://www.odoo.com/documentation/16.0/contributing/development/coding_guidelines.html).


En caso de ser un modulo de binaural se debe inicializar con `binaural_` seguido del modulo a heredar en ingles

Ejemplo:

```
binaural_invoice
```

En caso de ser un fork se debe inicializar con el nombre del fork o proyecto `fork_` seguido del modulo a heredad en ingles

Ejemplo:

```
fork_invoice
```

### Normas 📜

- Los tabs de identacion se establecen en `4` espacios

```python
@api.depends("example")
def compute_example(self):
    """
    This method its a example
    """
    for record in self:
        record.example = "example"
```
- Se establece como maximo `100 caracteres` por linea
- El código se escribe en ingles tanto variables como la explicacion de docstrings, por lo que se debe de tener la traduccion en `i18n/es_VE.po`
- No dejar en el codigo `_logger.warning` ya que estos pueden saltar alarma en odoo.sh (evitar en lo posible dejar cualquier otro tipo de logger)
- El nombre de variables y funciones se escriben en snake_case.
- El nombre de las clases se escriben en PascalCase
```python
class AccountMove(models.Model):
```

### Docstring (Pandas) 🐼

Se ha utilizado el estandar de [Pandas](https://pandas.pydata.org/docs/development/contributing_docstring.html) para el formato de los docstrings.

Utilizado para la mayoria de las funciones, pero esencial para aquellas funciones con herencias, o muy complejas. En caso de no usar docstring el codigo debe ser lo suficientemente entendible o sencillo. (Todos deberian serlo)

```python
def add(num1, num2):
    """
    Add up two integer numbers.

    This function simply wraps the ``+`` operator, and does not
    do anything interesting, except for illustrating what
    the docstring of a very simple function looks like.

    Parameters
    ----------
    num1 : int
        First number to add.
    num2 : int
        Second number to add.

    Returns
    -------
    int
        The sum of ``num1`` and ``num2``.

    See Also
    --------
    subtract : Subtract one integer from another.

    Examples
    --------
    >>> add(2, 2)
    4
    >>> add(25, 0)
    25
    >>> add(10, -10)
    0
    """
    return num1 + num2
```

### Herencias 👨‍👦

Al momento de heredar un modelo, debe llamarse el archivo como el modelo, es decir: no utilizar un archivo para dos modelos.
```bash
/binaural_invoice/account_move.py
```

Evitar a toda costa sobrescribir funciones de odoo, en caso de ser una exepcion, los modulos que utilicen esa misma funcion, deben ser dependientes de ese modulo y dejar en el docstring el por que fue heredado y que parte especifica fue adicionada o suprimida.
