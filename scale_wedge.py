import json
import os
import re
import sys
import time
import threading
import ctypes
import tkinter as tk
from tkinter import messagebox

try:
    import serial
except ImportError:
    serial = None

try:
    import keyboard
except ImportError:
    keyboard = None

try:
    from pynput import keyboard as pynput_keyboard
except ImportError:
    pynput_keyboard = None

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "port": "COM3",
    "baudrate": 9600,
    "trigger_key": "f2",
    "decimal_separator": ".",
    "hud_position": "+1150+20",
    "hud_width": 210,
    "hud_height": 75,
    "mock_mode": False,
    "auto_mock_on_error": True
}

def ensure_single_instance():
    """Garantiza que solo exista 1 única instancia ejecutándose en Windows."""
    try:
        kernel32 = ctypes.windll.kernel32
        mutex_name = "Global\\ScaleWedgePOS_SingleInstance_Mutex"
        mutex = kernel32.CreateMutexW(None, True, mutex_name)
        ERROR_ALREADY_EXISTS = 183
        if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            return None
        return mutex
    except Exception:
        return True

def win32_type_text(text):
    """Escribe texto directamente en la ventana activa utilizando Windows SendInput UNICODE."""
    try:
        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ("wVk", ctypes.c_ushort),
                ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
            ]

        class INPUT(ctypes.Structure):
            _fields_ = [
                ("type", ctypes.c_ulong),
                ("ki", KEYBDINPUT)
            ]

        INPUT_KEYBOARD = 1
        KEYEVENTF_UNICODE = 0x0004
        KEYEVENTF_KEYUP = 0x0002

        for char in text:
            code = ord(char)
            inp_down = INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wVk=0, wScan=code, dwFlags=KEYEVENTF_UNICODE, time=0, dwExtraInfo=None))
            ctypes.windll.user32.SendInput(1, ctypes.byref(inp_down), ctypes.sizeof(INPUT))
            inp_up = INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wVk=0, wScan=code, dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, time=0, dwExtraInfo=None))
            ctypes.windll.user32.SendInput(1, ctypes.byref(inp_up), ctypes.sizeof(INPUT))
        return True
    except Exception as e:
        print(f"Error en win32_type_text: {e}")
        return False

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                merged = DEFAULT_CONFIG.copy()
                merged.update(config)
                return merged
        except Exception as e:
            print(f"Error cargando {CONFIG_FILE}: {e}")
    return DEFAULT_CONFIG.copy()

def save_config(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"Error guardando {CONFIG_FILE}: {e}")

class ScaleBridgeApp:
    def __init__(self):
        self.config = load_config()
        self.current_weight = "0.000"
        self.status_msg = "Inicializando..."
        self.is_connected = False
        self.is_mock = self.config.get("mock_mode", False)
        self.running = True
        self.last_injection_time = 0
        self.lock = threading.Lock()
        self.active_ser = None
        self.pynput_listener = None
        self.reconnect_requested = False

        if self.is_mock:
            self.current_weight = "1.450"

        # Iniciar hilo de lectura serial en tiempo real
        self.serial_thread = threading.Thread(target=self._serial_worker, daemon=True)
        self.serial_thread.start()

        # Configurar Hotkey global
        self._setup_hotkey()

        # Crear Interfaz Gráfica (Tkinter)
        self._create_hud()

    def _setup_hotkey(self):
        trigger_key = self.config.get("trigger_key", "f2").lower()

        if keyboard:
            try:
                keyboard.clear_all_hotkeys()
                keyboard.add_hotkey(trigger_key, self._on_hotkey_pressed)
                print(f"Hotkey registrado con 'keyboard': {trigger_key.upper()}")
            except Exception as e:
                print(f"Error registrando hotkey con 'keyboard': {e}")

        if pynput_keyboard:
            def on_press(key):
                try:
                    key_name = None
                    if hasattr(key, 'name') and key.name:
                        key_name = key.name.lower()
                    elif hasattr(key, 'char') and key.char:
                        key_name = key.char.lower()

                    if key_name == trigger_key:
                        self._on_hotkey_pressed()
                except Exception:
                    pass

            try:
                self.pynput_listener = pynput_keyboard.Listener(on_press=on_press)
                self.pynput_listener.daemon = True
                self.pynput_listener.start()
                print(f"Hotkey listener de 'pynput' iniciado para {trigger_key.upper()}")
            except Exception as e:
                print(f"Error iniciando pynput listener: {e}")

    def _on_hotkey_pressed(self):
        now = time.time()
        if now - self.last_injection_time < 0.3:
            return
        self.last_injection_time = now
        self._inject_weight()

    def _retry_rs232_connection(self):
        """Fuerza reconexión limpia al puerto RS-232 en tiempo real."""
        port = self.config.get("port", "COM3")
        print(f"Fuerza reconexión al puerto RS-232 {port}...")
        with self.lock:
            self.is_mock = False
            self.reconnect_requested = True
            self.status_msg = f"Conectando {port}..."
            self.is_connected = False

        if hasattr(self, "canvas_status"):
            self.canvas_status.itemconfig(self.status_dot, fill="#EAB308")

    def _close_active_serial(self):
        if self.active_ser:
            try:
                if self.active_ser.is_open:
                    self.active_ser.close()
            except Exception as e:
                print(f"Error cerrando puerto serial: {e}")
            finally:
                self.active_ser = None

    def _serial_worker(self):
        """Hilo dedicado a la lectura e interpretación en TIEMPO REAL del puerto serial RS-232."""
        buffer_str = ""

        while self.running:
            with self.lock:
                is_mock = self.is_mock
                reconnect = self.reconnect_requested
                if reconnect:
                    self.reconnect_requested = False

            if is_mock and not reconnect:
                self._close_active_serial()
                with self.lock:
                    self.status_msg = "Modo Simulación"
                    self.is_connected = True
                time.sleep(0.2)
                continue

            port = self.config.get("port", "COM3")
            baudrate = self.config.get("baudrate", 9600)

            if not serial:
                with self.lock:
                    self.status_msg = "pyserial no instalado"
                    self.is_connected = False
                    self.is_mock = True
                time.sleep(2)
                continue

            self._close_active_serial()
            try:
                print(f"Conectando al puerto {port} ({baudrate} baudios)...")
                self.active_ser = serial.Serial(
                    port=port,
                    baudrate=baudrate,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=0.1
                )
                
                with self.lock:
                    self.status_msg = f"Conectado ({port})"
                    self.is_connected = True
                    self.is_mock = False

                buffer_str = ""

                # Bucle de lectura de alta frecuencia en tiempo real (50ms por iteración)
                while self.running and not self.is_mock and not self.reconnect_requested:
                    if self.active_ser and self.active_ser.is_open:
                        try:
                            waiting = self.active_ser.in_waiting
                            if waiting > 0:
                                raw_bytes = self.active_ser.read(waiting)
                                decoded = raw_bytes.decode("latin-1", errors="ignore")
                                buffer_str += decoded

                                # Dividir la trama por saltos de línea \n o retornos de carro \r
                                frames = re.split(r"[\r\n]+", buffer_str)

                                # Guardar el residuo no terminado en el buffer
                                buffer_str = frames[-1] if len(frames) > 1 else buffer_str
                                complete_frames = frames[:-1] if len(frames) > 1 else []

                                # Procesar la trama completa MÁS RECIENTE enviada por la báscula
                                if complete_frames:
                                    latest_frame = complete_frames[-1].strip()
                                    if latest_frame:
                                        match = re.search(r"[-+]?\s*(\d+[\.,]\d+|\d+)", latest_frame)
                                        if match:
                                            raw_val = match.group(1).replace(",", ".")
                                            try:
                                                val_float = float(raw_val)
                                                formatted = f"{val_float:.3f}"
                                                with self.lock:
                                                    self.current_weight = formatted
                                            except ValueError:
                                                pass

                        except Exception as read_err:
                            print(f"Error de lectura serial en tiempo real: {read_err}")
                            break

                    time.sleep(0.03)

                self._close_active_serial()

            except Exception as e:
                self._close_active_serial()
                with self.lock:
                    self.status_msg = f"Sin Balanza ({port})"
                    self.is_connected = False

                print(f"No se pudo conectar a {port}: {e}")
                
                if self.config.get("auto_mock_on_error", True):
                    print("Báscula no detectada. Activando modo simulación automático.")
                    with self.lock:
                        self.is_mock = True
                        if self.current_weight == "0.000":
                            self.current_weight = "1.450"

                time.sleep(2.0)

    def _inject_weight(self):
        with self.lock:
            weight = self.current_weight

        if weight in ["ERR", ""]:
            print("Peso no válido para inyectar.")
            return

        sep = self.config.get("decimal_separator", ".")
        weight_str = weight.replace(".", sep)

        injected = False
        if keyboard:
            try:
                keyboard.write(weight_str)
                injected = True
            except Exception as e:
                print(f"keyboard.write falló, usando Win32 SendInput: {e}")

        if not injected:
            win32_type_text(weight_str)

        self._pulse_hud_green()
        print(f"Inyectado peso: {weight_str}")

    def _pulse_hud_green(self):
        if hasattr(self, "lbl_weight"):
            original_color = "#22C55E"
            self.lbl_weight.config(fg="#86EFAC")
            self.root.after(250, lambda: self.lbl_weight.config(fg=original_color))

    def _create_hud(self):
        self.root = tk.Tk()
        self.root.title("Balanza POS Overlay")

        self.root.attributes("-topmost", True)
        self.root.overrideredirect(True)

        w = self.config.get("hud_width", 210)
        h = self.config.get("hud_height", 75)
        pos = self.config.get("hud_position", "+1150+20")
        self.root.geometry(f"{w}x{h}{pos}")

        bg_color = "#0F172A"
        self.root.configure(bg=bg_color)

        self.frame = tk.Frame(self.root, bg=bg_color, highlightbackground="#334155", highlightthickness=1)
        self.frame.pack(fill=tk.BOTH, expand=True)

        header_frame = tk.Frame(self.frame, bg=bg_color)
        header_frame.pack(fill=tk.X, padx=(8, 8), pady=(4, 0))

        key_name = self.config.get("trigger_key", "f2").upper()
        self.lbl_title = tk.Label(
            header_frame,
            text=f"BALANZA [{key_name}]",
            font=("Consolas", 9, "bold"),
            fg="#94A3B8",
            bg=bg_color
        )
        self.lbl_title.pack(side=tk.LEFT)

        # Botón de reconexión rápida
        self.btn_retry = tk.Button(
            header_frame,
            text="🔄",
            font=("Segoe UI", 7),
            fg="#94A3B8",
            bg=bg_color,
            activebackground="#1E293B",
            activeforeground="#FFFFFF",
            bd=0,
            cursor="hand2",
            command=self._retry_rs232_connection
        )
        self.btn_retry.pack(side=tk.RIGHT, padx=(0, 4))

        self.canvas_status = tk.Canvas(header_frame, width=10, height=10, bg=bg_color, highlightthickness=0, cursor="hand2")
        self.canvas_status.pack(side=tk.RIGHT, pady=2)
        self.status_dot = self.canvas_status.create_oval(1, 1, 9, 9, fill="#EF4444")
        self.canvas_status.bind("<Button-1>", lambda e: self._retry_rs232_connection())

        self.lbl_weight = tk.Label(
            self.frame,
            text="0.000 kg",
            font=("Segoe UI", 18, "bold"),
            fg="#22C55E",
            bg=bg_color
        )
        self.lbl_weight.pack(pady=(0, 2))

        # Eventos del mouse
        self._drag_data = {"x": 0, "y": 0}
        for widget in [self.root, self.frame, self.lbl_title, self.lbl_weight, header_frame]:
            widget.bind("<Button-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._on_drag)
            widget.bind("<ButtonRelease-1>", self._stop_drag)
            widget.bind("<Button-3>", self._show_context_menu)
            widget.bind("<Double-Button-1>", lambda e: self._inject_weight())

        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="🔌 Reconectar Puerto RS-232 (COM)", command=self._retry_rs232_connection)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="⚡ Probar Inyección (Simular Tecla)", command=self._inject_weight)
        
        sim_menu = tk.Menu(self.context_menu, tearoff=0)
        sim_menu.add_command(label="Establecer 1.450 kg", command=lambda: self._set_sim_weight("1.450"))
        sim_menu.add_command(label="Establecer 2.500 kg", command=lambda: self._set_sim_weight("2.500"))
        sim_menu.add_command(label="Establecer 0.750 kg", command=lambda: self._set_sim_weight("0.750"))
        sim_menu.add_command(label="Establecer 5.000 kg", command=lambda: self._set_sim_weight("5.000"))
        sim_menu.add_command(label="Establecer 0.000 kg", command=lambda: self._set_sim_weight("0.000"))
        
        self.context_menu.add_cascade(label="⚖️ Cambiar Peso de Prueba", menu=sim_menu)
        self.context_menu.add_command(label="🔄 Alternar Modo Simulación", command=self._toggle_mock)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="❌ Salir", command=self._quit_app)

        self._update_hud_loop()

        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self._quit_app()

    def _start_drag(self, event):
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y

    def _on_drag(self, event):
        deltax = event.x - self._drag_data["x"]
        deltay = event.y - self._drag_data["y"]
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")

    def _stop_drag(self, event):
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        self.config["hud_position"] = f"+{x}+{y}"
        save_config(self.config)

    def _show_context_menu(self, event):
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def _set_sim_weight(self, weight_str):
        with self.lock:
            self.is_mock = True
            self.current_weight = weight_str
        print(f"Peso simulado establecido a: {weight_str}")

    def _toggle_mock(self):
        with self.lock:
            self.is_mock = not self.is_mock
            if self.is_mock:
                self.current_weight = "1.450"
        print(f"Modo Simulación: {self.is_mock}")

    def _update_hud_loop(self):
        if not self.running:
            return

        with self.lock:
            weight = self.current_weight
            is_conn = self.is_connected
            is_mock = self.is_mock

        prefix = "SIM " if is_mock else ""
        self.lbl_weight.config(text=f"{prefix}{weight} kg")

        color = "#22C55E" if is_conn else "#EF4444"
        if is_mock:
            color = "#3B82F6"

        self.canvas_status.itemconfig(self.status_dot, fill=color)

        self.root.after(40, self._update_hud_loop)  # Refresco continuo a ~25 FPS en el HUD

    def _quit_app(self):
        print("Cerrando aplicación de forma limpia...")
        self.running = False
        self._close_active_serial()

        if self.pynput_listener:
            try:
                self.pynput_listener.stop()
            except Exception:
                pass

        if keyboard:
            try:
                keyboard.clear_all_hotkeys()
            except Exception:
                pass

        try:
            self.root.destroy()
        except Exception:
            pass

        sys.exit(0)

if __name__ == "__main__":
    mutex = ensure_single_instance()
    if mutex is None:
        print("Ya existe una instancia de ScaleWedgePOS ejecutándose. Saliendo...")
        sys.exit(0)
    ScaleBridgeApp()
