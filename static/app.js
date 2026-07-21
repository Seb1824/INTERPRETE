const codeInput = document.querySelector("#codigo");
const lineNumbers = document.querySelector("#line-numbers");
const fileInput = document.querySelector("#archivo");
const characterCount = document.querySelector("#character-count");
const fileName = document.querySelector("#editor-status");
const analysisForm = document.querySelector("#analysis-form");
const analyzeButton = document.querySelector("#analyze-button");

function updateCharacterCount() {
    const total = codeInput.value.length;
    characterCount.textContent = `${total.toLocaleString("es")} caracteres`;
}

function updateLineNumbers() {
    const totalLines = codeInput.value.split("\n").length;
    lineNumbers.textContent = Array.from(
        { length: totalLines },
        (_, index) => index + 1,
    ).join("\n");
}

function updateEditorMetrics() {
    updateCharacterCount();
    updateLineNumbers();
}

function syncLineNumberScroll() {
    lineNumbers.scrollTop = codeInput.scrollTop;
}

codeInput.addEventListener("input", updateEditorMetrics);
codeInput.addEventListener("scroll", syncLineNumberScroll);
updateEditorMetrics();

fileInput.addEventListener("change", () => {
    const [file] = fileInput.files;
    if (!file) {
        return;
    }

    fileName.textContent = file.name;
    const reader = new FileReader();
    reader.addEventListener("load", () => {
        codeInput.value = String(reader.result ?? "");
        updateEditorMetrics();
    });
    reader.readAsText(file, "UTF-8");
});

analysisForm.addEventListener("submit", (event) => {
    if (event.submitter?.id === "download-json") {
        return;
    }
    analyzeButton.disabled = true;
    analyzeButton.textContent = "Analizando...";
    analysisForm.setAttribute("aria-busy", "true");
});

const speechControls = document.querySelector("#speech-controls");

if (speechControls) {
    const speechStatus = document.querySelector("#speech-status");
    const speakAllButton = document.querySelector("#speak-all");
    const pauseButton = document.querySelector("#pause-speech");
    const stopButton = document.querySelector("#stop-speech");
    const rateSelect = document.querySelector("#speech-rate");
    const diagnosticItems = Array.from(document.querySelectorAll("[data-speech-item]"));
    const diagnosticButtons = Array.from(document.querySelectorAll("[data-speak-diagnostic]"));
    const speechSupported = "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;

    let availableVoices = [];
    let activeArticle = null;
    let activeButton = null;
    let currentUtterance = null;
    let readingQueue = [];
    let queueIndex = 0;
    let speechRunId = 0;

    function normalizeText(value) {
        return value.replace(/\s+/g, " ").trim();
    }

    function prepareTextForSpeech(value) {
        return normalizeText(value.replace(/#/g, " numeral "));
    }

    function diagnosticText(article) {
        const severity = normalizeText(article.querySelector(".severity")?.textContent ?? "Diagnostico");
        const title = normalizeText(article.querySelector("h3")?.textContent ?? "");
        const location = normalizeText(article.querySelector(".location")?.textContent ?? "");
        const explanations = Array.from(article.querySelectorAll(".explanation-list > div"))
            .map((section) => {
                const term = normalizeText(section.querySelector("dt")?.textContent ?? "");
                const detail = normalizeText(section.querySelector("dd")?.textContent ?? "");
                return `${term}. ${detail}`;
            });

        return [severity, title, location, ...explanations].filter(Boolean).join(". ");
    }

    function refreshVoices() {
        availableVoices = window.speechSynthesis.getVoices();
    }

    function preferredSpanishVoice() {
        return availableVoices.find((voice) => voice.lang.toLowerCase().startsWith("es-pe"))
            ?? availableVoices.find((voice) => voice.lang.toLowerCase().startsWith("es-419"))
            ?? availableVoices.find((voice) => voice.lang.toLowerCase().startsWith("es"))
            ?? null;
    }

    function clearActiveArticle() {
        if (activeArticle) {
            activeArticle.classList.remove("speech-active");
        }
        activeArticle = null;
    }

    function resetSpeechControls() {
        clearActiveArticle();
        diagnosticButtons.forEach((button) => button.setAttribute("aria-pressed", "false"));
        speakAllButton.setAttribute("aria-pressed", "false");
        pauseButton.textContent = "Pausar";
        pauseButton.disabled = true;
        stopButton.disabled = true;
        activeButton = null;
        currentUtterance = null;
        readingQueue = [];
        queueIndex = 0;
    }

    function finishReading(message) {
        resetSpeechControls();
        speechStatus.textContent = message;
    }

    function speakNext(runId) {
        if (runId !== speechRunId) {
            return;
        }

        if (queueIndex >= readingQueue.length) {
            finishReading("Lectura completada.");
            return;
        }

        const entry = readingQueue[queueIndex];
        clearActiveArticle();
        activeArticle = entry.article;
        activeArticle.classList.add("speech-active");
        speechStatus.textContent = `Leyendo diagnostico ${queueIndex + 1} de ${readingQueue.length}.`;

        const utterance = new SpeechSynthesisUtterance(entry.text);
        const voice = preferredSpanishVoice();
        utterance.lang = voice?.lang ?? "es-ES";
        utterance.rate = Number.parseFloat(rateSelect.value);
        if (voice) {
            utterance.voice = voice;
        }

        currentUtterance = utterance;
        utterance.addEventListener("end", () => {
            if (runId !== speechRunId || currentUtterance !== utterance) {
                return;
            }
            queueIndex += 1;
            speakNext(runId);
        });
        utterance.addEventListener("error", (event) => {
            if (runId !== speechRunId || currentUtterance !== utterance) {
                return;
            }
            if (event.error === "canceled" || event.error === "interrupted") {
                return;
            }
            finishReading("No se pudo completar la lectura por voz.");
        });
        window.speechSynthesis.speak(utterance);
    }

    function startReading(articles, triggerButton) {
        speechRunId += 1;
        window.speechSynthesis.cancel();
        resetSpeechControls();

        readingQueue = articles.map((article) => ({
            article,
            text: prepareTextForSpeech(diagnosticText(article)),
        }));
        activeButton = triggerButton;
        activeButton.setAttribute("aria-pressed", "true");
        pauseButton.disabled = false;
        stopButton.disabled = false;
        speakNext(speechRunId);
    }

    if (!speechSupported) {
        speechStatus.textContent = "La sintesis de voz no esta disponible en este navegador.";
        speakAllButton.disabled = true;
        pauseButton.disabled = true;
        stopButton.disabled = true;
        rateSelect.disabled = true;
        diagnosticButtons.forEach((button) => {
            button.disabled = true;
        });
    } else {
        refreshVoices();
        window.speechSynthesis.addEventListener("voiceschanged", refreshVoices);

        speakAllButton.addEventListener("click", () => {
            startReading(diagnosticItems, speakAllButton);
        });

        diagnosticButtons.forEach((button) => {
            button.addEventListener("click", () => {
                const article = button.closest("[data-speech-item]");
                if (article) {
                    startReading([article], button);
                }
            });
        });

        pauseButton.addEventListener("click", () => {
            if (!currentUtterance) {
                return;
            }

            if (window.speechSynthesis.paused) {
                window.speechSynthesis.resume();
                pauseButton.textContent = "Pausar";
                speechStatus.textContent = `Leyendo diagnostico ${queueIndex + 1} de ${readingQueue.length}.`;
            } else {
                window.speechSynthesis.pause();
                pauseButton.textContent = "Continuar";
                speechStatus.textContent = "Lectura pausada.";
            }
        });

        stopButton.addEventListener("click", () => {
            speechRunId += 1;
            window.speechSynthesis.cancel();
            finishReading("Lectura detenida.");
        });

        window.addEventListener("beforeunload", () => {
            window.speechSynthesis.cancel();
        });
    }
}
