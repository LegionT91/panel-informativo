// Variables globales
let avisos = [];
let currentAvisoIndex = 0;
let rotationInterval;
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
    const nuevaHora = `${horas}:${minutos} ${ampm}`;
    
    // Animación suave para cambio de hora
    if (horaElement.textContent !== nuevaHora) {
        horaElement.style.transform = 'scale(1.05)';
        horaElement.style.color = '#ffeb3b';
        setTimeout(() => {
            horaElement.textContent = nuevaHora;
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
        console.log('Avisos cargados:', avisos.length);
        if (avisos.length > 0) {
            iniciarRotacionAvisos();
        }
    } catch (error) {
        console.error('Error cargando avisos:', error);
    }
}

// Función para obtener avisos únicos para las tarjetas laterales
function obtenerAvisosUnicos(cantidadRequerida) {
    if (avisos.length === 0) return [];
    
    // Obtener el aviso que ACTUALMENTE está en el recuadro principal
    const avisoActualPrincipal = avisos[mainCardRotationIndex % avisos.length];
    const idAvisoActualPrincipal = avisoActualPrincipal ? avisoActualPrincipal.id : null;
    
    // Filtrar avisos disponibles excluyendo el principal
    const avisosDisponibles = avisos.filter(aviso => aviso.id !== idAvisoActualPrincipal);
    const avisosSeleccionados = [];
    const idsUsados = new Set([idAvisoActualPrincipal]); // Incluir el ID del principal para evitarlo
    
    // Si hay suficientes avisos únicos
    if (avisosDisponibles.length >= cantidadRequerida) {
        // Usar un índice diferente para las tarjetas laterales, asegurando que sea diferente del principal
        let startIndex = currentAvisoIndex % avisosDisponibles.length;
        
        for (let i = 0; i < cantidadRequerida && avisosSeleccionados.length < cantidadRequerida; i++) {
            const avisoIndex = (startIndex + i) % avisosDisponibles.length;
            const aviso = avisosDisponibles[avisoIndex];
            
            if (aviso && !idsUsados.has(aviso.id)) {
                avisosSeleccionados.push(aviso);
                idsUsados.add(aviso.id);
            }
        }
    } else {
        // Si no hay suficientes avisos únicos, usar los disponibles sin repetir
        avisosDisponibles.forEach(aviso => {
            if (avisosSeleccionados.length < cantidadRequerida && !idsUsados.has(aviso.id)) {
                avisosSeleccionados.push(aviso);
                idsUsados.add(aviso.id);
            }
        });
    }
    
    // Completar con placeholders si es necesario
    while (avisosSeleccionados.length < cantidadRequerida) {
        avisosSeleccionados.push({
            id: `placeholder_${Date.now()}_${avisosSeleccionados.length}`,
            title: 'Próximamente más noticias',
            image_url: 'https://images.unsplash.com/photo-1517649763962-0c623066013b?auto=format&fit=crop&w=400&q=80',
            fecha_inicio: '',
            fecha_fin: ''
        });
    }
    
    return avisosSeleccionados;
}

// Función para rotar avisos en las tarjetas
function rotarAvisos() {
    const sideCards = document.querySelectorAll('.side-card');
    
    if (avisos.length === 0 || sideCards.length === 0) return;
    
    // Obtener avisos únicos para las tarjetas laterales
    const avisosUnicos = obtenerAvisosUnicos(sideCards.length);
    
    sideCards.forEach((card, index) => {
        const aviso = avisosUnicos[index];
        
        if (aviso) {
            // Animación de salida
            card.style.opacity = '0.7';
            card.style.transform = 'scale(0.95)';
            
            setTimeout(() => {
                // Actualizar contenido con animación de zoom
                if (aviso.image_url) {
                    card.classList.add('image-transition');
                    card.style.backgroundImage = `url('${aviso.image_url}')`;
                    
                    // Remover la clase después de la animación
                    setTimeout(() => {
                        card.classList.remove('image-transition');
                    }, 800);
                }
                
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
    if (avisos.length === 0) return;
    
    // Primero avanzar el índice del aviso principal
    mainCardRotationIndex = (mainCardRotationIndex + 1) % avisos.length;
    
    // Luego rotar el aviso principal
    rotarAvisoPrincipalSincronizado();
    
    // Después rotar las tarjetas laterales con un pequeño delay
    setTimeout(() => {
        rotarAvisos();
        // Avanzar el índice de las tarjetas después de usarlo
        currentAvisoIndex = (currentAvisoIndex + 1) % Math.max(avisos.length, 1);
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
            if (avisoParaPrincipal.image_url) {
                mainCard.classList.add('image-transition');
                mainCard.style.backgroundImage = `url('${avisoParaPrincipal.image_url}')`;
                
                // Remover la clase después de la animación
                setTimeout(() => {
                    mainCard.classList.remove('image-transition');
                }, 800);
            }
            
            if (mainCardText) {
                mainCardText.innerHTML = avisoParaPrincipal.title || 'Se acerca el 18, con ello<br>actividades recreativas<br>¡Pasalo chancho!';
                mainCardText.dataset.avisoId = avisoParaPrincipal.id || '';
            }
            
            // Restaurar animación
            mainCard.style.opacity = '1';
            mainCard.style.transform = 'scale(1)';
        }, 400);
    }
}

// Función para obtener el siguiente aviso para el recuadro principal
function obtenerSiguienteAvisoParaPrincipal() {
    if (avisos.length === 0) return null;
    
    // Obtener el aviso en el índice actual del recuadro principal
    return avisos[mainCardRotationIndex % avisos.length];
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