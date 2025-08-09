# zoohaven_epson_kiosk.py

import socket
import sys
import time
import datetime
import requests
from queue import Queue
from gpiozero import Button

# ----------------- KONFIGURASJON -----------------
IP_ADDRESS      = "192.168.10.106"
PORT            = 9100
API_ENDPOINT    = 'https://www.chris-stian.no/kundeskjerm/create_queue.php'
STATUS_ENDPOINT = 'https://www.chris-stian.no/kundeskjerm/status.php'
BUTTON_PIN      = 17
SERVICE_NAME    = "Zoohaven"

queue_buffer = Queue(maxsize=1)

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
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect((IP_ADDRESS, PORT))
            sock.sendall(data)
        return True
    except Exception as e:
        print(f"Utskrift-feil: {e}")
        return False

# ----------------- STATUSFUNKSJON -----------------
def send_online_status():
    """Sender 'online' status med lokal IP til serveren."""
    payload = {
        "service":   SERVICE_NAME,
        "status":    "online",
        "timestamp": datetime.datetime.now().isoformat(),
        "ip":        get_local_ip()
    }
    try:
        resp = requests.post(STATUS_ENDPOINT, data=payload, timeout=5)
        if resp.status_code == 200:
            print("Status: online – melding sendt.")
        else:
            print(f"Statusmelding feilet: HTTP {resp.status_code}")
    except Exception as e:
        print(f"Feil ved sending av statusmelding: {e}")

# ----------------- PRINTFUNKSJON -----------------
# (samme som før – ikke vist for korthet)

# ----------------- PREFETCH -----------------
# (samme som før)

# ----------------- HOVEDLOGIKK -----------------
def main():
    send_online_status()
    # oppsett knapp og forhåndshenting…
    # …

if __name__ == '__main__':
    main()
