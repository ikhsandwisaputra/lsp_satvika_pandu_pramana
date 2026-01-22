/**
 * Face Presence Detection for Quiz Security
 * Uses face-api.js with TinyFaceDetector (lightweight model)
 *
 * Flow:
 * 1. Request webcam access
 * 2. Detect face every 2 seconds
 * 3. If face not detected for X seconds (FACE_MISSING_THRESHOLD), log violation
 */

(function() {
    'use strict';

    // ==================== CONFIGURATION ====================
    const CONFIG = {
        // How long face can be missing before violation (seconds)
        FACE_MISSING_THRESHOLD: 10,

        // Detection interval (milliseconds)
        DETECTION_INTERVAL: 2000,

        // Minimum confidence for face detection (0-1)
        MIN_CONFIDENCE: 0.5,

        // Warning before violation (seconds)
        WARNING_THRESHOLD: 5,

        // face-api.js model URL (CDN)
        MODEL_URL: 'https://cdn.jsdelivr.net/npm/@vladmandic/face-api/model'
    };

    // ==================== STATE ====================
    let video = null;
    let canvas = null;
    let isInitialized = false;
    let isDetecting = false;
    let detectionInterval = null;
    let faceMissingStart = null;
    let warningShown = false;
    let attemptId = null;
    let onViolationCallback = null;

    // ==================== INITIALIZATION ====================
    async function initialize(config = {}) {
        // Merge custom config
        Object.assign(CONFIG, config);

        attemptId = config.attemptId;
        onViolationCallback = config.onViolation;

        try {
            // Load face-api.js models
            await loadModels();

            // Setup video element
            await setupVideo();

            // Create UI elements
            createUI();

            isInitialized = true;
            console.log('[FaceDetection] Initialized successfully');

            return true;
        } catch (error) {
            console.error('[FaceDetection] Initialization failed:', error);
            showError(error.message);
            return false;
        }
    }

    async function loadModels() {
        console.log('[FaceDetection] Loading face-api.js models...');

        // Check if faceapi is loaded
        if (typeof faceapi === 'undefined') {
            throw new Error('face-api.js not loaded. Please include the library.');
        }

        // Load TinyFaceDetector model (smallest & fastest)
        await faceapi.nets.tinyFaceDetector.loadFromUri(CONFIG.MODEL_URL);

        console.log('[FaceDetection] Models loaded');
    }

    async function setupVideo() {
        console.log('[FaceDetection] Requesting webcam access...');

        // Check if browser supports getUserMedia
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            throw new Error('Browser tidak mendukung akses kamera');
        }

        // Create video element
        video = document.createElement('video');
        video.id = 'face-detection-video';
        video.setAttribute('autoplay', '');
        video.setAttribute('muted', '');
        video.setAttribute('playsinline', '');

        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    width: { ideal: 320 },
                    height: { ideal: 240 },
                    facingMode: 'user'
                },
                audio: false
            });

            video.srcObject = stream;
            await video.play();

            console.log('[FaceDetection] Webcam access granted');
        } catch (error) {
            if (error.name === 'NotAllowedError') {
                throw new Error('Akses kamera ditolak. Izinkan akses kamera untuk melanjutkan ujian.');
            } else if (error.name === 'NotFoundError') {
                throw new Error('Kamera tidak ditemukan. Pastikan perangkat memiliki webcam.');
            } else {
                throw new Error('Gagal mengakses kamera: ' + error.message);
            }
        }
    }

    function createUI() {
        // Create container for webcam preview
        const container = document.createElement('div');
        container.id = 'face-detection-container';
        container.innerHTML = `
            <style>
                #face-detection-container {
                    position: fixed;
                    bottom: 20px;
                    right: 20px;
                    z-index: 1000;
                    background: #0f172a;
                    border-radius: 12px;
                    overflow: hidden;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
                }

                #face-detection-video {
                    width: 200px;
                    height: 150px;
                    object-fit: cover;
                    display: block;
                    transform: scaleX(-1); /* Mirror effect */
                }

                #face-detection-status {
                    padding: 8px 12px;
                    font-size: 0.75rem;
                    font-weight: 600;
                    text-align: center;
                    color: white;
                    background: #22c55e;
                    transition: background 0.3s;
                }

                #face-detection-status.warning {
                    background: #f59e0b;
                    animation: blink-warning 1s infinite;
                }

                #face-detection-status.danger {
                    background: #dc2626;
                    animation: blink-danger 0.5s infinite;
                }

                @keyframes blink-warning {
                    0%, 100% { opacity: 1; }
                    50% { opacity: 0.7; }
                }

                @keyframes blink-danger {
                    0%, 100% { opacity: 1; }
                    50% { opacity: 0.5; }
                }

                #face-detection-overlay {
                    position: absolute;
                    top: 0;
                    left: 0;
                    width: 200px;
                    height: 150px;
                    pointer-events: none;
                }

                /* Minimized state */
                #face-detection-container.minimized #face-detection-video,
                #face-detection-container.minimized #face-detection-overlay {
                    height: 0;
                    width: 0;
                }

                #face-detection-toggle {
                    position: absolute;
                    top: 4px;
                    right: 4px;
                    background: rgba(0,0,0,0.5);
                    border: none;
                    color: white;
                    width: 24px;
                    height: 24px;
                    border-radius: 4px;
                    cursor: pointer;
                    font-size: 12px;
                    z-index: 10;
                }

                /* Error state */
                #face-detection-error {
                    padding: 16px;
                    color: #fca5a5;
                    text-align: center;
                    font-size: 0.8rem;
                }
            </style>
            <div style="position: relative;">
                <button id="face-detection-toggle" title="Minimize">−</button>
                <canvas id="face-detection-overlay"></canvas>
            </div>
            <div id="face-detection-status">Mendeteksi wajah...</div>
        `;

        document.body.appendChild(container);

        // Append video to container
        const videoWrapper = container.querySelector('div');
        videoWrapper.insertBefore(video, videoWrapper.firstChild);

        // Setup canvas for face overlay
        canvas = document.getElementById('face-detection-overlay');
        canvas.width = 200;
        canvas.height = 150;

        // Setup toggle button
        const toggleBtn = document.getElementById('face-detection-toggle');
        toggleBtn.addEventListener('click', function() {
            container.classList.toggle('minimized');
            this.textContent = container.classList.contains('minimized') ? '+' : '−';
        });
    }

    function showError(message) {
        const container = document.getElementById('face-detection-container');
        if (container) {
            container.innerHTML = `
                <div id="face-detection-error">
                    <strong>Kamera Error</strong><br>
                    ${message}
                </div>
            `;
        } else {
            // Create error container if main container doesn't exist
            const errorDiv = document.createElement('div');
            errorDiv.id = 'face-detection-container';
            errorDiv.innerHTML = `
                <style>
                    #face-detection-container {
                        position: fixed;
                        bottom: 20px;
                        right: 20px;
                        z-index: 1000;
                        background: #7f1d1d;
                        border-radius: 12px;
                        padding: 16px;
                        color: #fca5a5;
                        max-width: 250px;
                        font-size: 0.85rem;
                        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
                    }
                </style>
                <strong>Kamera Error</strong><br>
                ${message}
            `;
            document.body.appendChild(errorDiv);
        }
    }

    // ==================== DETECTION ====================
    function startDetection() {
        if (!isInitialized || isDetecting) return;

        isDetecting = true;
        console.log('[FaceDetection] Starting detection loop');

        detectionInterval = setInterval(detectFace, CONFIG.DETECTION_INTERVAL);

        // Run first detection immediately
        detectFace();
    }

    function stopDetection() {
        if (detectionInterval) {
            clearInterval(detectionInterval);
            detectionInterval = null;
        }
        isDetecting = false;
        console.log('[FaceDetection] Detection stopped');
    }

    async function detectFace() {
        if (!video || video.paused || video.ended) return;

        try {
            // Detect faces using TinyFaceDetector
            const detections = await faceapi.detectAllFaces(
                video,
                new faceapi.TinyFaceDetectorOptions({
                    inputSize: 224,
                    scoreThreshold: CONFIG.MIN_CONFIDENCE
                })
            );

            const statusEl = document.getElementById('face-detection-status');
            const ctx = canvas.getContext('2d');

            // Clear canvas
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            if (detections.length > 0) {
                // Face detected - reset missing counter
                handleFaceDetected(statusEl, ctx, detections);
            } else {
                // No face detected
                handleFaceMissing(statusEl);
            }
        } catch (error) {
            console.error('[FaceDetection] Detection error:', error);
        }
    }

    function handleFaceDetected(statusEl, ctx, detections) {
        faceMissingStart = null;
        warningShown = false;

        statusEl.textContent = 'Wajah Terdeteksi';
        statusEl.className = '';

        // Draw face box on canvas (mirrored)
        if (detections[0]) {
            const box = detections[0].box;
            const scaleX = canvas.width / video.videoWidth;
            const scaleY = canvas.height / video.videoHeight;

            ctx.strokeStyle = '#22c55e';
            ctx.lineWidth = 2;
            // Mirror the x position
            const mirroredX = canvas.width - (box.x * scaleX) - (box.width * scaleX);
            ctx.strokeRect(
                mirroredX,
                box.y * scaleY,
                box.width * scaleX,
                box.height * scaleY
            );
        }
    }

    function handleFaceMissing(statusEl) {
        const now = Date.now();

        if (!faceMissingStart) {
            faceMissingStart = now;
        }

        const missingSeconds = (now - faceMissingStart) / 1000;

        if (missingSeconds >= CONFIG.FACE_MISSING_THRESHOLD) {
            // Trigger violation
            statusEl.textContent = 'PELANGGARAN: Wajah Tidak Terdeteksi!';
            statusEl.className = 'danger';

            triggerViolation();

            // Reset counter to allow detection again
            faceMissingStart = now;
            warningShown = false;

        } else if (missingSeconds >= CONFIG.WARNING_THRESHOLD && !warningShown) {
            // Show warning
            statusEl.textContent = `Wajah Tidak Terdeteksi (${Math.ceil(CONFIG.FACE_MISSING_THRESHOLD - missingSeconds)}s)`;
            statusEl.className = 'warning';
            warningShown = true;

        } else if (missingSeconds < CONFIG.WARNING_THRESHOLD) {
            statusEl.textContent = 'Mencari wajah...';
            statusEl.className = 'warning';
        } else {
            // Update countdown
            statusEl.textContent = `Wajah Tidak Terdeteksi (${Math.ceil(CONFIG.FACE_MISSING_THRESHOLD - missingSeconds)}s)`;
        }
    }

    function triggerViolation() {
        console.log('[FaceDetection] Triggering violation');

        if (onViolationCallback) {
            onViolationCallback('face_not_detected');
        }

        // Also send to server
        if (attemptId) {
            logViolationToServer('face_not_detected');
        }
    }

    function logViolationToServer(violationType) {
        fetch('/certification/quiz/violation/' + attemptId, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                jsonrpc: '2.0',
                method: 'call',
                params: { type: violationType },
                id: Math.floor(Math.random() * 1000000)
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.result && window.handleFaceViolationResponse) {
                window.handleFaceViolationResponse(data.result);
            }
        })
        .catch(err => {
            console.error('[FaceDetection] Failed to log violation:', err);
        });
    }

    // ==================== CLEANUP ====================
    function destroy() {
        stopDetection();

        // Stop video stream
        if (video && video.srcObject) {
            const tracks = video.srcObject.getTracks();
            tracks.forEach(track => track.stop());
        }

        // Remove UI
        const container = document.getElementById('face-detection-container');
        if (container) {
            container.remove();
        }

        isInitialized = false;
        console.log('[FaceDetection] Destroyed');
    }

    // ==================== EXPORTS ====================
    window.FaceDetection = {
        initialize: initialize,
        startDetection: startDetection,
        stopDetection: stopDetection,
        destroy: destroy,
        isInitialized: () => isInitialized,
        isDetecting: () => isDetecting
    };

})();
