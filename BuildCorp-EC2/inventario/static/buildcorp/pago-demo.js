const cantidad = document.querySelector("#id_cantidad");
const total = document.querySelector("#total-demo");
const pasos = document.querySelectorAll("[data-paso]");
const pesos = new Intl.NumberFormat("es-CL", {
  style: "currency",
  currency: "CLP",
  maximumFractionDigits: 0,
});

function actualizarTotal() {
  total.value = cantidad.validity.valid && cantidad.value
    ? pesos.format(cantidad.valueAsNumber * Number(total.dataset.tarifa))
    : "—";
  const valor = cantidad.valueAsNumber;
  for (const boton of pasos) {
    boton.disabled = Number(boton.dataset.paso) < 0
      ? valor <= Number(cantidad.min)
      : valor >= Number(cantidad.max);
  }
}

for (const boton of pasos) {
  boton.hidden = false;
  boton.addEventListener("click", () => {
    cantidad.stepUp(Number(boton.dataset.paso));
    actualizarTotal();
    if (boton.disabled) cantidad.focus();
  });
}
cantidad.addEventListener("input", actualizarTotal);
actualizarTotal();
const tipoDocumento = document.querySelector("#id_tipo_documento");
const facturacion = document.querySelector("[data-facturacion]");
function actualizarFacturacion() {
  const requiereFactura = tipoDocumento.value === "factura";
  facturacion.hidden = !requiereFactura;
  for (const campo of facturacion.querySelectorAll("input")) campo.required = requiereFactura;
}
tipoDocumento.addEventListener("change", actualizarFacturacion);
actualizarFacturacion();

const formularioPago = document.querySelector("form.pago-layout");
const confirmarPago = formularioPago.querySelector('button[type="submit"]');
if (confirmarPago) {
  const textoConfirmar = confirmarPago.textContent;
  formularioPago.addEventListener("submit", () => {
    confirmarPago.disabled = true;
    confirmarPago.textContent = "Procesando pago…";
  });
  window.addEventListener("pageshow", () => {
    confirmarPago.disabled = false;
    confirmarPago.textContent = textoConfirmar;
  });
}
