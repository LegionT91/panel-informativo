function actualizarHoraFecha() {
    const ahora = new Date();
    // Hora
    let horas = ahora.getHours();
    const minutos = ahora.getMinutes().toString().padStart(2, '0');
    const ampm = horas >= 12 ? 'PM' : 'AM';
    horas = horas % 12;
    horas = horas ? horas : 12;
    document.getElementById('hora-actual').textContent = `${horas}:${minutos} ${ampm}`;
    // Fecha
    const dia = ahora.getDate().toString().padStart(2, '0');
    const mes = (ahora.getMonth() + 1).toString().padStart(2, '0');
    const anio = ahora.getFullYear();
    document.getElementById('fecha-actual').textContent = `${dia}/${mes}/${anio}`;
}
actualizarHoraFecha();
setInterval(actualizarHoraFecha, 1000);