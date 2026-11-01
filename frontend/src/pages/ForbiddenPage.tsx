import { ShieldAlert } from 'lucide-react'
import { Link } from 'react-router-dom'
import { EmptyState } from '@/components/EmptyState'
import { Button } from '@/components/ui/button'

export default function ForbiddenPage() {
  return (
    <EmptyState
      icon={<ShieldAlert />}
      title="No tienes acceso a esta sección"
      description="Tu rol no tiene permiso para ver esta página."
      action={
        <Button asChild>
          <Link to="/">Volver al inicio</Link>
        </Button>
      }
    />
  )
}
