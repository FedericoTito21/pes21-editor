# PES 2021 · Editor de Plantillas

Aplicación de escritorio en **Python** para editar el archivo de edición (`EDIT00000000`) de eFootball PES 2021 para PC: plantillas, traspasos, dorsales, capitán, datos y habilidades de los jugadores, nombres y colores de los equipos, y creación de jugadores nuevos.

## Qué tiene de interesante técnicamente

- **Cifrado y descifrado** del archivo de guardado (`pes21crypt.py`). Es un port a Python de pesXdecrypter: usa un generador MT19937 inicializado con la clave del juego y está vectorizado con **NumPy**, de modo que un archivo de unos 10 MB se procesa en menos de un segundo.
- **Lectura y escritura de un formato binario** (`pes21data.py`) con `struct`: jugadores, equipos, plantillas y alineaciones. Las partes del archivo que no están documentadas se conservan intactas.
- **Lector de archivos `.cpk`** (`cpkreader.py`), los contenedores del motor CRI, con descompresión **CRILAYLA** propia. Sirve para sacar la base de datos de jugadores (`Player.bin`) de la instalación del juego sin modificarla.
- **Detección automática del formato** de `Player.bin` comparando IDs con el archivo EDIT, con caché en JSON (`gamedb.py`).
- **Interfaz gráfica** con **Tkinter/ttk** (`pes21editor.py`): pestañas, búsquedas, selector de colores y tareas en segundo plano con `threading` y `queue` para que la ventana no se bloquee.
- **Seguridad de los datos**: hace una copia de seguridad automática al guardar por primera vez, y el botón «Guardar y jugar» cierra el juego, guarda y lo vuelve a abrir.

## Tecnologías

Python 3.10+ · Tkinter · NumPy · formatos binarios (`struct`) · criptografía (MT19937) · descompresión CRILAYLA

## Estructura

| Archivo | Qué hace |
| --- | --- |
| `pes21editor.py` | Interfaz gráfica |
| `pes21data.py` | Modelo de datos: jugadores, equipos y plantillas |
| `pes21crypt.py` | Cifrado y descifrado del EDIT |
| `cpkreader.py` | Lector de `.cpk` con descompresión CRILAYLA |
| `gamedb.py` | Lectura de `Player.bin`, detección del formato y caché |

## Ejecutar

```bash
pip install -r requirements.txt
python pes21editor.py
```

En Windows también puedes hacer doble clic en `Abrir editor.bat`.

En [LEEME.md](LEEME.md) tienes el manual completo con todas las pestañas, cómo hacer fichajes, cómo crear jugadores y cómo leer los nombres desde la carpeta del juego.

## Créditos

El formato del archivo y la clave de cifrado proceden del trabajo de la comunidad: [pesXdecrypter](https://github.com/the4chancup/pesXdecrypter) (dominio público) y [4ccEditor](https://github.com/the4chancup/4ccEditor) (licencia zlib), de the4chancup. Es un proyecto sin relación con Konami.

## Autor

Federico Mathias
