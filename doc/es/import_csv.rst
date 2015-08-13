============
Importar CSV
============

El módulo "Importar CSV" amplia las funcionalidades por defecto de importación
de CSV que lleva Tryton por defecto.

Este módulo le permite a parte de añadir nuevos registros al sistema,
como también le permite la actualización de registros.

Este módulo le permite:

* Definir perfiles CSV. Estos perfiles especifica la estructura del fichero
  CSV y sus columnas (técnico).
* Asistente importación CSV. Este asistente le permite seleccionar un perfil
  y un fichero CSV para ser importado.
* Logs de importación.

.. inheritref:: import_csv/import_csv:section:perfiles

Perfiles
========

Desde el menú |menu_import_profile_csvs| podrá definir los diferentes perfiles.

Un perfil cuenta con la siguiente estructura:

* Modelo: sobre que objeto se realizará la importación.
* Estructura del CSV (cabecera, separador, delimitador, ..)
* Columnas: cada columna a que campo del modelo equivale.

.. |menu_import_profile_csvs| tryref:: import_csv.menu_import_profile_csvs/complete_name

.. inheritref:: import_csv/import_csv:section:columnas

Columnas
========

Generalmente las importaciones del CSV, cada columna del CSV equivale a un campo del modelo.

Por ejemplo, en el modelo de "Terceros":

* Columna 0 -> Campo "name"
* Columna 1 -> Campo "lang"

Campos relación 'uno a muchos' (o2m), 'muchos a uno' (m2o) o 'muchos a muchos' (m2m)
====================================================================================

# TODO DOC Uso del campo "search_record_code" y como se usan o se relaciona los datos relacionados.

.. inheritref:: import_csv/import_csv:section:actualizar

Actualizar
==========

Si en el asistente marca la opción "Actualizar registros", se actualizarán los registros mediante
la información del fichero del CSV.

Para la actualización, previamente en el perfil del CSV debe marcar aquellos campos que desea
"Añadir al dominio de búsqueda". Esto le permite filtrar los registros, y aquellos que concidan,
en vez de crear o omitir, se actualizarán según la información del nuevo fichero CSV.

.. important:: Si la actualización de registros es sobre un modelo que según su estado ya no se permite
               la modificación, no podrá actualizar dicha información recibiendo un aviso.
               Por ejemplo, no podrá modificar pedidos de venta que su estado ya sea "confirmado".

.. inheritref:: import_csv/import_csv:section:omitir

Omitir
======

Del mismo modo que el punto anterior, "Actualizar", seleccionando esta opción evitará que se
creen nuevos registros si estos ya existen.

.. inheritref:: import_csv/import_csv:section:ejemplos

Ejemplos
========

Importación de terceros
-----------------------

El perfil de este CSV será en el modelo "Terceros" y las columnas:

* Columna 0 -> Campo "name"
* Columna 1 -> Campo "lang"

# TODO finalizar ejemplo fichero CSV

.. code-block:: csv

    "Test1","Catalán"
    "Test2","Español (España)"

Importación de productos
------------------------

Los productos disponen de dos partes:

* El producto o plantilla del producto (product.template)
* La variante (product.product

Ejemplo de producto o plantilla de producto:

* Columna 0 -> Campo "name"
* Columna 1 -> Campo "cost_price"
* Columna 2 -> Campo "list_price"
* Columna 3 -> Campo "cost_price_method"
* Columna 4 -> Campo "type"

.. code-block:: csv

    "name","street","city"
    "Test1","14,00","15,50","fixed","goods"
    "Test2","14,00","16,50","fixed","goods"
