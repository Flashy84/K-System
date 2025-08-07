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
        resp = requests.post(API_ENDPOINT,
                             data={"service_type": service},
                             timeout=5)
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
    """Bygger og sender en ryddig kølapp med ASCII-dekor nederst."""
    now = datetime.datetime.now().strftime('%d.%m.%Y %H:%M')
    date, clock = now.split()

    # ESC/POS-kommandoer
    INIT            = b"\x1b@"          # Reset
    CODE_PAGE_CP865 = b"\x1b\x74\x17"   # CP865 Nordic (ÆØÅ)
    CENTER          = b"\x1ba\x01"      # Center
    LEFT            = b"\x1ba\x00"      # Left
    BOLD_ON         = b"\x1bE\x01"
    BOLD_OFF        = b"\x1bE\x00"
    SIZE_TRIPLE     = b"\x1d!\x22"      # 3×3 font for nummer
    SIZE_NORMAL     = b"\x1d!\x00"      # Normal
    FEED_TOP        = b"\n" * 2         # Mat før dekor
    FEED_BOTTOM     = b"\n" * 6         # Mat før kutt
    CUT_FULL        = b"\x1dV\x00"      # Full cut

    buf = bytearray()
    buf += INIT
    buf += CODE_PAGE_CP865

    # --- Overskrift ---
    buf += CENTER + BOLD_ON
    buf += "Zoohaven\n".encode('cp865')
    buf += BOLD_OFF

    # --- Nummer i 3× størrelse ---
    buf += CENTER + SIZE_TRIPLE
    buf += f"{number}\n".encode('cp865')
    buf += SIZE_NORMAL

    # --- Detaljer venstrejustert ---
    buf += LEFT
    buf += f"Tjeneste: {SERVICE_NAME}\n".encode('cp865')
    buf += f"Dato:      {date}\n".encode('cp865')
    buf += f"Tid:       {clock}\n\n".encode('cp865')

    # --- Takk og ekstra info ---
    buf += CENTER
    buf += "Takk for ditt besøk!\n".encode('cp865')
    buf += "Sjekk ut www.zoohaven.no for oppdaterte åpningstider.\n".encode('cp865')
    buf += "Vi ønsker deg en fin dag.\n".encode('cp865')

    # --- ASCII-dekor nederst ---
    buf += FEED_TOP
    buf += "            |\_/|        D\___/\\n".encode('cp865')
    buf += "            (0_0)         (0_o)\n".encode('cp865')
    buf += "           ==(Y)==         (V)\n".encode('cp865')
    buf += "----------(u)---(u)----oOo--U--oOo---\n".encode('cp865')
    buf += "__|_______|_______|_______|_______|___\n".encode('cp865')

    # --- Mat og kutt ---
    buf += FEED_BOTTOM + CUT_FULL

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

    print("Starter Epson TM-T88VI kiosk med ASCII-dekor…")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Avslutter…")
        sys.exit(0)

if __name__ == '__main__':
    main()
