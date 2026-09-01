import serial
import serial.tools.list_ports
import winreg

print("=========================================================")
print(" ESCÁNER COMPLETO DE PUERTOS SERIALES REGISTRADOS EN WINDOWS ")
print("=========================================================\n")

# 1. Consultar el Registro de Windows donde se guardan los puertos COM mapeados
print("1. Buscando en el Registro de Windows (HARDWARE\\DEVICEMAP\\SERIALCOMM):")
try:
    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DEVICEMAP\SERIALCOMM")
    i = 0
    found_reg = False
    while True:
        try:
            name, val, _ = winreg.EnumValue(key, i)
            print(f"   -> Encontrado: Dispositivo '{name}' = PUERTO '{val}'")
            found_reg = True
            i += 1
        except OSError:
            break
    winreg.CloseKey(key)
    if not found_reg:
        print("   [Aviso]: No hay puertos seriales listados en el registro DEVICEMAP.")
except Exception as e:
    print(f"   Error consultando registro: {e}")

print("\n2. Probando apertura directa desde COM1 hasta COM20:")
for n in range(1, 21):
    port_name = f"COM{n}"
    try:
        s = serial.Serial(port_name, 9600, timeout=0.1)
        print(f"   ✅ ¡ÉXITO! {port_name} EXISTE Y SE PUEDE ABRIR EN WINDOWS.")
        s.close()
    except serial.SerialException as e:
        err_str = str(e)
        if "Access is denied" in err_str or "Acceso denegado" in err_str:
            print(f"   ⚠️ {port_name} EXISTE PERO ESTÁ OCUPADO/EN USO POR OTRO PROGRAMA.")
        elif "FileNotFoundError" in err_str or "no puede encontrar" in err_str:
            pass # No existe
        else:
            print(f"   ❓ {port_name} error: {e}")
    except Exception as e:
        print(f"   Error en {port_name}: {e}")

print("\n=========================================================")
