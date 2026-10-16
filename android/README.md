# LASRecomp para Android: desarrollo y actualizaciones

Objetivo: Retroid Pocket 6, 8 GB, Android 13, ARM64. Resolucion interna inicial
prevista: 720p, pendiente de medir en el dispositivo.

**Estado: base de desarrollo. No hay APK ni version jugable.** La compilacion
actual produce una biblioteca estatica con 22 archivos compartidos del runtime,
para detectar incompatibilidades con el NDK y Bionic. No enlaza el juego ni prueba
Vulkan, sonido, controles, consumo de RAM o funcionamiento en la Retroid.

## Organizacion

- `upstream`: repositorio original, https://github.com/peiikai/LASRecomp.git.
- `upstream-base`: referencia local a la revision original al iniciar este port.
- `codex/android`: desarrollo e integracion del port.
- `codex/android-testing`: candidatos para pruebas; inicialmente igual a desarrollo.
- `codex/android-stable`: reservada para la primera version jugable probada.
  **Aun no existe.** Una compilacion de parte del codigo no acredita estabilidad.
- `android/port.json`: objetivo, herramientas y revision original ya incorporada.

Concentrar el soporte Android en `android/`, `tools/android/` y, cuando se
implemente, `runtime/platform/android.c`. Mantener pequenos los cambios al codigo
compartido y evitar copiar el motor: las mejoras del original deben seguir entrando
por Git. El primer cambio compartido excluye Android del adaptador de glibc;
Android utiliza Bionic y ya proporciona esas funciones.

## Comprobaciones locales

Con Python 3, Git, CMake, Ninja y NDK 28.2.13676358:

```powershell
python tools/android/build_core.py
python tools/android/test_sync.py
python tools/android/sync_upstream.py check
```

El compilador detecta el SDK habitual de Windows o `ANDROID_HOME` /
`ANDROID_SDK_ROOT`. Tambien acepta `--ndk`, `--cmake` y `--ninja`.
Los resultados quedan en `build/android/core/result.json`. Los archivos del juego
no hacen falta para estas comprobaciones.

## Incorporar actualizaciones

Con los cambios locales ya guardados en un commit:

```powershell
python tools/android/sync_upstream.py prepare
python tools/android/check_candidate.py
```

La preparacion consulta `main` del original, congela la revision y clona el port
en una carpeta nueva dentro de `build/android/upstream/`. Alli intenta fusionar
los cambios en `codex/android-testing`. Nunca cambia HEAD, archivos, ramas o
guardados del checkout de trabajo. Tampoco publica nada.

El informe `build/android/upstream/latest.json` registra los commits, archivos
afectados, conflictos y si el cambio puede requerir regenerar el codigo del juego.
Una fusion limpia produce ademas un archivo `.bundle` con el candidato y su
historial Git. Un conflicto, un cambio de historial del original o una rama que
cambia durante la descarga detiene la preparacion. Se conserva el checkout del
candidato para inspeccion. Si no hay cambios, no crea un candidato.

`check_candidate.py` compila el candidato indicado por el ultimo informe. Si hubo
un conflicto, se detiene: no informa una compilacion del codigo anterior como si
hubiera probado la actualizacion.

Para abrir un candidato descargado desde GitHub, usar un directorio nuevo:

```powershell
git clone -b codex/android-testing RUTA-AL-CANDIDATO.bundle LASRecomp-pruebas
```

Cuando el candidato sea correcto, integrarlo en desarrollo sin perder historia:

```powershell
git fetch RUTA-AL-CANDIDATO codex/android-testing
git merge --ff-only FETCH_HEAD
```

Si hubo nuevos cambios locales, `--ff-only` se detiene y la integracion requiere
revision. Nunca usar un reset forzado para resolver ese caso.

## Comprobacion diaria en GitHub

`.github/workflows/android.yml` contiene la comprobacion de cada push y una
ejecucion diaria prevista a las **06:17 de Argentina** (09:17 UTC; GitHub puede
demorarla). Las ejecuciones diarias/manuales preparan un candidato aislado,
compilan el mismo subconjunto nativo y guardan informe/bundle por 14 dias.
No generan APK ni promueven versiones estables en esta etapa.

**Todavia no esta activa:** este repositorio es local y no tiene remoto `origin`.
Para activarla hay que publicar el fork en la cuenta del usuario, configurar
`codex/android` como rama predeterminada y habilitar Actions si corresponde.
Los cron de Actions se ejecutan desde la rama predeterminada. El flujo usa solo
permisos de lectura; no puede modificar ramas ni crear releases. No precisa
subir archivos del juego, codigo generado ni claves de firma.

## Antes de declarar una version estable

Falta implementar y verificar:

1. Host Android: memoria, ciclo de vida, almacenamiento privado y carga del juego.
2. SDL3, Vulkan, shaderc y FFmpeg para Android; enlace del runtime completo.
3. Aplicacion Android y proceso de preparacion local del juego desde PC.
4. Controles fisicos de la Retroid y comportamiento al suspender/reanudar.
5. Prueba de una zona jugable, audio, guardado/carga y memoria en la Retroid de 8 GB.

Registrar el commit exacto, version del APK, dispositivo, resultados y problemas
pendientes. Crear `codex/android-stable` solo tras esa validacion. Conservar el APK
estable previo y la misma firma/identificador para futuras actualizaciones.
Respaldar las partidas antes de pruebas; volver a un APK anterior puede requerir
reinstalarlo y no garantiza compatibilidad con partidas de una version nueva.

La clave de firma se creara y respaldara al preparar el primer APK distribuible;
no debe formar parte del repositorio. Si el original cambia el generador o la ABI,
puede ser necesario regenerar la biblioteca desde los archivos propios del juego,
ademas de actualizar el APK.
