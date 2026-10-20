
import { ApiClient } from './api.js';

const api = new ApiClient();

const el = (id) => document.getElementById(id);

// ==================================================
// MENSAJES
// ==================================================

function msg(text, danger = false) {
    const element = el('message');

    if (!element) return;

    element.textContent = text;

    element.className =
        'small mt-3 ' +
        (danger ? 'text-danger' : 'text-secondary');
}

// ==================================================
// VALIDAR ENLACES DE GOOGLE DRIVE
// ==================================================

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

// ==================================================
// REGLAS PARA IDENTIFICAR TEMAS DOCUMENTALES
// ==================================================

const TOPIC_RULES = [
    {
        title: 'Inteligencia Artificial',
        icon: '🧠',

        keywords: [
            'inteligencia artificial',
            'fundamentos de ia',
            'machine learning',
            'deep learning'
        ],

        description:
            'Fundamentos de IA, aprendizaje automático, ' +
            'redes neuronales, RAG y modelos generativos.',

        question:
            '¿Qué es la Inteligencia Artificial, ' +
            'cuáles son sus fundamentos principales ' +
            'y qué aplicaciones tiene?'
    },

    {
        title: 'Git y GitHub',
        icon: '🌿',

        keywords: [
            'git',
            'github',
            'control de versiones'
        ],

        description:
            'Control de versiones, repositorios, ' +
            'commits, ramas y trabajo colaborativo.',

        question:
            '¿Qué es Git, cuáles son sus principales ' +
            'características y en qué se diferencia de GitHub?'
    },

    {
        title: 'Bases de datos',
        icon: '🗄️',

        keywords: [
            'bases de datos',
            'base de datos',
            'glosario tema 2'
        ],

        description:
            'Conceptos básicos, modelos de datos, ' +
            'organización y administración de información.',

        question:
            '¿Cuáles son los fundamentos de las bases ' +
            'de datos y por qué son importantes?'
    },

    {
        title: 'Amazon AWS y RDS',
        icon: '☁️',

        keywords: [
            'aws',
            'amazon',
            'rds',
            'aurora'
        ],

        description:
            'Servicios de bases de datos en la nube ' +
            'y características de Amazon RDS.',

        question:
            '¿Qué es Amazon RDS y cuáles son sus ' +
            'ventajas para administrar bases de datos?'
    },

    {
        title: 'Objetivos de Desarrollo Sostenible',
        icon: '🌎',

        keywords: [
            'ods',
            'desarrollo sostenible',
            'sostenibilidad'
        ],

        description:
            'Objetivos de Desarrollo Sostenible, ' +
            'innovación, industria e infraestructura.',

        question:
            '¿En qué consiste el ODS 9 y cuál es su ' +
            'importancia para la innovación tecnológica?'
    },

    {
        title: 'Baja California Sur',
        icon: '🏝️',

        keywords: [
            'baja california sur'
        ],

        description:
            'Información cultural, histórica y ' +
            'geográfica sobre Baja California Sur.',

        question:
            '¿Cuáles son las principales características ' +
            'y tradiciones de Baja California Sur?'
    }
];

// ==================================================
// NORMALIZAR NOMBRES
// ==================================================

function normalizeName(value) {
    return String(value || '')
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .toLowerCase()
        .replace(/[_-]+/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
}

// Comparar palabras completas para evitar
// coincidencias accidentales.

function hasKeyword(filename, keyword) {
    const name = normalizeName(filename);
    const term = normalizeName(keyword);

    if (!name || !term) return false;

    return (' ' + name + ' ')
        .includes(' ' + term + ' ');
}

// ==================================================
// MOSTRAR DOCUMENTOS INDEXADOS
// ==================================================

function renderDocuments(documents) {
    const box = el('documents');
    const counter = el('doc-count');

    if (!box) return;

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
            link.textContent =
                archivo.name || 'Documento sin nombre';

            div.appendChild(link);

        } else {
            const span = document.createElement('span');

            span.textContent =
                archivo.name || 'Documento sin nombre';

            div.appendChild(span);
        }

        box.appendChild(div);
    }
}

// ==================================================
// CREAR TARJETAS DE SUGERENCIAS
// ==================================================

function createTopicCard(topic) {
    const button = document.createElement('button');

    button.type = 'button';
    button.className = 'topic-card';

    // Ícono
    const icon = document.createElement('span');

    icon.className = 'topic-icon';
    icon.textContent = topic.icon;
    icon.setAttribute('aria-hidden', 'true');

    // Título
    const title = document.createElement('span');

    title.className = 'topic-name';
    title.textContent = topic.title;

    // Descripción
    const description = document.createElement('span');

    description.className = 'topic-description';
    description.textContent = topic.description;

    // Acción
    const action = document.createElement('span');

    action.className = 'topic-action';
    action.textContent = 'Preguntar sobre este tema →';

    button.append(
        icon,
        title,
        description,
        action
    );

    // Al seleccionar una tarjeta,
    // colocar la pregunta en el formulario.
    button.addEventListener('click', () => {
        const questionField = el('question');

        if (!questionField) return;

        questionField.value = topic.question;

        questionField.focus();

        questionField.scrollIntoView({
            behavior: 'smooth',
            block: 'center'
        });
    });

    return button;
}

// ==================================================
// GENERAR TEMAS A PARTIR DE LOS DOCUMENTOS
// ==================================================

function renderSuggestedTopics(documents) {
    const container = el('suggested-topics');
    const status = el('topics-status');

    // La sección es opcional.
    // Si el HTML todavía no la tiene,
    // las demás funciones siguen trabajando.
    if (!container || !status) return;

    container.replaceChildren();

    if (documents.length === 0) {
        status.textContent =
            'No hay documentos disponibles para sugerir temas.';
        return;
    }

    const matchedFiles = new Set();

    // Identificar temas conocidos.
    const matchingTopics = TOPIC_RULES.filter(topic => {
        const matches = documents.filter(archivo =>
            topic.keywords.some(keyword =>
                hasKeyword(archivo.name, keyword)
            )
        );

        for (const archivo of matches) {
            matchedFiles.add(archivo);
        }

        return matches.length > 0;
    });

    for (const topic of matchingTopics) {
        container.appendChild(
            createTopicCard(topic)
        );
    }

    // Documentos que no coinciden con
    // ninguna de las categorías anteriores.
    const otherFiles = documents.filter(
        archivo => !matchedFiles.has(archivo)
    );

    for (const archivo of otherFiles) {
        const name = archivo.name || 'Documento';

        const topic = {
            title: name,
            icon: '📄',

            description:
                'Consulta los conceptos e información ' +
                'disponibles en este documento.',

            question:
                '¿Cuáles son los temas principales ' +
                'del documento "' + name + '"?'
        };

        container.appendChild(
            createTopicCard(topic)
        );
    }

    status.textContent =
        documents.length +
        ' documentos disponibles · ' +
        container.children.length +
        ' temas sugeridos';
}

// ==================================================
// CARGAR DOCUMENTOS Y SUGERENCIAS
// ==================================================

async function loadDocuments() {
    const box = el('documents');
    const counter = el('doc-count');
    const topicsStatus = el('topics-status');
    const topicsContainer = el('suggested-topics');

    if (box) {
        box.textContent = 'Cargando documentos...';
    }

    if (topicsStatus) {
        topicsStatus.textContent =
            'Identificando temas disponibles...';
    }

    try {
        // Una sola petición para ambas secciones.
        const result = await api.documents();

        const documents = Array.isArray(result.documents)
            ? result.documents
            : [];

        renderDocuments(documents);

        renderSuggestedTopics(documents);

    } catch (error) {
        if (counter) {
            counter.textContent = '—';
        }

        if (box) {
            box.textContent =
                'No se pudo cargar la base documental.';
        }

        if (topicsContainer) {
            topicsContainer.replaceChildren();
        }

        if (topicsStatus) {
            topicsStatus.textContent =
                'No fue posible cargar las sugerencias.';
        }

        msg(error.message, true);

        console.error(
            'Error al cargar documentos:',
            error
        );
    }
}

// ==================================================
// MOSTRAR FUENTES VERIFICABLES
// ==================================================

function showSources(sources = []) {
    const container = el('sources');

    if (!container) return;

    container.replaceChildren();

    if (!sources.length) {
        const li = document.createElement('li');

        li.className =
            'list-group-item px-0 text-secondary';

        li.textContent =
            'No se recibieron citas verificables ' +
            'para esta respuesta.';

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
            link.textContent =
                source.name || 'Documento';

            li.appendChild(link);

        } else {
            const span = document.createElement('span');

            span.textContent =
                source.name || 'Documento';

            li.appendChild(span);
        }

        container.appendChild(li);
    }
}

// ==================================================
// CONSULTAR AGENTE
// ==================================================

async function ask() {
    const questionField = el('question');
    const button = el('ask');

    if (!questionField || !button) return;

    if (button.disabled) return;

    const question = questionField.value.trim();

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
        const useSearch = el('use-search')?.checked ?? true;

        const result = await api.ask(
            question,
            useSearch
        );

        const answer = el('answer');

        if (answer) {
            answer.textContent =
                result.answer || 'Sin respuesta.';
        }

        showSources(result.sources || []);

        msg('Consulta finalizada.');

    } catch (error) {
        msg(error.message, true);

        console.error(
            'Error al consultar al agente:',
            error
        );

    } finally {
        button.disabled = false;
    }
}

// ==================================================
// ESTADO DEL SERVIDOR
// ==================================================

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

// ==================================================
// EVENTOS
// ==================================================

const askButton = el('ask');

if (askButton) {
    askButton.addEventListener('click', ask);
}

const questionInput = el('question');

if (questionInput) {
    questionInput.addEventListener('keydown', event => {
        if (
            event.key === 'Enter' &&
            (event.ctrlKey || event.metaKey)
        ) {
            event.preventDefault();
            ask();
        }
    });
}

// ==================================================
// INICIALIZACIÓN
// ==================================================

checkHealth();

loadDocuments();
