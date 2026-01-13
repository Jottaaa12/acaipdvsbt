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

                const fromJid = msg.key.remoteJid;
                const isGroup = fromJid.endsWith('@g.us');

                let realAuthorJid;
                if (isGroup) {
                    realAuthorJid = msg.key.participant;

                    if (!realAuthorJid) {
                        return; // Sem participant, não há como identificar o autor
                    }

                    // Verificar se participant parece ser um ID de grupo ou está incorreto
                    const participantClean = realAuthorJid.replace('@', '').replace('s.whatsapp.net', '').replace('g.us', '');
                    const isLikelyGroupId = (
                        participantClean.length > 15 ||
                        (!participantClean.match(/^55\d{10,11}$/) && !participantClean.match(/^\d{10,11}$/)) ||
                        !realAuthorJid.includes('@s.whatsapp.net')
                    );

                    if (isLikelyGroupId) {
                        // Tentar fallbacks para obter o JID real do usuário
                        let fallbackJid = null;

                        // 1. Tentar msg.key.author
                        if (msg.key.author && msg.key.author.includes('@s.whatsapp.net')) {
                            fallbackJid = msg.key.author;
                        }

                        // 2. Tentar extrair do message object
                        if (!fallbackJid && msg.message) {
                            const participantFromMessage = msg.message.participant || msg.message.key?.participant;
                            if (participantFromMessage && participantFromMessage.includes('@s.whatsapp.net')) {
                                fallbackJid = participantFromMessage;
                            }
                        }

                        // 3. Tentar msg.key.senderPn
                        if (!fallbackJid && msg.key.senderPn && msg.key.senderPn.includes('@s.whatsapp.net')) {
                            fallbackJid = msg.key.senderPn;
                        }

                        // 4. Último recurso: buscar JIDs brasileiros válidos
                        if (!fallbackJid) {
                            if (msg.key.author && msg.key.author.includes('@s.whatsapp.net') && msg.key.author !== realAuthorJid) {
                                fallbackJid = msg.key.author;
                            }

                            if (!fallbackJid) {
                                // Buscar diretamente nos campos conhecidos ao invés de stringify
                                const potentialJids = [
                                    msg.key.participant,
                                    msg.key.author,
                                    msg.key.senderPn,
                                    msg.message?.participant
                                ].filter(jid => jid && /^\d{10,11}@s\.whatsapp\.net$/.test(jid));

                                if (potentialJids.length > 0) {
                                    fallbackJid = potentialJids[0];
                                }
                            }
                        }

                        // Aplicar o fallback se encontrado
                        if (fallbackJid) {
                            realAuthorJid = fallbackJid;
                        } else if (participantClean.match(/^\d{10,11}$/)) {
                            // Usar participant normalizado
                            realAuthorJid = participantClean + '@s.whatsapp.net';
                        }
                    }
                } else {
                    // Chat privado: usar senderPn ou fromJid
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
                            from: fromJid,
                            author: realAuthorJid,
                            isGroup: isGroup,
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
            try { await sock?.end?.(); } catch { }
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
                // Verificar se sock está conectado antes de tentar enviar
                if (!sock || !sock.user || !sock.user.id) {
                    response.error = 'WhatsApp não está conectado. Aguarde a conexão.';
                    safeLog(response);
                    return;
                }

                // Se for um ID de grupo ou LID, envie diretamente sem verificar.
                if (recipientId.endsWith('@g.us') || recipientId.endsWith('@lid')) {
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
                // Verificar se sock está conectado antes de tentar enviar
                if (!sock || !sock.user || !sock.user.id) {
                    response.error = 'WhatsApp não está conectado. Aguarde a conexão.';
                    safeLog(response);
                    return;
                }

                // Verificar se o arquivo existe
                if (!fs.existsSync(file_path)) {
                    response.error = `Arquivo não encontrado: ${file_path}`;
                    safeLog(response);
                    return;
                }

                // Preparar o JID correto
                let targetJid;
                if (chat_id.endsWith('@g.us') || chat_id.endsWith('@lid')) {
                    // Grupo ou LID - enviar diretamente
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
