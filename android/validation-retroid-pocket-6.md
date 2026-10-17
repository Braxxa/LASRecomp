# Validacion experimental: Retroid Pocket 6

Fecha local: 16 de octubre de 2026. APK `0.1.0-experimental`, versionCode 2,
paquete `io.github.braxxa.lasrecomp`, ABI `arm64-v8a`, Android minimo 13.
Base original incorporada: `6244eb9d4d3497094e21cac7dabe998ded1f2800`.
Dispositivo fisico: Retroid Pocket 6 de 8 GB, Android 13, Adreno 740,
driver Vulkan 1.3.128. Se uso el driver del sistema.

## Resultado comprobado

- Compilacion del runtime completo, biblioteca personal ARM64 y APK instalable.
- Instalacion mediante ADB y actualizacion sin desinstalar ni perder los datos.
- Video inicial; el usuario confirmo que se escucha su audio.
- Titulo L+R, seleccion de partida, partida nueva en modo normal con nombre Link.
- Dialogos y movimiento en la casa de Marin/Tarin; entrega del escudo.
- Inventario con el escudo y transicion al exterior de Aldea Mabe.
- Guardado manual desde el menu del juego, respaldo local y cierre del proceso.
- Tras actualizar el APK, seleccion y carga del mismo archivo en Aldea Mabe
  con el escudo. Tambien se observaron escrituras de guardado automatico.
- Salir a Inicio y volver a la misma sesion: mismo proceso, recreacion de la
  superficie Vulkan y movimiento posterior. Una prueba, no un ensayo prolongado.
- Pantalla horizontal completa sin la franja que recortaba corazones/FPS.
- Diagnostico del APK final: 6144 resultados aritmeticos de GPU coinciden con
  la referencia CPU de 64 bits y se presentaron 180 cuadros en hardware real.
- El usuario confirmo expresamente movimiento con el stick fisico y sonido
  durante la partida en Aldea Mabe.
- Seis pruebas del mecanismo de actualizacion: todas correctas.

Los registros, capturas, respaldo de guardados y APK personal se conservan
localmente en `build/android/`, excluido de Git. No se publican recursos ni
codigo generado del juego. El manifiesto local de entrega registra el hash
del APK final; el constructor por si solo no marca una compilacion como jugable.

## Rendimiento observado

Son observaciones del contador y registros durante las primeras escenas,
no un benchmark de toda la aventura ni una garantia de minimos sostenidos.

| Escena/perfil | Observacion |
| --- | --- |
| Casa de Marin/Tarin, resolucion interna 1x (1080p) | Aproximadamente 30 FPS tras cargar shaders |
| Aldea Mabe, 1x (1080p) | Aproximadamente 15-20 FPS |
| Aldea Mabe, 75% de pantalla (1440x810), desenfoque desactivado | Alrededor de 20 FPS en el punto probado |
| Aldea Mabe, 50% (960x540), desenfoque desactivado | Alrededor de 20 FPS; bajar mas no resolvio el cuello de botella |

El perfil inicial para instalaciones nuevas usa 75%, bilineal, sin AA y sin
desenfoque. Los ajustes existentes se conservan al actualizar. En la prueba a
540p, `dumpsys meminfo` indico unos 1,65 GiB de PSS y 1,74 GiB de RSS del
proceso del juego; no se midio el maximo de todas las zonas.

## Problemas pendientes

- Manchas negras y defectos de profundidad en vegetacion/terreno, que pueden
  variar al mover la camara. El ajuste de tolerancia EQUAL ya existente se probo
  y empeoro otras partes de la escena: no se dejo activado.
- El exterior aun no mantiene 30 FPS. La ruta sin importacion de memoria de host
  usa copias y esperas explicitas; requiere optimizacion.
- La primera carga/compilacion de shaders puede mostrar pantalla negra y tirones.
- No se probaron mazmorras, combate, aventura completa, sesiones largas,
  suspension prolongada, otras versiones de Android ni otros dispositivos.
- El selector de carpetas para importar recursos aun requiere prueba completa;
  para esta validacion se uso la transferencia USB con el UID de la aplicacion.
- No hay firma de distribucion ni actualizador de APK dentro de la aplicacion.
  La instalacion personal actual usa una firma debug local conservada para updates.

Se acredita una primera version minimamente jugable en las zonas descritas.
No se crea una rama estable ni se afirma compatibilidad con todo el juego.
