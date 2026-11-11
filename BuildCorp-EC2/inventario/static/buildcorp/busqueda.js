const buscador = document.querySelector("[data-sugerencias-url]");
const lista = document.querySelector("#sugerencias-catalogo");
const estadoBusqueda = document.querySelector("[data-busqueda-estado]");
let esperaBusqueda;
let peticionBusqueda;
let seleccionBusqueda = -1;
let enlacesBusqueda = [];

function cerrarSugerencias() {
  peticionBusqueda?.abort();
  window.clearTimeout(esperaBusqueda);
  lista.hidden = true;
  buscador.setAttribute("aria-expanded", "false");
  buscador.removeAttribute("aria-activedescendant");
  seleccionBusqueda = -1;
}

async function buscarSugerencias(consulta) {
  peticionBusqueda?.abort();
  const controlador = new AbortController();
  peticionBusqueda = controlador;
  try {
    const url = new URL(buscador.dataset.sugerenciasUrl, location.origin);
    url.searchParams.set("q", consulta);
    const respuesta = await fetch(url, {signal: controlador.signal});
    if (!respuesta.ok) return cerrarSugerencias();
    const datos = await respuesta.json();
    if (consulta !== buscador.value.trim() || document.activeElement !== buscador) return;
    lista.replaceChildren();
    enlacesBusqueda = [];
    for (const [indice, item] of datos.resultados.entries()) {
      const opcion = document.createElement("li");
      opcion.id = `sugerencia-${indice}`;
      opcion.setAttribute("role", "option");
      opcion.setAttribute("aria-selected", "false");
      const enlace = document.createElement("a");
      enlace.href = item.url;
      enlace.tabIndex = -1;
      const nombre = document.createElement("strong");
      nombre.textContent = item.nombre;
      const categoria = document.createElement("span");
      categoria.textContent = item.categoria;
      enlace.append(nombre, categoria);
      opcion.append(enlace);
      lista.append(opcion);
      enlacesBusqueda.push(enlace);
    }
    seleccionBusqueda = -1;
    buscador.removeAttribute("aria-activedescendant");
    lista.hidden = enlacesBusqueda.length === 0;
    buscador.setAttribute("aria-expanded", String(!lista.hidden));
    estadoBusqueda.textContent = enlacesBusqueda.length
      ? `${enlacesBusqueda.length} sugerencias. Usa las flechas para elegir.`
      : "Sin sugerencias. Pulsa Buscar para ver el catálogo.";
  } catch (error) {
    if (error.name !== "AbortError") cerrarSugerencias();
  }
}

buscador.addEventListener("input", () => {
  cerrarSugerencias();
  const consulta = buscador.value.trim();
  if (consulta.length >= 2) {
    esperaBusqueda = window.setTimeout(() => buscarSugerencias(consulta), 180);
  } else {
    estadoBusqueda.textContent = "";
  }
});
buscador.addEventListener("keydown", (evento) => {
  if (evento.key === "Escape") return cerrarSugerencias();
  if (lista.hidden) return;
  if (evento.key === "Enter" && seleccionBusqueda >= 0) {
    evento.preventDefault();
    enlacesBusqueda[seleccionBusqueda].click();
  }
  if (!["ArrowDown", "ArrowUp"].includes(evento.key)) return;
  evento.preventDefault();
  const paso = evento.key === "ArrowDown" ? 1 : -1;
  seleccionBusqueda = (seleccionBusqueda + paso + enlacesBusqueda.length) % enlacesBusqueda.length;
  for (const [i, enlace] of enlacesBusqueda.entries()) {
    enlace.parentElement.setAttribute("aria-selected", String(i === seleccionBusqueda));
  }
  const opcion = enlacesBusqueda[seleccionBusqueda].parentElement;
  buscador.setAttribute("aria-activedescendant", opcion.id);
  opcion.scrollIntoView({block: "nearest"});
});
buscador.closest("form").addEventListener("submit", cerrarSugerencias);
document.addEventListener("pointerdown", (evento) => {
  if (!buscador.closest("form").contains(evento.target)) cerrarSugerencias();
});
buscador.closest("form").addEventListener("focusout", (evento) => {
  if (!buscador.closest("form").contains(evento.relatedTarget)) cerrarSugerencias();
});
