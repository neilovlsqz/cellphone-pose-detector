# Detector de Pose y Celular en Mano (MediaPipe + PyQt5 + Docker)

Esta aplicación detecta en tiempo real las posturas corporales (pose estimation) usando **MediaPipe**, y está especializada en identificar a través de heurística geométrica si un usuario está distraído mirando un celular en la mano. Cuenta con una interfaz moderna desarrollada en **PyQt5** y está completamente dockerizada para funcionar en sistemas Linux sin problemas de dependencias gráficas cruzadas (X11/XCB).

## Características
*   **Detección de Pose (33 Puntos Clave):** Rastreo de todo el tren superior y dibujo en tiempo real del esqueleto.
*   **Tolerancia Geométrica Afinada:** Detecta celulares cuando la mano está frente al pecho, cara u hombros. Se adapta a agarres naturales donde los dedos envuelven el dispositivo por el costado.
*   **MediaPipe Hands en Simultáneo:** Para evitar falsos positivos al levantar el brazo o tener la mano abierta, se enciende el modelo de Manos para verificar hiper-puntos (21 por mano).
*   **Doble Comprobación Temporal (Buffer):** Se requiere sostener la postura sospechosa durante casi 1 segundo para disparar una alerta confirmada, evitando *flasheos* causados por un frame defectuoso o un simple rascarse la cara.
*   **Hot-Swap de Cámaras USB:** Selector en la interfaz que escanea y permite intercambiar la cámara web en tiempo real sin reiniciar el contenedor.
*   **Docker Plug-and-Play:** Monta tu sistema de ventanas X11 automáticamente. Adiós al clásico error `qt.qpa.plugin: Could not load the Qt platform plugin "xcb"`.

## Estructura del Proyecto

*   `main.py`: Código principal en Python con la arquitectura de la ventana PyQt5 y los bucles de `cv2` / MediaPipe.
*   `Dockerfile`: Imagen base optimizada basada en `ubuntu:22.04` instalando las librerías nativas de Qt5 y OpenCV vía `apt-get` para coincidir perfectamente con el display host.
*   `requirements.txt`: Dependencias de Python puro (Nota: Mediapipe y la versión específica de Numpy para evitar quiebres de OpenCV `core.multiarray`).
*   `run.sh`: Script en Bash que construye, autoriza el puerto X11 local, inyecta **TODAS** las cámaras disponibles de `/dev/video*` y lanza el contenedor.

## Requisitos Previos

Solamente necesitas:
1. Un sistema operativo basado en Linux (Probado en Ubuntu).
2. [Docker](https://docs.docker.com/engine/install/) u o equivalente.
3. Una Webcam USB conectada.

## Instrucciones de Uso

1.  Clona o descarga este repositorio y entra en su directorio.
2.  Asegúrate que el script tenga permisos de ejecución:
    ```bash
    chmod +x run.sh
    ```
3.  Lanza la aplicación (el script hará automáticamente el build de Docker si es la primera vez e inyectará los permisos gráficos):
    ```bash
    ./run.sh
    ```

## 🔍 Reglas Heurísticas (Cómo funciona)

La App cruza dos modelos de Meta (Google): **Pose** y **Hands**.
1. **Fase 1 (Naranja - Sospecha):** Evalúa si la muñeca está más alta que el codo, el codo debajo del hombro, y la mano se acerca al eje central del pecho/espalda con una distancia vertical cercana a la nariz. Si entras en esta postura sospechosa, se enciende la *Fase 2.*
2. **Fase 2 (Verde/Amarillo - Analizando):** El procesador busca hiper-puntos en tu mano. Usando trigonometría bidimensional, mide qué tan lejos está la punta de tus dedos (TIP) de tus nudillos (MCP), para comprobar que la mano no está plana/abierta. Si al menos 2 dedos cierran sobre el centro o envuelven un objeto, inicia la comprobación "Amarilla" y arranca un contador de **850ms**.
3. **Fase 3 (Roja - Distracción Confirmada):** Si logras mantener la mano cerrada y el brazo en la misma zona de castigo por 850 milisegundos, el sistema lanza la confirmación oficial.

---

<p align="center">Creado con usando Python, OpenCV y MediaPipe</p>
