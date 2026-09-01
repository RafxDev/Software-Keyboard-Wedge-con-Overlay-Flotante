# Software Keyboard Wedge con Overlay Flotante (Balanza POS)

Este módulo en Python actúa como un puente (Keyboard Wedge) entre una balanza o báscula electrónica (conectada por puerto serial RS-232 / USB COM) y cualquier sistema POS web (como tu aplicación Next.js).

---

## 🚀 Características Principales

1. **HUD Overlay Flotante (Tkinter):**
   - Siempre visible por encima de todas las ventanas (`topmost`).
   - Sin bordes molestos.
   - **Móvil:** Haz clic izquierdo y arrastra el widget con el ratón a cualquier esquina de la pantalla táctil o monitor.
   - Muestra el peso en tiempo real con números grandes.
   - Indicador visual de estado (Punto Verde = Conectado/Simulación, Punto Rojo = Desconectado).

2. **Inyección por Tecla Global (`keyboard`):**
   - Captura una tecla configurada (por defecto `F2`).
   - Al presionar `F2`, pega automáticamente el peso actual en la casilla o campo activo del navegador donde se encuentra el cursor del cajero.
   - Permite elegir el separador decimal (`.` o `,`).

3. **Modo Simulación Inteligente:**
   - Si no hay balanza física conectada al probar en la PC, se activa un modo de simulación (`SIM: 1.450 kg`) para poder probar la inyección en el navegador sin depender del hardware.

---

## 📂 Archivos del Proyecto

- [`scale_wedge.py`](scale_wedge.py): Código fuente del programa.
- [`config.json`](config.json): Archivo de configuración (puerto COM, baudrate, tecla asignada, separador decimal, etc.).
- [`requirements.txt`](requirements.txt): Librerías de Python requeridas (`pyserial`, `keyboard`, `pyinstaller`).
- [`build.bat`](build.bat): Script para instalar dependencias y compilar a ejecutable de Windows (`ScaleWedgePOS.exe`).

---

## ⚙️ Configuración (`config.json`)

```json
{
  "port": "COM3",
  "baudrate": 9600,
  "trigger_key": "f2",
  "decimal_separator": ".",
  "hud_position": "+1150+20",
  "hud_width": 210,
  "hud_height": 75,
  "mock_mode": false,
  "auto_mock_on_error": true
}
```

- **`port`**: Puerto COM de la balanza (ej. `"COM1"`, `"COM3"`).
- **`baudrate`**: Velocidad en baudios (generalmente `9600`).
- **`trigger_key`**: Tecla asignada para inyectar el peso (ej. `"f2"`, `"space"`, `"f4"`).
- **`decimal_separator`**: `"."` o `","` según lo exija el input del POS.

---

## 💻 Instrucciones de Compilación e Instalación Automática

1. **Instalar Dependencias:**
   ```powershell
   pip install -r requirements.txt
   ```

2. **Probar en desarrollo:**
   ```powershell
   python scale_wedge.py
   ```

3. **Compilar a Ejecutable Silencioso (`.exe`):**
   Ejecuta el archivo `build.bat` o corre en consola:
   ```powershell
   pyinstaller --noconsole --onefile --name "ScaleWedgePOS" scale_wedge.py
   ```
   El ejecutable resultante estará ubicado en `dist\ScaleWedgePOS.exe`.

4. **Inicio Automático con Windows (Para el Todo-en-Uno):**
   - Presiona `Win + R` y escribe `shell:startup`.
   - Copia un acceso directo del archivo `ScaleWedgePOS.exe` a esa carpeta.
   - Cada vez que la máquina All-in-One se encienda, el widget de la balanza estará activo inmediatamente.
