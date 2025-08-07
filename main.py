# main.py

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
LOGO_PATH    = "logo.png"
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
    """Les PNG, skaler til maks 75% av utskriftsbredden, konverter til ESC/POS rasterbit-bilde"""
    im = Image.open(path).convert('1')  # 1-bit
    # Skaler til maks 75% av bredden (640px = 80mm * 8)
    PRINTER_MAX_WIDTH = 640  # i piksler
    target_width = int(PRINTER_MAX_WIDTH * 0.75)
    w, h = im.size
    if w > target_width:
        new_h = int(h * (target_width / w))
        im = im.resize((target_width, new_h), Image.LANCZOS)
        w, h = im.size
    # Juster bredde til multiple of 8
    if w % 8:
        w_new = w + (8 - w % 8)
        im = im.crop((0, 0, w_new, h))
        w = w_new
    width_bytes = w // 8
    # GS v 0 raster header
    buf = bytearray()
    buf += b"\x1d\x76\x30\x00"
    buf += bytes([width_bytes & 0xFF, (width_bytes >> 8) & 0xFF, h & 0xFF, (h >> 8) & 0xFF])
    pixels = im.load()
    for y in range(h):
        for x_byte in range(width_bytes):
            byte = 0
            for bit in range(8):
                x = x_byte * 8 + bit
                if pixels[x, y] == 0:
                    byte |= 1 << (7 - bit)
            buf.append(byte)
    return bytes(buf)


def send_to_printer(data: bytes) -> bool:
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
    now = datetime.datetime.now().strftime('%d.%m.%Y %H:%M')
    INIT        = b"\x1b@"        # ESC @
    CENTER      = b"\x1ba\x01"    # Center
    SIZE_DOUBLE = b"\x1d!\x11"    # 2x2
    SIZE_NORMAL = b"\x1d!\x00"    # normal
    FEED        = b"\n" * 8       # 8 lines
    CUT_FULL    = b"\x1dV\x00"    # Full cut
    buf = bytearray()
    buf += INIT + CENTER
    # Logo
    buf += image_to_raster(LOGO_PATH) + b"\n"
    # Nummer
    buf += SIZE_DOUBLE + f"Nr: {number}\n".encode('utf-8') + SIZE_NORMAL
    # Tekst
    buf += f"Tjeneste: {SERVICE_NAME}\n".encode('utf-8')
    buf += f"{now}\n\n".encode('utf-8')
    buf += "Takk for ditt besøk!\n\n".encode('utf-8')
    # QR-kode
    buf += image_to_raster(QR_PATH) + b"\n"
    # Feed & cut
    buf += FEED + CUT_FULL
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
    print("Starter Epson TM-T88VI kiosk...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Avslutter...")
        sys.exit(0)

if __name__ == '__main__':
    main()
