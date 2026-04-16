from flask import Flask, request
import requests
import anthropic
import os

app = Flask(__name__)

PAGE_TOKEN   = os.environ.get("PAGE_TOKEN", "")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "hospital123")
CLAUDE_KEY = os.environ.get("CLAUDE_KEY") or os.environ.get("claude_key") or ""

SYSTEM_PROMPT = """Eres el asistente virtual oficial de Hospital Tampico. Responde de manera amigable, clara y concisa. Usa emojis con moderación. NUNCA inventes información; si no sabes algo, indica que llamen al 833 306 1616.

INFORMACIÓN DEL HOSPITAL:
Nombre: Hospital Tampico
Dirección: Avenida Hidalgo #6307, Colonia Nuevo Aeropuerto, Tampico, Tamaulipas.
Teléfono: 833 306 1616
Horario: Lun–Vie 7am–8pm | Sáb 8am–3pm | Urgencias 24 hrs

SERVICIOS Y PRECIOS:
- Consulta medicina general: $350 MXN
- Consulta especialista: $600–$900 MXN
- Consulta pediatría: $450 MXN
- Biometría hemática: $180 MXN
- Ultrasonido obstétrico: $700 MXN
- Tomografía simple: $2,800 MXN
- Rayos X: $350 MXN
- Cuarto individual: $2,000 MXN/día
- Cesárea: desde $22,000 MXN

SEGUROS ACEPTADOS: GNP, AXA, MetLife, Seguros Monterrey
ESTACIONAMIENTO: Gratuito para pacientes
FARMACIA: Sí, mismo horario del hospital

REGLAS:
- Responde siempre en español
- Máximo 5 líneas por respuesta
- Si no tienes la info, indica llamar al 833 306 1616
- No des diagnósticos médicos"""

# Guardar historial simple por usuario
conversaciones = {}

@app.route("/", methods=["GET"])
def index():
    return "Bot Hospital Tampico funcionando ✅", 200

@app.route("/webhook", methods=["GET"])
def verify():
    mode  = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("✅ Webhook verificado")
        return challenge, 200
    return "Token inválido", 403

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    if data.get("object") == "page":
        for entry in data.get("entry", []):
            for event in entry.get("messaging", []):
                sender_id = event["sender"]["id"]
                if "message" in event and "text" in event["message"]:
                    texto = event["message"]["text"]
                    print(f"📨 Mensaje de {sender_id}: {texto}")
                    respuesta = get_ai_response(sender_id, texto)
                    send_message(sender_id, respuesta)
    return "OK", 200

def get_ai_response(user_id, texto):
    try:
        if user_id not in conversaciones:
            conversaciones[user_id] = []
        conversaciones[user_id].append({"role": "user", "content": texto})
        # Mantener solo últimos 10 mensajes
        if len(conversaciones[user_id]) > 10:
            conversaciones[user_id] = conversaciones[user_id][-10:]
        import os api_key = os.environ.get("CLAUDE_KEY", "") print(f"🔑 API Key presente: {bool(api_key)}") client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            system=SYSTEM_PROMPT,
            messages=conversaciones[user_id]
        )
        respuesta = response.content[0].text
        conversaciones[user_id].append({"role": "assistant", "content": respuesta})
        return respuesta
    except Exception as e:
        print(f"❌ Error Claude: {e}")
        return "Lo siento, hubo un error. Por favor llama al 833 306 1616."

def send_message(recipient_id, text):
    try:
        # Facebook limita mensajes a 2000 caracteres
        if len(text) > 2000:
            text = text[:1997] + "..."
        r = requests.post(
            "https://graph.facebook.com/v19.0/me/messages",
            params={"access_token": PAGE_TOKEN},
            json={
                "recipient": {"id": recipient_id},
                "message": {"text": text}
            }
        )
        print(f"✅ Mensaje enviado: {r.status_code}")
    except Exception as e:
        print(f"❌ Error enviando mensaje: {e}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
