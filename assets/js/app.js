
import { ApiClient } from './api.js';

const api = new ApiClient();

const el = (id) => document.getElementById(id);

// --------------------------------------------------
// MENSAJES
// --------------------------------------------------

function msg(text, danger = false) {
    const element = el('message');

    if (!element) return;

    element.textContent = text;
    element.className =
        'small mt-3 ' +
        (danger ? 'text-danger' : 'text-secondary');
}

// --------------------------------------------------
// VALIDAR ENLACES DE GOOGLE DRIVE
// --------------------------------------------------

function linkFor(source) {
    if (!source || !source.url) return null;

    try {
        const url = new URL(source.url);

        if (
            url.protocol === 'https:' &&
            ['drive.google.com', 'docs.google.com']
                .includes(url.hostname)
        ) {
            return url.href;
        }
    } catch (error) {
        return null;
    }

    return null;
}

// --------------------------------------------------
// MOSTRAR DOCUMENTOS INDEXADOS
// --------------------------------------------------

async function loadDocuments() {
    const box = el('documents');
    const counter = el('doc-count');

    if (!box) return;

    box.textContent = 'Cargando documentos...';

    try {
        const result = await api.documents();
        const documents = result.documents || [];

        if (counter) {
            counter.textContent = documents.length;
        }

        box.replaceChildren();

        if (documents.length === 0) {
            box.textContent =
                'No se encontraron documentos indexados.';
            return;
        }


        for (const archivo of documents) {
            const div = document.createElement('div');
            div.className = 'doc-item';

            const href = linkFor(archivo);

            if (href) {
                const link = document.createElement('a');

                link.href = href;
                link.target = '_blank';
                link.rel = 'noopener noreferrer';
                link.textContent = archivo.name;

                div.appendChild(link);
            } else {
                const span = document.createElement('span');

                span.textContent = archivo.name;

                div.appendChild(span);
            }

            box.appendChild(div);
        }


    } catch (error) {
        if (counter) counter.textContent = '—';

        box.textContent =
            'No se pudo cargar la base documental.';

        msg(error.message, true);
    }
}

// --------------------------------------------------
// MOSTRAR FUENTES VERIFICABLES
// --------------------------------------------------

function showSources(sources = []) {
    const container = el('sources');

    if (!container) return;

    container.replaceChildren();

    if (!sources.length) {
        const li = document.createElement('li');

        li.className =
            'list-group-item px-0 text-secondary';

        li.textContent =
            'No se recibieron citas verificables para esta respuesta.';

        container.appendChild(li);
        return;
    }

    for (const source of sources) {
        const li = document.createElement('li');

        li.className = 'list-group-item px-0';

        const href = linkFor(source);

        if (href) {
            const link = document.createElement('a');

            link.href = href;
            link.target = '_blank';
            link.rel = 'noopener noreferrer';
            link.textContent = source.name;

            li.appendChild(link);
        } else {
            const span = document.createElement('span');

            span.textContent = source.name;

            li.appendChild(span);
        }

        container.appendChild(li);
    }
}

// --------------------------------------------------
// CONSULTAR AGENTE
// --------------------------------------------------

async function ask() {
    const question = el('question').value.trim();
    const button = el('ask');

    if (question.length < 3) {
        msg(
            'Escribe una pregunta de al menos 3 caracteres.',
            true
        );
        return;
    }

    button.disabled = true;

    msg('Consultando al agente...');

    try {
        const useSearch = el('use-search').checked;

        const result = await api.ask(
            question,
            useSearch
        );

        el('answer').textContent =
            result.answer || 'Sin respuesta.';

        showSources(result.sources || []);

        msg('Consulta finalizada.');

    } catch (error) {
        msg(error.message, true);

    } finally {
        button.disabled = false;
    }
}

// --------------------------------------------------
// ESTADO DEL SERVIDOR
// --------------------------------------------------

async function checkHealth() {
    const indicator = el('health');

    if (!indicator) return;

    try {
        const result = await api.health();

        indicator.textContent = result.configured
            ? 'Servidor conectado'
            : 'Configuración pendiente';

    } catch (error) {
        indicator.textContent = 'Sin conexión';
    }
}

// --------------------------------------------------
// EVENTOS
// --------------------------------------------------

const askButton = el('ask');

if (askButton) {
    askButton.addEventListener('click', ask);
}

const questionInput = el('question');

if (questionInput) {
    questionInput.addEventListener('keydown', (event) => {
        if (
            event.key === 'Enter' &&
            (event.ctrlKey || event.metaKey)
        ) {
            ask();
        }
    });
}

// --------------------------------------------------
// INICIALIZACIÓN
// --------------------------------------------------

checkHealth();
loadDocuments();
