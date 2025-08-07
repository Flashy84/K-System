# zoohaven_epson_kiosk.py

import socket
import sys
import time
import datetime
import requests
from queue import Queue
from gpiozero import Button

# ----------------- KONFIGURASJON -----------------
IP_ADDRESS   = "192.168.10.154"  # Endre til din Epson TM-T88VI IP
PORT         = 9100
API_ENDPOINT = 'https://www.chris-stian.no/kundeskjerm/create_queue.php'
BUTTON_PIN   = 17                # BCM-pin for trykknapp
SERVICE_NAME = "Zoohaven"

# Buffer for forhåndshenting av maks 1 nummer
queue_buffer = Queue(maxsize=1)

# ----------------- HJELPEFUNKSJONER -----------------
def get_new_ticket_from_api(service):
    try:
        resp = requests.post(
            API_ENDPOINT,
            data={"service_type": service},
            timeout=5
        )
        j = resp.json()
        if resp.status_code == 200 and j.get("status") == "success":
            return j.get("queue_number")
    except Exception as e:
        print(f"API-feil: {e}")
    return None

def send_to_printer(data: bytes) -> bool:
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
    """Bygger og sender en ryddig og oversiktlig kølapp."""
    now = datetime.datetime.now().strftime('%d.%m.%Y %H:%M')
    date, clock = now.split()

    # ESC/POS-kommandoer
    INIT        = b"\x1b@"      # ESC @ (reset)
    CENTER      = b"\x1ba\x01"  # ESC a 1 (center)
    LEFT        = b"\x1ba\x00"  # ESC a 0 (left)
    BOLD_ON     = b"\x1bE\x01"  # ESC E 1 (bold on)
    BOLD_OFF    = b"\x1bE\x00"  # ESC E 0 (bold off)
    SIZE_DOUBLE = b"\x1d!\x22"  # GS ! 0x11 (double width & height)
    SIZE_NORMAL = b"\x1d!\x00"  # GS ! 0x00 (normal size)
    FEED        = b"\n" * 4     # Feed 4 lines
    CUT_FULL    = b"\x1dV\x00"  # GS V 0 (full cut)

    buf = bytearray()
    buf += INIT

    # 1) Overskrift
    buf += CENTER + BOLD_ON
    buf += "Zoohaven\n".encode('utf-8')
    buf += BOLD_OFF

    # 2) Nummer i stor & tydelig stil
    buf += CENTER + SIZE_DOUBLE
    buf += f"{number}\n".encode('utf-8')
    buf += SIZE_NORMAL

    # 3) Detaljer venstrejustert
    buf += LEFT
    buf += f"Tjeneste: {SERVICE_NAME}\n".encode('utf-8')
    buf += f"Dato:      {date}\n".encode('utf-8')
    buf += f"Tid:       {clock}\n\n".encode('utf-8')

    # 4) Takkemelding
    buf += CENTER
    buf += "Takk for ditt besøk!\n".encode('utf-8')

    # 5) Feed og kutt
    buf += FEED + CUT_FULL

    if send_to_printer(buf):
        print(f"Utskrift OK: {number}")
    else:
        print(f"Utskrift feilet for {number}")

# ----------------- PREFETCH -----------------
def prefetch_tickets():
    while True:
        if not queue_buffer.full():
            num = get_new_ticket_from_api(SERVICE_NAME)
            if num:
                queue_buffer.put(num)
                print(f"Forhåndshentet: {num}")
        time.sleep(0.1)

# ----------------- HOVEDLOGIKK -----------------
def issue_new_ticket():
    if queue_buffer.empty():
        num = get_new_ticket_from_api(SERVICE_NAME)
    else:
        num = queue_buffer.get()

    if num:
        print_ticket(num)
    else:
        print("Kunne ikke hente kønummer.")

def main():
    # Sett opp knapp med debounce
    btn = Button(BUTTON_PIN, bounce_time=0.3)
    btn.when_pressed = issue_new_ticket

    # Start forhåndshenting i bakgrunnen
    import threading
    threading.Thread(target=prefetch_tickets, daemon=True).start()

    print("Starter Epson TM-T88VI kiosk...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Avslutter…")
        sys.exit(0)

if __name__ == '__main__':
    main()
