const canvas = document.querySelector("#firma");
const input = document.querySelector("#id_firma");
const ctx = canvas.getContext("2d");
ctx.strokeStyle = "#243047";
ctx.lineWidth = 3;
ctx.lineCap = "round";
let puntero = null;

function punto(event) {
  const rect = canvas.getBoundingClientRect();
  return [
    (event.clientX - rect.left) * canvas.width / rect.width,
    (event.clientY - rect.top) * canvas.height / rect.height,
  ];
}

if (input.value.startsWith("data:image/png;base64,")) {
  const imagen = new Image();
  imagen.addEventListener("load", () => {
    if (input.value === imagen.src && puntero === null) ctx.drawImage(imagen, 0, 0);
  });
  imagen.src = input.value;
}

canvas.addEventListener("pointerdown", (event) => {
  if (puntero !== null || event.button !== 0) return;
  puntero = event.pointerId;
  canvas.setPointerCapture(puntero);
  ctx.beginPath();
  ctx.moveTo(...punto(event));
});

canvas.addEventListener("pointermove", (event) => {
  if (event.pointerId !== puntero) return;
  ctx.lineTo(...punto(event));
  ctx.stroke();
  input.value = canvas.toDataURL("image/png");
});

for (const nombre of ["pointerup", "pointercancel", "lostpointercapture"]) {
  canvas.addEventListener(nombre, (event) => {
    if (event.pointerId === puntero) puntero = null;
  });
}

document.querySelector("#borrar-firma").addEventListener("click", () => {
  puntero = null;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  input.value = "";
});
