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

            // Logging detalhado para debug do problema de identificação de usuário em grupos
            safeLog({
                type: 'debug_message',
                data: {
                    fromJid: fromJid,
                    isGroup: isGroup,
                    participant: msg.key.participant,
                    senderPn: msg.key.senderPn,
                    author: msg.key.author,
                    id: msg.key.id,
                    messageType: msg.message ? Object.keys(msg.message)[0] : 'unknown'
                }
            });

            let realAuthorJid;
            if (isGroup) {
                // Em um grupo, o autor é sempre o participante
                realAuthorJid = msg.key.participant;

                // Verificação adicional para casos onde participant pode estar incorreto
                if (!realAuthorJid) {
                    safeLog({
                        type: 'debug_error',
                        data: {
                            error: 'participant_undefined',
                            fromJid: fromJid,
                            messageId: msg.key.id,
                            messageKeys: Object.keys(msg.key)
                        }
                    });
                    return;
                }

                // MELHORADA: Verificar se participant parece ser um ID de grupo ou está incorreto
                // IDs de grupo geralmente são números muito longos (>15 dígitos) ou não têm formato de telefone
                const participantClean = realAuthorJid.replace('@', '').replace('s.whatsapp.net', '').replace('g.us', '');
                const isLikelyGroupId = (
                    // ID muito longo (IDs de grupo têm mais de 15 dígitos geralmente)
                    participantClean.length > 15 ||
                    // ID que não parece um número de telefone brasileiro (não começa com códigos válidos)
                    (!participantClean.match(/^55\d{10,11}$/) && !participantClean.match(/^\d{10,11}$/)) ||
                    // ID que não tem sufixo @s.whatsapp.net
                    !realAuthorJid.includes('@s.whatsapp.net')
                );

                if (isLikelyGroupId) {
                    safeLog({
                        type: 'debug_warning',
                        data: {
                            warning: 'possible_invalid_participant_detected',
                            participant: realAuthorJid,
                            participant_clean: participantClean,
                            fromJid: fromJid,
                            messageId: msg.key.id,
                            attempting_fallback: true
                        }
                    });

                    // Tentar múltiplos fallbacks para obter o JID real do usuário
                    let fallbackJid = null;

                    // 1. Tentar msg.key.author (mais confiável para mensagens em grupo)
                    if (msg.key.author && msg.key.author.includes('@s.whatsapp.net')) {
                        fallbackJid = msg.key.author;
                        safeLog({
                            type: 'debug_info',
                            data: {
                                info: 'using_author_as_fallback',
                                original_participant: realAuthorJid,
                                fallback_author: fallbackJid,
                                messageId: msg.key.id
                            }
                        });
                    }

                    // 2. Tentar extrair do message object
                    if (!fallbackJid && msg.message) {
                        const participantFromMessage = msg.message.participant || msg.message.key?.participant;
                        if (participantFromMessage && participantFromMessage.includes('@s.whatsapp.net')) {
                            fallbackJid = participantFromMessage;
                            safeLog({
                                type: 'debug_info',
                                data: {
                                    info: 'using_message_participant_as_fallback',
                                    original_participant: realAuthorJid,
                                    fallback_message_participant: fallbackJid,
                                    messageId: msg.key.id
                                }
                            });
                        }
                    }

                    // 3. Tentar msg.key.senderPn (número real do dispositivo)
                    if (!fallbackJid && msg.key.senderPn && msg.key.senderPn.includes('@s.whatsapp.net')) {
                        fallbackJid = msg.key.senderPn;
                        safeLog({
                            type: 'debug_info',
                            data: {
                                info: 'using_senderPn_as_fallback',
                                original_participant: realAuthorJid,
                                fallback_senderPn: fallbackJid,
                                messageId: msg.key.id
                            }
                        });
                    }

                    // 4. Último recurso: tentar encontrar o JID correto de forma mais precisa
                    if (!fallbackJid) {
                        // Primeiro tentar encontrar no msg.key.author se existir
                        if (msg.key.author && msg.key.author.includes('@s.whatsapp.net') && msg.key.author !== realAuthorJid) {
                            fallbackJid = msg.key.author;
                            safeLog({
                                type: 'debug_info',
                                data: {
                                    info: 'using_key_author_as_final_fallback',
                                    original_participant: realAuthorJid,
                                    fallback_extracted: fallbackJid,
                                    messageId: msg.key.id
                                }
                            });
                        }

                        // Se ainda não encontrou, procurar especificamente por JIDs que parecem números brasileiros
                        if (!fallbackJid) {
                            const messageStr = JSON.stringify(msg);
                            // Procurar por padrões que parecem números brasileiros válidos
                            const brazilianNumbers = messageStr.match(/\b\d{10,11}@s\.whatsapp\.net\b/g);

                            if (brazilianNumbers && brazilianNumbers.length > 0) {
                                // Filtrar números que parecem válidos (não são IDs de grupo)
                                const validNumbers = brazilianNumbers.filter(jid => {
                                    const numberPart = jid.replace('@s.whatsapp.net', '');
                                    // Deve ter 10 ou 11 dígitos e começar com códigos de área brasileiros válidos
                                    return /^\d{10,11}$/.test(numberPart) &&
                                           (numberPart.startsWith('88') || // Ceará
                                            numberPart.startsWith('85') || // Ceará
                                            numberPart.match(/^8[1-9]/) || // Outros códigos da região
                                            numberPart.match(/^[1-9][1-9]/)); // Códigos de área gerais
                                });

                                if (validNumbers.length > 0) {
                                    fallbackJid = validNumbers[0]; // Pegar o primeiro válido
                                    safeLog({
                                        type: 'debug_info',
                                        data: {
                                            info: 'using_filtered_brazilian_jid',
                                            original_participant: realAuthorJid,
                                            fallback_extracted: fallbackJid,
                                            all_found: brazilianNumbers,
                                            valid_found: validNumbers,
                                            messageId: msg.key.id
                                        }
                                    });
                                }
                            }
                        }
                    }

                    // Aplicar o fallback se encontrado
                    if (fallbackJid) {
                        realAuthorJid = fallbackJid;
                        safeLog({
                            type: 'debug_success',
                            data: {
                                success: 'fallback_applied',
                                original_participant: msg.key.participant,
                                new_real_author_jid: realAuthorJid,
                                messageId: msg.key.id
                            }
                        });
                    } else {
                        safeLog({
                            type: 'debug_error',
                            data: {
                                error: 'no_valid_fallback_found',
                                participant: realAuthorJid,
                                fromJid: fromJid,
                                messageId: msg.key.id,
                                available_keys: Object.keys(msg.key),
                                message_keys: msg.message ? Object.keys(msg.message) : [],
                                all_jids_found: JSON.stringify(msg).match(/\d+@s\.whatsapp\.net/g) || []
                            }
                        });
                        // Mesmo sem fallback, tentar usar o participant original se parecer válido
                        if (participantClean.match(/^\d{10,11}$/)) {
                            realAuthorJid = participantClean + '@s.whatsapp.net';
                            safeLog({
                                type: 'debug_info',
                                data: {
                                    info: 'using_normalized_participant',
                                    original_participant: msg.key.participant,
                                    normalized_participant: realAuthorJid,
                                    messageId: msg.key.id
                                }
                            });
                        }
                    }
                }
            } else {
                // Em um chat privado, o autor é o próprio chat.
                // Usamos `senderPn` se existir para resolver LIDs para um número real.
                realAuthorJid = msg.key.senderPn || fromJid;
            }

            if (!realAuthorJid) {
                safeLog({
                    type: 'debug_error',
                    data: {
                        error: 'realAuthorJid_undefined',
                        fromJid: fromJid,
                        isGroup: isGroup,
                        participant: msg.key.participant,
                        senderPn: msg.key.senderPn
                    }
                });
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

    if (msg.action === 'send_media') {
      const chat_id = msg.chat_id || '';
      const file_path = msg.file_path || '';
      const caption = msg.caption || '';
      const message_id = msg.message_id || null;

      if (!chat_id || !file_path) return;

      let response = {
        type: 'message_result',
        message_id: message_id,
        success: false,
        error: null,
        phone: chat_id,
        phone_validation_attempted: false,
        phone_exists: false
      };

      try {
        // Verificar se o arquivo existe
        if (!fs.existsSync(file_path)) {
          response.error = `Arquivo não encontrado: ${file_path}`;
          safeLog(response);
          return;
        }

        // Preparar o JID correto
        let targetJid;
        if (chat_id.endsWith('@g.us')) {
          // Grupo - enviar diretamente
          targetJid = chat_id;
        } else {
          // Usuário - validar e converter
          const jid = chat_id.endsWith('@s.whatsapp.net') ? chat_id : chat_id.replace(/[^\d]/g, '') + '@s.whatsapp.net';
          const [result] = await sock.onWhatsApp(jid);
          if (!result?.exists) {
            response.phone_validation_attempted = true;
            response.phone_exists = false;
            response.error = `O número ${chat_id} não existe no WhatsApp.`;
            safeLog(response);
            return;
          }
          response.phone_validation_attempted = true;
          response.phone_exists = true;
          targetJid = result.jid;
        }

        // Ler o arquivo e criar buffer
        const fileBuffer = fs.readFileSync(file_path);
        const fileName = path.basename(file_path);

        // Determinar o tipo MIME baseado na extensão
        const ext = path.extname(file_path).toLowerCase();
        let mimetype = 'application/octet-stream';
        if (ext === '.jpg' || ext === '.jpeg') mimetype = 'image/jpeg';
        else if (ext === '.png') mimetype = 'image/png';
        else if (ext === '.gif') mimetype = 'image/gif';
        else if (ext === '.pdf') mimetype = 'application/pdf';

        // Enviar a mídia
        await sock.sendMessage(targetJid, {
          document: fileBuffer,
          mimetype: mimetype,
          fileName: fileName,
          caption: caption
        });

        response.success = true;
        safeLog(response);

      } catch (e) {
        response.error = 'Falha ao enviar mídia: ' + (e?.message || e.toString());
        safeLog(response);
      }
      return;
    }
  });

  rl.on('close', () => {
    process.exit(0);
  });
})();
