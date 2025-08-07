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
    """Les PNG, skaler til maks 75% av utskriftsbredde, konverter til ESC/POS rasterbit-bilde"""
    im = Image.open(path).convert('1')  # 1-bit råbilde
    # Skaler logo/QR til max 75% av printerens bredde (i piksler)
    PRINTER_MAX_WIDTH = int(80 * 8)  # 80mm * 8 dots/mm = 640 pixels  # juster etter skriverbredden
    target_width = int(PRINTER_MAX_WIDTH * 0.75)
    w, h = im.size
    # Behold proporsjoner
    if w > target_width:
        new_h = int(h * (target_width / w))
        im = im.resize((target_width, new_h), Image.ANTIALIAS)
        w, h = im.size
    
    # Juster bredde til multiple of 8 for ESC/POS
    if w % 8:
        new_w = w + (8 - w % 8)
        im = im.crop((0, 0, new_w, h))
        w = new_w
    width_bytes = w // 8

    # Bygg GS v 0 rasterbit-image header
    data = bytearray()
    data += b"\x1d\x76\x30\x00"  # GS v 0 m=0

