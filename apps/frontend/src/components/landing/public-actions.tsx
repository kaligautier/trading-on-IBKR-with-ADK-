import Link from "next/link"

export function PublicActions() {
  return (
    <div className="flex flex-wrap items-center gap-4">
      <Link href="/#market-scanner" className="inline-flex min-h-11 items-center rounded-full bg-on-surface px-6 text-sm font-medium text-surface-lowest transition-colors hover:bg-on-surface/80">
        Consulter le scanner
      </Link>
      <Link href="/docs" className="inline-flex min-h-11 items-center text-sm underline underline-offset-4">
        Lire la documentation
      </Link>
    </div>
  )
}
