/**
 * Cuentas de la demo grande (`app/db/demo_full.py`, Banquetería Volcán Llaima) para el acceso rápido del login.
 * Son datos ficticios con la contraseña pública del seed; no hay cuentas reales aquí.
 *
 * Se muestran en desarrollo (`vite dev`) o en un build hecho con `VITE_DEMO_LOGIN=true`. En un build de producción sin
 * esa variable no aparecen. Si el seed se corrió con otra `SEED_DEMO_PASSWORD`, se indica con `VITE_DEMO_PASSWORD`.
 */
/** Solo la dueña y un cliente del portal: las dos caras de la demo (pedido del usuario, 17-nov-2026). */
export type DemoUserKey = 'owner' | 'customer'

export const DEMO_USERS: { key: DemoUserKey; email: string }[] = [
  { key: 'owner', email: 'duena.llaima@demo.local' },
  { key: 'customer', email: 'cliente1.llaima@demo.local' },
]

export const DEMO_PASSWORD: string = import.meta.env.VITE_DEMO_PASSWORD || 'caterin-demo-2026'

export const demoLoginEnabled: boolean = import.meta.env.DEV || import.meta.env.VITE_DEMO_LOGIN === 'true'
