import serial
import serial.tools.list_ports
import time

print("=== DIAGNÓSTICO DE PUERTOS SERIALES Y BÁSCULA BBG ===")
ports = serial.tools.list_ports.comports()
print("Puertos COM detectados en el sistema:")
for p in ports:
    print(f"  - {p.device}: {p.description}")

target_port = "COM1"
baudrates = [9600, 2400, 4800, 19200]

for baud in baudrates:
    print(f"\n--- Intentando conectar a {target_port} a {baud} baudios ---")
    try:
        ser = serial.Serial(target_port, baud, timeout=1)
        print(f"ÉXITO: Puerto {target_port} abierto a {baud} baudios.")
        print("Escuchando datos de la báscula por 3 segundos...")
        start = time.time()
        read_bytes = b""
        while time.time() - start < 3:
            if ser.in_waiting > 0:
                chunk = ser.read(ser.in_waiting)
                read_bytes += chunk
                print(f"  [RAW BYTES RECIBIDOS]: {chunk}")
                print(f"  [TEXTO ASCII]: {chunk.decode('latin-1', errors='ignore')}")
            time.sleep(0.1)
        
        ser.close()
        if read_bytes:
            print(f"\n>>> ¡DATOS DETECTADOS A {baud} BAUDIOS! <<<")
            break
        else:
            print(f"No se recibieron datos a {baud} baudios.")
    except Exception as e:
        print(f"ERROR abriendo {target_port} a {baud}: {e}")
