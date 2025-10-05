
const fs = require('fs');
const path = require('path');

function safeLog(obj) {
  try {
    process.stdout.write(JSON.stringify(obj) + '\n');
  } catch (e) {
    // ignore
  }
}

(async () => {
  let baileys;
  let pino;
  try {
    baileys = require('@whiskeysockets/baileys');
    pino = require('pino');
  } catch (e) {
    safeLog({ type: 'error', data: "Dependências Node ausentes. Instale com: npm i @whiskeysockets/baileys pino" });
    process.exit(1);
    return;
  }

  const { default: makeWASocket, useMultiFileAuthState, DisconnectReason, fetchLatestBaileysVersion } = baileys;
  const args = process.argv.slice(2);
  const sessionPath = args[0] || path.join(process.cwd(), 'whatsapp_session');

  const { state, saveCreds } = await useMultiFileAuthState(sessionPath);
  const { version } = await fetchLatestBaileysVersion();
  let sock;

  function startSock() {
    sock = makeWASocket({
      version,
      auth: state,
      printQRInTerminal: false,
      browser: ['PDV-Desktop', 'Chrome', '1.0.0'],
      logger: pino({ level: 'trace' }),
      markOnlineOnConnect: false,
      syncFullHistory: false,
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', (update) => {
        const { connection, lastDisconnect, qr } = update;
        if (qr) {
            safeLog({ type: 'qr', data: qr });
        }

        if (connection === 'close') {
            const reason = lastDisconnect?.error?.output?.statusCode;
            const shouldReconnect = reason !== DisconnectReason.loggedOut;
            
            safeLog({ type: 'status', data: `Conexão fechada, motivo: ${reason}. Tentando reconectar: ${shouldReconnect}` });

            if (shouldReconnect) {
                startSock();
            } else {
                safeLog({ type: 'status', data: 'Desconectado permanentemente.' });
                try {
                    if (fs.existsSync(sessionPath)) {
                        fs.rmSync(sessionPath, { recursive: true, force: true });
                    }
                } catch (e) {
                    safeLog({ type: 'error', data: 'Falha ao remover sessão.' });
                }
                process.exit(0);
            }
        } else if (connection === 'open') {
            safeLog({ type: 'status', data: 'connected' });
        } else {
            safeLog({ type: 'status', data: connection });
        }
    });

    sock.ev.on('messages.upsert', m => {
        m.messages.forEach(msg => {
            if (!msg.message || msg.key.fromMe) {
                return;
            }
            const sender = msg.key.remoteJid;
            const text = msg.message.conversation || msg.message.extendedTextMessage?.text;
            if (sender && text) {
                safeLog({
                    type: 'message',
                    data: {
                        sender: sender.split('@')[0],
                        text: text
                    }
                });
            }
        });
    });
  }

  startSock();

  // Leitura de comandos via STDIN (NDJSON)
  const readline = require('readline');
  const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });

  rl.on('line', async (line) => {
    let msg;
    try { msg = JSON.parse(line); } catch { return; }
    if (!msg || typeof msg !== 'object') return;

    if (msg.action === 'shutdown') {
      try { await sock?.end?.(); } catch {}
      process.exit(0);
      return;
    }

    if (msg.action === 'send') {
      const phone = (msg.phone || '').replace(/[^\d]/g, '');
      const text = msg.message || '';
      if (!phone || !text) return;
      
      try {
        const jid = phone.endsWith('@s.whatsapp.net') ? phone : phone + '@s.whatsapp.net';
        
        const [result] = await sock.onWhatsApp(jid);
        if (!result?.exists) {
            safeLog({ type: 'error', data: `O número ${phone} não existe no WhatsApp.` });
            return;
        }

        // Use the JID returned by onWhatsApp, as it might be corrected by the server
        const correctJid = result.jid;
        await sock.sendMessage(correctJid, { text });
        safeLog({ type: 'log', data: 'Mensagem enviada com sucesso.' });

      } catch (e) {
        safeLog({ type: 'error', data: 'Falha ao enviar mensagem: ' + (e?.message || e) });
      }
      return;
    }
  });

  rl.on('close', () => {
    process.exit(0);
  });
})();
