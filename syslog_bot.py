import socket
import re
import requests
import datetime

# Configuración
UDP_IP = "TU IP"
UDP_PORT = 514
TELEGRAM_BOT_TOKEN = "TU TOKEN "
TELEGRAM_CHAT_ID = "CHATID"
FILTER_PATTERN = r""       # patrón deseado
FILTER_CALL = r""          # filtro adicional dentro del patrón
LOG_FILE = "syslog.log"
LOG_ENABLED = True
LOG_ONLY_FILTERED = True

def log_message(message):
    if LOG_ENABLED:
        timestamp = datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        with open(LOG_FILE, "a") as log_file:
            log_file.write(f"[{timestamp}] {message}\n")

def escape_markdown(text):
    # Escapa caracteres especiales para Telegram MarkdownV2
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    for ch in escape_chars:
        text = text.replace(ch, "\\" + ch)
    return text

def extract_message_after_pattern(message):
    match = re.search(FILTER_PATTERN, message)
    if match:
        if (len(FILTER_CALL) > 1) and (FILTER_CALL in message):
            return message[message.index(FILTER_CALL):].strip()
        if (len(FILTER_CALL) > 1):
            return None
        return message[match.end():].strip()
    return None

def extract_emisor_receptor(raw_message):
    """
    Extrae callsign emisor y receptor/igate/digi del mensaje real.
    """
    m = re.search(r"(RX|TX) / ([^/]+) / ([^/]+) / ([^/]+)", raw_message)
    if m:
        emisor = m.group(3).strip()
        receptor = m.group(4).strip()
        return emisor, receptor

    m2 = re.search(r"(RX|TX) / ([A-Z0-9\-]+)>([A-Z0-9\-]+)", raw_message)
    if m2:
        return m2.group(2), m2.group(3)

    m3 = re.search(r"(RX|TX) / <([A-Z0-9\-]+)>", raw_message)
    if m3:
        return m3.group(2), None

    m4 = re.search(r"(RX|TX) / MESSAGE / ([A-Z0-9\-]+)", raw_message)
    if m4:
        return m4.group(2), None

    m5 = re.search(r"([A-Z0-9\-]+)\s*--->", raw_message)
    if m5:
        return m5.group(1), None

    return None, None

def add_value_based_icons(message, timestamp=None, emisor=None, receptor=None):
    alerts = []
    lines = []

    if timestamp:
        lines.append(f"🕒 *{timestamp}*")
    if emisor:
        lines.append(f"📡 *Emisor: {emisor}*")
    if receptor:
        lines.append(f"📟 *Receptor: {receptor}*")

    # TX / RX
    if "TX" in message:
        lines.append("📤 *TX*")
    elif "RX" in message:
        lines.append("📥 *RX*")

    # ack
    ack_match = re.search(r"(ack\d*)", message, flags=re.IGNORECASE)
    if ack_match:
        lines.append(f"✅ *{ack_match.group(1)}*")

    # dBm
    dbm_match = re.search(r"(-\d{2,3})dBm", message)
    if dbm_match:
        dbm = int(dbm_match.group(1))
        if dbm > -90:
            icon = "📶"
        elif dbm > -110:
            icon = "📡"
        else:
            icon = "❌"
            if dbm <= -115:
                alerts.append("Señal débil")
        lines.append(f"{icon} *{dbm}dBm*")

    # dB
    db_match = re.search(r"(-\d+\.\d{1,2})dB", message)
    if db_match:
        db_value = float(db_match.group(1))
        icon = "🔈" if db_value > -1.0 else "🔇"
        if db_value <= -2.0:
            alerts.append("Ruido alto")
        lines.append(f"{icon} *{db_value}dB*")

    # Hz
    hz_match = re.search(r"([-+]?\d{1,5})Hz", message)
    if hz_match:
        hz = abs(int(hz_match.group(1)))
        icon = "🎯" if hz < 100 else "📈"
        if hz >= 200:
            alerts.append("Desviación alta de frecuencia")
        lines.append(f"{icon} *{hz}Hz*")

    # PARM
    if "PARM" in message:
        lines.append("📊 *PARM*")

    # Voltajes
    voltages = re.findall(r"V_Batt=(\d+\.\d+),?V_Ext=(\d+\.\d+)?", message)
    if voltages:
        for v_batt_str, v_ext_str in voltages:
            v_batt = float(v_batt_str)
            v_ext = float(v_ext_str) if v_ext_str else 0.0

            if v_batt >= 13.0:
                batt_icon = "🔋🔋🔋🔋"
            elif v_batt >= 12.5:
                batt_icon = "🔋🔋🔋"
            elif v_batt >= 12.0:
                batt_icon = "🔋🔋"
            else:
                batt_icon = "🔋🪫"
                alerts.append("Batería baja")

            ext_icon = "⚡" if v_ext >= 12.0 else "⚠️"
            if v_ext < 12.0:
                alerts.append("Voltaje externo bajo")

            lines.append(f"{batt_icon} *V_Batt={v_batt_str}V*")
            lines.append(f"{ext_icon} *V_Ext={v_ext_str}V*")

    if alerts:
        alert_line = "🔔 *ALERTA: " + ", ".join(alerts) + "*"
        lines.insert(2, alert_line)  # Después del timestamp y emisor

    return "\n".join(lines)

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    print(f"Escuchando en UDP {UDP_PORT} para mensajes syslog...")

    while True:
        data, addr = sock.recvfrom(1024)
        raw_message = data.decode('utf-8', errors='ignore').strip()
        log_entry = f"Syslog de {addr}: {raw_message}"
        print(log_entry)

        if LOG_ENABLED and (not LOG_ONLY_FILTERED or re.search(FILTER_PATTERN, raw_message)):
            log_message(log_entry)

        filtered_message = extract_message_after_pattern(raw_message)
        if filtered_message:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            emisor, receptor = extract_emisor_receptor(raw_message)

            decorated_message = add_value_based_icons(filtered_message, timestamp=timestamp, emisor=emisor, receptor=receptor)
            safe_message = escape_markdown(decorated_message)

            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            data = {
                "chat_id": TELEGRAM_CHAT_ID,
                "text": safe_message,
                "parse_mode": "MarkdownV2",
                "disable_notification": False
            }
            try:
                response = requests.post(url, data=data)
                if response.status_code != 200:
                    print(f"Error Telegram: {response.text}")
            except Exception as e:
                print(f"Error enviando a Telegram: {e}")

if __name__ == "__main__":
    main()
