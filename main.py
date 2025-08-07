# main.py

import socket
import sys
import time
import datetime
import requests
from gpiozero import Button

# ----------------- KONFIGURASJON -----------------
IP_ADDRESS   = "192.168.10.154"  # Endre til Epson TM-T88VI IP
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
    now = datetime.datetime.now().strftime('%d.%m.%Y %H:%M')

    # ESC/POS-kommandoer
    INIT        = b"\x1b@"        # ESC @
    CENTER      = b"\x1ba\x01"    # Center
    SIZE_DOUBLE = b"\x1d!\x11"    # 2x2
    SIZE_NORMAL = b"\x1d!\x00"    # normal
    FEED        = b"\n" * 8       # 8 lines
    CUT_FULL    = b"\x1dV\x00"    # Full cut

    buf = bytearray()
    buf += INIT + CENTER
    # Nr i dobbel størrelse
    buf += SIZE_DOUBLE + f"Nr: {number}\n".encode('utf-8') + SIZE_NORMAL
    # Tekst
    buf += f"Tjeneste: {SERVICE_NAME}\n".encode('utf-8')
    buf += f"{now}\n\n".encode('utf-8')
    buf += "Takk for ditt besøk!\n\n".encode('utf-8')
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
```
