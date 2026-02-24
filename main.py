import sys
import cv2
import glob
import numpy as np
import mediapipe as mp
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QSlider, QPushButton, QComboBox)
from PyQt5.QtCore import Qt, QTimer, QTime
from PyQt5.QtGui import QImage, QPixmap, QFont

mp_drawing = mp.solutions.drawing_utils
mp_pose = mp.solutions.pose

class PoseApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Detector de Articulaciones (MediaPipe + PyQt5)")
        self.resize(900, 700)
        self.setStyleSheet("background-color: #1e1e1e; color: #ffffff;")
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        
        # Título
        title_label = QLabel("Detección de Articulaciones en Tiempo Real")
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("padding: 10px; color: #4db8ff;")
        self.layout.addWidget(title_label)
        
        # Display de Video
        self.video_label = QLabel("Iniciando cámara...")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMinimumSize(640, 480)
        self.video_label.setStyleSheet("background-color: #000000; border: 2px solid #333333; border-radius: 5px;")
        self.layout.addWidget(self.video_label, stretch=1)
        
        # Panel de Controles
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(20, 10, 20, 10)
        self.layout.addLayout(controls_layout)
        
        # Confianza de Detección
        det_layout = QVBoxLayout()
        self.det_label = QLabel("Confianza de Detección: 50%")
        self.det_label.setFont(QFont("Arial", 10))
        self.det_slider = QSlider(Qt.Horizontal)
        self.det_slider.setRange(10, 100)
        self.det_slider.setValue(50)
        self.det_slider.setStyleSheet("""
            QSlider::groove:horizontal { border-radius: 4px; height: 8px; background: #333; }
            QSlider::handle:horizontal { background: #4db8ff; width: 16px; height: 16px; margin: -4px 0; border-radius: 8px; }
        """)
        self.det_slider.valueChanged.connect(self.update_det_label)
        det_layout.addWidget(self.det_label)
        det_layout.addWidget(self.det_slider)
        controls_layout.addLayout(det_layout)
        
        # Espaciador
        controls_layout.addSpacing(40)
        
        # Confianza de Rastreo
        trk_layout = QVBoxLayout()
        self.trk_label = QLabel("Confianza de Rastreo: 50%")
        self.trk_label.setFont(QFont("Arial", 10))
        self.trk_slider = QSlider(Qt.Horizontal)
        self.trk_slider.setRange(10, 100)
        self.trk_slider.setValue(50)
        self.trk_slider.setStyleSheet("""
            QSlider::groove:horizontal { border-radius: 4px; height: 8px; background: #333; }
            QSlider::handle:horizontal { background: #ff4d4d; width: 16px; height: 16px; margin: -4px 0; border-radius: 8px; }
        """)
        self.trk_slider.valueChanged.connect(self.update_trk_label)
        trk_layout.addWidget(self.trk_label)
        trk_layout.addWidget(self.trk_slider)
        controls_layout.addLayout(trk_layout)
        
        # --- Selector de Cámara ---
        cam_layout = QHBoxLayout()
        cam_label = QLabel("Seleccionar Cámara:")
        cam_label.setFont(QFont("Arial", 10))
        self.cam_combo = QComboBox()
        self.cam_combo.setStyleSheet("""
            QComboBox { background: #333; color: white; border-radius: 4px; padding: 4px; }
            QComboBox::drop-down { border: none; }
        """)
        self.scan_cameras() # Poblar el combobox con dev/video*
        self.cam_combo.currentIndexChanged.connect(self.change_camera)
        
        cam_layout.addWidget(cam_label)
        cam_layout.addWidget(self.cam_combo)
        cam_layout.addStretch()
        self.layout.addLayout(cam_layout)

        # Inicializar Dispositivo de Cámara
        self.cap = None
        self.change_camera(0)
        
        self.pose = None
        self.hands = None
        self.mp_hands = mp.solutions.hands
        self.init_models()
        
        # Buffer de tiempo para doble comprobación
        self.grip_timer = QTime()
        self.gripping_duration_ms = 0
        self.is_currently_gripping = False
        self.time_threshold_ms = 850  # 850 ms (casi 1 segundo completo de confirmación visual)
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30) # Aprox 30 FPS
        
    def scan_cameras(self):
        self.cam_combo.clear()
        # En Linux, las cámaras suelen montarse en /dev/video*
        # Revisamos del 0 al 9 en cv2 directamente, o leemos /dev/video*
        devices = glob.glob('/dev/video*')
        if not devices:
            self.cam_combo.addItem("Cámara por defecto (0)", 0)
            return
            
        for dev in sorted(devices):
            # Intentar deducir el índice del nombre (/dev/videoX -> X)
            try:
                idx = int(dev.replace('/dev/video', ''))
                self.cam_combo.addItem(f"Cámara {idx} ({dev})", idx)
            except ValueError:
                pass

    def change_camera(self, index):
        if self.cap:
            self.cap.release()
            
        cam_idx = self.cam_combo.itemData(index) if self.cam_combo.count() > 0 else 0
        self.cap = cv2.VideoCapture(cam_idx)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        if not self.cap.isOpened():
            self.video_label.setText(f"Error: No se puede acceder a la cámara {cam_idx}.\\nAsegúrate de mapear todos los dispositivos en Docker.")
            
    def init_models(self):
        if self.pose:
            self.pose.close()
        if self.hands:
            self.hands.close()
            
        min_det = self.det_slider.value() / 100.0
        min_trk = self.trk_slider.value() / 100.0
        self.pose = mp_pose.Pose(min_detection_confidence=min_det,
                                 min_tracking_confidence=min_trk)
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.6,
            min_tracking_confidence=0.6)

    def update_det_label(self, value):
        self.det_label.setText(f"Confianza de Detección: {value}%")
        self.init_models()

    def update_trk_label(self, value):
        self.trk_label.setText(f"Confianza de Rastreo: {value}%")
        self.init_models()
        
    def check_phone_grip(self, hand_landmarks):
        """
        Heurística estricta:
        Evita activar el positivo si la mano está simplemente abierta frente a la cámara.
        Comprobamos que los dedos estén flexionados midiendo la distancia relativa
        entre la punta (TIP) y la articulación base (MCP). Si la mano está abierta, 
        la punta está muy lejos de la base. Si está cerrada o sosteniendo un celular, 
        la punta se acerca a la base.
        """
        # (TIP, PIP (articulación media), MCP (base))
        fingers = [
            (self.mp_hands.HandLandmark.INDEX_FINGER_TIP, self.mp_hands.HandLandmark.INDEX_FINGER_PIP, self.mp_hands.HandLandmark.INDEX_FINGER_MCP),
            (self.mp_hands.HandLandmark.MIDDLE_FINGER_TIP, self.mp_hands.HandLandmark.MIDDLE_FINGER_PIP, self.mp_hands.HandLandmark.MIDDLE_FINGER_MCP),
            (self.mp_hands.HandLandmark.RING_FINGER_TIP, self.mp_hands.HandLandmark.RING_FINGER_PIP, self.mp_hands.HandLandmark.RING_FINGER_MCP),
            (self.mp_hands.HandLandmark.PINKY_TIP, self.mp_hands.HandLandmark.PINKY_PIP, self.mp_hands.HandLandmark.PINKY_MCP)
        ]
        
        curled_fingers = 0
        
        for tip_idx, pip_idx, mcp_idx in fingers:
            tip = hand_landmarks.landmark[tip_idx]
            pip = hand_landmarks.landmark[pip_idx]
            mcp = hand_landmarks.landmark[mcp_idx]
            
            # Condición 1: El dedo está doblado hacia abajo (TIP abajo de PIP)
            is_folded_down = tip.y > pip.y
            
            # Condición 2: El dedo envuelve algo (TIP está muy cerca de la base MCP en el eje 2D)
            # Una mano abierta tiene una distancia TIP-MCP grande (~0.15+ en coord normalizadas).
            # Una mano abrazando un celular tiene los dedos curvos acercando la punta a la palma (<0.10)
            dist_tip_to_base = np.sqrt((tip.x - mcp.x)**2 + (tip.y - mcp.y)**2)
            is_curled_around_object = dist_tip_to_base < 0.12 # Tolerancia para celular ancho
            
            if is_folded_down or is_curled_around_object:
                curled_fingers += 1
                
        # Pulgar
        thumb_tip_y = hand_landmarks.landmark[self.mp_hands.HandLandmark.THUMB_TIP].y
        thumb_mcp_y = hand_landmarks.landmark[self.mp_hands.HandLandmark.THUMB_MCP].y
        thumb_extended = thumb_tip_y < thumb_mcp_y # Apuntando hacia arriba
        
        # Para evitar el falso positivo de la mano totalmente abierta (foto), 
        # necesitamos que AL MENOS 2 dedos estén claramente curvados 
        # o 1 dedo fuertemente envuelto pero con el pulgar extendido.
        return curled_fingers >= 2 or (curled_fingers >= 1 and thumb_extended)
        
    def update_frame(self):
        if not self.cap.isOpened():
            return
            
        ret, frame = self.cap.read()
        if not ret:
            return
            
        # Reflejo para la cámara frontal (efecto espejo)
        frame = cv2.flip(frame, 1)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Procesar con MediaPipe Pose y Hands
        results = self.pose.process(rgb_frame)
        hands_results = self.hands.process(rgb_frame)
        
        # Analizar pose para teléfono y dibujar resultados (esqueleto)
        phone_detected = False
        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark
            
            # Obtener altura y ancho para las coordenadas normalizadas
            h, w, ch = rgb_frame.shape

            # === HEURÍSTICA: DETECTAR SI MIRA EL TELÉFONO ===
            # Extraer puntos clave (nariz, muñecas, codos)
            nose = landmarks[mp_pose.PoseLandmark.NOSE.value]
            left_wrist = landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value]
            right_wrist = landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value]
            left_elbow = landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value]
            right_elbow = landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value]
            left_shoulder = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value]
            right_shoulder = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value]

            # Verificar visibilidad de los puntos (para evitar falsos positivos si no se ven las manos)
            threshold_vis = 0.5
            
            # Condición: ¿Las manos están cerca de la altura de la cara (nariz/pecho) y los codos doblados?
            # En MediaPipe, Y=0 es arriba y Y=1 es abajo.
            
            looking_phone_left = False
            looking_phone_right = False
            
            # Brazo Izquierdo
            if (left_wrist.visibility > threshold_vis and 
                left_elbow.visibility > threshold_vis and 
                left_shoulder.visibility > threshold_vis):
                
                # Muñeca más alta (Y menor) que el codo y codo más bajo que el hombro
                if left_wrist.y < left_elbow.y and left_elbow.y > left_shoulder.y:
                    # Distancia Y de la muñeca a la nariz (cerca de la cara o pecho superior)
                    dist_y_nose = abs(left_wrist.y - nose.y)
                    # Las manos hacia el centro del cuerpo
                    dist_x_center = abs(left_wrist.x - nose.x)
                    
                    # Ampliamos tolerancia: hasta 0.55 abajo de la nariz en Y y 0.45 hacia los lados en X
                    if dist_y_nose < 0.55 and dist_x_center < 0.45:
                        looking_phone_left = True

            # Brazo Derecho
            if (right_wrist.visibility > threshold_vis and 
                right_elbow.visibility > threshold_vis and 
                right_shoulder.visibility > threshold_vis):
                
                if right_wrist.y < right_elbow.y and right_elbow.y > right_shoulder.y:
                    dist_y_nose = abs(right_wrist.y - nose.y)
                    dist_x_center = abs(right_wrist.x - nose.x)
                    
                    if dist_y_nose < 0.55 and dist_x_center < 0.45:
                        looking_phone_right = True


            # Dibujar Alerta si hay postura de celular
            if looking_phone_left or looking_phone_right:
                cv2.rectangle(rgb_frame, (10, 10), (w - 10, 60), (255, 165, 0), -1) # Fondo naranja 
                msg = "POSICION SOSPECHOSA..."
                cv2.putText(rgb_frame, msg, (w//2 - 180, 45), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 3, cv2.LINE_AA)
            
            # FASE 2: Confirmar con las manos si el brazo está en posición sospechosa
            momentary_grip_detected = False
            
            if (looking_phone_left or looking_phone_right) and hands_results.multi_hand_landmarks:
                for hand_landmarks in hands_results.multi_hand_landmarks:
                    if self.check_phone_grip(hand_landmarks):
                        momentary_grip_detected = True
                        # Dibujar puntos de la mano detectada simulando sostener algo
                        mp_drawing.draw_landmarks(
                            rgb_frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS,
                            landmark_drawing_spec=mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=2)
                        )

            # LÓGICA TEMPORAL (DOBLE COMPROBACIÓN - 1 SEGUNDO DE RETRASO)
            if momentary_grip_detected:
                if not self.is_currently_gripping:
                    # Empieza a contar el tiempo desde ahora
                    self.is_currently_gripping = True
                    self.grip_timer.start()
                else:
                    self.gripping_duration_ms = self.grip_timer.elapsed()
            else:
                # Si baja la mano o la abre, reseteamos el contador
                self.is_currently_gripping = False
                self.gripping_duration_ms = 0

            # Reemplazar alerta solo si lleva más del tiempo umbral (1 segundo) confirmando la postura ininterrumpidamente
            if self.is_currently_gripping and self.gripping_duration_ms > self.time_threshold_ms:
                cv2.rectangle(rgb_frame, (10, 10), (w - 10, 60), (255, 0, 0), -1) # Fondo rojo 
                msg = "¡CELULAR EN MANO CONFIRMADO!"
                cv2.putText(rgb_frame, msg, (w//2 - 240, 45), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 3, cv2.LINE_AA)
            elif self.is_currently_gripping:
                # Mostramos que estamos analizando para feedback visual
                cv2.rectangle(rgb_frame, (10, 10), (w - 10, 60), (255, 255, 0), -1) # Fondo amarillo/cyan
                # Animamos cargando
                dots = "." * ((self.gripping_duration_ms // 200) % 4)
                msg = f"ANALIZANDO EMPUÑADURA{dots}"
                cv2.putText(rgb_frame, msg, (w//2 - 200, 45), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2, cv2.LINE_AA)

            # Dibujar el esqueleto siempre
            mp_drawing.draw_landmarks(
                rgb_frame,
                results.pose_landmarks,
                mp_pose.POSE_CONNECTIONS,
                landmark_drawing_spec=mp_drawing.DrawingSpec(color=(77, 184, 255), thickness=3, circle_radius=4),
                connection_drawing_spec=mp_drawing.DrawingSpec(color=(255, 255, 255), thickness=2, circle_radius=2)
            )
            
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        
        qt_img = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        
        # Escalar preservando aspecto
        pixmap = QPixmap.fromImage(qt_img).scaled(
            self.video_label.width(), self.video_label.height(), 
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.video_label.setPixmap(pixmap)
        
    def closeEvent(self, event):
        self.cap.release()
        if self.pose:
            self.pose.close()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = PoseApp()
    window.show()
    sys.exit(app.exec_())
