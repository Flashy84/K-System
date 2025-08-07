# zoohaven_epson_kiosk.py

from escpos.printer import Network
import sys
import time
import datetime
import requests
from gpiozero import Button

# ----------------- KONFIGURASJON -----------------
IP_ADDRESS   = "192.168.10.154"  # Epson TM-T88VI IP
PORT         = 9100
API_ENDPOINT = 'https://www.chris-stian.no/kundeskjerm/create_queue.php'
BUTTON_PIN   = 17  # BCM-pin for trykknapp
SERVICE_NAME = "Zoohaven"
LOGO_PATH    = "logo_new.png"
QR_PATH      = "googleqr.png"

# Initialiser printer over nettverk
printer = Network(IP_ADDRESS, PORT, timeout=5)

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

# ----------------- PRINTFUNKSJON -----------------
def print_ticket(number):
    """Printer ut billett med logo, større tekst, ÆØÅ-støtte og QR-kode."""
    now = datetime.datetime.now().strftime('%d.%m.%Y %H:%M')

    # Velkommen-tekst
    printer.set(align='center')
    printer.image(LOGO_PATH)
    printer.text("\n")

    # Stor, fet kjølapp
    printer.set(align='center', width=2, height=2)
    printer.text(f"Nr: {number}\n")
    printer.set(width=1, height=1)
    
    # Tjeneste og tidspunkt
    printer.text(f"Tjeneste: {SERVICE_NAME}\n")
    printer.text(f"{now}\n")
    printer.text("Takk for ditt besøk!\n\n")

    # QR-kode nederst
    printer.image(QR_PATH)
    printer.text("\n")

    # Klipp papiret
    printer.cut()
    print(f"Utskrift OK: {number}")

# ----------------- HOVEDLOGIKK -----------------
def issue_new_ticket():
    number = get_new_ticket_from_api(SERVICE_NAME)
    if number:
        print_ticket(number)
    else:
        print("Kunne ikke hente kønummer.")


def main():
    # Sett opp knapp med litt debounce
    btn = Button(BUTTON_PIN, bounce_time=0.3)
    btn.when_pressed = issue_new_ticket

    print("Starter Epson TM-T88VI kiosk med logo og QR-kode...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Avslutter...")
        sys.exit(0)

if __name__ == '__main__':
    main()
