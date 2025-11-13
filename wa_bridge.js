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
      logger: pino({ level: 'silent' }),
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
            if (!msg.message || msg.key.fromMe || !msg.key.remoteJid || msg.key.remoteJid.endsWith('status@broadcast')) {
                return;
            }

            const fromJid = msg.key.remoteJid; // Onde responder (grupo ou chat privado)
            const isGroup = fromJid.endsWith('@g.us');
            
            let realAuthorJid;
            if (isGroup) {
                // Em um grupo, o autor é sempre o participante
                realAuthorJid = msg.key.participant;
            } else {
                // Em um chat privado, o autor é o próprio chat.
                // Usamos `senderPn` se existir para resolver LIDs para um número real.
                realAuthorJid = msg.key.senderPn || fromJid;
            }

            if (!realAuthorJid) {
                return; // Não processa se não conseguir identificar o autor
            }

            const text = msg.message.conversation || msg.message.extendedTextMessage?.text;
            
            if (text) {
                safeLog({
                    type: 'message',
                    data: {
                        from: fromJid,          // O JID da conversa
                        author: realAuthorJid,  // O JID real do autor
                        isGroup: isGroup,       // Flag para indicar se é um grupo
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
      const recipientId = msg.phone || '';
      const text = msg.message || '';
      const message_id = msg.message_id || null;

      if (!recipientId || !text) return;

      let response = {
        type: 'message_result',
        message_id: message_id,
        success: false,
        error: null,
        phone: recipientId,
        phone_validation_attempted: false,
        phone_exists: false
      };

      try {
        // Se for um ID de grupo, envie diretamente sem verificar.
        if (recipientId.endsWith('@g.us')) {
          await sock.sendMessage(recipientId, { text });
          response.success = true;
          safeLog(response);
          return;
        }

        // Se não for um grupo, é um usuário. Prossiga com a validação.
        const jid = recipientId.endsWith('@s.whatsapp.net') ? recipientId : recipientId.replace(/[^\d]/g, '') + '@s.whatsapp.net';

        const [result] = await sock.onWhatsApp(jid);
        if (!result?.exists) {
            response.phone_validation_attempted = true;
            response.phone_exists = false;
            response.error = `O número ${recipientId} não existe no WhatsApp.`;
            safeLog(response);
            return;
        }

        response.phone_validation_attempted = true;
        response.phone_exists = true;

        // Use o JID retornado pela verificação, pois ele pode ser corrigido pelo servidor
        const correctJid = result.jid;
        await sock.sendMessage(correctJid, { text });
        response.success = true;
        safeLog(response);

      } catch (e) {
        response.error = 'Falha ao enviar mensagem: ' + (e?.message || e.toString());
        safeLog(response);
      }
      return;
    }
  });

  rl.on('close', () => {
    process.exit(0);
  });
})();
