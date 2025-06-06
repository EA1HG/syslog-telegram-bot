# Syslog Telegram Bot

Este script escucha mensajes syslog vía UDP, filtra mensajes específicos y envía notificaciones enriquecidas a Telegram con iconos según valores detectados.

## Requisitos

- Python 3.x
- Librerías: `requests`

Puedes instalarlas con:

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

