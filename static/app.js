const codeInput = document.querySelector("#codigo");
const fileInput = document.querySelector("#archivo");
const characterCount = document.querySelector("#character-count");
const fileName = document.querySelector("#editor-status");
const analysisForm = document.querySelector("#analysis-form");
const analyzeButton = document.querySelector("#analyze-button");

function updateCharacterCount() {
    const total = codeInput.value.length;
    characterCount.textContent = `${total.toLocaleString("es")} caracteres`;
}

codeInput.addEventListener("input", updateCharacterCount);
updateCharacterCount();

fileInput.addEventListener("change", () => {
    const [file] = fileInput.files;
    if (!file) {
        return;
    }

    fileName.textContent = file.name;
    const reader = new FileReader();
    reader.addEventListener("load", () => {
        codeInput.value = String(reader.result ?? "");
        updateCharacterCount();
    });
    reader.readAsText(file, "UTF-8");
});

analysisForm.addEventListener("submit", () => {
    analyzeButton.disabled = true;
    analyzeButton.textContent = "Analizando...";
    analysisForm.setAttribute("aria-busy", "true");
});
