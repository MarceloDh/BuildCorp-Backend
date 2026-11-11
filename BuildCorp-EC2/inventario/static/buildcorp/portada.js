const carrusel = document.querySelector("[data-carrusel]");
const laminas = Array.from(carrusel.querySelectorAll("[data-lamina]"));
const controles = carrusel.querySelector("[data-controles]");
const pausa = carrusel.querySelector("[data-pausa]");
const posicion = carrusel.querySelector("[data-posicion]");
const anuncio = carrusel.querySelector("[data-anuncio]");
const movimientoReducido = window.matchMedia("(prefers-reduced-motion: reduce)");
let actual = 0;
let reproduciendo = !movimientoReducido.matches;
let punteroDentro = false;
let temporizador;

function mostrar(indice, anunciar = false) {
  actual = (indice + laminas.length) % laminas.length;
  laminas.forEach((lamina, i) => {
    const activa = i === actual;
    lamina.inert = !activa;
    lamina.setAttribute("aria-hidden", String(!activa));
    lamina.hidden = false;
  });
  posicion.textContent = `${actual + 1} de ${laminas.length}`;
  if (anunciar) {
    const titulo = laminas[actual].querySelector("h1, h2").textContent;
    anuncio.textContent = `Banner ${posicion.textContent}. ${titulo}`;
  }
}

function programar() {
  window.clearTimeout(temporizador);
  pausa.textContent = reproduciendo ? "Pausar" : "Reanudar";
  if (reproduciendo && !punteroDentro && !document.hidden) {
    temporizador = window.setTimeout(() => {
      mostrar(actual + 1);
      programar();
    }, 7000);
  }
}

function cambiar(paso) {
  reproduciendo = false;
  mostrar(actual + paso, true);
  programar();
}

carrusel.querySelector("[data-anterior]").addEventListener("click", () => cambiar(-1));
carrusel.querySelector("[data-siguiente]").addEventListener("click", () => cambiar(1));
pausa.addEventListener("click", () => {
  reproduciendo = !reproduciendo;
  programar();
});
carrusel.addEventListener("pointerenter", (evento) => {
  if (evento.pointerType !== "mouse") return;
  punteroDentro = true;
  programar();
});
carrusel.addEventListener("pointerleave", (evento) => {
  if (evento.pointerType !== "mouse") return;
  punteroDentro = false;
  programar();
});
carrusel.addEventListener("focusin", (evento) => {
  if (carrusel.contains(evento.relatedTarget) || !evento.target.matches(":focus-visible")) return;
  reproduciendo = false;
  programar();
});
movimientoReducido.addEventListener("change", (evento) => {
  if (evento.matches) reproduciendo = false;
  programar();
});
document.addEventListener("visibilitychange", programar);

mostrar(0);
controles.hidden = false;
programar();
