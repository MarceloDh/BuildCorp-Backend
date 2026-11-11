const preferenciaMovimiento = window.matchMedia("(prefers-reduced-motion: reduce)");
const mascotas = Array.from(document.querySelectorAll("[data-mascota]"));

function cambiarAnimacion(mascota, animar) {
  const imagen = mascota.querySelector("img");
  const boton = mascota.querySelector("[data-animar]");
  imagen.src = animar ? imagen.dataset.gif : imagen.dataset.estatica;
  boton.textContent = animar ? "Pausar animación" : "Animar mascota";
  boton.setAttribute("aria-pressed", String(animar));
}

for (const mascota of mascotas) {
  const boton = mascota.querySelector("[data-animar]");
  boton.hidden = false;
  cambiarAnimacion(mascota, !preferenciaMovimiento.matches);
  boton.addEventListener("click", () => {
    cambiarAnimacion(mascota, boton.getAttribute("aria-pressed") !== "true");
  });
}
preferenciaMovimiento.addEventListener("change", (evento) => {
  if (evento.matches) mascotas.forEach(mascota => cambiarAnimacion(mascota, false));
});
