import serial
import time
import re

print("=========================================================")
print(" ESCUCHANDO TRAMAS REALES DE BBG MARKET 30 EN COM1 ")
print("=========================================================\n")

try:
    ser = serial.Serial("COM1", 9600, timeout=0.5)
    ser.dtr = True
    ser.rts = True
    print("✅ Puerto COM1 abierto exitosamente. Muestra 10 tramas puras recibidas:\n")
    
    start = time.time()
    count = 0
    buffer = ""
    while time.time() - start < 5 and count < 10:
        if ser.in_waiting > 0:
            raw = ser.read(ser.in_waiting)
            decoded = raw.decode("latin-1", errors="ignore")
            buffer += decoded
            
            lines = re.split(r"[\r\n]+", buffer)
            buffer = lines[-1]
            complete = lines[:-1]
            
            for line in complete:
                if line.strip():
                    count += 1
                    print(f"Trama RAW [{count}]: '{line.strip()}'")
                    kg_match = re.search(r"[-+]?\s*(\d+[\.,]\d+)\s*kg", line, re.IGNORECASE)
                    if kg_match:
                        peso = kg_match.group(1)
                        print(f"   -> PESO EXTRACTADO (vía kg): {peso} kg")
                    else:
                        first_match = re.search(r"[-+]?\s*(\d+[\.,]\d+)", line)
                        if first_match:
                            peso = first_match.group(1)
                            print(f"   -> PESO EXTRACTADO (primer número): {peso} kg")
        time.sleep(0.05)
    ser.close()
except Exception as e:
    print(f"Error en COM1: {e}")
