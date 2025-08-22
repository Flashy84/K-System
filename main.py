# zoohaven_epson_kiosk.py

import socket
import sys
import time
import datetime
import requests
from gpiozero import Button
import threading

# ----------------- KONFIGURASJON -----------------
IP_ADDRESS      = "192.168.10.103"  # Din Epson TM-T88VI IP
PORT            = 9100
API_ENDPOINT    = 'https://www.chris-stian.no/kundeskjerm/create_queue.php'
STATUS_ENDPOINT = 'https://www.chris-stian.no/kundeskjerm/status.php'  # Endepunkt for statusmeldinger
BUTTON_PIN      = 17                # BCM-pin for trykknapp
SERVICE_NAME    = "Zoohaven"

# Hindrer at to utskrifter starter samtidig
print_lock = threading.Lock()

# ----------------- HJELPEFUNKSJONER -----------------
def get_local_ip():
    """Finner lokal IP-adresse ved å koble mot en ekstern adresse."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "unknown"
    finally:
        s.close()

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
            sock.settimeout(5)  # liten timeout så vi ikke henger
            sock.connect((IP_ADDRESS, PORT))
            sock.sendall(data)
        return True
    except Exception as e:
        print(f"Utskrift-feil: {e}")
        return False

# ----------------- STATUSFUNKSJON -----------------
def send_online_status():
    """Sender en 'online' statusmelding til serveren (inkl. lokal IP)."""
    try:
        payload = {
            "service":   SERVICE_NAME,
            "status":    "online",
            "timestamp": datetime.datetime.now().isoformat(),
            "ip":        get_local_ip(),
        }
        resp = requests.post(STATUS_ENDPOINT, data=payload, timeout=5)
        if resp.status_code == 200:
            print(f"Status: online – melding sendt (ip={payload['ip']}).")
        else:
            print(f"Statusmelding feilet: HTTP {resp.status_code}")
    except Exception as e:
        print(f"Feil ved sending av statusmelding: {e}")

# ----------------- PRINTFUNKSJON -----------------
def print_ticket(number):
    """Bygger og sender en kølapp med ASCII-hund venstrejustert nederst."""
    now = datetime.datetime.now().strftime('%d.%m.%Y %H:%M')
    date, clock = now.split()

    # ESC/POS-kommandoer
    INIT            = b"\x1b@"          # Reset
    CODE_PAGE_CP865 = b"\x1b\x74\x17"   # CP865 Nordic (ÆØÅ)
    CENTER          = b"\x1ba\x01"      # Center-align
    LEFT            = b"\x1ba\x00"      # Left-align
    BOLD_ON         = b"\x1bE\x01"
    BOLD_OFF        = b"\x1bE\x00"
    SIZE_TRIPLE     = b"\x1d!\x22"      # 3×3 font for nummer
    SIZE_NORMAL     = b"\x1d!\x00"      # Normal size
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



    # --- Takk og ekstra info ---
    buf += CENTER
    buf += "Takk for ditt besøk!\n".encode('cp865')
    buf += "Vi ønsker deg en fin dag.\n".encode('cp865')

    # --- ASCII-hund venstrejustert nederst ---
    buf += FEED_TOP
    buf += LEFT
    buf += "           ^\\\n".encode('cp865')
    buf += " /        //o__o\n".encode('cp865')
    buf += "/\\       /  __/\n".encode('cp865')
    buf += "\\ \\______\\  /     -GODBIT! Sier Nala\n".encode('cp865')
    buf += " \\         /\n".encode('cp865')
    buf += "  \\ \\----\\ \\\n".encode('cp865')
    buf += "   \\_\\_   \\_\\_\n\n".encode('cp865')

    buf += f"Tid:    {clock} - {date}\n".encode('cp865')
    # --- Mat & kutt ---
    buf += FEED_BOTTOM + CUT_FULL

    if send_to_printer(buf):
        print(f"Utskrift OK: {number}")
    else:
        print(f"Utskrift feilet for {number}")

# ----------------- HOVEDLOGIKK -----------------
def issue_new_ticket():
    # Lås så vi ikke dobbelprinter hvis knappen “spretter”
    if not print_lock.acquire(blocking=False):
        return
    try:
        num = get_new_ticket_from_api(SERVICE_NAME)
        if num:
            print_ticket(num)
        else:
            print("Kunne ikke hente kønummer.")
    finally:
        print_lock.release()

def main():
    # Send statusmelding ved oppstart
    send_online_status()

    # Sett opp knapp med debounce
    btn = Button(BUTTON_PIN, bounce_time=0.3)
    btn.when_pressed = issue_new_ticket

    print("Starter Epson TM-T88VI kiosk (ingen prefetch)…")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Avslutter…")
        sys.exit(0)

if __name__ == '__main__':
    main()
