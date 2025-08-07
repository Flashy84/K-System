# zoohaven_epson_kiosk.py

import socket
import sys
import time
import datetime
import requests
from gpiozero import Button
from PIL import Image

# ----------------- KONFIGURASJON -----------------
IP_ADDRESS   = "192.168.10.154"  # Endre til Epson TM-T88VI IP
PORT         = 9100
API_ENDPOINT = 'https://www.chris-stian.no/kundeskjerm/create_queue.php'
BUTTON_PIN   = 17  # BCM-pin for trykknapp
SERVICE_NAME = "Zoohaven"
LOGO_PATH    = "logo_new.png"
QR_PATH      = "googleqr.png"

# ----------------- HJELPEFUNKSJONER -----------------
def get_new_ticket_from_api(service):
    try:
        resp = requests.post(API_ENDPOINT, data={"service_type": service}, timeout=5)
        data = resp.json()
        if resp.status_code == 200 and data.get('status') == 'success':
            return data.get('queue_number')
    except Exception as e:
        print(f"API-feil: {e}")
    return None


def image_to_raster(path):
    """Les PNG, konverter til ESC/POS rasterbit-bilde"""
    im = Image.open(path).convert('1')  # 1-bit
    w, h = im.size
    # juster bredde til multiple of 8
    if w % 8:
        new_w = w + (8 - w % 8)
        im = im.crop((0, 0, new_w, h))
        w = new_w
    width_bytes = w // 8

    # GS v 0 rasterbit-image header
    data = bytearray()
    data += b"\x1d\x76\x30\x00"  # GS v 0 m=0
    data += bytes([width_bytes % 256, width_bytes // 256, h % 256, h // 256])

    pixels = im.load()
    for y in range(h):
        for x_byte in range(width_bytes):
            byte = 0
            for bit in range(8):
                x = x_byte * 8 + bit
                if pixels[x, y] == 0:
                    byte |= 1 << (7 - bit)
            data.append(byte)
    return bytes(data)


def send_to_printer(data: bytes) -> bool:
    """Sender rå ESC/POS-data til skriveren over TCP/IP."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(5)
            sock.connect((IP_ADDRESS, PORT))
            sock.sendall(data)
        return True
    except Exception as e:
        print(f"Utskrift-feil: {e}")
        return False

# ----------------- PRINTFUNKSJON -----------------
def print_ticket(number):
    """Bygger og sender ESC/POS-kommandoer for kjølapp med bilder."""
    now = datetime.datetime.now().strftime('%d.%m.%Y %H:%M')

    INIT        = b"\x1b@"      # ESC @
    CENTER      = b"\x1ba\x01"  # ESC a 1 Center
    SIZE_DOUBLE = b"\x1d!\x11"  # GS ! 0x11 = 2×2
    SIZE_NORMAL = b"\x1d!\x00"  # GS ! 0x00 normal
    FEED        = b"\n" * 8     # feed 8 linjer
    CUT_FULL    = b"\x1dV\x00"  # GS V 0 full cut

    buf = bytearray()
    buf += INIT
    buf += CENTER
    # Logo raster print
    buf += image_to_raster(LOGO_PATH)
    buf += b"\n"
    # Nummer
    buf += SIZE_DOUBLE
    buf += f"Nr: {number}\n".encode('utf-8')
    buf += SIZE_NORMAL
    # Tjeneste og tid
    buf += f"Tjeneste: {SERVICE_NAME}\n".encode('utf-8')
    buf += f"{now}\n\n".encode('utf-8')
    # Takk
    buf += "Takk for ditt besøk!\n\n".encode('utf-8')
    # QR raster print
    buf += image_to_raster(QR_PATH)
    buf += b"\n"
    # Feed and cut
    buf += FEED
    buf += CUT_FULL

    if send_to_printer(buf):
        print(f"Utskrift OK: {number}")
    else:
        print(f"Utskrift feilet for {number}")

# ----------------- HOVEDLOGIKK -----------------
def issue_new_ticket():
    num = get_new_ticket_from_api(SERVICE_NAME)
    if num:
        print_ticket(num)
    else:
        print("Kunne ikke hente kønummer.")


def main():
    btn = Button(BUTTON_PIN, bounce_time=0.3)
    btn.when_pressed = issue_new_ticket

    print("Starter Epson TM-T88VI kiosk med bilder...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Avslutter...")
        sys.exit(0)

if __name__ == '__main__':
    main()
