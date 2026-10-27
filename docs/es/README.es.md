# Visor de Webcam OFM

[![Estado](https://img.shields.io/badge/estado-activo-2E7D32)](../../)
[![Python](https://img.shields.io/badge/python-3.11%2B-1565C0)](../../)
[![PyQt5](https://img.shields.io/badge/UI-PyQt5-7B1FA2?logo=qt&logoColor=white)](../../)
[![OpenCV](https://img.shields.io/badge/visión-OpenCV-C62828?logo=opencv&logoColor=white)](../../)
[![Sangaboard](https://img.shields.io/badge/plataforma-Sangaboard-E65100)](../../)
[![Microscopía](https://img.shields.io/badge/aplicación-Microscopía-F9A825)](../../)
[![Licencia](https://img.shields.io/badge/licencia-GPL--3.0-5D4037)](../../LICENSE)

**Idiomas:** [English](../../README.md) | Español

Aplicación desarrollada con PyQt5 y OpenCV para visualizar imágenes de cámaras web y capturar fotografías y grabaciones, con control opcional de una plataforma de precisión XYZ y enfoque automático de búsqueda gruesa a fina para sistemas de microscopía (basadas en Sangaboard).

> **Más documentación:** la [wiki para desarrolladores](../WIKI.md) explica la arquitectura y las funciones principales; [BUILDING.md](../BUILDING.md) describe cómo generar ejecutables, paquetes `.deb` e instalar mediante pip; [TRANSLATING.md](../TRANSLATING.md) explica cómo gestionar los idiomas de la interfaz.
>
> Este README se centra en cómo ejecutar la aplicación.

---

## Estructura del proyecto

```text
ofm-webcam-gui/
├── app.py                      # Punto de entrada: python app.py [--mode manual|automated|simulation] [--stage-port PORT] [--lang CODE] [--log-level DEBUG] [--save-log [PATH]]
├── LICENSE                     # Licencia Pública General de GNU v3 (también se muestra en la aplicación: About / License)
├── pyproject.toml              # Metadatos del paquete y dependencias (opcional: pip install .)
├── requirements/               # Listas de dependencias por plataforma (base / windows / linux; i18n para traductores)
├── core/                       # Tipos, configuración y cálculos independientes del framework (sin Qt ni E/S de cv2)
│   ├── types.py                #   Axis, Direction, Position, AxisCalibration, Resolution, ...
│   ├── version.py              #   Versión de la aplicación
│   ├── platform_info.py        #   Detección de plataforma y valores predeterminados por sistema operativo (PlatformProfile)
│   ├── app_mode.py             #   Enum AppMode: manual / automated / simulation
│   ├── app_info.py             #   Nombre de la aplicación, datos de la licencia, load_license_text()
│   ├── device_status.py        #   DeviceState / DeviceStatus: cómo informa un dispositivo "conectando / conectado / no detectado / perdido"
│   ├── logging_setup.py        #   Registro de la sesión: historial en memoria, archivo de registro opcional, captura de excepciones no controladas
│   ├── i18n.py                 #   Gestión de los idiomas de la interfaz durante la ejecución
│   ├── locales/                #   Catálogos de traducción
│   ├── config.py               #   Resoluciones, listas de backends, puertos predeterminados y carpeta de salida
│   ├── stage_motion.py         #   plan_jog(): cálculos de planificación de movimientos incrementales, comprobables mediante pruebas unitarias
│   ├── autofocus.py            #   Cálculos del enfoque automático: planificación del barrido, evaluación del enfoque y convergencia
│   ├── overlays.py             #   draw_grid() / draw_scale_bar(): dibujo de cuadrículas y barras de escala
│   └── scale_calibration.py    #   validate_um_per_pixel(): calibración física opcional para la barra de escala
├── hardware/                   # Capa de abstracción del hardware (sin importaciones de PyQt)
│   ├── abstract.py             #   StageController / CameraController / SensorController ABCs
│   ├── cameras.py              #   Lista cámaras conectadas por nombre (Windows: pygrabber; Linux: sysfs)
│   ├── errors.py               #   StageCommunicationError
│   └── stage/
│       ├── __init__.py         #   create_stage(mode, port) (creada, sin conectar) / create_real_stage() / create_mock_stage() / connect_real_stage()
│       ├── sangaboard.py       #   SangaboardStageController
│       ├── mock.py             #   MockStageController (simulación)
│       └── _position_tracking.py  # Seguimiento compartido de posiciones
├── ui/                         # Capa de presentación PyQt5
│   ├── startup.py              #   Inicio: selección de modo e idioma (no toca el hardware)
│   ├── language.py             #   Aplica y recuerda el idioma de la interfaz (integración Qt de core/i18n)
│   ├── main_window.py          #   QMainWindow: integra paneles e hilos y gestiona el estado de la aplicación
│   ├── stage_module.py         #   StageModule: controlador de la plataforma, conexión en segundo plano, panel, movimiento, enfoque y gestión de "no detectada / perdida"
│   ├── dialogs/                #   LogViewerDialog (registro de la sesión en vivo), AboutDialog (licencia)
│   ├── panels/                 #   CameraPanel, CapturePanel, StagePanel, DisplayPanel (widgets QGroupBox), LogBar (controles del registro en la barra de estado)
│   └── threads/                #   CameraThread, StageConnectThread, StageMovementThread, AutoFocusThread (QThread)
├── packaging/                  # Configuración de PyInstaller y scripts de compilación (véase BUILDING.md)
├── tools/i18n.py               # Herramientas de traducción (véase TRANSLATING.md)
└── docs/                       # WIKI.md, BUILDING.md, TRANSLATING.md y README.es.md
```

**La dirección de las dependencias es unidireccional:** `ui` → `hardware`/`core`, y `hardware` → `core`. Las capas `core` y `hardware` no importan PyQt, por lo que ambas pueden probarse mediante pruebas unitarias o reutilizarse sin interfaz gráfica. Consulta la [wiki](../WIKI.md) para conocer las ventajas de esta arquitectura y cómo navegar por el código.

---

## Instalación (ejecución desde el código fuente)

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# Windows:
pip install -r requirements/windows.txt

# Linux:
pip install -r requirements/linux.txt
```

### Linux: permisos del puerto serie USB (grupo `dialout`)

En Linux basado en Debian, los dispositivos serie USB (Sangaboard) aparece como `/dev/ttyACM*` o `/dev/ttyUSB*`. De forma predeterminada, solo `root` y los usuarios del grupo `dialout` pueden leerlos y escribir en ellos. Si la conexión con la plataforma falla por un error de permisos, añade tu usuario a ese grupo:

```bash
sudo usermod -aG dialout $USER
```

**Cierra la sesión y vuelve a iniciarla** (o reinicia el equipo) para aplicar la nueva pertenencia al grupo. Una terminal que ya estaba abierta no detectará automáticamente los nuevos permisos. Comprueba que se haya aplicado correctamente con:

```bash
groups        # debería mostrar "dialout"
ls -l /dev/ttyACM0   # o el puerto al que esté conectada la plataforma
```

Sin estos permisos, el modo automatizado no podrá abrir el puerto y mostrará un error explícito al iniciarse, con una indicación sobre el grupo necesario. Consulta la sección [Solución de problemas](#solución-de-problemas).

---

## Uso

```bash
python app.py                       # pregunta qué modo iniciar
python app.py --mode automated      # omite el diálogo
python app.py --mode manual
python app.py --mode simulation     # solo desde la línea de comandos; no aparece en el diálogo
python app.py --stage-port COM5     # fuerza el puerto serie de la plataforma
python app.py --lang es_419         # idioma de la interfaz para esta ejecución (inglés o español)
python app.py --log-level DEBUG
python app.py --save-log            # además, guarda el registro de la sesión en un archivo (véase "Registro de la sesión")
python app.py --save-log ~/lab/run1.log   # ...en un archivo a tu elección (o en una carpeta)
python app.py --help                # modos, funciones y ejemplos
```

Al iniciar, puedes seleccionar un modo en la pantalla de inicio o saltarte esa selección mediante `--mode`:

| Modo | Uso previsto | Controles de la plataforma | Comportamiento |
|---|---|---|---|
| **Automatizado** | Microscopio totalmente motorizado | Visibles, hardware real.
| **Manual** | Dispositivo sin motores | Solo selección de cámara, captura de fotografías y grabación. |
| **Simulación** | Probar el software sin hardware | Visibles, plataforma simulada | Solo desde la línea de comandos (`--mode simulation` o `--simulate`); no aparece en la pantalla de inicio. No se mueve ningún componente físico y el título de la ventana termina en `SIMULATION`. |

### Controles

1. **Cámara** —> Selecciona la cámara por nombre, el backend y la resolución; después, pulsa **Start Stream**. El botón de actualización (↻) vuelve a consultar la lista de cámaras cuando conectas una nueva.

2. **Capturas y grabación** —> Permite guardar fotografías en PNG o grabaciones en MP4. De forma predeterminada, los archivos se guardan en `gallery/` al ejecutar desde el repositorio, o en `~/Pictures/ofm-webcam-gui` al utilizar los ejecutables o una instalación mediante pip. El botón **Browse** permite seleccionar otra carpeta y **Open folder** abre la carpeta actual en el explorador de archivos. La opción *Burn timestamp* se encuentra debajo del botón de grabación.

3. **Control de la plataforma** —> Los controles U/D/L/R mueven los ejes XY (en español aparecen como Ar/Ab/Iz/De), mientras que W/S controlan el eje Z (enfoque). Incluye tamaños de paso, velocidad, lectura de posición en tiempo real y **Autofocus**, que realiza una búsqueda de enfoque gruesa a fina alrededor de la posición actual. Consulta la [wiki](../WIKI.md#coreautofocuspy--the-autofocus-search-as-pure-math) para conocer su funcionamiento.

4. **Visualización** —> Permite mostrar una cuadrícula de alineación (solo en la vista previa; nunca se guarda) y una barra de escala que se incorpora a las fotografías y grabaciones, en blanco o negro, según tu elección. De forma predeterminada, la barra muestra distancias en **píxeles** (por ejemplo, `100 px`), calculadas automáticamente a partir de la imagen, sin necesidad de configuración. La sección **Advanced**, contraída de forma predeterminada, permite introducir un valor físico real en µm/píxel si has calibrado el sistema. Consulta la sección [Configuración](#configuración).

---

## Configuración

**Puerto de la plataforma:** el modo automatizado intenta primero utilizar el puerto predeterminado de la plataforma (`DEFAULT_STAGE_PORT_WINDOWS` / `DEFAULT_STAGE_PORT_LINUX` en `core/config.py`) y, después, busca entre los puertos serie disponibles. Puedes especificar uno mediante `--stage-port` o pasar `port=` a `create_stage()` / `create_real_stage()` / `SangaboardStageController()` desde el código.

**Idioma de la interfaz:** se selecciona en el diálogo de inicio, donde la aplicación recuerda la elección entre ejecuciones, o mediante `--lang`. Para editar o añadir idiomas, consulta [TRANSLATING.md](../TRANSLATING.md).

**Ajustes del enfoque automático:** se configuran mediante `AutoFocusSettings()` en `StageModule._run_autofocus()` (`ui/stage_module.py`). Amplía `coarse_range_um` o aumenta `max_coarse_passes` si tu sistema necesita buscar más lejos de lo que permiten los valores predeterminados. Reduce `fine_range_um` o `fine_step_um` para conseguir mayor precisión, a costa de aumentar el tiempo de búsqueda.

**Barra de escala:** la barra predeterminada, expresada en píxeles, no requiere configuración. Si necesitas unidades físicas reales, abre la sección **Advanced** del panel **Display**, activa *Override with physical calibration* e introduce un valor en **µm/pixel**. Si todavía no dispones de una referencia de calibración, deja desactivada esta opción; la barra automática en píxeles sigue siendo útil para encuadrar y comparar imágenes.

---

## Requisitos de hardware

- **Controlador Sangaboard** mediante USB (puerto predeterminado `COM5` en Windows y `/dev/ttyACM0` en Linux). Requiere el paquete `sangaboard`. En Linux, el usuario debe pertenecer al grupo `dialout` (véase la sección anterior).
- **Nombres de las cámaras** en el menú desplegable: en Windows se obtienen mediante el paquete `pygrabber`, instalado por `requirements/windows.txt`. En Linux se leen directamente del sistema, sin paquetes adicionales. Si no se dispone de los nombres, el menú mostrará entradas genéricas como `Camera 0`, `Camera 1`, etc.

---

## Solución de problemas

**La cámara no se inicia** —> Selecciona otro dispositivo de la lista (↻ actualiza la lista), cambia el backend de Media Foundation a DirectShow en Windows, comprueba que ninguna otra aplicación esté utilizando la cámara y verifica que los controladores estén instalados.

**"Stage not detected" en Linux** —> Normalmente se debe a un problema de permisos o a que el usuario no pertenece al grupo `dialout`. Consulta [Linux: permisos del puerto serie USB](#linux-permisos-del-puerto-serie-usb-grupo-dialout). Comprueba también `/dev/tty*`, verifica que `sangaboard` esté instalado e intenta ejecutar `--stage-port /dev/ttyACM0`. El registro contiene el mensaje completo, que muestra los puertos serie que el sistema puede detectar. Después de corregir la causa, pulsa **Retry connection** (no es necesario reiniciar el programa; un cambio de grupo requiere iniciar sesión de nuevo).

**"Stage not detected" en Windows** —> Busca el puerto `COM*` de la placa en el Administrador de dispositivos y especifícalo mediante `--stage-port COM5`. Comprueba que `sangaboard` esté instalado, cierra cualquier otro programa que pueda estar utilizando el puerto y pulsa **Retry connection**.

**Aparece "Camera not detected" en el área de imagen** —> Selecciona otro dispositivo o backend y pulsa de nuevo **Start Stream**. Cierra otras aplicaciones que puedan estar utilizando la cámara.

**La interfaz sigue en inglés** —> Ejecuta `python app.py --lang es_419`. El selector de idioma solo aparece en el diálogo de inicio si hay una traducción instalada. Si el idioma que has añadido no aparece, consulta [TRANSLATING.md](../TRANSLATING.md).

**El enfoque automático no alcanza el enfoque correcto en un solo intento** —> Amplía `coarse_range_um` o aumenta `max_coarse_passes` en `AutoFocusSettings()` si la posición inicial habitual está más alejada del enfoque de lo que permiten los valores predeterminados. Si la búsqueda se detiene demasiado pronto con imágenes realmente desenfocadas, ajusta `min_relative_spread` en `has_weak_signal()` dentro de `core/autofocus.py`, teniendo en cuenta el nivel de ruido real de tu cámara. Consulta la [wiki](../WIKI.md#coreautofocuspy--the-autofocus-search-as-pure-math) para conocer el funcionamiento de la búsqueda.

**Errores de importación** —> Activa el entorno virtual, ejecuta `pip install -r requirements/<platform>.txt` y comprueba que utilizas Python 3.11 o una versión posterior.

---

## Uso de IA
Se utilizaron herramientas de IA como apoyo en la generación de código, depuración, refactorización y documentación. Todo el código debe revisarse y validarse, independientemente de su origen. Este proyecto sigue una política de prohibición de agentes autónomos de IA; los agentes de IA no pueden modificar ni contribuir al código de forma independiente.

## Licencia

Publicado bajo la **Licencia Pública General de GNU, versión 3**: consulta el archivo [`LICENSE`](../../LICENSE).
## Colaboradores

- Joaquín Acosta Aguilera, Caracara Tech
- Pierre Padilla-Huamantinco, Caracara Tech