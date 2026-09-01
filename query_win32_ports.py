import ctypes

def get_dos_devices():
    print("=== NOMBRES DE DISPOSITIVOS KERNEL REGISTRADOS EN WINDOWS ===")
    buffer = ctypes.create_unicode_buffer(65536)
    res = ctypes.windll.kernel32.QueryDosDeviceW(None, buffer, 65536)
    if res == 0:
        print(f"Error QueryDosDeviceW: {ctypes.GetLastError()}")
        return
    
    devices = buffer.value.split('\0')
    com_ports = [d for d in devices if d.startswith("COM") or "serial" in d.lower() or "sil" in d.lower()]
    print("Puertos COM o Seriales encontrados en Kernel Windows:")
    if not com_ports:
        print("  [NINGUNO]: No existe ningún dispositivo registrado que empiece por COM.")
    else:
        for c in com_ports:
            print(f"  -> Dispositivo encontrado: {c}")

if __name__ == "__main__":
    get_dos_devices()
