import { Compass } from 'lucide-react'
import { Link } from 'react-router-dom'
import { EmptyState } from '@/components/EmptyState'
import { Button } from '@/components/ui/button'

export default function NotFoundPage() {
  return (
    <EmptyState
      icon={<Compass />}
      title="Página no encontrada"
      description="La dirección que buscas no existe o fue movida."
      action={
        <Button asChild>
          <Link to="/">Ver eventos</Link>
        </Button>
      }
    />
  )
}
