# zoohaven_epson_kiosk.py

import socket
import sys
import time
import datetime
import requests
from gpiozero import Button

# ----------------- KONFIGURASJON -----------------
# Sett IP-adresse til din Epson TM-T88VI
IP_ADDRESS   = "192.168.10.154"  # Endre til skriverens IP
PORT         = 9100
API_ENDPOINT = 'https://www.chris-stian.no/kundeskjerm/create_queue.php'
BUTTON_PIN   = 17  # BCM-pin for trykknapp
SERVICE_NAME = "Zoohaven"

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


def send_to_printer(data: bytes):
    """Sender rå ESC/POS-data til skriveren over TCP/IP."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect((IP_ADDRESS, PORT))
            sock.sendall(data)
        return True
    except Exception as e:
        print(f"Utskrift-feil: {e}")
        return False

# ----------------- PRINTFUNKSJON -----------------
def print_ticket(number):
    """Bygger ESC/POS-kommando og sender til Epson-kutter."""
    now = datetime.datetime.now().strftime('%d.%m.%Y %H:%M')
    # ESC/POS-kommandoer
    INIT        = b"\x1b@"            # ESC @ (Initialize)
    CENTER      = b"\x1ba\x01"      # ESC a 1 (Center)
    SIZE_DOUBLE = b"\x1d!\x11"      # GS ! 0x11 (2×2)
    SIZE_NORMAL = b"\x1d!\x00"      # GS ! 0x00 (normal)
    FEED        = b"\n" * 8         # 8 linjer feed
    CUT_FULL    = b"\x1dV\x00"      # GS V 0 (full cut)

    data = bytearray()
    data += INIT
    data += CENTER
    data += SIZE_DOUBLE
    data += f"Nr: {number}\n".encode('utf-8')
    data += SIZE_NORMAL
    data += f"Tjeneste: {SERVICE_NAME}\n".encode('utf-8')
    data += f"{now}\n\n".encode('utf-8')
    data += b"Takk for ditt besok!\n\n"
    data += FEED
    data += CUT_FULL

    if send_to_printer(data):
        print(f"Utskrift OK: {number}")
    else:
        print(f"Utskrift feilet for {number}")

# ----------------- HOVEDLOGIKK -----------------
def issue_new_ticket():
    number = get_new_ticket_from_api(SERVICE_NAME)
    if number:
        print_ticket(number)
    else:
        print("Kunne ikke hente kønummer.")


def main():
    # Oppsett knapp
    btn = Button(BUTTON_PIN, bounce_time=0.1)  # Debounce knapp for å unngå flere utskrifter per trykk
    btn.when_pressed = issue_new_ticket

    print("Starter Epson TM-T88VI kiosk (en lapp per trykk)...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Avslutter...")
        sys.exit(0)

if __name__ == '__main__':
    main()
