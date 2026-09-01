# 📄 Guía Completa de Instalación, Configuración y Pruebas
## Software Keyboard Wedge con Overlay Flotante para Balanza POS

Esta guía te explica detalladamente cómo utilizar, probar y desplegar la integración de la báscula/balanza digital (RS-232 / USB COM) con tu sistema POS Web (Next.js) en el equipo Todo-en-Uno (All-in-One).

---

## 🎯 1. Estructura de Archivos en la Carpeta

- **`dist\ScaleWedgePOS.exe`**: Ejecutable principal independiente que se corre en Windows.
- **`config.json`**: Archivo de configuración para puerto COM, velocidad, tecla de acceso rápido y decimales.
- **`scale_wedge.py`**: Código fuente en Python.
- **`build.bat`**: Script para compilar el ejecutable nuevamente si se realizan cambios al código.

---

## 🧪 2. Pruebas en la PC de Desarrollo (Sin Balanza Física)

Puedes probar el funcionamiento de la ventana flotante y la inyección en el teclado sin necesidad de tener la báscula física conectada:

1. Ejecuta **`dist\ScaleWedgePOS.exe`**.
2. Aparecerá el recuadro flotante **`BALANZA [F2] | SIM 1.450 kg`** en la esquina de la pantalla.
3. Haz **clic derecho** sobre el recuadro flotante y ve a **`⚖️ Cambiar Peso de Prueba`** para seleccionar valores como `2.500 kg`, `0.750 kg`, etc.
4. Abre cualquier campo de texto (un Bloc de notas o el POS Web) y haz clic sobre él para posicionar el cursor.
5. Inyecta el peso usando cualquiera de estas 3 alternativas:
   - Presiona la tecla **`F2`** en tu teclado.
   - Haz **doble clic izquierdo** sobre el recuadro del peso.
   - Clic derecho en el recuadro -> **`⚡ Probar Inyección (Simular Tecla)`**.

---

## 🔌 3. Instalación con la Balanza Física Real en el Local

Cuando estés en el local con el equipo Todo-en-Uno y la báscula comercial:

### Paso 1: Conexión y Detección del Puerto COM en Windows
1. Conecta la balanza al puerto serial RS-232 de la máquina o mediante un adaptador USB-a-Serial.
2. En Windows, presiona `Win + X` y abre el **Administrador de Dispositivos**.
3. Despliega la categoría **Puertos (COM y LPT)**.
4. Anota el número de puerto asignado (ejemplo: `COM1`, `COM3`, `COM4`).

### Paso 2: Configurar `config.json` para la Báscula BBG Market 30 / IPBG
Abre el archivo `config.json` ubicado en la carpeta del programa y confirma los valores para el modelo **BBG Market 30 / IPBG**:

```json
{
  "scale_model": "BBG Market 30 / IPBG",
  "port": "COM3",
  "baudrate": 9600,
  "trigger_key": "f2",
  "decimal_separator": ".",
  "hud_position": "+1150+20",
  "hud_width": 210,
  "hud_height": 75,
  "mock_mode": false,
  "auto_mock_on_error": false,
  "debug_raw_serial": false
}
```

* **`scale_model`**: Identificador del modelo (**BBG Market 30 / IPBG**).
* **`port`**: Cambia `"COM3"` por el puerto detectado en el paso 1 (ej. `"COM1"` o `"COM4"`).
* **`baudrate`**: `9600` baudios (8 bits de datos, sin paridad, 1 bit de parada - Estándar BBG).
* **`trigger_key`**: Tecla asignada para inyectar el peso (`"f2"`).
* **`decimal_separator`**: Usa `"."` si tu formulario POS acepta punto (ej. `1.450`), o `","` si exige coma (ej. `1,450`).
* **`auto_mock_on_error`**: Déjalo en `false` cuando estés operando la balanza real en el local.
* **`debug_raw_serial`**: Si se cambia a `true`, guardará una bitácora `debug_serial.log` con las tramas ASCII puras recibidas por la báscula BBG.

### Paso 3: Verificación de Lectura en Vivo
1. Enciende la balanza y coloca un objeto o paquete pesado encima.
2. Abre **`ScaleWedgePOS.exe`**.
3. El indicador del recuadro se pondrá en **Punto Verde (Conectado)** y la palabra `SIM` desaparecerá.
4. Verás los kilogramos variando en vivo en la pantalla a medida que pongas o quites productos de la báscula.

### Paso 4: Flujo de Venta en el POS Web
1. En la pantalla táctil de la All-in-One, abre el POS Web en el navegador.
2. Selecciona un producto vendido por peso (ej. *Pollo kg*, *Queso kg*).
3. Haz clic o toca en la casilla de cantidad/peso del formulario.
4. Presiona **`F2`** (o haz doble clic táctil en el recuadro flotante).
5. El peso exacto de la balanza se escribirá en el campo activo de la pantalla táctil al instante.

---

## 🚀 4. Configurar Inicio Automático con Windows

Para que el cajero no tenga que abrir manualmente el programa cada vez que encienda la máquina Todo-en-Uno:

1. Presiona `Win + R` en el teclado de Windows.
2. Escribe `shell:startup` y presiona **Enter**. Se abrirá la carpeta de inicio automático de Windows.
3. Copia un **Acceso Directo** de `ScaleWedgePOS.exe` dentro de esa carpeta.
4. ¡Listo! A partir de ese momento, cada vez que la máquina All-in-One se encienda, el widget de la balanza estará activo en pantalla listo para usar.

---

## 🛠️ 5. Solución de Problemas Frecuentes

- **El indicador está en Rojo (`Sin Balanza`):**
  - Revisa que el cable RS-232/USB esté bien conectado.
  - Verifica en el Administrador de Dispositivos que el puerto asignado en `config.json` coincida con el puerto COM activo en Windows.

- **El POS no acepta el valor (ej: `1.450`):**
  - Cambia `"decimal_separator": ","` en `config.json` si la configuración regional de Windows o el input del POS requiere coma en lugar de punto.

- **Mover la ventanita en la pantalla táctil:**
  - Mantén presionado con el dedo o ratón sobre el recuadro flotante y arrástralo a la posición de la pantalla donde les sea más cómodo a los cajeros.
