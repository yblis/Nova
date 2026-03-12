window.TextsMermaidMixin = {

    mermaidCode: '',
    mermaidEditorCode: '',
    mermaidLoading: false,
    mermaidError: '',
    mermaidRenderedSvg: '',
    mermaidRenderCounter: 0,
    mermaidFullscreen: false,
    mermaidZoom: 1,
    mermaidPanning: false,
    mermaidPanX: 0,
    mermaidPanY: 0,
    mermaidImageBase64: '',
    mermaidImagePreview: '',
    mermaidShowCanvas: false,
    mermaidCanvasFullscreen: false,
    mermaidCanvasTool: 'pen',
    mermaidCanvasColor: '#000000',
    mermaidCanvasSize: 3,
    _mermaidCanvasHistory: [],
    _mermaidCanvasDrawing: false,
    _mermaidCanvasLastPoint: null,
    _mermaidCanvasPoints: [],
    _mermaidPanStartX: 0,
    _mermaidPanStartY: 0,
    _mermaidPanOriginX: 0,
    _mermaidPanOriginY: 0,

    async generateMermaid() {
        if (!this.currentModel) {
            this.mermaidError = 'Veuillez selectionner un modele IA';
            return;
        }

        if (!this.inputText.trim() && !this.mermaidImageBase64) {
            this.mermaidError = 'Veuillez decrire le diagramme ou fournir une image';
            return;
        }

        this.mermaidLoading = true;
        this.mermaidError = '';

        try {
            const payload = {
                description: this.inputText,
                model: this.currentModel
            };

            if (this.mermaidCode) {
                payload.previous_code = this.mermaidCode;
            }

            if (this.mermaidImageBase64) {
                payload.image_base64 = this.mermaidImageBase64;
            }

            const response = await fetch('/api/tools/generate-mermaid', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await response.json();

            if (data.success) {
                this.mermaidCode = data.result;
                this.mermaidEditorCode = data.result;
                this.mermaidError = '';
                this.mermaidResetView();
                await this.renderMermaidPreview();
                await this.loadHistory();
                // Clear image after successful generation
                this.mermaidImageBase64 = '';
                this.mermaidImagePreview = '';
            } else {
                this.mermaidError = data.error || 'Erreur lors de la generation';
            }
        } catch (err) {
            console.error('Mermaid Generation Error:', err);
            this.mermaidError = 'Erreur de connexion au serveur';
        } finally {
            this.mermaidLoading = false;
        }
    },

    async fixMermaidWithAI() {
        const codeToFix = this.mermaidEditorCode || this.mermaidCode;
        if (!this.currentModel || !codeToFix) return;

        this.mermaidLoading = true;
        const errorMsg = this.mermaidError;

        try {
            const payload = {
                description: `Corrige cette erreur de syntaxe Mermaid : ${errorMsg}`,
                model: this.currentModel,
                previous_code: codeToFix
            };

            const response = await fetch('/api/tools/generate-mermaid', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await response.json();

            if (data.success) {
                this.mermaidCode = data.result;
                this.mermaidEditorCode = data.result;
                this.mermaidError = '';
                this.mermaidResetView();
                await this.renderMermaidPreview();
                await this.loadHistory();
            } else {
                this.mermaidError = data.error || 'Erreur lors de la correction';
            }
        } catch (err) {
            console.error('Mermaid Fix Error:', err);
            this.mermaidError = 'Erreur de connexion au serveur';
        } finally {
            this.mermaidLoading = false;
        }
    },

    async renderMermaidPreview() {
        if (!this.mermaidEditorCode.trim()) {
            this.mermaidRenderedSvg = '';
            return;
        }

        if (typeof mermaid === 'undefined') {
            this.mermaidError = 'Mermaid.js non charge. Veuillez rafraichir la page.';
            return;
        }

        try {
            this.mermaidRenderCounter++;
            const id = 'mermaid-render-' + this.mermaidRenderCounter;
            const { svg } = await mermaid.render(id, this.mermaidEditorCode);
            this.mermaidRenderedSvg = svg;
            this.mermaidError = '';
        } catch (err) {
            console.error('Mermaid Render Error:', err);
            this.mermaidRenderedSvg = '';
            this.mermaidError = 'Erreur de syntaxe Mermaid : ' + (err.message || err.str || 'syntaxe invalide');
        }
    },

    copyMermaidCode() {
        const code = this.mermaidEditorCode || this.mermaidCode;
        if (code) {
            navigator.clipboard.writeText(code);
        }
    },

    exportMermaidSVG() {
        if (!this.mermaidRenderedSvg) return;

        const blob = new Blob([this.mermaidRenderedSvg], { type: 'image/svg+xml' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'diagram.svg';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    },

    async exportMermaidPNG() {
        if (!this.mermaidRenderedSvg) return;

        try {
            const svgEl = new DOMParser().parseFromString(this.mermaidRenderedSvg, 'image/svg+xml').documentElement;
            const bbox = svgEl.getAttribute('viewBox');
            let width = 1200;
            let height = 800;

            if (bbox) {
                const parts = bbox.split(/\s+/);
                if (parts.length === 4) {
                    width = Math.ceil(parseFloat(parts[2]));
                    height = Math.ceil(parseFloat(parts[3]));
                }
            }

            const scale = 2;
            const canvas = document.createElement('canvas');
            canvas.width = width * scale;
            canvas.height = height * scale;
            const ctx = canvas.getContext('2d');
            ctx.scale(scale, scale);

            ctx.fillStyle = '#ffffff';
            ctx.fillRect(0, 0, width, height);

            const img = new Image();
            const svgBlob = new Blob([this.mermaidRenderedSvg], { type: 'image/svg+xml;charset=utf-8' });
            const svgUrl = URL.createObjectURL(svgBlob);

            await new Promise((resolve, reject) => {
                img.onload = resolve;
                img.onerror = reject;
                img.src = svgUrl;
            });

            ctx.drawImage(img, 0, 0, width, height);
            URL.revokeObjectURL(svgUrl);

            canvas.toBlob(blob => {
                const pngUrl = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = pngUrl;
                a.download = 'diagram.png';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(pngUrl);
            }, 'image/png');

        } catch (err) {
            console.error('PNG Export Error:', err);
            this.mermaidError = 'Erreur lors de l\'export PNG';
        }
    },

    // Zoom / Pan / Fullscreen
    mermaidZoomIn() {
        this.mermaidZoom = Math.min(this.mermaidZoom + 0.25, 5);
    },

    mermaidZoomOut() {
        this.mermaidZoom = Math.max(this.mermaidZoom - 0.25, 0.25);
    },

    mermaidResetView() {
        this.mermaidZoom = 1;
        this.mermaidPanX = 0;
        this.mermaidPanY = 0;
    },

    mermaidToggleFullscreen() {
        this.mermaidFullscreen = !this.mermaidFullscreen;
        if (!this.mermaidFullscreen) {
            // optionally reset view on exit
        }
    },

    mermaidHandleWheel(e) {
        e.preventDefault();
        if (e.deltaY < 0) {
            this.mermaidZoom = Math.min(this.mermaidZoom + 0.1, 5);
        } else {
            this.mermaidZoom = Math.max(this.mermaidZoom - 0.1, 0.25);
        }
    },

    mermaidStartPan(e) {
        // Pinch-to-zoom: 2 fingers
        if (e.touches && e.touches.length === 2) {
            this._mermaidPinching = true;
            this.mermaidPanning = false;
            const dx = e.touches[0].clientX - e.touches[1].clientX;
            const dy = e.touches[0].clientY - e.touches[1].clientY;
            this._mermaidPinchStartDist = Math.hypot(dx, dy);
            this._mermaidPinchStartZoom = this.mermaidZoom;
            return;
        }
        // Single finger: pan
        this.mermaidPanning = true;
        this._mermaidPinching = false;
        const point = e.touches ? e.touches[0] : e;
        this._mermaidPanStartX = point.clientX;
        this._mermaidPanStartY = point.clientY;
        this._mermaidPanOriginX = this.mermaidPanX;
        this._mermaidPanOriginY = this.mermaidPanY;
    },

    mermaidOnPan(e) {
        // Pinch-to-zoom
        if (this._mermaidPinching && e.touches && e.touches.length === 2) {
            e.preventDefault();
            const dx = e.touches[0].clientX - e.touches[1].clientX;
            const dy = e.touches[0].clientY - e.touches[1].clientY;
            const dist = Math.hypot(dx, dy);
            const scale = dist / this._mermaidPinchStartDist;
            this.mermaidZoom = Math.min(Math.max(this._mermaidPinchStartZoom * scale, 0.25), 5);
            return;
        }
        // Single finger pan
        if (!this.mermaidPanning) return;
        const point = e.touches ? e.touches[0] : e;
        this.mermaidPanX = this._mermaidPanOriginX + (point.clientX - this._mermaidPanStartX);
        this.mermaidPanY = this._mermaidPanOriginY + (point.clientY - this._mermaidPanStartY);
    },

    mermaidEndPan() {
        this.mermaidPanning = false;
        this._mermaidPinching = false;
    },

    resetMermaid() {
        this.mermaidCode = '';
        this.mermaidEditorCode = '';
        this.mermaidRenderedSvg = '';
        this.mermaidError = '';
        this.mermaidFullscreen = false;
        this.mermaidImageBase64 = '';
        this.mermaidImagePreview = '';
        this.mermaidShowCanvas = false;
        this.mermaidResetView();
        this.inputText = '';
        this.saveInputForTool('mermaid', '');
    },

    applyMermaidExample(text) {
        this.inputText = text;
    },

    // Image handling
    mermaidHandleImageUpload(event) {
        const file = event.target.files?.[0];
        if (!file) return;

        if (!file.type.startsWith('image/')) {
            this.mermaidError = 'Seuls les fichiers image sont acceptes';
            return;
        }

        if (file.size > 10 * 1024 * 1024) {
            this.mermaidError = 'L\'image ne doit pas depasser 10 Mo';
            return;
        }

        const reader = new FileReader();
        reader.onload = (e) => {
            this.mermaidImageBase64 = e.target.result;
            this.mermaidImagePreview = e.target.result;
            this.mermaidError = '';
        };
        reader.readAsDataURL(file);

        // Reset file input
        event.target.value = '';
    },

    async mermaidPasteImage(event) {
        const items = event?.clipboardData?.items || [];
        for (const item of items) {
            if (item.type.startsWith('image/')) {
                event.preventDefault();
                const file = item.getAsFile();
                if (!file) continue;

                const reader = new FileReader();
                reader.onload = (e) => {
                    this.mermaidImageBase64 = e.target.result;
                    this.mermaidImagePreview = e.target.result;
                    this.mermaidError = '';
                };
                reader.readAsDataURL(file);
                return;
            }
        }
    },

    mermaidRemoveImage() {
        this.mermaidImageBase64 = '';
        this.mermaidImagePreview = '';
    },

    // ===== Canvas Drawing =====
    mermaidToggleCanvas() {
        this.mermaidShowCanvas = !this.mermaidShowCanvas;
        if (this.mermaidShowCanvas) {
            setTimeout(() => this.mermaidInitCanvas(), 50);
        }
    },

    mermaidToggleCanvasFullscreen() {
        // Save content BEFORE switching state (while current canvas still exists)
        const prevData = this._mermaidCanvasHistory.length > 0
            ? this._mermaidCanvasHistory[this._mermaidCanvasHistory.length - 1]
            : null;

        this.mermaidCanvasFullscreen = !this.mermaidCanvasFullscreen;

        // Wait for Alpine to create/destroy templates, then init the new canvas
        const initNewCanvas = (retries = 0) => {
            const canvas = this._mermaidGetCanvas();
            if (!canvas) {
                if (retries < 10) {
                    requestAnimationFrame(() => initNewCanvas(retries + 1));
                }
                return;
            }
            this._mermaidSetupCanvas(canvas);
            if (prevData) {
                const ctx = canvas.getContext('2d');
                const dpr = window.devicePixelRatio || 1;
                const img = new Image();
                img.onload = () => {
                    ctx.setTransform(1, 0, 0, 1, 0, 0);
                    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
                    this._mermaidCanvasSaveState();
                };
                img.src = prevData;
            }
        };
        // Give Alpine time to process x-if changes
        setTimeout(() => initNewCanvas(), 50);
    },

    _mermaidGetCanvas() {
        if (this.mermaidCanvasFullscreen) {
            return document.getElementById('mermaidCanvasFs');
        }
        return document.getElementById('mermaidCanvasInline');
    },

    _mermaidSetupCanvas(canvas) {
        if (!canvas) return;
        const dpr = window.devicePixelRatio || 1;
        let w, h;
        if (this.mermaidCanvasFullscreen) {
            // In fullscreen, use window dimensions minus toolbar
            w = window.innerWidth;
            const toolbar = canvas.parentElement?.previousElementSibling;
            const toolbarH = toolbar ? toolbar.getBoundingClientRect().height : 56;
            h = window.innerHeight - toolbarH;
        } else {
            const rect = canvas.parentElement.getBoundingClientRect();
            w = rect.width;
            h = Math.max(rect.height, 300);
        }
        canvas.width = w * dpr;
        canvas.height = h * dpr;
        canvas.style.width = w + 'px';
        canvas.style.height = h + 'px';
        const ctx = canvas.getContext('2d');
        ctx.scale(dpr, dpr);
        // White background
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, w, h);
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
    },

    mermaidInitCanvas() {
        const canvas = this._mermaidGetCanvas();
        if (!canvas) return;
        this._mermaidSetupCanvas(canvas);
        this._mermaidCanvasHistory = [];
        this._mermaidCanvasSaveState();
    },

    _mermaidCanvasSaveState() {
        const canvas = this._mermaidGetCanvas();
        if (!canvas) return;
        this._mermaidCanvasHistory.push(canvas.toDataURL());
        if (this._mermaidCanvasHistory.length > 30) {
            this._mermaidCanvasHistory.shift();
        }
    },

    _mermaidGetCanvasPos(e) {
        const canvas = this._mermaidGetCanvas();
        if (!canvas) return { x: 0, y: 0 };
        const rect = canvas.getBoundingClientRect();
        const touch = e.touches ? e.touches[0] : e;
        return {
            x: touch.clientX - rect.left,
            y: touch.clientY - rect.top
        };
    },

    mermaidCanvasDown(e) {
        e.preventDefault();
        this._mermaidCanvasDrawing = true;
        const pos = this._mermaidGetCanvasPos(e);
        this._mermaidCanvasLastPoint = pos;
        this._mermaidCanvasPoints = [pos];

        const canvas = this._mermaidGetCanvas();
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        ctx.beginPath();
        ctx.moveTo(pos.x, pos.y);

        if (this.mermaidCanvasTool === 'eraser') {
            ctx.globalCompositeOperation = 'destination-out';
            ctx.lineWidth = this.mermaidCanvasSize * 4;
        } else {
            ctx.globalCompositeOperation = 'source-over';
            ctx.strokeStyle = this.mermaidCanvasColor;
            ctx.lineWidth = this.mermaidCanvasSize;
        }
    },

    mermaidCanvasMove(e) {
        if (!this._mermaidCanvasDrawing) return;
        e.preventDefault();
        const canvas = this._mermaidGetCanvas();
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const pos = this._mermaidGetCanvasPos(e);

        this._mermaidCanvasPoints.push(pos);
        const pts = this._mermaidCanvasPoints;

        if (pts.length >= 3) {
            // Smooth curve using quadratic bezier through midpoints
            const last = pts[pts.length - 3];
            const mid1 = { x: (last.x + pts[pts.length - 2].x) / 2, y: (last.y + pts[pts.length - 2].y) / 2 };
            const mid2 = { x: (pts[pts.length - 2].x + pos.x) / 2, y: (pts[pts.length - 2].y + pos.y) / 2 };

            ctx.beginPath();
            ctx.moveTo(mid1.x, mid1.y);
            ctx.quadraticCurveTo(pts[pts.length - 2].x, pts[pts.length - 2].y, mid2.x, mid2.y);

            if (this.mermaidCanvasTool === 'eraser') {
                ctx.globalCompositeOperation = 'destination-out';
                ctx.lineWidth = this.mermaidCanvasSize * 4;
            } else {
                ctx.globalCompositeOperation = 'source-over';
                ctx.strokeStyle = this.mermaidCanvasColor;
                ctx.lineWidth = this.mermaidCanvasSize;
            }
            ctx.lineCap = 'round';
            ctx.lineJoin = 'round';
            ctx.stroke();
        } else {
            // For the first 2 points, draw a simple line
            ctx.lineTo(pos.x, pos.y);
            ctx.stroke();
        }

        this._mermaidCanvasLastPoint = pos;
    },

    mermaidCanvasUp(e) {
        if (!this._mermaidCanvasDrawing) return;
        this._mermaidCanvasDrawing = false;
        const canvas = this._mermaidGetCanvas();
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        ctx.globalCompositeOperation = 'source-over';
        this._mermaidCanvasPoints = [];
        this._mermaidCanvasLastPoint = null;
        this._mermaidCanvasSaveState();
    },

    mermaidCanvasUndo() {
        if (this._mermaidCanvasHistory.length <= 1) return;
        this._mermaidCanvasHistory.pop();
        const last = this._mermaidCanvasHistory[this._mermaidCanvasHistory.length - 1];
        const canvas = this._mermaidGetCanvas();
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const dpr = window.devicePixelRatio || 1;
        const img = new Image();
        img.onload = () => {
            ctx.setTransform(1, 0, 0, 1, 0, 0);
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.drawImage(img, 0, 0);
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        };
        img.src = last;
    },

    mermaidCanvasClear() {
        const canvas = this._mermaidGetCanvas();
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const dpr = window.devicePixelRatio || 1;
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        this._mermaidCanvasSaveState();
    },

    mermaidCanvasSubmit() {
        const canvas = this._mermaidGetCanvas();
        if (!canvas) return;
        const dataUrl = canvas.toDataURL('image/png');
        this.mermaidImageBase64 = dataUrl;
        this.mermaidImagePreview = dataUrl;
        this.mermaidShowCanvas = false;
        this.mermaidCanvasFullscreen = false;
        this.mermaidError = '';
    }
};
