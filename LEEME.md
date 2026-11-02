# PES 2021 · Editor de Plantillas

Aplicación de escritorio para editar el archivo de edición (`EDIT00000000`) de
**eFootball PES 2021 en PC (Steam)**: plantillas, traspasos, dorsales, capitán,
datos y habilidades de jugadores, nombres y colores de equipos, y creación de jugadores.

## Puesta en marcha (Windows)

1. Instala Python 3.10 o superior desde python.org (marca *Add python.exe to PATH*).
2. Haz doble clic en **`Abrir editor.bat`**. La primera vez instala `numpy` sola.
   - Alternativa manual: `py -m pip install numpy` y luego `py pes21editor.py`.
3. Pulsa **Abrir EDIT…**. El diálogo intenta ir directo a tu carpeta:
   `Documentos\KONAMI\eFootball PES 2021 SEASON UPDATE\<tu_id_steam>\save\EDIT00000000`

**Para ver los cambios en el juego** pulsa **▶ Guardar y jugar**: si PES 2021 está
abierto lo cierra (te avisa antes), guarda y lo vuelve a abrir (con el `PES2021.exe`
de la carpeta del juego si se la has indicado; si no, desde Steam). El juego
solo lee el EDIT al arrancar, así que no hay forma de que cambie con el juego abierto.

Si usas el botón normal **Guardar**, cierra PES 2021 antes. Al guardar por primera vez se crea una copia
`EDIT00000000.backup_FECHA` junto al original. Para deshacerlo todo, borra el EDIT
y renombra la copia a `EDIT00000000`.

## Qué puedes hacer

| Pestaña | Funciones |
|---|---|
| **Plantillas** | Plantilla de cada equipo (titulares en verde, capitán marcado). Fichar desde otro equipo o agentes libres, dar de baja, cambiar dorsal, nombrar capitán, reordenar, **titular ↔ suplente** (selecciona dos con Ctrl+clic) y **mejorar equipo** (suma o resta puntos a todas las habilidades de la plantilla) |
| **Jugadores › Básico** | Nombre, nombre de camiseta, nombre impreso (selección), edad, altura, peso, nacionalidad (con el país al lado si hay carpeta del juego), pie y mano buenos, posición, estilo de juego, pie malo, forma, lesiones, estrellas, actitud |
| **Jugadores › Habilidades** | Las 25 habilidades (40-99) con ajuste rápido ±1/±5 |
| **Jugadores › Posiciones** | Dominio C/B/A de las 13 posiciones |
| **Jugadores › Especiales / IA** | 41 habilidades especiales y 7 estilos de juego de la IA |
| **Jugadores › Físico** | 14 medidas corporales (-7 a +7), color de piel y de ojos |
| **Jugadores › Equipación** | Mangas, camiseta interior, camiseta por dentro/fuera, medias, mallas, muñequeras y sus colores, gafas y su color, guantes y su color, vendaje de tobillo, ID de botas y de guantes de portero |
| **Jugadores › Animaciones** | Estilo de regate y carrera, lanzamiento de córner, falta y penalti, dos celebraciones |
| **Equipos** | Nombre, abreviatura, dos colores, nombre del estadio, 4 pancartas, ID de entrenador y de estadio, 3 rivales |

Todo lo que el editor no toca se conserva tal cual (incluidas las partes del archivo que
no están documentadas, como la cara y el pelo).

### Fichajes
- Al **fichar** eliges de qué equipo sale. Si marcas *No quitarlo del equipo de origen*,
  el jugador queda en los dos (útil para convocarlo con una selección).
- Si sale un titular, el editor pone en su lugar al primer suplente y reajusta el
  índice del capitán. **Los lanzadores de faltas, córners y penaltis no se tocan**:
  revísalos en el juego (Editar › Equipos) después de traspasos grandes.
- Máximo 40 jugadores por equipo (límite del archivo).

### Crear jugadores
El jugador nuevo parte de una copia de otro (cara, físico, botas, habilidades) y
después lo ajustas. Dos modos:
- **Reutilizar un agente libre** (recomendado): se sobrescribe el agente libre con
  la media más baja. El juego siempre lo acepta porque el hueco ya existía.
- **Registro nuevo** (experimental): añade un hueco al final del archivo con un ID
  nuevo. Prueba primero con copia de seguridad; si el juego no lo muestra, usa el otro modo.

## Nombres de jugadores: carpeta del juego
El EDIT solo guarda los jugadores que se han editado alguna vez; los nombres y datos del
resto están dentro de los `.cpk` de la instalación. Pulsa **📁 Carpeta del juego…** y elige
la carpeta de instalación (la que contiene `Data` y `download`), normalmente:

`C:\Program Files (x86)\Steam\steamapps\common\eFootball PES 2021`

El programa busca `Player.bin` dentro de los `.cpk`, lo descomprime, reconoce su formato
comparando con los IDs de tus plantillas y muestra los nombres reales en plantillas,
fichajes y búsquedas. La ruta se recuerda y el resultado se guarda en caché, así que la
segunda vez es instantáneo. **No modifica nada de la carpeta del juego**: solo lee.

- Si el formato de la base coincide con el del EDIT, además verás posición, edad y media,
  y podrás **editar cualquier jugador**: al pulsar «Añadir al EDIT y aplicar» se copia al
  EDIT, igual que hace el juego cuando editas a alguien.
- Si solo se reconocen los nombres, esos jugadores se pueden fichar, dar de baja, cambiar
  de dorsal y nombrar capitán. Para editar sus habilidades, edítalos una vez en el juego.
- Si algo no cuadra, en esa misma ventana tienes el **informe** de la lectura y el botón
  **Guardar diagnóstico…**, que extrae los `Player.bin` y un `informe.txt` a una carpeta.

## Notas
- La **nacionalidad** es el código interno del juego. Para poner un país, mira el
  número que tiene otro jugador de ese país y cópialo.
- La "media" que se muestra es una media simple de habilidades para ordenar y
  comparar; no es la valoración oficial del juego.
- Solo para PES 2021 de PC. Los EDIT de PS4 o de otros PES usan otra clave y otros offsets.
- Los parches tipo SmokePatch/EvoWeb con su propio EDIT funcionan igual: edita el EDIT que estés usando.

## Archivos
- `pes21editor.py` — la interfaz.
- `pes21data.py` — lectura/escritura de jugadores, equipos, plantillas y alineaciones.
- `pes21crypt.py` — cifrado/descifrado del EDIT (port a Python de pesXdecrypter).
- `cpkreader.py` — lector de archivos `.cpk` de CRI con descompresión CRILAYLA.
- `gamedb.py` — lectura de `Player.bin`, detección automática del formato y caché.

## Créditos
El formato del archivo y la clave de cifrado proceden del trabajo de la comunidad:
[pesXdecrypter](https://github.com/the4chancup/pesXdecrypter) (dominio público) y
[4ccEditor](https://github.com/the4chancup/4ccEditor) (licencia zlib) de the4chancup.
Proyecto sin relación con Konami.
