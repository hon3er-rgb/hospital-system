footer_html = """
    </div> <!-- end container -->

    <!-- AUDIO ELEMENTS -->
    <!-- Sound: Precise Medical Frequency -->
    <audio id="ringtoneCall" preload="auto" loop><source src="https://assets.mixkit.co/active_storage/sfx/1359/1359-preview.mp3" type="audio/mpeg"></audio>
    <audio id="remoteAudioTrack" autoplay playsinline></audio>

    <!-- PREMIUM GLASS CALL POPUP -->
    <div id="incomingCallPopup" class="position-fixed top-0 start-50 translate-middle-x mt-4 shadow-2xl animate__animated animate__zoomIn"
        style="z-index:9999999; display:none; width:400px; pointer-events: auto;">
        <div class="card border-0 rounded-5 overflow-hidden shadow-2xl" 
             style="background: rgba(255,255,255,0.85); backdrop-filter: blur(50px); border: 2px solid rgba(0,122,255,0.1) !important;">
            <div class="card-body p-4 text-center">
                <div id="incomingCallAvatar" class="bg-primary text-white rounded-circle mx-auto mb-3 d-flex align-items-center justify-content-center fw-bold shadow-lg animate__animated animate__pulse animate__infinite" 
                     style="width:100px;height:100px;font-size:2.4rem; background: linear-gradient(135deg, #007aff, #5856d6) !important;">?</div>
                <h3 class="fw-bold mb-1" id="callerNameDisplay" style="color: #000 !important;">مكالمة طبية واردة</h3>
                <div class="text-primary small mb-4 fw-bold"><i class="fas fa-stethoscope me-1"></i> اتصال مباشر الآن</div>
                <div class="d-flex justify-content-center gap-2">
                    <button class="btn btn-outline-danger rounded-pill px-4" onclick="rejectIncomingCall()">رفض</button>
                    <button class="btn btn-primary rounded-pill px-5 py-2 fw-bold shadow-lg" onclick="acceptIncomingCall()" 
                            style="background: linear-gradient(135deg, #007aff, #5856d6) !important;">إجابة</button>
                </div>
            </div>
        </div>
    </div>

    <!-- COMMAND CENTER PRO INTERFACE -->
    <div id="videoCallInterface" class="position-fixed top-0 start-0 w-100 h-100 animate__animated animate__fadeIn"
        style="z-index:9999998; display:none; background: #000 !important;">
        <video id="remoteVideo" class="w-100 h-100" style="object-fit: contain; background: #000;" playsinline autoplay></video>
        <div class="position-absolute d-flex flex-column gap-3" style="bottom: 40px; left: 40px; z-index: 250;">
            <div class="shadow-lg border-2 border-white rounded-5 overflow-hidden" 
                 style="width: 280px; height: 170px; border: 3px solid rgba(255,255,255,0.2) !important;">
                <video id="localVideo" class="w-100 h-100" style="object-fit: cover;" autoplay muted playsinline></video>
            </div>
        </div>
        <div class="position-absolute top-0 start-0 w-100 p-5 d-flex justify-content-between align-items-start text-white" style="z-index:250;">
            <div>
                <h4 class="fw-bold mb-0" id="callRemoteName">...</h4>
                <div class="small fw-bold text-success animate__animated animate__flash animate__infinite mt-1">● اتصال طبي مباشر عالي الثبات</div>
                <span id="callTimeDisplay" class="badge bg-danger mt-1">00:00</span>
            </div>
            <button class="btn btn-danger btn-lg rounded-circle p-4 shadow-lg border-4 border-white border-opacity-25" onclick="endCurrentCall()" style="width: 90px; height:90px;"><i class="fas fa-phone-slash fa-2x"></i></button>
        </div>
        <div class="position-absolute bottom-0 start-0 w-100 p-5 d-flex justify-content-center gap-4 align-items-center" style="z-index:250;">
            <button class="btn btn-light rounded-circle shadow p-3" onclick="toggleMic()"><i class="fas fa-microphone fa-lg" id="micIconMain"></i></button>
            <button class="btn btn-light rounded-circle shadow p-3" onclick="toggleCam()"><i class="fas fa-video fa-lg" id="camIconMain"></i></button>
        </div>
    </div>

    <div id="statusIndicator" class="position-fixed bottom-0 end-0 m-3 px-3 py-1 rounded-pill bg-dark text-white fw-bold shadow-lg" style="z-index:9999999; font-size:0.6rem; opacity:0.6; display:none;">
        HYPER-SIGNAL: <span id="debugStatus">ACTIVE</span> | ID: {{ session.get('user_id', '0') }}
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        const userId = "{{ session.get('user_id', '0') }}";
        let pc = null, localStream = null, inCall = false, currentTargetId = null;
        let callTimerInterval, callSeconds = 0, lastSignalId = 0;
        const ringtone = document.getElementById('ringtoneCall');

        if (userId !== '0') {
            setInterval(async () => {
                fetch('/api_presence_heartbeat').catch(()=>{});
                if (document.getElementById('videoCallInterface').style.display === 'none' && document.getElementById('incomingCallPopup').style.display === 'none') {
                    inCall = false; document.getElementById('debugStatus').innerText = 'OPERATIONAL';
                }
            }, 6000);
            
            // Continuous High-Speed Long-Polling
            runHyperPolling();
        }

        async function runHyperPolling() {
            while (true) {
                try {
                    const res = await fetch(`/api_get_signals?since=${lastSignalId}`);
                    const signals = await res.json();
                    if (signals && signals.length > 0) {
                        for (let s of signals) {
                            if (s.id > lastSignalId) lastSignalId = s.id;
                            await processOneSignal(s);
                        }
                    }
                } catch(e) { await new Promise(r => setTimeout(r, 2000)); }
                // Wait 1.5s if empty to keep server CPU low with 2M records
                await new Promise(r => setTimeout(r, 1500));
            }
        }

        async function processOneSignal(s) {
            const type = s.type.toLowerCase();
            const sFromId = String(s.from_id);
            const sTargetId = String(currentTargetId);

            if (type === 'offer' && !inCall) {
                inCall = true; currentTargetId = s.from_id;
                document.getElementById('callerNameDisplay').innerText = s.from_name;
                document.getElementById('incomingCallAvatar').innerText = (s.from_name || '?').charAt(0);
                document.getElementById('incomingCallPopup').style.display = 'block';
                ringtone.play().catch(()=>{});
                window.pendingOffer = JSON.parse(s.data);
            } else if (type === 'end') { stopAll(); }
            else if (inCall && type !== 'offer' && (sFromId === sTargetId || !currentTargetId)) {
                if (type === 'answer') {
                    await pc.setRemoteDescription(new RTCSessionDescription(JSON.parse(s.data)));
                    document.getElementById('debugStatus').innerText = 'CONNECTED';
                } else if (type === 'candidate') {
                    await pc.addIceCandidate(new RTCIceCandidate(JSON.parse(s.data)));
                }
            }
        }

        function stopAll() {
            document.getElementById('incomingCallPopup').style.display = 'none';
            document.getElementById('videoCallInterface').style.display = 'none';
            ringtone.pause(); ringtone.currentTime = 0;
            inCall = false; currentTargetId = null;
            if(pc) { try{pc.close();}catch(e){} pc = null; }
            if(localStream) { localStream.getTracks().forEach(t => t.stop()); localStream = null; }
            clearInterval(callTimerInterval);
        }

        async function acceptIncomingCall() {
            try {
                ringtone.pause(); document.getElementById('incomingCallPopup').style.display = 'none';
                showCallUI(document.getElementById('callerNameDisplay').innerText);
                localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
                document.getElementById('localVideo').srcObject = localStream;
                initPC();
                localStream.getTracks().forEach(t => pc.addTrack(t, localStream));
                await pc.setRemoteDescription(new RTCSessionDescription(window.pendingOffer));
                const answer = await pc.createAnswer(); await pc.setLocalDescription(answer);
                sendSignal(currentTargetId, 'answer', JSON.stringify(answer));
            } catch(e) { stopAll(); }
        }

        async function makeCall(targetId, targetName) {
            try {
                inCall = true; currentTargetId = targetId; showCallUI(targetName);
                localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
                document.getElementById('localVideo').srcObject = localStream;
                initPC();
                localStream.getTracks().forEach(t => pc.addTrack(t, localStream));
                const offer = await pc.createOffer(); await pc.setLocalDescription(offer);
                sendSignal(targetId, 'offer', JSON.stringify(offer));
            } catch(e) { stopAll(); }
        }

        function initPC() {
            pc = new RTCPeerConnection({ iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] });
            pc.onicecandidate = e => { if (e.candidate) sendSignal(currentTargetId, 'candidate', JSON.stringify(e.candidate)); };
            pc.ontrack = e => { 
                const v = document.getElementById('remoteVideo'); v.srcObject = e.streams[0]; 
                document.getElementById('remoteAudioTrack').srcObject = e.streams[0]; v.play().catch(()=>{});
            };
        }

        async function sendSignal(toId, type, data) {
            const fd = new FormData(); fd.append('to_id', toId); fd.append('type', type); fd.append('data', data);
            await fetch('/api_send_signal', { method: 'POST', body: fd }).catch(()=>{});
        }

        function endCurrentCall() { if(currentTargetId) sendSignal(currentTargetId, 'end', ''); stopAll(); }
        
        function showCallUI(name) {
            document.getElementById('videoCallInterface').style.display = 'block';
            document.getElementById('callRemoteName').innerText = name;
            callSeconds = 0; clearInterval(callTimerInterval);
            callTimerInterval = setInterval(() => {
                if(!inCall) return;
                callSeconds++; document.getElementById('callTimeDisplay').innerText = `${Math.floor(callSeconds/60).toString().padStart(2,'0')}:${(callSeconds%60).toString().padStart(2,'0')}`;
            }, 1000);
        }

        function toggleMic() { if(localStream) { const t = localStream.getAudioTracks()[0]; t.enabled = !t.enabled; document.getElementById('micIconMain').className = t.enabled?'fas fa-microphone fa-lg':'fas fa-microphone-slash fa-lg text-danger'; } }
        function toggleCam() { if(localStream) { const t = localStream.getVideoTracks()[0]; t.enabled = !t.enabled; document.getElementById('camIconMain').className = t.enabled?'fas fa-video fa-lg':'fas fa-video-slash fa-lg text-danger'; } }
        function rejectIncomingCall() { endCurrentCall(); }
        
        window.makeCall = makeCall;
        document.body.addEventListener('click', () => { ringtone.load(); }, {once: true});
    </script>
</body>
</html>
"""
