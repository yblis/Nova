/**
 * Texts App — CV/Resume Generator Mixin
 * Methods for the CV builder: CRUD sections, generation, download.
 * Merged into textsApp via spread operator.
 */
window.TextsResumeMixin = {

    // ========== CV Generator Methods ==========

    // CRUD methods for CV sections
    addExperience() { this.resumeData.experience.push({ role: '', company: '', date: '', description: '' }); },
    removeExperience(index) { this.resumeData.experience.splice(index, 1); },
    addEducation() { this.resumeData.education.push({ school: '', degree: '', date: '' }); },
    removeEducation(index) { this.resumeData.education.splice(index, 1); },
    addSkill() { this.resumeData.skills.push({ name: '' }); },
    removeSkill(index) { this.resumeData.skills.splice(index, 1); },
    addLanguage() { this.resumeData.languages.push({ name: '' }); },
    removeLanguage(index) { this.resumeData.languages.splice(index, 1); },
    addInterest() { this.resumeData.interests.push({ name: '' }); },
    removeInterest(index) { this.resumeData.interests.splice(index, 1); },

    // Reset all CV fields to empty
    resetResume() {
        this.resumeData = {
            firstname: '',
            lastname: '',
            title: '',
            email: '',
            phone: '',
            location: '',
            website: '',
            summary: '',
            experience: [],
            education: [],
            skills: [],
            languages: [],
            interests: [],
            instructions: ''
        };
        this.resumeGeneratedHtml = '';
        this.resumeError = '';
    },

    // Generate CV
    async generateResume() {
        if (!this.currentModel) {
            this.resumeError = 'Veuillez sélectionner un modèle IA en haut à gauche';
            return;
        }

        this.resumeLoading = true;
        this.resumeError = '';

        try {
            const response = await fetch('/api/resume/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    data: this.resumeData,
                    style: this.resumeStyle,
                    model: this.currentModel
                })
            });

            const result = await response.json();

            if (result.success) {
                this.resumeGeneratedHtml = result.html;
                this.resumeError = '';
            } else {
                this.resumeError = result.error || 'Erreur lors de la génération du CV';
                this.resumeGeneratedHtml = '';
            }
        } catch (err) {
            console.error('CV Generation Error:', err);
            this.resumeError = 'Erreur de connexion au serveur';
            this.resumeGeneratedHtml = '';
        } finally {
            this.resumeLoading = false;
        }
    },

    // Download HTML
    downloadResumeHTML() {
        if (!this.resumeGeneratedHtml) {
            alert('Veuillez d\'abord générer le CV');
            return;
        }

        const fullHTML = `<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CV - ${this.resumeData.firstname} ${this.resumeData.lastname}</title>
    <script src="https://cdn.tailwindcss.com"><\/script>
    <style>
        body { background-color: #f3f4f6; display: flex; justify-content: center; padding: 40px; }
        .cv-container { box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25); margin: 0 auto; }
        @media print {
            body { background: none; padding: 0; display: block; }
            .cv-container { box-shadow: none; margin: 0; width: 100%; height: 100%; }
        }
    </style>
</head>
<body>
    ${this.resumeGeneratedHtml}
</body>
</html>`;
        const blob = new Blob([fullHTML], { type: 'text/html' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `cv-${this.resumeData.firstname.toLowerCase()}-${this.resumeData.lastname.toLowerCase()}.html`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    },

    // Download PDF
    async downloadResumePDF() {
        if (!this.resumeGeneratedHtml) {
            alert('Veuillez d\'abord générer le CV');
            return;
        }

        // Check if jsPDF is loaded
        if (typeof window.jspdf === 'undefined') {
            alert('Bibliothèque PDF non chargée. Veuillez rafraîchir la page.');
            return;
        }

        const { jsPDF } = window.jspdf;
        const element = document.getElementById('cv-preview-resume');

        if (!element) {
            alert('Erreur: Zone de prévisualisation introuvable');
            return;
        }

        try {
            const canvas = await html2canvas(element, {
                scale: 2,
                useCORS: true,
                logging: false
            });

            const imgData = canvas.toDataURL('image/jpeg', 1.0);
            const pdf = new jsPDF('p', 'mm', 'a4');
            const pdfWidth = pdf.internal.pageSize.getWidth();
            const pdfHeight = pdf.internal.pageSize.getHeight();

            pdf.addImage(imgData, 'JPEG', 0, 0, pdfWidth, pdfHeight);
            pdf.save(`cv-${this.resumeData.firstname.toLowerCase()}-${this.resumeData.lastname.toLowerCase()}.pdf`);
        } catch (error) {
            console.error('PDF Generation Error:', error);
            alert('Erreur lors de la génération du PDF');
        }
    }
};
