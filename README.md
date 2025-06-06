# Syslog Telegram Bot

Este script escucha mensajes syslog vía UDP, filtra mensajes específicos y envía notificaciones enriquecidas a Telegram con iconos según valores detectados.

## Requisitos

- Python 3.x
- Librerías: `requests`

Puedes instalarlas con:

```bash
pip install requests

Configuración

Modifica las siguientes variables en el script:

    UDP_IP — IP para escuchar (ej. "0.0.0.0" para todas)

    UDP_PORT — Puerto UDP (ej. 514)

    TELEGRAM_BOT_TOKEN — Token de tu bot Telegram

    TELEGRAM_CHAT_ID — ID del chat donde enviar mensajes

    FILTER_PATTERN — Expresión regular para filtrar mensajes

Uso

Ejecuta el script:

python syslog_bot.py

El bot escuchará mensajes syslog y enviará alertas a Telegram.
2. .gitignore

Crea un archivo .gitignore para ignorar archivos innecesarios, por ejemplo:

*.log
__pycache__/
.env

3. Recomendación para no subir el token

Crea un archivo .env con:

TELEGRAM_BOT_TOKEN=tu_token_aqui
TELEGRAM_CHAT_ID=tu_chat_id_aqui

Y modifica tu script para cargar esas variables usando python-dotenv:

from dotenv import load_dotenv
import os

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

Instalas la librería:

pip install python-dotenv
