from flask import Flask, request, render_template_string, jsonify
from flask_socketio import SocketIO, emit
import requests
import anthropic
import os
import json
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'hospital123secret')
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins='*')

PAGE_TOKEN   = os.environ.get("PAGE_TOKEN", "")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "hospital123")
CLAUDE_KEY   = os.environ.get("CLAUDE_KEY", "")

print(f"PAGE_TOKEN presente: {bool(PAGE_TOKEN)}")
print(f"CLAUDE_KEY presente: {bool(CLAUDE_KEY)}")

SYSTEM_PROMPT = """Eres el asistente virtual oficial de Hospital Tampico. Responde de manera amigable, clara y concisa. Usa emojis con moderacion. NUNCA inventes informacion; si no sabes algo, indica que llamen al 833 306 1616.

INFORMACION DEL HOSPITAL:
Nombre: Hospital Tampico
Direccion: Avenida Hidalgo #6307, Colonia Nuevo Aeropuerto, Tampico, Tamaulipas.
Telefono: 833 306 1616
Horario: Lun-Vie 7am-8pm | Sab 8am-3pm | Urgencias 24 hrs

SERVICIOS Y PRECIOS:
- Consulta medicina general: $350 MXN
- Consulta especialista: $600-$900 MXN
- Consulta pediatria: $450 MXN
- Biometria hematica: $180 MXN
- Ultrasonido obstetrico: $700 MXN
- Tomografia simple: $2,800 MXN
- Rayos X: $350 MXN
- Cuarto individual: $2,000 MXN/dia
- Cesarea: desde $22,000 MXN

SEGUROS ACEPTADOS: GNP, AXA, MetLife, Seguros Monterrey
ESTACIONAMIENTO: Gratuito
FARMACIA: Si, mismo horario

REGLAS:
- Responde siempre en espanol
- Maximo 5 lineas por respuesta
- Si no tienes la info, indica llamar al 833 306 1616
- No des diagnosticos medicos"""

# Estado en memoria
conversaciones = {}  # {sender_id: [{role, content}]}
bot_pausado = {}     # {sender_id: True/False}
metadata = {}        # {sender_id: {nombre, canal, ultimo_msg}}

DASHBOARD_HTML = '''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Hospital Tampico – Panel de Mensajes</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Nunito',sans-serif;background:#f0f4f8;height:100vh;display:flex;flex-direction:column}
.topbar{background:#0d2d6e;color:#fff;padding:12px 20px;display:flex;align-items:center;justify-content:space-between;flex-shrink:0}
.topbar-left{display:flex;align-items:center;gap:12px}
.topbar h1{font-size:16px;font-weight:800}
.topbar-sub{font-size:12px;opacity:.6}
.status-badge{background:#22c55e;color:#fff;border-radius:20px;padding:4px 12px;font-size:12px;font-weight:700}
.main{display:flex;flex:1;overflow:hidden}
/* Sidebar */
.sidebar{width:280px;background:#fff;border-right:1px solid #e2e8f0;display:flex;flex-direction:column;flex-shrink:0}
.sidebar-header{padding:12px 14px;border-bottom:1px solid #f1f5f9}
.sidebar-header p{font-size:13px;font-weight:700;color:#0f172a;margin-bottom:8px}
.search{width:100%;padding:7px 12px;border:1px solid #e2e8f0;border-radius:8px;font-size:13px;font-family:'Nunito',sans-serif;outline:none;background:#f8fafc}
.conv-list{flex:1;overflow-y:auto}
.conv-item{padding:12px 14px;border-bottom:1px solid #f8fafc;cursor:pointer;display:flex;gap:10px;align-items:flex-start;transition:background .15s}
.conv-item:hover{background:#f8fafc}
.conv-item.active{background:#eff6ff}
.conv-item.unread{border-left:3px solid #0d2d6e}
.av{width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#fff;font-size:13px;font-weight:700;flex-shrink:0}
.av-fb{background:#0084ff}.av-ig{background:#e1306c}.av-wa{background:#25d366}
.conv-info{flex:1;min-width:0}
.conv-name{font-size:13px;font-weight:700;color:#0f172a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.conv-preview{font-size:11.5px;color:#64748b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:2px}
.conv-meta{display:flex;align-items:center;justify-content:space-between;margin-bottom:2px}
.conv-time{font-size:10px;color:#94a3b8}
.plat{font-size:10px;padding:1px 7px;border-radius:8px;font-weight:700}
.plat-fb{background:#dbeafe;color:#1e40af}
.plat-ig{background:#fce7f3;color:#9d174d}
.plat-wa{background:#dcfce7;color:#166534}
.unread-dot{width:8px;height:8px;border-radius:50%;background:#0d2d6e;flex-shrink:0;margin-top:4px}
/* Chat area */
.chat-area{flex:1;display:flex;flex-direction:column;min-width:0}
.chat-header{background:#fff;border-bottom:1px solid #e2e8f0;padding:10px 18px;display:flex;align-items:center;justify-content:space-between;flex-shrink:0}
.chat-header-left{display:flex;align-items:center;gap:10px}
.chat-name{font-size:14px;font-weight:700;color:#0f172a}
.chat-sub{font-size:12px;color:#64748b}
.btn{padding:6px 14px;border-radius:8px;font-size:12px;font-weight:700;cursor:pointer;font-family:'Nunito',sans-serif;border:1px solid;transition:all .15s}
.btn-bot{background:#f0fdf4;color:#16a34a;border-color:#bbf7d0}
.btn-human{background:#fffbeb;color:#92400e;border-color:#fde68a}
.btn-send{background:#0d2d6e;color:#fff;border-color:#0d2d6e;padding:8px 18px}
.btn-send:hover{background:#0a2156}
.btn-group{display:flex;gap:8px}
.messages{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:8px;background:#f8fafc}
.msg-row{display:flex}
.msg-row.out{justify-content:flex-end}
.msg-row.in{justify-content:flex-start;gap:8px;align-items:flex-end}
.msg-av{width:24px;height:24px;border-radius:50%;background:#0084ff;display:flex;align-items:center;justify-content:center;color:#fff;font-size:9px;flex-shrink:0}
.bubble{max-width:68%;padding:8px 13px;border-radius:12px;font-size:13px;line-height:1.45;word-break:break-word}
.bubble-in{background:#fff;border:1px solid #e2e8f0;border-bottom-left-radius:3px;color:#0f172a}
.bubble-out-bot{background:#0d2d6e;color:#fff;border-bottom-right-radius:3px}
.bubble-out-human{background:#f59e0b;color:#fff;border-bottom-right-radius:3px}
.msg-label{font-size:9px;padding:1px 7px;border-radius:8px;margin-bottom:3px;display:inline-block}
.label-bot{background:#f0fdf4;color:#166534}
.label-human{background:#fffbeb;color:#92400e}
.msg-time{font-size:10px;color:#94a3b8;margin-top:2px}
.msg-row.out .msg-time{text-align:right}
.paused-bar{background:#fffbeb;border-top:1px solid #fde68a;padding:8px 18px;display:flex;align-items:center;justify-content:space-between;font-size:12px;color:#92400e;flex-shrink:0}
.input-bar{background:#fff;border-top:1px solid #e2e8f0;padding:10px 18px;display:flex;gap:8px;align-items:center;flex-shrink:0}
.input-bar input{flex:1;padding:9px 14px;border:1px solid #e2e8f0;border-radius:8px;font-size:13px;font-family:'Nunito',sans-serif;outline:none;background:#f8fafc}
.bot-bar{background:#f0fdf4;border-top:1px solid #bbf7d0;padding:9px 18px;font-size:12px;color:#166534;text-align:center;flex-shrink:0}
.empty-state{flex:1;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:12px;color:#94a3b8}
.empty-state .icon{font-size:48px}
.empty-state p{font-size:14px}
/* Right panel */
.right-panel{width:200px;background:#fff;border-left:1px solid #e2e8f0;padding:16px;display:flex;flex-direction:column;gap:16px;flex-shrink:0;overflow-y:auto}
.rp-title{font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px}
.stat-card{background:#f8fafc;border-radius:8px;padding:10px 12px;margin-bottom:8px}
.stat-num{font-size:24px;font-weight:700;color:#0d2d6e}
.stat-lbl{font-size:11px;color:#64748b;margin-top:2px}
.rp-row{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;font-size:12px}
.rp-label{color:#64748b}
.rp-val{font-weight:700;color:#0f172a}
</style>
</head>
<body>
<div class="topbar">
  <div class="topbar-left">
    <span style="font-size:22px">🏥</span>
    <div>
      <h1>Hospital Tampico — Panel de Mensajes</h1>
      <div class="topbar-sub">Bandeja unificada de conversaciones</div>
    </div>
  </div>
  <div style="display:flex;align-items:center;gap:10px">
    <span id="conv-count" style="font-size:12px;opacity:.7">0 conversaciones</span>
    <div class="status-badge">● Bot activo</div>
  </div>
</div>

<div class="main">
  <!-- Sidebar -->
  <div class="sidebar">
    <div class="sidebar-header">
      <p>Conversaciones</p>
      <input class="search" placeholder="Buscar..." oninput="filterConvs(this.value)" />
    </div>
    <div class="conv-list" id="conv-list">
      <div class="empty-state" style="padding:40px 20px;text-align:center">
        <div class="icon">💬</div>
        <p>Esperando mensajes...</p>
      </div>
    </div>
  </div>

  <!-- Chat area -->
  <div class="chat-area" id="chat-area">
    <div class="empty-state">
      <div class="icon">🤖</div>
      <p>Selecciona una conversación</p>
    </div>
  </div>

  <!-- Right panel -->
  <div class="right-panel">
    <div>
      <div class="rp-title">Hoy</div>
      <div class="stat-card">
        <div class="stat-num" id="stat-total">0</div>
        <div class="stat-lbl">conversaciones</div>
      </div>
      <div class="stat-card" style="background:#fef9c3">
        <div class="stat-num" id="stat-human" style="color:#92400e">0</div>
        <div class="stat-lbl">atención humana</div>
      </div>
    </div>
    <div>
      <div class="rp-title">Canales</div>
      <div class="rp-row"><span class="rp-label">💬 Messenger</span><span class="rp-val" id="stat-fb">0</span></div>
      <div class="rp-row"><span class="rp-label">📸 Instagram</span><span class="rp-val" id="stat-ig">0</span></div>
      <div class="rp-row"><span class="rp-label">📱 WhatsApp</span><span class="rp-val" id="stat-wa">0</span></div>
    </div>
    <div id="contact-info" style="display:none">
      <div class="rp-title">Contacto activo</div>
      <div class="rp-row"><span class="rp-label">Canal</span><span class="rp-val" id="ci-canal">—</span></div>
      <div class="rp-row"><span class="rp-label">Mensajes</span><span class="rp-val" id="ci-msgs">0</span></div>
      <div class="rp-row"><span class="rp-label">Bot</span><span class="rp-val" id="ci-bot">Activo</span></div>
    </div>
  </div>
</div>

<script>
const socket = io();
let convs = {};
let activeId = null;

socket.on('nuevo_mensaje', function(data) {
  const id = data.sender_id;
  if (!convs[id]) {
    convs[id] = { sender_id: id, canal: data.canal, mensajes: [], pausado: false, unread: 0 };
  }
  convs[id].mensajes.push({ role: data.role, text: data.text, time: data.time, tipo: data.tipo });
  if (id !== activeId) convs[id].unread = (convs[id].unread || 0) + 1;
  renderSidebar();
  if (id === activeId) renderChat(id);
  updateStats();
});

socket.on('bot_toggle', function(data) {
  if (convs[data.sender_id]) {
    convs[data.sender_id].pausado = data.pausado;
    if (data.sender_id === activeId) renderChat(data.sender_id);
    renderSidebar();
  }
});

function renderSidebar() {
  const list = document.getElementById('conv-list');
  const ids = Object.keys(convs);
  document.getElementById('conv-count').textContent = ids.length + ' conversaciones';
  if (ids.length === 0) {
    list.innerHTML = '<div class="empty-state" style="padding:40px 20px;text-align:center"><div class="icon">💬</div><p>Esperando mensajes...</p></div>';
    return;
  }
  list.innerHTML = ids.map(id => {
    const c = convs[id];
    const last = c.mensajes[c.mensajes.length - 1];
    const platClass = c.canal === 'fb' ? 'plat-fb' : c.canal === 'ig' ? 'plat-ig' : 'plat-wa';
    const platLabel = c.canal === 'fb' ? 'FB' : c.canal === 'ig' ? 'IG' : 'WA';
    const avClass = c.canal === 'fb' ? 'av-fb' : c.canal === 'ig' ? 'av-ig' : 'av-wa';
    const initials = id.toString().slice(-2).toUpperCase();
    return `<div class="conv-item ${id === activeId ? 'active' : ''} ${c.unread ? 'unread' : ''}" onclick="selectConv('${id}')">
      <div class="av ${avClass}">${initials}</div>
      <div class="conv-info">
        <div class="conv-meta">
          <span class="plat ${platClass}">${platLabel}</span>
          <span class="conv-time">${last ? last.time : ''}</span>
        </div>
        <div class="conv-name">Usuario ${id.toString().slice(-6)}</div>
        <div class="conv-preview">${last ? last.text.substring(0, 40) : ''}</div>
      </div>
      ${c.unread ? '<div class="unread-dot"></div>' : ''}
    </div>`;
  }).join('');
}

function selectConv(id) {
  activeId = id;
  if (convs[id]) convs[id].unread = 0;
  renderSidebar();
  renderChat(id);
  // Update contact info
  const c = convs[id];
  document.getElementById('contact-info').style.display = 'block';
  document.getElementById('ci-canal').textContent = c.canal === 'fb' ? 'Messenger' : c.canal === 'ig' ? 'Instagram' : 'WhatsApp';
  document.getElementById('ci-msgs').textContent = c.mensajes.length;
  document.getElementById('ci-bot').textContent = c.pausado ? 'Pausado' : 'Activo';
}

function renderChat(id) {
  const c = convs[id];
  if (!c) return;
  const area = document.getElementById('chat-area');
  const msgsHtml = c.mensajes.map(m => {
    if (m.role === 'user') {
      return `<div class="msg-row in">
        <div class="msg-av">${id.toString().slice(-2).toUpperCase()}</div>
        <div><div class="bubble bubble-in">${m.text}</div><div class="msg-time">${m.time}</div></div>
      </div>`;
    } else {
      const isHuman = m.tipo === 'human';
      return `<div class="msg-row out">
        <div>
          <div class="msg-label ${isHuman ? 'label-human' : 'label-bot'}">${isHuman ? '✋ Personal' : '● Bot'}</div>
          <div class="bubble ${isHuman ? 'bubble-out-human' : 'bubble-out-bot'}">${m.text}</div>
          <div class="msg-time">${m.time}</div>
        </div>
      </div>`;
    }
  }).join('');

  const botBar = c.pausado
    ? `<div class="paused-bar">⚠️ Bot pausado — respondiendo manualmente <button class="btn btn-bot" onclick="reactivarBot()">Reactivar bot</button></div>
       <div class="input-bar"><input id="manual-input" placeholder="Escribe tu respuesta..." onkeydown="if(event.key==='Enter')enviarManual()" /><button class="btn btn-send" onclick="enviarManual()">Enviar</button></div>`
    : `<div class="bot-bar">🤖 El bot está respondiendo automáticamente — <button class="btn btn-human" onclick="tomarControl()" style="margin-left:8px">✋ Tomar control</button></div>`;

  area.innerHTML = `
    <div class="chat-header">
      <div class="chat-header-left">
        <div class="av ${c.canal === 'fb' ? 'av-fb' : c.canal === 'ig' ? 'av-ig' : 'av-wa'}">${id.toString().slice(-2).toUpperCase()}</div>
        <div>
          <div class="chat-name">Usuario ${id.toString().slice(-6)}</div>
          <div class="chat-sub">${c.canal === 'fb' ? 'Facebook Messenger' : c.canal === 'ig' ? 'Instagram DM' : 'WhatsApp'} · ${c.pausado ? '✋ Atención humana' : '🤖 Bot activo'}</div>
        </div>
      </div>
      <div class="btn-group">
        <button class="btn ${c.pausado ? 'btn-human' : 'btn-bot'}" onclick="${c.pausado ? 'reactivarBot()' : 'tomarControl()'}">${c.pausado ? '⏸ Bot pausado' : '● Bot activo'}</button>
      </div>
    </div>
    <div class="messages" id="messages">${msgsHtml}</div>
    ${botBar}`;

  setTimeout(() => {
    const msgs = document.getElementById('messages');
    if (msgs) msgs.scrollTop = msgs.scrollHeight;
  }, 50);
}

function tomarControl() {
  if (!activeId) return;
  fetch('/toggle_bot', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({sender_id: activeId, pausado: true}) });
}

function reactivarBot() {
  if (!activeId) return;
  fetch('/toggle_bot', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({sender_id: activeId, pausado: false}) });
}

function enviarManual() {
  const input = document.getElementById('manual-input');
  const text = input ? input.value.trim() : '';
  if (!text || !activeId) return;
  fetch('/send_manual', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({sender_id: activeId, text: text}) });
  input.value = '';
}

function updateStats() {
  const ids = Object.keys(convs);
  document.getElementById('stat-total').textContent = ids.length;
  document.getElementById('stat-human').textContent = ids.filter(id => convs[id].pausado).length;
  document.getElementById('stat-fb').textContent = ids.filter(id => convs[id].canal === 'fb').length;
  document.getElementById('stat-ig').textContent = ids.filter(id => convs[id].canal === 'ig').length;
  document.getElementById('stat-wa').textContent = ids.filter(id => convs[id].canal === 'wa').length;
}

function filterConvs(q) {
  document.querySelectorAll('.conv-item').forEach(el => {
    el.style.display = el.textContent.toLowerCase().includes(q.toLowerCase()) ? '' : 'none';
  });
}
</script>
</body>
</html>'''

@app.route('/')
def dashboard():
    return render_template_string(DASHBOARD_HTML)

@app.route('/webhook', methods=['GET'])
def verify():
    mode      = request.args.get('hub.mode')
    token     = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    if mode == 'subscribe' and token == VERIFY_TOKEN:
        print('Webhook verificado OK')
        return challenge, 200
    return 'Token invalido', 403

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    if data.get('object') == 'page':
        for entry in data.get('entry', []):
            for event in entry.get('messaging', []):
                sender_id = event['sender']['id']
                if 'message' in event and 'text' in event['message']:
                    texto = event['message']['text']
                    print(f'Mensaje de {sender_id}: {texto}')
                    now = datetime.now().strftime('%H:%M')
                    # Emit to dashboard
                    socketio.emit('nuevo_mensaje', {
                        'sender_id': sender_id,
                        'role': 'user',
                        'text': texto,
                        'time': now,
                        'canal': 'fb',
                        'tipo': 'user'
                    })
                    # Respond if bot not paused
                    if not bot_pausado.get(sender_id, False):
                        respuesta = get_ai_response(sender_id, texto)
                        send_fb_message(sender_id, respuesta)
                        socketio.emit('nuevo_mensaje', {
                            'sender_id': sender_id,
                            'role': 'assistant',
                            'text': respuesta,
                            'time': datetime.now().strftime('%H:%M'),
                            'canal': 'fb',
                            'tipo': 'bot'
                        })
    return 'OK', 200

@app.route('/toggle_bot', methods=['POST'])
def toggle_bot():
    data = request.json
    sender_id = data.get('sender_id')
    pausado   = data.get('pausado', False)
    bot_pausado[sender_id] = pausado
    socketio.emit('bot_toggle', {'sender_id': sender_id, 'pausado': pausado})
    return jsonify({'ok': True})

@app.route('/send_manual', methods=['POST'])
def send_manual():
    data = request.json
    sender_id = data.get('sender_id')
    text      = data.get('text', '')
    if sender_id and text:
        send_fb_message(sender_id, text)
        socketio.emit('nuevo_mensaje', {
            'sender_id': sender_id,
            'role': 'assistant',
            'text': text,
            'time': datetime.now().strftime('%H:%M'),
            'canal': 'fb',
            'tipo': 'human'
        })
    return jsonify({'ok': True})

def get_ai_response(user_id, texto):
    try:
        if user_id not in conversaciones:
            conversaciones[user_id] = []
        conversaciones[user_id].append({'role': 'user', 'content': texto})
        if len(conversaciones[user_id]) > 10:
            conversaciones[user_id] = conversaciones[user_id][-10:]
        client = anthropic.Anthropic(api_key=CLAUDE_KEY)
        response = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=500,
            system=SYSTEM_PROMPT,
            messages=conversaciones[user_id]
        )
        respuesta = response.content[0].text
        conversaciones[user_id].append({'role': 'assistant', 'content': respuesta})
        return respuesta
    except Exception as e:
        print(f'Error Claude: {e}')
        return 'Lo siento, hubo un error. Por favor llama al 833 306 1616.'

def send_fb_message(recipient_id, text):
    try:
        if len(text) > 2000:
            text = text[:1997] + '...'
        r = requests.post(
            'https://graph.facebook.com/v19.0/me/messages',
            params={'access_token': PAGE_TOKEN},
            json={'recipient': {'id': recipient_id}, 'message': {'text': text}}
        )
        print(f'FB enviado: {r.status_code}')
    except Exception as e:
        print(f'Error FB: {e}')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port)
