/**
 * Model Editor Component
 * Alpine.js function for the model creation/edit page
 */
function modelEditor() {
    return {
        newName: '',
        systemPrompt: '',
        temperature: 0.7,
        numCtx: 4096,
        topP: 0.9,
        seed: null,
        creating: false,
        status: '',
        error: '',

        async createModel() {
            if (!this.newName) return;

            this.creating = true;
            this.status = 'Préparation...';
            this.error = '';

            // Get the source model name from the page
            const fromModel = window.sourceModelName || '';

            const payload = {
                name: this.newName,
                from_model: fromModel,
                system: this.systemPrompt || null,
                parameters: {}
            };

            // Only include non-default parameters
            if (this.temperature !== 0.7) payload.parameters.temperature = parseFloat(this.temperature);
            if (this.numCtx !== 4096) payload.parameters.num_ctx = parseInt(this.numCtx);
            if (this.topP !== 0.9) payload.parameters.top_p = parseFloat(this.topP);
            if (this.seed) payload.parameters.seed = parseInt(this.seed);

            // Empty parameters object? Remove it
            if (Object.keys(payload.parameters).length === 0) {
                delete payload.parameters;
            }

            try {
                const response = await fetch('/api/models/create', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'text/event-stream'
                    },
                    body: JSON.stringify(payload)
                });

                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.error || 'Erreur lors de la création');
                }

                // Read SSE stream
                const reader = response.body.getReader();
                const decoder = new TextDecoder();

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    const text = decoder.decode(value);
                    const lines = text.split('\n').filter(l => l.startsWith('data: '));

                    for (const line of lines) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            if (data.status) this.status = data.status;
                            if (data.error) {
                                this.error = data.error;
                                this.creating = false;
                                return;
                            }
                            if (data.done) {
                                this.status = 'Modèle créé avec succès !';
                                this.creating = false;
                                // Redirect after short delay
                                setTimeout(() => {
                                    window.location.href = '/models';
                                }, 1500);
                                return;
                            }
                        } catch (e) {
                            // Ignore parse errors
                        }
                    }
                }

                this.status = 'Modèle créé avec succès !';
                setTimeout(() => {
                    window.location.href = '/models';
                }, 1500);

            } catch (err) {
                this.error = err.message;
                this.status = 'Échec de la création';
            } finally {
                this.creating = false;
            }
        }
    };
}
