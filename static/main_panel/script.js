// Variables globales
let avisos = [];
let avisosEnPantalla = [];
let currentAvisoIndex = 0;
let rotationInterval;
let hashPollInterval;
let ultimoHashAvisos = null;
let currentMainCardId = null;  // Para evitar duplicados con el recuadro principal
let usedAvisoIds = new Set();  // Para rastrear avisos ya mostrados
let mainCardRotationIndex = 0;  // Índice específico para el recuadro principal

// Función para actualizar hora y fecha con animaciones suaves
function actualizarHoraFecha() {
    const ahora = new Date();
    const horaElement = document.getElementById('hora-actual');
    const fechaElement = document.getElementById('fecha-actual');
    
    // Hora
    let horas = ahora.getHours();
    const minutos = ahora.getMinutes().toString().padStart(2, '0');
    const ampm = horas >= 12 ? 'PM' : 'AM';
    horas = horas % 12;
    horas = horas ? horas : 12;
    const textoPlano = `${horas}:${minutos} ${ampm}`;
    
    // Animación suave para cambio de hora
    if (horaElement.textContent.trim() !== textoPlano) {
        horaElement.style.transform = 'scale(1.05)';
        horaElement.style.color = '#ffeb3b';
        setTimeout(() => {
            horaElement.innerHTML = `<span class="hhmm">${horas}:${minutos}</span> <span class="ampm">${ampm}</span>`;
            horaElement.style.transform = 'scale(1)';
            horaElement.style.color = '#fff';
        }, 200);
    }
    
    // Fecha
    const dia = ahora.getDate().toString().padStart(2, '0');
    const mes = (ahora.getMonth() + 1).toString().padStart(2, '0');
    const anio = ahora.getFullYear();
    const nuevaFecha = `${dia}/${mes}/${anio}`;
    
    if (fechaElement.textContent !== nuevaFecha) {
        fechaElement.style.transform = 'scale(1.02)';
        setTimeout(() => {
            fechaElement.textContent = nuevaFecha;
            fechaElement.style.transform = 'scale(1)';
        }, 200);
    }
}

// Función para actualizar el clima dinámicamente
async function actualizarClima() {
    try {
        const response = await fetch('/api/clima');
        const clima = await response.json();
        
        if (clima) {
            const iconoElement = document.getElementById('icono-clima');
            const temperaturaElement = document.getElementById('temperatura-actual');
            const descripcionElement = document.getElementById('descripcion-clima');
            
            // Animación suave para cambio de clima
            const weatherInfo = document.querySelector('.weather-info');
            weatherInfo.style.opacity = '0.7';
            weatherInfo.style.transform = 'scale(0.95)';
            
            setTimeout(() => {
                // Actualizar icono
                if (iconoElement) {
                    iconoElement.className = `bi ${clima.icono_bootstrap} weather-icon`;
                }
                
                // Actualizar temperatura
                if (temperaturaElement) {
                    temperaturaElement.textContent = `${Math.round(clima.temperatura_actual)}°C`;
                }
                
                // Actualizar descripción
                if (descripcionElement) {
                    descripcionElement.textContent = clima.descripcion;
                }
                
                // Restaurar animación
                weatherInfo.style.opacity = '1';
                weatherInfo.style.transform = 'scale(1)';
            }, 300);
        }
    } catch (error) {
        console.error('Error actualizando clima:', error);
    }
}

// Función para cargar avisos desde la API
async function cargarAvisos() {
    try {
        const response = await fetch('/panel/avisos');
        const data = await response.json();
        avisos = data;
        // Limitar el set de rotación a los 4 que están en la vista (main + 3 laterales)
        avisosEnPantalla = obtenerAvisosInicialesDesdeDOM(avisos);
        console.log('Avisos cargados:', avisos.length);
        if (avisosEnPantalla.length > 0) {
            iniciarRotacionAvisos();
        }
    } catch (error) {
        console.error('Error cargando avisos:', error);
    }
}

// Función para obtener avisos únicos para las tarjetas laterales
function obtenerAvisosVentanaCircular(cantidadRequerida) {
    const fuente = avisosEnPantalla.length ? avisosEnPantalla : avisos;
    if (fuente.length === 0) return [];
    const result = [];
    // Principal es offset 0; laterales deben ser offsets 1..cantidad
    for (let i = 1; i <= cantidadRequerida; i++) {
        const idx = (mainCardRotationIndex + i) % fuente.length;
        result.push(fuente[idx]);
    }
    return result;
}

// Función para rotar avisos en las tarjetas
function rotarAvisos() {
    const sideCards = document.querySelectorAll('.side-card');
    
    if (avisos.length === 0 || sideCards.length === 0) return;
    
    // Avisos para laterales basados en ventana circular a partir del índice del principal
    const avisosUnicos = obtenerAvisosVentanaCircular(sideCards.length);
    
    sideCards.forEach((card, index) => {
        const aviso = avisosUnicos[index];
        
        if (aviso) {
            // Animación de salida
            card.style.opacity = '0.7';
            card.style.transform = 'scale(0.95)';
            
            setTimeout(() => {
                // Actualizar contenido con animación de zoom
                const imgUrl = aviso.image_url && aviso.image_url.trim() !== ''
                    ? aviso.image_url
                    : 'static/main_panel/img/logo.png';
                card.classList.add('image-transition');
                card.style.backgroundImage = `url('${imgUrl}')`;
                
                // Remover la clase después de la animación
                setTimeout(() => {
                    card.classList.remove('image-transition');
                }, 800);
                
                const overlay = card.querySelector('.side-card-overlay');
                if (overlay) {
                    const dateElement = overlay.querySelector('.side-card-date');
                    const titleElement = overlay.querySelector('.side-card-title');
                    
                    if (dateElement) {
                        const fechaInicio = aviso.fecha_inicio ? new Date(aviso.fecha_inicio).toLocaleDateString('es-ES') : '';
                        const fechaFin = aviso.fecha_fin ? new Date(aviso.fecha_fin).toLocaleDateString('es-ES') : '';
                        dateElement.textContent = fechaInicio && fechaFin ? `${fechaInicio} - ${fechaFin}` : '';
                    }
                    
                    if (titleElement) {
                        titleElement.textContent = aviso.title || '';
                    }
                }
                
                // Animación de entrada
                card.style.opacity = '1';
                card.style.transform = 'scale(1)';
            }, 300);
        }
    });
    
    // Nota: El índice se avanza ahora en rotarTodosLosAvisos()
}

// Función para rotar tanto el aviso principal como las tarjetas laterales
function rotarTodosLosAvisos() {
    const fuente = avisosEnPantalla.length ? avisosEnPantalla : avisos;
    if (fuente.length === 0) return;
    
    // Primero avanzar el índice del aviso principal
    mainCardRotationIndex = (mainCardRotationIndex + 1) % fuente.length;
    
    // Luego rotar el aviso principal
    rotarAvisoPrincipalSincronizado();
    
    // Después rotar las tarjetas laterales con un pequeño delay
    setTimeout(() => {
        rotarAvisos();
        // currentAvisoIndex ya no es necesario para la ventana circular, pero lo mantenemos si en el futuro se usa
        currentAvisoIndex = (currentAvisoIndex + 1) % Math.max((avisosEnPantalla.length ? avisosEnPantalla.length : avisos.length), 1);
    }, 200);
}

// Función para rotar el aviso principal de forma sincronizada
function rotarAvisoPrincipalSincronizado() {
    const mainCard = document.querySelector('.main-card');
    const mainCardText = document.querySelector('.main-card-text');
    
    if (avisos.length === 0 || !mainCard) return;
    
    // Obtener el aviso actual para el recuadro principal (el índice ya fue avanzado)
    const avisoParaPrincipal = obtenerSiguienteAvisoParaPrincipal();
    
    if (avisoParaPrincipal) {
        // Actualizar el ID del aviso principal actual
        currentMainCardId = avisoParaPrincipal.id;
        
        // Animación de transición
        mainCard.style.opacity = '0.8';
        mainCard.style.transform = 'scale(0.98)';
        
        setTimeout(() => {
            const imgUrl = avisoParaPrincipal.image_url && avisoParaPrincipal.image_url.trim() !== ''
                ? avisoParaPrincipal.image_url
                : 'static/main_panel/img/logo.png';
            mainCard.classList.add('image-transition');
            mainCard.style.backgroundImage = `url('${imgUrl}')`;
            
            // Remover la clase después de la animación
            setTimeout(() => {
                mainCard.classList.remove('image-transition');
            }, 800);
            
            if (mainCardText) {
                mainCardText.innerHTML = avisoParaPrincipal.title || 'Se acerca el 18, con ello<br>actividades recreativas<br>¡Pasalo chancho!';
                mainCardText.dataset.avisoId = avisoParaPrincipal.id || '';
            }
            // Actualizar badge de fecha dinámicamente
            actualizarBadgeFechaPrincipal(avisoParaPrincipal);
            
            // Restaurar animación
            mainCard.style.opacity = '1';
            mainCard.style.transform = 'scale(1)';
        }, 400);
    }
}

function humanizeFecha(fechaIso) {
    if (!fechaIso) return '';
    try {
        const f = new Date(fechaIso.replace(' ', 'T'));
        const hoy = new Date();
        const dF = new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate());
        const dA = new Date(f.getFullYear(), f.getMonth(), f.getDate());
        const delta = Math.round((dA - dF) / (1000*60*60*24));
        if (delta === 0) return 'Hoy';
        if (delta === 1) return 'Mañana';
        if (delta > 1 && delta <= 7) return `En ${delta} días`;
        const dd = dA.getDate().toString().padStart(2, '0');
        const mm = (dA.getMonth()+1).toString().padStart(2, '0');
        const yyyy = dA.getFullYear();
        return `${dd}/${mm}/${yyyy}`;
    } catch (e) { return ''; }
}

function actualizarBadgeFechaPrincipal(aviso) {
    const badge = document.querySelector('.main-card-badge');
    if (!badge) return;
    const label = humanizeFecha(aviso.fecha_inicio);
    badge.textContent = label;
    badge.style.display = label ? 'block' : 'none';
}

// Función para obtener el siguiente aviso para el recuadro principal
function obtenerSiguienteAvisoParaPrincipal() {
    const fuente = avisosEnPantalla.length ? avisosEnPantalla : avisos;
    if (fuente.length === 0) return null;
    
    // Obtener el aviso en el índice actual del recuadro principal
    return fuente[mainCardRotationIndex % fuente.length];
}

// Función para iniciar la rotación de avisos
function iniciarRotacionAvisos() {
    // Rotar inmediatamente
    rotarTodosLosAvisos();
    
    // Configurar rotación automática cada 8 segundos
    if (rotationInterval) {
        clearInterval(rotationInterval);
    }
    rotationInterval = setInterval(rotarTodosLosAvisos, 8000);

    // Programar recarga completa cada 10 minutos
    if (hashPollInterval) {
        clearInterval(hashPollInterval);
    }
    // Chequear cambios cada 5s; recargar si cambia el hash. Además, forzar reload cada 10 minutos
    const startTime = Date.now();
    const checkHash = async () => {
        try {
            const r = await fetch('/panel/avisos_hash');
            const j = await r.json();
            if (j && j.hash) {
                if (!ultimoHashAvisos) {
                    ultimoHashAvisos = j.hash;
                } else if (ultimoHashAvisos !== j.hash) {
                    location.reload();
                }
            }
        } catch (e) {
            // ignorar errores transitorios
        }
        if (Date.now() - startTime > 10 * 60 * 1000) {
            location.reload();
        }
    };
    // Primera comprobación inmediata
    checkHash();
    // Intervalo periódico
    hashPollInterval = setInterval(checkHash, 5000);
    // Al volver a la pestaña, comprobar de nuevo
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) {
            checkHash();
        }
    });
}


// Función para obtener el aviso más próximo por fecha
function obtenerAvisoMasProximo() {
    if (avisos.length === 0) return null;
    
    const ahora = new Date();
    const avisosConFecha = avisos.filter(aviso => aviso.fecha_inicio);
    
    if (avisosConFecha.length === 0) return avisos[0];
    
    // Ordenar por proximidad de fecha de inicio
    avisosConFecha.sort((a, b) => {
        const fechaA = new Date(a.fecha_inicio);
        const fechaB = new Date(b.fecha_inicio);
        const diffA = Math.abs(fechaA - ahora);
        const diffB = Math.abs(fechaB - ahora);
        return diffA - diffB;
    });
    
    return avisosConFecha[0];
}

// Función para obtener el ID del aviso principal inicial desde el HTML
function obtenerIdAvisoPrincipalInicial() {
    // Intentar obtener el ID del aviso principal desde el HTML renderizado por el servidor
    const mainCardText = document.querySelector('.main-card-text');
    if (mainCardText && mainCardText.dataset && mainCardText.dataset.avisoId) {
        currentMainCardId = parseInt(mainCardText.dataset.avisoId);
    }

    // Construir lista inicial a partir del DOM: principal + laterales
    const sideCards = Array.from(document.querySelectorAll('.side-card'));
    const idsSide = sideCards
        .map(c => parseInt(c.getAttribute('data-aviso-id'))) 
        .filter(v => !Number.isNaN(v));
    const ids = [];
    if (!Number.isNaN(currentMainCardId)) ids.push(currentMainCardId);
    ids.push(...idsSide);
    // Mapear a objetos de avisos ya cargados cuando llegue la API
    window.__idsInicialesAvisos = ids;
}

function obtenerAvisosInicialesDesdeDOM(listaAvisosApi) {
    if (!window.__idsInicialesAvisos || !Array.isArray(window.__idsInicialesAvisos)) return listaAvisosApi.slice(0, 4);
    const byId = new Map(listaAvisosApi.map(a => [a.id, a]));
    const result = [];
    window.__idsInicialesAvisos.forEach(id => {
        const a = byId.get(id);
        if (a) result.push(a);
    });
    // Asegurar máximo 4
    return result.slice(0, 4);
}

// Inicialización
document.addEventListener('DOMContentLoaded', function() {
    actualizarHoraFecha();
    setInterval(actualizarHoraFecha, 1000);
    
    // Actualizar clima inmediatamente y luego cada 10 minutos
    actualizarClima();
    setInterval(actualizarClima, 600000); // 10 minutos = 600,000 ms
    
    // Obtener el ID del aviso principal inicial
    obtenerIdAvisoPrincipalInicial();
    
    // Cargar avisos después de un breve delay para permitir que la página cargue
    setTimeout(() => {
        cargarAvisos();
        // Nota: La rotación del aviso principal ahora está integrada con las tarjetas laterales
        // en la función iniciarRotacionAvisos(), no necesita intervalo separado
    }, 2000);
});