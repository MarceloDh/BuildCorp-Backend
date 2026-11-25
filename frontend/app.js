"use strict";

const secciones = {
  obras: { titulo: "Obras", campos: [
    { clave: "nombre", nombre: "Nombre", max: 100, requerido: true },
    { clave: "direccion", nombre: "Dirección", max: 200, requerido: true },
  ] },
  bodegas: { titulo: "Bodegas", campos: [
    { clave: "nombre", nombre: "Nombre", max: 100, requerido: true },
    { clave: "obra", nombre: "Obra", relacion: "obras", requerido: true },
  ] },
  herramientas: { titulo: "Herramientas", campos: [
    { clave: "codigo", nombre: "Código", max: 30, requerido: true },
    { clave: "nombre", nombre: "Nombre", max: 120, requerido: true },
    { clave: "descripcion", nombre: "Descripción", tipo: "textarea" },
    { clave: "bodega", nombre: "Bodega", relacion: "bodegas", requerido: true },
    { clave: "horas_uso", nombre: "Horas de uso", lectura: true },
    { clave: "estado", nombre: "Estado", lectura: true },
  ] },
  mantenimientos: { titulo: "Mantenimientos", campos: [
    { clave: "activo", nombre: "Herramienta", relacion: "herramientas", requerido: true },
    { clave: "tarea", nombre: "Tarea", max: 150, requerido: true },
    { clave: "fecha_limite", nombre: "Fecha límite", tipo: "date", anulable: true },
    { clave: "horas_limite", nombre: "Umbral en horas", tipo: "number", anulable: true },
    { clave: "observaciones", nombre: "Observaciones", tipo: "textarea", max: 2000 },
    { clave: "estado", nombre: "Estado", lectura: true },
  ] },
};

const elemento = id => document.getElementById(id);
const nombresEstado = {
  disponible: "Disponible", reservado: "Reservado", en_uso: "En uso",
  mantenimiento: "En mantenimiento", baja: "Dada de baja", programado: "Programado",
  en_curso: "En curso", completado: "Completado", cancelado: "Cancelado",
};
let tokens;
let perfil;
let seccion = "herramientas";
let pagina = 1;
let editando;
let ocupado = false;

function texto(tag, valor) {
  const nodo = document.createElement(tag);
  nodo.textContent = valor;
  return nodo;
}

function boton(etiqueta, accion) {
  const nodo = texto("button", etiqueta);
  nodo.type = "button";
  nodo.addEventListener("click", () => { void procesar(accion); });
  return nodo;
}

function mensaje(texto, error = false) {
  elemento("estado").textContent = texto;
  elemento("estado").classList.toggle("error", error);
}

async function procesar(accion) {
  if (ocupado) return;
  ocupado = true;
  mensaje("");
  try {
    await accion();
  } catch (error) {
    mensaje(error.message, true);
  } finally {
    ocupado = false;
  }
}

async function solicitar(ruta, { metodo = "GET", datos, autenticado = true } = {}) {
  const headers = { Accept: "application/json" };
  if (datos !== undefined) headers["Content-Type"] = "application/json";
  if (autenticado) headers.Authorization = "Bearer " + tokens.access;
  const url = new URL(ruta, window.BUILDCORP_API);
  const opciones = { method: metodo, headers, body: JSON.stringify(datos) };
  let respuesta = await fetch(url, opciones);
  if (respuesta.status === 401 && autenticado) {
    try {
      const renovado = await solicitar("token/refresh/", {
        metodo: "POST", datos: { refresh: tokens.refresh }, autenticado: false,
      });
      tokens.access = renovado.access;
      headers.Authorization = "Bearer " + tokens.access;
      respuesta = await fetch(url, opciones);
    } catch (error) {
      if (error.status !== 401) throw error;
    }
    if (respuesta.status === 401) cerrarSesion();
  }
  const contenido = respuesta.status === 204 ? null : await respuesta.json().catch(() => null);
  if (!respuesta.ok) {
    const detalle = Array.isArray(contenido) ? contenido.join(" ") : Object.entries(contenido || {})
      .map(([campo, valor]) => (campo === "detail" ? valor : campo + " · " + valor)).join(" ");
    const error = new Error(detalle || "La API respondió HTTP " + respuesta.status + ".");
    error.status = respuesta.status;
    throw error;
  }
  return contenido;
}

function cerrarFormulario() {
  editando = null;
  elemento("panel-formulario").hidden = true;
  elemento("campos").replaceChildren();
}

function cerrarSesion() {
  tokens = undefined;
  perfil = undefined;
  elemento("login").reset();
  elemento("inventario").hidden = true;
  elemento("cuenta").hidden = true;
  elemento("acceso").hidden = false;
  elemento("filas").replaceChildren();
  elemento("descarga").hidden = true;
  elemento("descarga").removeAttribute("href");
  cerrarFormulario();
}

async function cargar(registroPagina = pagina, destino = seccion) {
  const datos = await solicitar(destino + "/?page=" + registroPagina);
  seccion = destino;
  pagina = registroPagina;
  const { titulo, campos } = secciones[seccion];
  elemento("titulo").textContent = titulo;
  elemento("nuevo").hidden = !perfil.puede_editar;
  for (const item of elemento("navegacion").children) {
    if (item.dataset.seccion === seccion) item.setAttribute("aria-current", "page");
    else item.removeAttribute("aria-current");
  }
  const encabezado = document.createElement("tr");
  encabezado.append(texto("th", "ID"), ...campos.map(campo => texto("th", campo.nombre)));
  if (perfil.puede_editar) encabezado.append(texto("th", "Acciones"));
  elemento("columnas").replaceChildren(encabezado);

  const filas = datos.results.map(registro => {
    const fila = document.createElement("tr");
    fila.append(texto("td", registro.id), ...campos.map(campo => texto(
      "td", campo.clave === "estado" ? nombresEstado[registro.estado] || registro.estado : registro[campo.clave] ?? "—",
    )));
    if (perfil.puede_editar) {
      const celda = document.createElement("td");
      if (seccion !== "mantenimientos" || registro.estado === "programado") {
        const acciones = document.createElement("div");
        acciones.className = "acciones";
        acciones.append(
          boton("Editar", () => abrirFormulario(registro)),
          boton("Eliminar", () => eliminar(registro)),
        );
        celda.append(acciones);
      }
      fila.append(celda);
    }
    return fila;
  });
  if (!filas.length) {
    const fila = document.createElement("tr");
    const celda = texto("td", "Aún no hay registros.");
    celda.colSpan = encabezado.children.length;
    fila.append(celda);
    filas.push(fila);
  }
  elemento("filas").replaceChildren(...filas);
  elemento("anterior").disabled = !datos.previous;
  elemento("siguiente").disabled = !datos.next;
  elemento("pagina").textContent = "Página " + pagina + " · " + datos.count + " registros";
  return datos;
}

async function abrirFormulario(registro = null) {
  cerrarFormulario();
  const controles = [];
  for (const campo of secciones[seccion].campos) {
    if (campo.lectura || (registro && campo.relacion)) continue;
    const etiqueta = document.createElement("label");
    const titulo = texto("span", campo.nombre);
    titulo.id = "etiqueta-" + campo.clave;
    const control = document.createElement(campo.relacion ? "select" : campo.tipo === "textarea" ? "textarea" : "input");
    control.name = campo.clave;
    control.setAttribute("aria-labelledby", titulo.id);
    control.required = Boolean(campo.requerido);
    if (control.tagName === "INPUT") control.type = campo.tipo || "text";
    if (campo.max) control.maxLength = campo.max;
    if (campo.tipo === "number") {
      control.min = "1";
      control.max = "1000000";
    }
    if (campo.relacion) {
      control.append(new Option("Selecciona " + campo.nombre.toLowerCase(), ""));
      let numero = 1;
      let datos;
      do {
        datos = await solicitar(campo.relacion + "/?page=" + numero++);
        for (const opcion of datos.results) {
          const titulo = opcion.codigo ? opcion.codigo + " · " + opcion.nombre : opcion.nombre;
          control.append(new Option(titulo + " (#" + opcion.id + ")", opcion.id));
        }
      } while (datos.next);
      if (control.options.length === 1) throw new Error("Crea primero un registro en " + secciones[campo.relacion].titulo + ".");
    }
    control.value = registro?.[campo.clave] ?? "";
    etiqueta.append(titulo, control);
    controles.push(etiqueta);
  }
  editando = registro;
  elemento("titulo-formulario").textContent = registro ? "Editar registro #" + registro.id : "Nuevo registro";
  elemento("campos").replaceChildren(...controles);
  elemento("panel-formulario").hidden = false;
  controles[0]?.lastElementChild.focus();
}

async function eliminar(registro) {
  if (!window.confirm("¿Eliminar el registro #" + registro.id + "?")) return;
  const unicaFila = elemento("filas").children.length === 1;
  await solicitar(seccion + "/" + registro.id + "/", { metodo: "DELETE" });
  cerrarFormulario();
  await cargar(unicaFila && pagina > 1 ? pagina - 1 : pagina);
  mensaje("Registro eliminado · HTTP 204.");
}

for (const [clave, datos] of Object.entries(secciones)) {
  const item = boton(datos.titulo, async () => {
    await cargar(1, clave);
    cerrarFormulario();
    elemento("titulo").focus();
  });
  item.dataset.seccion = clave;
  elemento("navegacion").append(item);
}

elemento("login").addEventListener("submit", evento => {
  evento.preventDefault();
  void procesar(async () => {
    const formulario = evento.currentTarget || elemento("login");
    const datos = Object.fromEntries(new FormData(formulario));
    try {
      tokens = await solicitar("token/", { metodo: "POST", datos, autenticado: false });
      perfil = await solicitar("perfil/");
      await cargar(1, "herramientas");
      formulario.reset();
      elemento("usuario").textContent = perfil.usuario + (perfil.puede_editar ? " · Supervisión" : " · Bodega");
      elemento("acceso").hidden = true;
      elemento("cuenta").hidden = false;
      elemento("inventario").hidden = false;
      elemento("titulo").focus();
    } catch (error) {
      cerrarSesion();
      throw error;
    }
  });
});

elemento("registro").addEventListener("submit", evento => {
  evento.preventDefault();
  void procesar(async () => {
    const datos = Object.fromEntries(new FormData(elemento("registro")));
    for (const campo of secciones[seccion].campos) {
      if (!(campo.clave in datos)) continue;
      const valor = datos[campo.clave];
      if (valor === "" && campo.anulable) datos[campo.clave] = null;
      else if (campo.tipo === "number" || campo.relacion) datos[campo.clave] = Number(valor);
    }
    const registro = editando;
    const guardado = await solicitar(seccion + "/" + (registro ? registro.id + "/" : ""), {
      metodo: registro ? "PATCH" : "POST", datos,
    });
    cerrarFormulario();
    await cargar(registro ? pagina : 1);
    mensaje((registro ? "Actualización guardada · HTTP 200." : "Registro creado · HTTP 201.") + " ID " + guardado.id + ".");
  });
});

elemento("salir").addEventListener("click", () => procesar(cerrarSesion));
elemento("nuevo").addEventListener("click", () => procesar(() => abrirFormulario()));
elemento("cancelar").addEventListener("click", cerrarFormulario);
elemento("anterior").addEventListener("click", () => procesar(async () => { await cargar(pagina - 1); cerrarFormulario(); }));
elemento("siguiente").addEventListener("click", () => procesar(async () => { await cargar(pagina + 1); cerrarFormulario(); }));
elemento("guia").addEventListener("click", () => procesar(async () => {
  const enlace = elemento("descarga");
  enlace.hidden = true;
  enlace.removeAttribute("href");
  const recurso = await solicitar("recursos/guia/");
  const url = new URL(recurso.url);
  if (url.protocol !== "https:") throw new Error("La descarga requiere HTTPS.");
  enlace.href = url;
  enlace.hidden = false;
  mensaje("Descarga disponible durante " + recurso.vence_en_segundos + " segundos.");
}));
