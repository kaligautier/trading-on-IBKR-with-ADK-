"use client"

import { useState, useEffect, useRef } from "react"
import Link from "next/link"
import { Menu, X } from "lucide-react"

const PRODUCT_ITEMS = [
  { href: "#market-scanner", label: "Market Scanner", mobileLabel: "Voir le marché" },
  { href: "#momentum-mcp", label: "Momentum MCP", mobileLabel: "Connecter ses agents" },
  { href: "#deep-copy", label: "Deep Copy", mobileLabel: "Piloter un portefeuille" },
]

const NAV_ITEMS = [{ href: "#security", label: "Sécurité" }]

const RESOURCE_ITEMS = [
  { href: "/docs", label: "Documentation" },
]

export function NavSection() {
  const [scrolled, setScrolled] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const menuTriggerRef = useRef<HTMLButtonElement>(null)
  const mobileNavigationRef = useRef<HTMLDivElement>(null)
  const wasMobileOpen = useRef(false)

  function handleMobileNavigationKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    if (event.key !== "Tab") return

    const menuItems = Array.from(
      mobileNavigationRef.current?.querySelectorAll<HTMLElement>("[data-mobile-menu-item]") ?? [],
    )
    const firstMenuItem = menuItems[0]
    const lastMenuItem = menuItems.at(-1)
    const activeElement = document.activeElement

    if (!firstMenuItem || !lastMenuItem) return
    if (event.shiftKey && activeElement === firstMenuItem) {
      event.preventDefault()
      lastMenuItem.focus()
      return
    }
    if (!event.shiftKey && activeElement === lastMenuItem) {
      event.preventDefault()
      firstMenuItem.focus()
    }
  }

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20)
    window.addEventListener("scroll", onScroll, { passive: true })
    return () => window.removeEventListener("scroll", onScroll)
  }, [])

  useEffect(() => {
    if (!mobileOpen) {
      if (wasMobileOpen.current) menuTriggerRef.current?.focus()
      wasMobileOpen.current = false
      return
    }

    wasMobileOpen.current = true
    mobileNavigationRef.current?.querySelector<HTMLElement>("[data-mobile-menu-item]")?.focus()

    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return

      setMobileOpen(false)
    }

    window.addEventListener("keydown", closeOnEscape)
    return () => window.removeEventListener("keydown", closeOnEscape)
  }, [mobileOpen])

  return (
    <nav aria-label="Navigation principale" className={`fixed top-0 z-50 w-full transition-all duration-300 ${scrolled || mobileOpen ? "border-b border-outline-variant bg-surface/95 backdrop-blur-xl" : "bg-transparent"}`}>
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-3 px-4 sm:px-6">
        <a href="#" className="flex min-h-11 min-w-11 shrink-0 items-center gap-2" aria-label="Deep Copy — revenir en haut">
          <div className="w-7 h-7 rounded-lg bg-on-surface flex items-center justify-center font-bold text-xs text-surface-lowest">
            DC
          </div>
          <span className="hidden text-sm font-semibold tracking-tight min-[380px]:inline">Deep Copy</span>
        </a>

        <div className="hidden items-center gap-5 text-sm text-on-surface-variant xl:flex">
          <div className="flex items-center gap-3" aria-label="Produits">
            <a href="#products" className="inline-flex min-h-11 items-center font-medium text-on-surface whitespace-nowrap transition-colors hover:text-primary-dim">
              Produits
            </a>
            <span className="h-4 w-px bg-outline-variant" aria-hidden="true" />
            {PRODUCT_ITEMS.map((item) => (
              <a
                key={item.href}
                href={item.href}
                className="inline-flex min-h-11 items-center whitespace-nowrap transition-colors hover:text-on-surface"
              >
                {item.label}
              </a>
            ))}
          </div>
          {NAV_ITEMS.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="inline-flex min-h-11 items-center whitespace-nowrap transition-colors hover:text-on-surface"
            >
              {item.label}
            </a>
          ))}
        </div>

        <div className="hidden items-center xl:flex">
          <Link
            href="/docs"
            prefetch={false}
            className="flex min-h-11 items-center gap-1.5 rounded-full bg-on-surface px-4 text-xs font-medium text-surface-lowest transition-colors hover:bg-on-surface/80"
          >
            <div className="h-1.5 w-1.5 rounded-full bg-primary-container" />
            Documentation
          </Link>
        </div>

        <div className="flex items-center gap-1.5 xl:hidden">
          <Link
            href="/docs"
            prefetch={false}
            className="inline-flex min-h-11 items-center rounded-full bg-on-surface px-3.5 text-xs font-medium text-surface-lowest transition-colors hover:bg-on-surface/80 sm:px-4"
          >
            Documentation
          </Link>
          <button
            ref={menuTriggerRef}
            type="button"
            aria-expanded={mobileOpen}
            aria-controls="mobile-navigation"
            aria-label={mobileOpen ? "Fermer le menu" : "Ouvrir le menu"}
            onClick={() => setMobileOpen((open) => !open)}
            className="inline-flex h-11 w-11 items-center justify-center rounded-full text-on-surface transition-colors hover:bg-surface-low"
          >
            {mobileOpen ? <X className="h-5 w-5" aria-hidden="true" /> : <Menu className="h-5 w-5" aria-hidden="true" />}
          </button>
        </div>
      </div>

      {mobileOpen && (
        <div
          ref={mobileNavigationRef}
          id="mobile-navigation"
          onKeyDown={handleMobileNavigationKeyDown}
          className="max-h-[calc(100dvh-4rem)] overflow-y-auto overscroll-contain border-t border-outline-variant bg-surface px-4 pb-5 pt-3 sm:px-6 xl:hidden"
        >
          <div className="mx-auto grid max-w-6xl gap-1 sm:grid-cols-2">
            <a
              href="#products"
              data-mobile-menu-item
              onClick={() => setMobileOpen(false)}
              className="flex min-h-12 items-center rounded-xl px-3 text-sm font-semibold text-on-surface transition-colors hover:bg-surface-low"
            >
              Produits
            </a>
            {PRODUCT_ITEMS.map((item) => (
              <a
                key={item.href}
                href={item.href}
                data-mobile-menu-item
                onClick={() => setMobileOpen(false)}
                className="flex min-h-12 items-center rounded-xl px-3 text-sm font-medium text-on-surface-variant transition-colors hover:bg-surface-low hover:text-on-surface"
              >
                <span className="flex flex-col">
                  <span>{item.mobileLabel}</span>
                  <span className="text-xs font-normal text-on-surface-muted">{item.label}</span>
                </span>
              </a>
            ))}
            {NAV_ITEMS.map((item) => (
              <a
                key={item.href}
                href={item.href}
                data-mobile-menu-item
                onClick={() => setMobileOpen(false)}
                className="flex min-h-12 items-center rounded-xl px-3 text-sm font-medium text-on-surface-variant transition-colors hover:bg-surface-low hover:text-on-surface"
              >
                {item.label}
              </a>
            ))}
            {RESOURCE_ITEMS.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                data-mobile-menu-item
                onClick={() => setMobileOpen(false)}
                className="flex min-h-12 items-center rounded-xl px-3 text-sm font-medium text-on-surface-variant transition-colors hover:bg-surface-low hover:text-on-surface"
              >
                {item.label}
              </Link>
            ))}
          </div>
        </div>
      )}
    </nav>
  )
}
