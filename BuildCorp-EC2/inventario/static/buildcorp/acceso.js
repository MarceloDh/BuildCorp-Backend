const botonClave = document.querySelector("[data-ver-clave]");
const clave = document.getElementById(botonClave.getAttribute("aria-controls"));

botonClave.hidden = false;
botonClave.addEventListener("click", () => {
  const mostrar = clave.type === "password";
  clave.type = mostrar ? "text" : "password";
  botonClave.textContent = mostrar ? "Ocultar" : "Mostrar";
});
