"use strict";

const secciones = {
  obras: {
    titulo: "Obras",
    descripcion: "Proyectos activos de construcción con nombre único.",
    editable: true,
    campos: [
      { clave: "nombre", nombre: "Nombre", max: 100, requerido: true },
      { clave: "direccion", nombre: "Dirección", max: 200, requerido: true },
    ],
  },
  bodegas: {
    titulo: "Bodegas",
    descripcion: "Recintos de almacenamiento asociados a cada obra.",
    editable: true,
    campos: [
      { clave: "nombre", nombre: "Nombre", max: 100, requerido: true },
      { clave: "obra", nombre: "Obra", relacion: "obras", requerido: true },
    ],
  },
  herramientas: {
    titulo: "Herramientas",
    descripcion: "Inventario de equipos y maquinaria asignados por bodega.",
    editable: true,
    campos: [
      { clave: "codigo", nombre: "Código", max: 30, requerido: true },
      { clave: "nombre", nombre: "Nombre", max: 120, requerido: true },
      { clave: "descripcion", nombre: "Descripción", tipo: "textarea" },
      { clave: "bodega", nombre: "Bodega", relacion: "bodegas", requerido: true },
      { clave: "horas_uso", nombre: "Horas de uso", lectura: true },
      { clave: "estado", nombre: "Estado", lectura: true },
    ],
  },
  clientes: {
    titulo: "Clientes",
    descripcion: "Contratistas y empresas habilitadas para arriendo o préstamo de herramientas.",
    editable: true,
    campos: [
      { clave: "nombre", nombre: "Nombre / Razón social", max: 120, requerido: true },
      { clave: "identificador", nombre: "RUT o identificador", max: 30, requerido: true },
      { clave: "contacto", nombre: "Correo de contacto", tipo: "email" },
      { clave: "telefono", nombre: "Teléfono", max: 25 },
      { clave: "direccion", nombre: "Dirección", max: 200 },
      { clave: "comuna", nombre: "Comuna", max: 80 },
      { clave: "region", nombre: "Región", max: 80 },
    ],
  },
  prestamos: {
    titulo: "Préstamos",
    descripcion: "Asignación y entrega de herramientas a clientes con control de devolución.",
    soloCrear: true,
    campos: [
      { clave: "activo", nombre: "Herramienta", relacion: "herramientas", requerido: true },
      { clave: "contratista", nombre: "Cliente", relacion: "clientes", requerido: true },
      { clave: "bodega", nombre: "Bodega origen", relacion: "bodegas", lectura: true },
      { clave: "vence_en", nombre: "Devolver antes de", tipo: "datetime-local", requerido: true },
      { clave: "responsable_entrega", nombre: "Responsable entrega", max: 120, requerido: true },
      { clave: "firma_entrega", nombre: "Firma entrega", max: 200, requerido: true, ocultarTabla: true },
      { clave: "horas_utilizadas", nombre: "Horas usadas", lectura: true },
      { clave: "estado_visible", nombre: "Estado", lectura: true },
    ],
  },
  traslados: {
    titulo: "Traslados",
    descripcion: "Movimiento auditado de herramientas disponibles entre bodegas.",
    soloCrear: true,
    campos: [
      { clave: "activo", nombre: "Herramienta", relacion: "herramientas", requerido: true },
      { clave: "origen", nombre: "Bodega origen", relacion: "bodegas", lectura: true },
      { clave: "destino", nombre: "Bodega destino", relacion: "bodegas", requerido: true },
      { clave: "registrado_en", nombre: "Fecha", lectura: true },
    ],
  },
  mantenimientos: {
    titulo: "Mantenimientos",
    descripcion: "Inspecciones programadas por fecha límite o umbral de horas.",
    editable: true,
    campos: [
      { clave: "activo", nombre: "Herramienta", relacion: "herramientas", requerido: true },
      { clave: "tarea", nombre: "Tarea", max: 150, requerido: true },
      { clave: "fecha_limite", nombre: "Fecha límite", tipo: "date", anulable: true },
      { clave: "horas_limite", nombre: "Umbral en horas", tipo: "number", anulable: true },
      { clave: "observaciones", nombre: "Observaciones", tipo: "textarea", max: 2000 },
      { clave: "estado", nombre: "Estado", lectura: true },
    ],
  },
};

const elemento = id => document.getElementById(id);
const nombresEstado = {
  disponible: "Disponible", reservado: "Reservado", en_uso: "En uso",
  mantenimiento: "En mantenimiento", baja: "Dada de baja", programado: "Programado",
  en_curso: "En curso", completado: "Completado", cancelado: "Cancelado",
  Vigente: "Vigente", Vencido: "Vencido", Devuelto: "Devuelto",
};
let tokens;
let perfil;
let seccion = "herramientas";
let pagina = 1;
let editando;
let devolviendo;
let ocupado = false;
let registrosActuales = [];
let mapasRelacion = { obras: new Map(), bodegas: new Map(), herramientas: new Map(), clientes: new Map() };

function texto(tag, valor, clase = "") {
  const nodo = document.createElement(tag);
  nodo.textContent = valor;
  if (clase) nodo.className = clase;
  return nodo;
}

function boton(etiqueta, accion, clase = "") {
  const nodo = texto("button", etiqueta, clase);
  nodo.type = "button";
  nodo.addEventListener("click", () => { void procesar(accion); });
  return nodo;
}

function mensaje(contenido, error = false) {
  elemento("estado").textContent = contenido;
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

function etiquetaRegistro(opcion) {
  if (opcion.codigo) return opcion.codigo + " · " + opcion.nombre;
  if (opcion.identificador) return opcion.nombre + " (" + opcion.identificador + ")";
  return opcion.nombre;
}

async function listarTodo(nombreSeccion) {
  const lista = [];
  let numero = 1;
  let datos;
  do {
    datos = await solicitar(nombreSeccion + "/?page=" + numero++);
    lista.push(...datos.results);
  } while (datos.next);
  return { total: datos.count, items: lista };
}

async function actualizarResumenYMapas() {
  const tarjetas = [];
  const nuevosMapas = { obras: new Map(), bodegas: new Map(), herramientas: new Map(), clientes: new Map() };
  const resultados = await Promise.all(
    Object.keys(secciones).map(async clave => [clave, await listarTodo(clave)]),
  );
  for (const [clave, info] of resultados) {
    if (clave in nuevosMapas) {
      for (const item of info.items) {
        nuevosMapas[clave].set(item.id, etiquetaRegistro(item));
      }
    }
    const card = boton("", async () => {
      elemento("filtro").value = "";
      await cargar(1, clave);
      cerrarFormulario();
      elemento("titulo").focus();
    }, "tarjeta");
    card.append(
      texto("span", secciones[clave].titulo, "tarjeta-etiqueta"),
      texto("span", String(info.total), "tarjeta-valor"),
    );
    tarjetas.push(card);
  }
  mapasRelacion = nuevosMapas;
  elemento("resumen").replaceChildren(...tarjetas);
}

function valorCelda(campo, registro) {
  const bruto = registro[campo.clave];
  if (campo.relacion && bruto != null) {
    const etiqueta = mapasRelacion[campo.relacion]?.get(bruto);
    return etiqueta ? etiqueta + " (#" + bruto + ")" : "#" + bruto;
  }
  if (campo.clave === "estado" || campo.clave === "estado_visible") {
    return nombresEstado[bruto] || bruto || "—";
  }
  if ((campo.clave === "vence_en" || campo.clave === "registrado_en") && bruto) {
    return String(bruto).slice(0, 16).replace("T", " ");
  }
  if (bruto === null || bruto === undefined || bruto === "") return "—";
  return String(bruto);
}

function renderizarFilas() {
  const cfg = secciones[seccion];
  const camposVisibles = cfg.campos.filter(c => !c.ocultarTabla);
  const termino = elemento("filtro").value.trim().toLowerCase();
  const filtrados = termino
    ? registrosActuales.filter(registro => {
        const textoFila = [
          String(registro.id),
          ...camposVisibles.map(c => valorCelda(c, registro)),
        ].join(" ").toLowerCase();
        return textoFila.includes(termino);
      })
    : registrosActuales;

  const filas = filtrados.map(registro => {
    const fila = document.createElement("tr");
    fila.append(
      texto("td", registro.id),
      ...camposVisibles.map(campo => {
        const celda = document.createElement("td");
        const val = valorCelda(campo, registro);
        const claveEstado = campo.clave === "estado" || campo.clave === "estado_visible" ? registro[campo.clave] : "";
        if (claveEstado) {
          celda.append(texto("span", val, "estado-pill estado-" + String(claveEstado).toLowerCase()));
        } else {
          celda.textContent = val;
        }
        return celda;
      }),
    );
    if (perfil.puede_editar && (cfg.editable || seccion === "prestamos")) {
      const celda = document.createElement("td");
      const acciones = document.createElement("div");
      acciones.className = "acciones";
      if (seccion === "prestamos" && !registro.devuelto_en) {
        acciones.append(boton("Registrar devolución", () => abrirDevolucion(registro), "principal"));
      } else if (cfg.editable && (seccion !== "mantenimientos" || registro.estado === "programado")) {
        acciones.append(
          boton("Editar", () => abrirFormulario(registro)),
          boton("Eliminar", () => eliminar(registro), "peligro"),
        );
      }
      if (acciones.children.length) celda.append(acciones);
      fila.append(celda);
    }
    return fila;
  });

  if (!filas.length) {
    const fila = document.createElement("tr");
    const celda = texto("td", termino ? "Sin coincidencias para el filtro actual." : "Aún no hay registros.");
    celda.colSpan = elemento("columnas").firstElementChild?.children.length || 1;
    fila.append(celda);
    filas.push(fila);
  }
  elemento("filas").replaceChildren(...filas);
}

function cerrarFormulario() {
  editando = null;
  devolviendo = null;
  elemento("panel-formulario").hidden = true;
  elemento("campos").replaceChildren();
}

function cerrarSesion() {
  tokens = undefined;
  perfil = undefined;
  registrosActuales = [];
  mapasRelacion = { obras: new Map(), bodegas: new Map(), herramientas: new Map(), clientes: new Map() };
  elemento("login").reset();
  elemento("filtro").value = "";
  elemento("resumen").replaceChildren();
  elemento("inventario").hidden = true;
  elemento("cuenta").hidden = true;
  elemento("acceso").hidden = false;
  elemento("filas").replaceChildren();
  elemento("descarga").hidden = true;
  elemento("descarga").removeAttribute("href");
  cerrarFormulario();
}

async function cargar(registroPagina = pagina, destino = seccion) {
  const [datos] = await Promise.all([
    solicitar(destino + "/?page=" + registroPagina),
    actualizarResumenYMapas(),
  ]);
  seccion = destino;
  pagina = registroPagina;
  registrosActuales = datos.results;
  const cfg = secciones[seccion];
  const camposVisibles = cfg.campos.filter(c => !c.ocultarTabla);
  elemento("titulo").textContent = cfg.titulo;
  elemento("subtitulo").textContent =
    cfg.descripcion + (perfil.puede_editar ? " · Permiso: Supervisión (lectura y escritura)." : " · Permiso: Bodega (solo consulta).");
  elemento("nuevo").hidden = !perfil.puede_editar;
  for (const item of elemento("navegacion").children) {
    if (item.dataset.seccion === seccion) item.setAttribute("aria-current", "page");
    else item.removeAttribute("aria-current");
  }
  const encabezado = document.createElement("tr");
  encabezado.append(texto("th", "ID"), ...camposVisibles.map(campo => texto("th", campo.nombre)));
  if (perfil.puede_editar && (cfg.editable || seccion === "prestamos")) encabezado.append(texto("th", "Acciones"));
  elemento("columnas").replaceChildren(encabezado);

  renderizarFilas();
  elemento("anterior").disabled = !datos.previous;
  elemento("siguiente").disabled = !datos.next;
  elemento("pagina").textContent = "Página " + pagina + " · " + datos.count + " registros";
  return datos;
}

function abrirDevolucion(prestamo) {
  cerrarFormulario();
  devolviendo = prestamo;
  const camposDev = [
    { clave: "horas_utilizadas", nombre: "Horas utilizadas", tipo: "number", min: "0", max: "100000", requerido: true },
    { clave: "responsable_devolucion", nombre: "Responsable devolución", max: 120, requerido: true },
    { clave: "firma_devolucion", nombre: "Firma devolución", max: 200, requerido: true },
  ];
  const controles = camposDev.map(campo => {
    const etiqueta = document.createElement("label");
    const titulo = texto("span", campo.nombre);
    const control = document.createElement("input");
    control.name = campo.clave;
    control.type = campo.tipo || "text";
    control.required = Boolean(campo.requerido);
    if (campo.min !== undefined) control.min = campo.min;
    if (campo.max !== undefined) {
      if (control.type === "number") control.max = campo.max;
      else control.maxLength = campo.max;
    }
    etiqueta.append(titulo, control);
    return etiqueta;
  });
  elemento("titulo-formulario").textContent = "Registrar devolución · Préstamo #" + prestamo.id;
  elemento("campos").replaceChildren(...controles);
  elemento("panel-formulario").hidden = false;
  controles[0]?.lastElementChild.focus();
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
      const { items } = await listarTodo(campo.relacion);
      for (const opcion of items) {
        control.append(new Option(etiquetaRegistro(opcion) + " (#" + opcion.id + ")", opcion.id));
      }
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
  const unicaFila = registrosActuales.length === 1;
  await solicitar(seccion + "/" + registro.id + "/", { metodo: "DELETE" });
  cerrarFormulario();
  await cargar(unicaFila && pagina > 1 ? pagina - 1 : pagina);
  mensaje("Registro eliminado · HTTP 204.");
}

for (const [clave, datos] of Object.entries(secciones)) {
  const item = boton(datos.titulo, async () => {
    elemento("filtro").value = "";
    await cargar(1, clave);
    cerrarFormulario();
    elemento("titulo").focus();
  });
  item.dataset.seccion = clave;
  elemento("navegacion").append(item);
}

elemento("filtro").addEventListener("input", renderizarFilas);

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
    if (devolviendo) {
      datos.horas_utilizadas = Number(datos.horas_utilizadas);
      const idPrestamo = devolviendo.id;
      await solicitar("prestamos/" + idPrestamo + "/devolver/", { metodo: "POST", datos });
      cerrarFormulario();
      await cargar(pagina);
      mensaje("Devolución registrada · Préstamo #" + idPrestamo + ".");
      return;
    }
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
elemento("actualizar").addEventListener("click", () => procesar(() => cargar(pagina)));
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
