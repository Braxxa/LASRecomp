# LASRecomp para Android

Port experimental ARM64 para Retroid Pocket 6 de 8 GB, Android 13 y Adreno 740.
Ya enlaza el runtime completo y el juego recompilado. Se ha ejecutado una partida
real: introduccion, seleccion de partida, casa de Marin y Tarin, movimiento,
dialogos, recepcion del escudo, salida a Aldea Mabe y guardado/carga.
El usuario confirmo el audio de la introduccion.

**No es una version estable ni se ha probado el juego completo.** Hay defectos
graficos y el rendimiento depende de la escena. Consultar
[la validacion del dispositivo](validation-retroid-pocket-6.md) para el alcance
exacto de las pruebas y los problemas pendientes.

## Uso en la consola

Abrir **LAS Recomp** y pulsar **Jugar**. En el titulo se entra con **L + R**.
El stick izquierdo mueve a Link; los botones se asignan por posicion como en
Switch (A a la derecha, B abajo). Start abre el inventario; R cambia a la pestaña
del menu donde estan Guardar/Cargar. Select + Start abre los ajustes del port.
La primera visita a una zona puede tardar mientras se compilan shaders.

El APK personal lleva el codigo recompilado; sus recursos se guardan aparte en
el directorio privado externo de la aplicacion. No necesita claves en la consola.
Actualizar con la misma firma e identificador conserva los datos. Desinstalar
elimina esos datos: respaldar los guardados antes.

## Compilacion personal en PC

Se necesitan los archivos propios de la version base 1.0.0 en
`extracted/exefs/{main,sdk}` y `extracted/romfs`, Python 3 con las dependencias del
generador, CMake/Ninja, Android SDK 34, NDK 28.2.13676358, Java 21 y Gradle 9.3.
El generador requiere capstone, unicorn y lz4; se prefiere `tools/venv` cuando
existe. Usar un checkout completo con `third_party/`.

Las bibliotecas publicas FFmpeg, shaderc, Vulkan y VMA se construyen con
`tools/android/build_deps.sh` en Linux, con `ANDROID_NDK_HOME` apuntando al NDK.
Tambien pueden descargarse del artefacto `android-public-deps-arm64` de
[Android dependencies](https://github.com/Braxxa/LASRecomp/actions/workflows/android-deps.yml).
Extraer su contenido en `build/android/deps/` (debe contener `include/` y `lib/`).
SDL3 y DejaVu Sans se descargan de versiones oficiales verificadas por SHA-256.

```powershell
python tools/android/build_apk.py --personal --java-home 'RUTA/AL/JDK-21'
python tools/android/deploy.py --serial SERIAL --apk build/android/output/LASRecomp-Android-personal.apk
```

`build_apk.py` detecta el SDK habitual de Windows o `ANDROID_HOME`. Acepta
`--sdk` y `--gradle`. La primera compilacion genera y compila el codigo personal;
las siguientes reutilizan las salidas si coinciden el juego y la ABI del generador.
`--package-only` sirve exclusivamente para cambios de Java/manifest: omite la
compilacion nativa y exige bibliotecas ya compiladas del modo correcto.

Para transferir recursos por USB, abrir primero la aplicacion una vez:

```powershell
python tools/android/deploy.py --serial SERIAL --assets
```

Alternativamente, copiar `extracted` a una carpeta seleccionable de la consola y
usar **Importar archivos del juego**. Esta importacion por selector de Android
todavia no tiene una prueba completa en hardware; la transferencia USB si.
La primera apertura construye `romfs.bin` localmente: reservar unos 14 GB libres
para recursos, imagen y aplicacion. Los guardados estan en
`Android/data/io.github.braxxa.lasrecomp/files/save/`.

**No publicar el APK personal, el codigo generado, recursos, contenedores ni
claves.** Todos quedan en directorios ignorados por Git. El repositorio publico
solo contiene el port y herramientas. El APK de CI sin `--personal` sirve para
probar el runtime y diagnostico grafico: no contiene el codigo del juego y no
permite jugar por si solo. La firma debug es local; conservar el mismo keystore
para actualizar una instalacion existente.

## Host y renderer

El host usa SDL3, Vulkan, FFmpeg y shaderc, con el juego en un proceso separado.
Android dispone de su propia reserva de memoria invitada, rutas, registro,
preparacion de RomFS y control del ciclo de vida. La fuente libre DejaVu Sans
incluye el glifo de sustitucion que necesita la biblioteca de texto del juego.

El Adreno probado no ofrece `shaderInt64` ni importacion de punteros de host.
El traductor GLSL utiliza pares de enteros de 32 bits y el renderer carga y
recupera los rangos de almacenamiento necesarios, con sincronizacion explicita.
El diagnostico compara 6144 resultados aritmeticos de GPU con la referencia CPU.
Esta ruta conservadora todavia requiere optimizacion.

## Actualizaciones del original

`upstream` apunta a https://github.com/peiikai/LASRecomp.git y `origin` al fork
[Braxxa/LASRecomp](https://github.com/Braxxa/LASRecomp). La rama de desarrollo y
predeterminada es `codex/android`; `codex/android-testing` recibe candidatos.
`codex/android-stable` sigue reservada: aun no existe una version estable.
`android/port.json` registra la revision original incorporada.

Con los cambios locales guardados en un commit:

```powershell
python tools/android/test_sync.py
python tools/android/sync_upstream.py prepare
python tools/android/check_candidate.py
```

La preparacion consulta el original, congela su revision y crea un checkout
aislado dentro de `build/android/upstream/`. Intenta fusionar en una rama de
pruebas sin modificar el checkout activo ni los guardados. Genera un informe y,
si la fusion es limpia, un `.bundle`. Se detiene ante conflictos, cambios de
historial o una rama que cambia durante la descarga. `check_candidate.py`
compila el subconjunto nativo del candidato, nunca el codigo anterior como si
fuera el actualizado. El subconjunto no sustituye las pruebas del runtime completo.

Cuando el candidato se haya revisado, compilar el APK personal en ese checkout
y probar en la consola carga, movimiento, audio y guardado antes de integrarlo.
Si cambia el generador/ABI, `prepare_code.py` regenera desde los archivos propios.
Un merge limpio no garantiza compatibilidad; no se instala automaticamente.

## GitHub Actions

- `android.yml`: comprueba merges/conflictos y compila 22 archivos del nucleo.
  Diariamente, a las 09:17 UTC (06:17 Argentina, sujeto a demoras de GitHub),
  prepara candidatos del original y conserva informe/bundle durante 14 dias.
- `android-deps.yml`: compila dependencias publicas fijadas por version y hash.
- `android-runtime.yml`: compila el runtime completo y empaqueta un APK sin juego
  en pushes a desarrollo/pruebas, PR y ejecucion manual. No usa archivos privados.

Todos tienen permisos de lectura del repositorio. Los flujos no promueven
versiones estables ni reemplazan el APK personal de la consola. Una actualizacion
del original sigue pasando por fusion, compilacion y prueba de juego real.
