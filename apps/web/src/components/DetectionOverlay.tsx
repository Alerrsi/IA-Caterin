/** Foto con las cajas detectadas encima (coordenadas normalizadas 0 a 1: x1, y1, x2, y2). */
export function DetectionOverlay({
  src,
  alt,
  boxes,
}: {
  src: string
  alt: string
  boxes: { vision_class: string; box: [number, number, number, number] }[]
}) {
  return (
    <div className="relative w-full overflow-hidden rounded-xl bg-surface-container-highest">
      <img src={src} alt={alt} className="block h-auto w-full" />
      {boxes.map((d, i) => {
        const [x1, y1, x2, y2] = d.box
        return (
          <div
            key={i}
            aria-hidden="true"
            className="absolute rounded border-2 border-primary bg-primary/10"
            style={{
              left: `${x1 * 100}%`,
              top: `${y1 * 100}%`,
              width: `${Math.max(0, x2 - x1) * 100}%`,
              height: `${Math.max(0, y2 - y1) * 100}%`,
            }}
          />
        )
      })}
    </div>
  )
}
