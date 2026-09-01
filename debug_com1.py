import serial
import time

print("=========================================================")
print("  DIAGNÓSTICO AVANZADO COM1 (CON DTR/RTS Y NAMESPACE)   ")
print("=========================================================")

com_variations = ["COM1", r"\\.\COM1", "COM0", "COM2", "COM3", "COM4"]
baudrates = [9600, 2400, 4800, 19200]

for name in com_variations:
    for baud in baudrates:
        print(f"\n--- Intentando abrir {name} a {baud} baudios (DTR=True, RTS=True) ---")
        try:
            ser = serial.Serial()
            ser.port = name
            ser.baudrate = baud
            ser.timeout = 0.5
            ser.dtr = True
            ser.rts = True
            ser.open()

            print(f"✅ ¡PUERTO {name} ABIERTO EXITOSAMENTE a {baud} baudios!")
            print("Escuchando si la báscula transmite datos durante 3 segundos...")
            
            start = time.time()
            data_found = False
            while time.time() - start < 3:
                if ser.in_waiting > 0:
                    raw = ser.read(ser.in_waiting)
                    print(f"🎉 ¡DATOS RECIBIDOS EN {name}! Raw: {raw}")
                    print(f"   Texto ASCII: {raw.decode('latin-1', errors='ignore')}")
                    data_found = True
                    break
                time.sleep(0.1)

            ser.close()
            if data_found:
                print(f"\n🎯 ¡BÁSCULA DETECTADA EN {name} a {baud} BAUDIOS!")
                sys.exit(0)
            else:
                print(f"El puerto {name} abrió pero no envió bytes en 3 seg.")

        except serial.SerialException as se:
            print(f"❌ SerialException en {name}: {se}")
        except Exception as e:
            print(f"❌ Error en {name}: {e}")
