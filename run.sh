#!/bin/bash

# Script de ejecución para el contenedor
# Recopilar todos los dispositivos de video existentes
DEVICES=""
for cam in /dev/video*; do
    if [ -e "$cam" ]; then
        DEVICES="$DEVICES --device=$cam:$cam"
    fi
done

if [ -z "$DEVICES" ]; then
    echo "=========================================================="
    echo " Advertencia: No se encontraron cámaras en /dev/video*"
    echo " El contenedor iniciará de todos modos pero no habrá video."
    echo "=========================================================="
fi

echo "[1/3] Otorgando permisos a X11 localmente para lanzar interfaces gráficas desde Docker..."
xhost +local:docker

echo "[2/3] Construyendo imagen de Docker 'pose-app-img'..."
docker build -t pose-app-img .

echo "[3/3] Iniciando la App. Mapeando dispositivos: $DEVICES"
docker run --rm -it \
    --name my-pose-app \
    --net host \
    -e DISPLAY=$DISPLAY \
    -e QT_X11_NO_MITSHM=1 \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    $DEVICES \
    pose-app-img

echo "[!] Contenedor finalizado. Revocando permisos a X11..."
xhost -local:docker
