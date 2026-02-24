FROM ubuntu:22.04                                                                

# Evitar prompts interactivos durante la instalación                               
ENV DEBIAN_FRONTEND=noninteractive

# Forzar el uso del backend xcb de QT y no el de cv2 xcb
ENV QT_DEBUG_PLUGINS=1
ENV QT_QPA_PLATFORM_PLUGIN_PATH=/usr/lib/x86_64-linux-gnu/qt5/plugins/platforms

# Instalar Python, PyQt5 y librerías del sistema necesarias para renderizado y cámara
RUN apt-get update && apt-get install -y \                                       
    python3 \                                                                    
    python3-pip \                                                                
    python3-pyqt5 \                                                              
    python3-opencv \
    && rm -rf /var/lib/apt/lists/*                                               

WORKDIR /app                                                                     

# Copiar configuración de dependencias python e instalarlas                      
COPY requirements.txt .                                                          
RUN pip3 install --no-cache-dir -r requirements.txt && pip3 uninstall -y opencv-python opencv-python-headless opencv-contrib-python || true                              

# Copiar el script principal                                                     
COPY main.py .                                                                   

CMD ["python3", "main.py"]
