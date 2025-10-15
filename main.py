# main.py — Zoohaven Epson Kiosk

import os
import socket
import sys
import time
import datetime
import threading
import requests
from gpiozero import Button

# ----------------- EKSTERN LOGGING -----------------
LOG_ENDPOINT = 'https://www.chris-stian.no/kundeskjerm/kundelogg.php'
AUTH_TOKEN   = os.environ.get("AUTH_TOKEN", "W5Rcv7XdqbAthfeMjEI41qqodakzAo")
HEARTBEAT_EVERY_S = 60  # send heartbeat hvert minutt

# ----------------- KONFIGURASJON -----------------
IP_ADDRESS      = "192.168.10.104"   # Epson TM-T88VI IP
PORT            = 9100
API_ENDPOINT    = 'https://www.chris-stian.no/kundeskjerm/create_queue.php'
STATUS_ENDPOINT = 'https://www.chris-stian.no/kundeskjerm/status.php'
BUTTON_PIN      = 17                 # BCM-pin for trykknapp
SERVICE_NAME    = "Zoohaven"

# Knapp-tuning
BUTTON_DEBOUNCE_S = 0.02             # 20 ms program-debounce (rask respons)
PRESS_COOLDOWN_S  = 0.35             # grace-vindu som stopper dobbelt-tapp

# Hindrer overlappende utskrifter
print_lock = threading.Lock()

# Til intern tapp-cooldown
_last_press_ts = 0.0
_last_press_lock = threading.Lock()


# ----------------- HJELPEFUNKSJONER -----------------
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "unknown"
    finally:
        s.close()


def _post_event(payload, timeout=2.5):
    """Fire-and-forget til ekstern logger, blokkerer ikke hovedflyt."""
    try:
        headers = {"X-Auth-Token": AUTH_TOKEN, "Content-Type": "application/json"}
        requests.post(LOG_ENDPOINT, json=payload, headers=headers, timeout=timeout)
    except Exception:
        pass  # Logging skal aldri stoppe kjernefunksjoner


def log_event(level: str, message: str, event: str = "log", meta: dict | None = None):
    payload = {
        "device": SERVICE_NAME,
        "ts": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "level": str(level).upper(),
        "event": event,
        "message": message,
        "meta": meta or {},
        "ip": get_local_ip(),
    }
    threading.Thread(target=_post_event, args=(payload,), daemon=True).start()


def heartbeat_loop():
    while True:
        log_event("INFO", "heartbeat", event="heartbeat")
        for _ in range(HEARTBEAT_EVERY_S):
            time.sleep(1)


def get_new_ticket_from_api(service):
    try:
        resp = requests.post(API_ENDPOINT, data={"service_type": service}, timeout=5)
        j = resp.json()
        if resp.status_code == 200 and j.get("status") == "success":
            return j.get("queue_number")
        else:
            log_event("ERROR", f"API uventet svar: {resp.status_code}", event="queue_fetch_error")
    except Exception as e:
        print(f"API-feil: {e}")
        log_event("ERROR", f"API-feil: {e}", event="queue_fetch_error")
    return None


def send_to_printer(data: bytes) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(5)
            sock.connect((IP_ADDRESS, PORT))
            sock.sendall(data)
        return True
    except Exception as e:
        print(f"Utskrift-feil: {e}")
        log_event("ERROR", f"Utskrift-feil: {e}", event="print_error")
        return False


def send_online_status():
    try:
        payload = {
            "service":   SERVICE_NAME,
            "status":    "online",
            "timestamp": datetime.datetime.now().isoformat(),
            "ip":        get_local_ip(),
        }
        resp = requests.post(STATUS_ENDPOINT, data=payload, timeout=5)
        if resp.status_code == 200:
            print(f"Status: online – sendt (ip={payload['ip']}).")
        else:
            print(f"Statusmelding feilet: HTTP {resp.status_code}")
    except Exception as e:
        print(f"Feil ved sending av statusmelding: {e}")


# ----------------- PRINTFUNKSJON -----------------
def print_ticket(number):
    """Skriv ut billett der nummer vises som 00–99 (to siffer)."""
    now = datetime.datetime.now().strftime('%d.%m.%Y %H:%M')
    date, clock = now.split()

    # Map til 00–99 for visning
    try:
        n_real = int(str(number).strip())
    except Exception:
        n_real = 0
    n_disp = n_real % 100
    n_disp_txt = f"{n_disp:02d}"

    # ESC/POS-kommandoer
    INIT            = b"\x1b@"          # Reset
    CODE_PAGE_CP865 = b"\x1b\x74\x17"   # CP865 Nordic (ÆØÅ)
    CENTER          = b"\x1ba\x01"
    LEFT            = b"\x1ba\x00"
    BOLD_ON         = b"\x1bE\x01"
    BOLD_OFF        = b"\x1bE\x00"
    SIZE_TRIPLE     = b"\x1d!\x22"
    SIZE_NORMAL     = b"\x1d!\x00"
    FEED_TOP        = b"\n" * 2
    FEED_BOTTOM     = b"\n" * 6
    CUT_FULL        = b"\x1dV\x00"

    buf = bytearray()
    buf += INIT + CODE_PAGE_CP865

    buf += CENTER + BOLD_ON
    buf += "Zoohaven\n".encode('cp865')
    buf += BOLD_OFF

    # Visningsnummer i stor skrift (00–99)
    buf += CENTER + SIZE_TRIPLE
    buf += (n_disp_txt + "\n").encode('cp865')
    buf += SIZE_NORMAL

    buf += CENTER
    buf += "Takk for ditt besok!\n".encode('cp865')
    buf += "Vi onsker deg en fin dag.\n".encode('cp865')

    buf += FEED_TOP + LEFT
    buf += "           ^\\\n".encode('cp865')
    buf += " /        //o__o\n".encode('cp865')
    buf += "/\\       /  __/\n".encode('cp865')
    buf += "\\ \\______\\  /     -GODBIT! Sier Nala\n".encode('cp865')
    buf += " \\         /\n".encode('cp865')
    buf += "  \\ \\----\\ \\\n".encode('cp865')
    buf += "   \\_\\_   \\_\\_\n\n".encode('cp865')

    buf += f"Tid:    {clock} - {date}\n".encode('cp865')

    buf += FEED_BOTTOM + CUT_FULL

    if send_to_printer(buf):
        print(f"Utskrift OK: real={n_real} visning={n_disp_txt}")
        log_event("INFO", f"Etikett {n_real} sendt til skriver", event="print", meta={"display": n_disp_txt})
    else:
        print(f"Utskrift feilet for {n_real}")
        log_event("ERROR", "Utskrift feilet", event="print_error", meta={"queue": n_real})


# ----------------- JOBB (kjøres i egen tråd) -----------------
def issue_new_ticket():
    if not print_lock.acquire(blocking=False):
        return
    try:
        log_event("INFO", "Kunde trykker", event="button")
        num = get_new_ticket_from_api(SERVICE_NAME)
        if num is not None:
            log_event("INFO", f"Etikett {num} hentet fra API", event="queue_fetch", meta={"queue": num})
            print_ticket(num)
            log_event("INFO", "venter på trykk.......", event="idle")
        else:
            print("Kunne ikke hente kønummer.")
            log_event("ERROR", "Kunne ikke hente kønummer", event="queue_fetch_error")
    finally:
        print_lock.release()


# ----------------- KNAPPEHÅNDTERER -----------------
def on_button_pressed():
    """Kalles ved press; filtrerer raske gjentak og starter jobb i egen tråd."""
    global _last_press_ts
    now = time.monotonic()
    with _last_press_lock:
        if now - _last_press_ts < PRESS_COOLDOWN_S:
            return
        _last_press_ts = now
    threading.Thread(target=issue_new_ticket, daemon=True).start()


# ----------------- MAIN -----------------
def main():
    log_event("INFO", "startup", event="startup", meta={"version": "1.0"})
    send_online_status()

    # Start heartbeat
    threading.Thread(target=heartbeat_loop, daemon=True).start()

    # Knappoppsett
    btn = Button(BUTTON_PIN, pull_up=True, bounce_time=BUTTON_DEBOUNCE_S)
    btn.when_pressed = on_button_pressed

    print("Starter Epson TM-T88VI kiosk… (00–99 visning aktiv, logging + heartbeat)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Avslutter…")
        log_event("INFO", "shutdown", event="shutdown")
        sys.exit(0)


if __name__ == '__main__':
    main()
