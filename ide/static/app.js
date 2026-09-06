CodeMirror.defineSimpleMode("compiscript", {
  start: [
    { regex: /\b(?:let|var|const|function|class|new|this|if|else|while|do|for|foreach|in|switch|case|default|break|continue|return|try|catch|print)\b/, token: "keyword" },
    { regex: /\b(?:boolean|integer|string|true|false|null)\b/, token: "atom" },
    { regex: /"(?:[^\\"]|\\.)*"/, token: "string" },
    { regex: /\b\d+\b/, token: "number" },
    { regex: /\/\/.*/, token: "comment" },
    { regex: /\/\*/, token: "comment", next: "comment" },
    { regex: /[-+/*%=<>!&|?:]+/, token: "operator" },
    { regex: /[A-Za-z_]\w*/, token: "variable" }
  ],
  comment: [
    { regex: /.*?\*\//, token: "comment", next: "start" },
    { regex: /.*/, token: "comment" }
  ],
  meta: { lineComment: "//", blockCommentStart: "/*", blockCommentEnd: "*/" }
});

const editor = CodeMirror.fromTextArea(document.querySelector("#source"), {
  mode: "compiscript",
  lineNumbers: true,
  indentUnit: 4,
  tabSize: 4,
  lineWrapping: true
});

const compileButton = document.querySelector("#compile");
const errorsPanel = document.querySelector("#errors");
const symbolsPanel = document.querySelector("#symbols");
const treePanel = document.querySelector("#tree");
const errorCount = document.querySelector("#error-count");

function escapeHtml(value) {
  const element = document.createElement("span");
  element.textContent = String(value);
  return element.innerHTML;
}

function renderErrors(errors) {
  errorCount.textContent = errors.length;
  if (!errors.length) {
    errorsPanel.innerHTML = '<div class="empty success"><strong>Sin errores</strong><p>El programa pasó todas las fases.</p></div>';
    return;
  }
  errorsPanel.innerHTML = errors.map(error => `
    <article class="error-card">
      <div><span class="badge">${escapeHtml(error.category)}</span><code>${escapeHtml(error.rule)}</code></div>
      <strong>Línea ${error.line}, columna ${error.column}</strong>
      <p>${escapeHtml(error.message)}</p>
    </article>`).join("");
}

function renderSymbols(symbols) {
  if (!symbols.length) {
    symbolsPanel.innerHTML = '<div class="empty"><strong>Sin símbolos disponibles</strong></div>';
    return;
  }
  symbolsPanel.innerHTML = `<div class="table-wrap"><table>
    <thead><tr><th>Nombre</th><th>Tipo</th><th>Categoría</th><th>Ámbito</th></tr></thead>
    <tbody>${symbols.map(symbol => `<tr>
      <td>${escapeHtml(symbol.name)}</td><td>${escapeHtml(symbol.type)}</td>
      <td>${escapeHtml(symbol.category)}</td><td>${escapeHtml(symbol.scope)} #${symbol.scopeId}</td>
    </tr>`).join("")}</tbody>
  </table></div>`;
}

function treeNode(node) {
  const children = node.children || [];
  if (!children.length) return `<li><span class="token">${escapeHtml(node.label)}</span></li>`;
  return `<li><details><summary>${escapeHtml(node.label)}</summary><ul>${children.map(treeNode).join("")}</ul></details></li>`;
}

function renderTree(tree) {
  treePanel.innerHTML = tree ? `<ul>${treeNode(tree)}</ul>` : '<div class="empty">Árbol no disponible.</div>';
}

async function compile() {
  compileButton.disabled = true;
  compileButton.firstChild.textContent = "Compilando… ";
  try {
    const response = await fetch("/compile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source: editor.getValue() })
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "No se pudo compilar.");
    renderErrors(result.errors);
    renderSymbols(result.symbols);
    renderTree(result.tree);
  } catch (error) {
    renderErrors([{ category: "servidor", rule: "error-interno", line: 0, column: 0, message: error.message }]);
  } finally {
    compileButton.disabled = false;
    compileButton.firstChild.textContent = "Compilar ";
  }
}

document.querySelectorAll(".tab").forEach(tab => tab.addEventListener("click", () => {
  document.querySelectorAll(".tab, .result-panel").forEach(item => item.classList.remove("active"));
  tab.classList.add("active");
  document.querySelector(`#${tab.dataset.panel}`).classList.add("active");
}));

compileButton.addEventListener("click", compile);
editor.setOption("extraKeys", { "Ctrl-Enter": compile, "Cmd-Enter": compile });
compile();
