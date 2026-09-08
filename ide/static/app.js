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
const demoPanel = document.querySelector("#demo");
const errorCount = document.querySelector("#error-count");
const demoCount = document.querySelector("#demo-count");

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

function renderDemoTests(tests) {
  const total = tests.length;
  const passed = tests.filter(test => test.passed).length;
  demoCount.textContent = `${passed}/${total}`;

  const groups = [];
  const byGroup = new Map();
  for (const test of tests) {
    if (!byGroup.has(test.group)) {
      byGroup.set(test.group, []);
      groups.push(test.group);
    }
    byGroup.get(test.group).push(test);
  }

  const summaryClass = passed === total ? "success" : "failure";
  const summary = `
    <div class="demo-summary ${summaryClass}">
      <strong>${passed} / ${total} casos pasaron</strong>
      <button id="demo-rerun" type="button">Ejecutar de nuevo</button>
    </div>`;

  const body = groups.map(group => `
    <div class="demo-group">
      <h3>${escapeHtml(group)}</h3>
      ${byGroup.get(group).map(test => `
        <article class="demo-card ${test.passed ? "pass" : "fail"}" data-id="${escapeHtml(test.id)}">
          <span class="demo-status">${test.passed ? "✅" : "❌"}</span>
          <strong>${escapeHtml(test.title)}</strong>
          <button class="demo-load" type="button" data-source="${encodeURIComponent(test.source)}">Cargar</button>
        </article>`).join("")}
    </div>`).join("");

  demoPanel.innerHTML = summary + body;

  document.querySelector("#demo-rerun").addEventListener("click", runDemoSuite);
  document.querySelectorAll(".demo-load").forEach(button => button.addEventListener("click", () => {
    editor.setValue(decodeURIComponent(button.dataset.source));
    document.querySelector('.tab[data-panel="errors"]').click();
    compile();
  }));
}

async function runDemoSuite() {
  demoPanel.innerHTML = '<div class="empty">Ejecutando pruebas…</div>';
  try {
    const response = await fetch("/demo-tests");
    const tests = await response.json();
    renderDemoTests(tests);
  } catch (error) {
    demoPanel.innerHTML = `<div class="empty">No se pudieron ejecutar las pruebas: ${escapeHtml(error.message)}</div>`;
  }
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

let demoLoaded = false;
document.querySelectorAll(".tab").forEach(tab => tab.addEventListener("click", () => {
  document.querySelectorAll(".tab, .result-panel").forEach(item => item.classList.remove("active"));
  tab.classList.add("active");
  document.querySelector(`#${tab.dataset.panel}`).classList.add("active");
  if (tab.dataset.panel === "demo" && !demoLoaded) {
    demoLoaded = true;
    runDemoSuite();
  }
}));

compileButton.addEventListener("click", compile);
editor.setOption("extraKeys", { "Ctrl-Enter": compile, "Cmd-Enter": compile });
compile();
