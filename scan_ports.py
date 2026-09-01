import time
import serial.tools.list_ports

print("=========================================================")
print("  ESCÁNER EN TIEMPO REAL DE PUERTOS COM DE BÁSCULA BBG  ")
print("=========================================================")
print("Lista completa de puertos COM en el sistema:")
ports = serial.tools.list_ports.comports()
if not ports:
    print("  [ATENCIÓN]: No se detectó ningún puerto COM activo en Windows.")
else:
    for p in ports:
        print(f"  - Puerto: {p.device} | Descripción: {p.description}")

print("\nRevisando si el puerto serial de la báscula responde...")
