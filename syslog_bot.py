import socket
import re
import requests
import datetime
import threading
from flask import Flask, jsonify, render_template_string

# Configuración UDP y Telegram
UDP_IP = "192.168.1.47"
UDP_PORT = 514
TELEGRAM_BOT_TOKEN = "7628504082:AAG7y6bZgtWzINXBte1vEF5GPUGo35pDN8g"
TELEGRAM_CHAT_ID = "-1002149472286"
FILTER_PATTERN = r""       # patrón deseado (ajusta aquí)
FILTER_CALL = r""          # filtro adicional dentro del patrón (ajusta aquí)
LOG_FILE = "syslog.log"
LOG_ENABLED = True
LOG_ONLY_FILTERED = True

messages_data = []

app = Flask(__name__)

def log_message(message):
    if LOG_ENABLED:
        timestamp = datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as log_file:
            log_file.write(f"[{timestamp}] {message}\n")

def escape_markdown(text):
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

def extract_coordinates(message):
    lat_match = re.search(r"(\d{1,2}\.\d+)([NS])", message)
    lon_match = re.search(r"(-?\d{1,3}\.\d+)([EW])", message)
    if lat_match and lon_match:
        lat = float(lat_match.group(1))
        if lat_match.group(2) == 'S':
            lat = -lat
        lon = float(lon_match.group(1))
        if lon_match.group(2) == 'W':
            lon = -lon
        return lat, lon
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

    if "TX" in message:
        lines.append("📤 *TX*")
    elif "RX" in message:
        lines.append("📥 *RX*")

    ack_match = re.search(r"(ack\d*)", message, flags=re.IGNORECASE)
    if ack_match:
        lines.append(f"✅ *{ack_match.group(1)}*")

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

    db_match = re.search(r"(-\d+\.\d{1,2})dB", message)
    if db_match:
        db_value = float(db_match.group(1))
        icon = "🔈" if db_value > -1.0 else "🔇"
        if db_value <= -2.0:
            alerts.append("Ruido alto")
        lines.append(f"{icon} *{db_value}dB*")

    hz_match = re.search(r"([-+]?\d{1,5})Hz", message)
    if hz_match:
        hz = abs(int(hz_match.group(1)))
        icon = "🎯" if hz < 100 else "📈"
        if hz >= 200:
            alerts.append("Desviación alta de frecuencia")
        lines.append(f"{icon} *{hz}Hz*")

    if "PARM" in message:
        lines.append("📊 *PARM*")

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

    batt_match = re.search(r"Batt=(\d+\.\d+)V", message)
    if batt_match:
        batt_value = batt_match.group(1)
        batt_float = float(batt_value)
        if batt_float >= 4.0:
            batt_icon = "🔋"
        else:
            batt_icon = "🪫"
            alerts.append("Batería baja")
        lines.append(f"{batt_icon} *Batt={batt_value}V*")

    low_voltage_match = re.search(r"LowVoltagePowerOff\s*=\s*([01])", message)
    if low_voltage_match:
        lvp_value = low_voltage_match.group(1)
        estado = "🔴 ACTIVADO" if lvp_value == "1" else "🟢 DESACTIVADO"
        lines.append(f"⚠️ *LowVoltagePowerOff: {estado}*")

   # if alerts:
     #   alert_line = "🔔 *ALERTA: " + ", ".join(alerts) + "*"
      #  lines.insert(2, alert_line)

    return "\n".join(lines)

def udp_listener():
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

            lat, lon = extract_coordinates(raw_message)

            if lat is not None and lon is not None and emisor is not None:
                entry = {
                    "timestamp": timestamp,
                    "emisor": emisor,
                    "receptor": receptor,
                    "lat": lat,
                    "lon": lon,
                    "message": safe_message
                }
                messages_data.append(entry)
                if len(messages_data) > 1000:
                    messages_data.pop(0)

            # Enviar Telegram
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            data_telegram = {
                "chat_id": TELEGRAM_CHAT_ID,
                "text": safe_message,
                "parse_mode": "MarkdownV2"
            }
            try:
                requests.post(url, data=data_telegram, timeout=5)
            except Exception as e:
                print(f"Error al enviar mensaje Telegram: {e}")

@app.route('/')
def index():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>Mapa de emisores/receptores UDP</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <!-- Leaflet CSS -->
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />

    <!-- Leaflet JS -->
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

    <style>
      #map { height: 100vh; }
      .callsign-label {
          font-weight: bold;
          color: darkblue;
          background-color: white;
          padding: 2px 4px;
          border-radius: 3px;
          border: 1px solid navy;
      }
    </style>
</head>
<body>
    <div id="map"></div>

    <script>
      var map = L.map('map').setView([40.960, -5.663], 7);

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
          maxZoom: 18,
          attribution: '© OpenStreetMap'
      }).addTo(map);

      function haversine(lat1, lon1, lat2, lon2) {
          function toRad(x) { return x * Math.PI / 180; }
          var R = 6371;
          var dLat = toRad(lat2 - lat1);
          var dLon = toRad(lon2 - lon1);
          var a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                  Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) *
                  Math.sin(dLon/2) * Math.sin(dLon/2);
          var c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
          return R * c;
      }

      async function loadMarkers() {
          const response = await fetch("/data");
          const data = await response.json();

          if (window.markersLayer) {
              window.markersLayer.clearLayers();
          } else {
              window.markersLayer = L.layerGroup().addTo(map);
          }

          const ea1hg = data.find(d => d.emisor.toUpperCase() === "EA1HG-10");
          const ea1hgLat = ea1hg ? ea1hg.lat : null;
          const ea1hgLon = ea1hg ? ea1hg.lon : null;

          data.forEach(item => {
              let distText = "Distancia a EA1HG-10: N/D";
              if (ea1hgLat !== null && ea1hgLon !== null) {
                  let distKm = haversine(item.lat, item.lon, ea1hgLat, ea1hgLon);
                  distText = `Distancia a EA1HG-10: ${distKm.toFixed(2)} km`;
              }

              let marker = L.marker([item.lat, item.lon]);

              marker.bindTooltip(item.emisor, {permanent: true, direction: 'right', offset: [10, 0], className: 'callsign-label'});

              marker.bindPopup(
                  `<b>Emisor:</b> ${item.emisor}<br>` +
                  `<b>Receptor:</b> ${item.receptor || 'N/A'}<br>` +
                  `<b>Hora:</b> ${item.timestamp}<br>` +
                  `<pre>${item.message}</pre>` +
                  `<b>${distText}</b>`
              );

              window.markersLayer.addLayer(marker);
          });
      }

      loadMarkers();
      setInterval(loadMarkers, 15000);
    </script>
</body>
</html>
    """)

@app.route('/data')
def data():
    return jsonify(messages_data)

if __name__ == "__main__":
    threading.Thread(target=udp_listener, daemon=True).start()
    app.run(host="0.0.0.0", port=5000)
