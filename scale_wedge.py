import json
import os
import re
import sys
import time
import threading
import ctypes
import tkinter as tk

try:
    import serial
    import serial.tools.list_ports
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
    "scale_model": "BBG Market 30 / IPBG",
    "port": "COM2",
    "baudrate": 9600,
    "trigger_key": "f2",
    "decimal_separator": ".",
    "hud_position": "+1150+20",
    "hud_width": 220,
    "hud_height": 80
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
        self.is_scale_on = False
        self.active_port_name = self.config.get("port", "COM2")
        self.status_detail = "CONECTANDO A BÁSCULA..."
        self.running = True
        self.last_injection_time = 0
        self.lock = threading.Lock()
        self.active_ser = None
        self.pynput_listener = None
        self.reconnect_requested = False

        # Hilo de lectura estable con filtro anti-parpadeo
        self.serial_thread = threading.Thread(target=self._realtime_hardware_worker, daemon=True)
        self.serial_thread.start()

        # Configurar Hotkey global (F2)
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
        """Forzar reconexión inmediata del puerto."""
        print("Forzando reconexión limpia del puerto serial...")
        with self.lock:
            self.reconnect_requested = True
            self.is_scale_on = False
            self.status_detail = "CONECTANDO..."

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

    def _get_ports_to_scan(self):
        preferred_port = self.config.get("port", "COM2")
        ports_list = [preferred_port]

        if serial and hasattr(serial, "tools") and hasattr(serial.tools, "list_ports"):
            try:
                detected = [p.device for p in serial.tools.list_ports.comports()]
                for d in detected:
                    if d not in ports_list:
                        ports_list.append(d)
            except Exception:
                pass

        for i in range(1, 16):
            cp = f"COM{i}"
            if cp not in ports_list:
                ports_list.append(cp)

        return ports_list

    def _realtime_hardware_worker(self):
        """Monitorea el puerto COM con filtro antirrebote de estabilidad y latch de peso."""
        baudrates = [self.config.get("baudrate", 9600), 9600, 2400, 4800]
        baudrates = list(dict.fromkeys(baudrates))

        consecutive_zeros = 0

        while self.running:
            with self.lock:
                reconnect = self.reconnect_requested
                if reconnect:
                    self.reconnect_requested = False

            ports_to_try = self._get_ports_to_scan()
            active_connection = False

            for port_name in ports_to_try:
                if not self.running or self.reconnect_requested:
                    break

                for baud in baudrates:
                    if not self.running or self.reconnect_requested:
                        break

                    self._close_active_serial()
                    try:
                        with self.lock:
                            self.status_detail = f"PROBANDO {port_name} ({baud})..."

                        self.active_ser = serial.Serial(
                            port=port_name,
                            baudrate=baud,
                            bytesize=serial.EIGHTBITS,
                            parity=serial.PARITY_NONE,
                            stopbits=serial.STOPBITS_ONE,
                            timeout=0.05
                        )
                        self.active_ser.dtr = True
                        self.active_ser.rts = True

                        buffer_str = ""
                        last_valid_data_time = time.time()
                        found_scale_on_port = False

                        # Bucle de prueba de puerto
                        start_test = time.time()
                        while self.running and not self.reconnect_requested and (time.time() - start_test < 1.0):
                            if self.active_ser and self.active_ser.is_open:
                                try:
                                    waiting = self.active_ser.in_waiting
                                    if waiting > 0:
                                        raw_bytes = self.active_ser.read(waiting)
                                        self.active_ser.reset_input_buffer()

                                        decoded = raw_bytes.decode("latin-1", errors="ignore")
                                        buffer_str += decoded

                                        matches = re.findall(r"[-+]?\s*(\d+[\.,]\d+|\d+)", buffer_str)
                                        if matches:
                                            latest_raw = matches[-1].replace(",", ".")
                                            try:
                                                val_float = float(latest_raw)
                                                if val_float >= 0.005:
                                                    consecutive_zeros = 0
                                                    formatted = f"{val_float:.3f}"
                                                    with self.lock:
                                                        self.current_weight = formatted
                                                        self.is_scale_on = True
                                                        self.status_detail = f"ENCENDIDA ({port_name})"
                                                else:
                                                    consecutive_zeros += 1
                                                    if consecutive_zeros >= 4:
                                                        with self.lock:
                                                            self.current_weight = "0.000"
                                                            self.is_scale_on = True
                                                            self.status_detail = f"ENCENDIDA ({port_name})"

                                                found_scale_on_port = True
                                                last_valid_data_time = time.time()
                                                buffer_str = ""

                                                if self.config.get("port") != port_name or self.config.get("baudrate") != baud:
                                                    self.config["port"] = port_name
                                                    self.config["baudrate"] = baud
                                                    save_config(self.config)
                                            except ValueError:
                                                pass
                                except Exception as read_err:
                                    print(f"Error comprobando {port_name}: {read_err}")
                                    break
                            time.sleep(0.02)

                        # Bucle principal de lectura constante con FILTRO ANTI-PARPADEO
                        if found_scale_on_port:
                            print(f"¡Báscula transmitiendo estable en {port_name}!")
                            
                            while self.running and not self.reconnect_requested:
                                if self.active_ser and self.active_ser.is_open:
                                    try:
                                        waiting = self.active_ser.in_waiting
                                        if waiting > 0:
                                            raw_bytes = self.active_ser.read(waiting)
                                            self.active_ser.reset_input_buffer()

                                            decoded = raw_bytes.decode("latin-1", errors="ignore")
                                            buffer_str += decoded

                                            matches = re.findall(r"[-+]?\s*(\d+[\.,]\d+|\d+)", buffer_str)
                                            if matches:
                                                latest_raw = matches[-1].replace(",", ".")
                                                try:
                                                    val_float = float(latest_raw)
                                                    
                                                    # FILTRO ANTI-PARPADEO / DEBOUNCE:
                                                    # Si llega un peso mayor o igual a 5 gramos, fijar peso y reiniciar contador de ceros.
                                                    if val_float >= 0.005:
                                                        consecutive_zeros = 0
                                                        formatted = f"{val_float:.3f}"
                                                        with self.lock:
                                                            self.current_weight = formatted
                                                            self.is_scale_on = True
                                                            self.status_detail = f"ENCENDIDA ({port_name})"
                                                    else:
                                                        # Si llega una trama intercalada de cero, incrementar contador.
                                                        # ÚNICAMENTE tras 4 ceros seguidos se confirma que se retiró el objeto de la báscula.
                                                        consecutive_zeros += 1
                                                        if consecutive_zeros >= 4:
                                                            with self.lock:
                                                                self.current_weight = "0.000"
                                                                self.is_scale_on = True
                                                                self.status_detail = f"ENCENDIDA ({port_name})"

                                                    last_valid_data_time = time.time()
                                                    buffer_str = ""
                                                except ValueError:
                                                    pass
                                    except Exception as err:
                                        print(f"Error de lectura serial: {err}")
                                        break

                                now = time.time()
                                # Si pasan más de 4 segundos sin señal, marcar como apagada
                                if now - last_valid_data_time > 4.0:
                                    with self.lock:
                                        self.is_scale_on = False
                                        self.status_detail = f"APAGADA ({port_name})"
                                    break

                                time.sleep(0.02)

                            active_connection = True
                            break

                        self._close_active_serial()

                    except Exception as e:
                        self._close_active_serial()

            if not active_connection:
                with self.lock:
                    self.is_scale_on = False
                    self.status_detail = "APAGADA / DESCONECTADA"
                time.sleep(1.5)

    def _inject_weight(self):
        with self.lock:
            scale_on = self.is_scale_on
            weight = self.current_weight

        if not scale_on:
            print("No se puede inyectar: La báscula está APAGADA o DESCONECTADA.")
            self._pulse_hud_red()
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
        print(f"Inyectado peso de báscula real: {weight_str}")

    def _pulse_hud_green(self):
        if hasattr(self, "lbl_weight"):
            original_color = "#22C55E"
            self.lbl_weight.config(fg="#86EFAC")
            self.root.after(250, lambda: self.lbl_weight.config(fg=original_color))

    def _pulse_hud_red(self):
        if hasattr(self, "lbl_weight"):
            self.lbl_weight.config(fg="#EF4444")
            self.root.after(250, lambda: self.lbl_weight.config(fg="#64748B"))

    def _create_hud(self):
        self.root = tk.Tk()
        self.root.title("Balanza POS Overlay")

        self.root.attributes("-topmost", True)
        self.root.overrideredirect(True)

        w = self.config.get("hud_width", 220)
        h = self.config.get("hud_height", 80)
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
            fg="#64748B",
            bg=bg_color
        )
        self.lbl_weight.pack(pady=(0, 0))

        self.lbl_status_text = tk.Label(
            self.frame,
            text="CONECTANDO A COM2...",
            font=("Segoe UI", 7, "bold"),
            fg="#EAB308",
            bg=bg_color
        )
        self.lbl_status_text.pack(pady=(0, 2))

        # Eventos del mouse
        self._drag_data = {"x": 0, "y": 0}
        for widget in [self.root, self.frame, self.lbl_title, self.lbl_weight, self.lbl_status_text, header_frame]:
            widget.bind("<Button-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._on_drag)
            widget.bind("<ButtonRelease-1>", self._stop_drag)
            widget.bind("<Button-3>", self._show_context_menu)
            widget.bind("<Double-Button-1>", lambda e: self._inject_weight())

        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="🔌 Reconectar Puerto RS-232", command=self._retry_rs232_connection)
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

    def _update_hud_loop(self):
        if not self.running:
            return

        with self.lock:
            weight = self.current_weight
            is_scale_on = self.is_scale_on
            status_text = self.status_detail

        if is_scale_on:
            self.lbl_weight.config(text=f"{weight} kg", fg="#22C55E")
            self.lbl_status_text.config(text=status_text, fg="#22C55E")
            self.canvas_status.itemconfig(self.status_dot, fill="#22C55E")
        else:
            self.lbl_weight.config(text=f"{weight} kg", fg="#64748B")
            self.lbl_status_text.config(text=status_text, fg="#EF4444" if "APAGADA" in status_text else "#EAB308")
            dot_color = "#EF4444" if "APAGADA" in status_text else "#EAB308"
            self.canvas_status.itemconfig(self.status_dot, fill=dot_color)

        self.root.after(30, self._update_hud_loop)

    def _quit_app(self):
        print("Cerrando aplicación...")
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
