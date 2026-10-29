import styles from "./nav-section.module.css"

const NAV_ITEMS = [
  { href: "#market-scanner", label: "Market Scanner" },
  { href: "#momentum-mcp", label: "Momentum" },
  { href: "#deep-copy", label: "Experimental trading" },
  { href: "#engineering", label: "Engineering" },
  { href: "#partners", label: "Ecosystem" },
  { href: "#tech", label: "Technology" },
  { href: "/docs", label: "Documentation" },
]

export function NavSection({ sectionPath = "" }: { sectionPath?: string }) {
  return (
    <nav aria-label="Main navigation" className={styles.navigation}>
      <ul className={styles.links}>
        {NAV_ITEMS.map((item) => (
          <li key={item.href}>
            <a href={item.href.startsWith("#") ? `${sectionPath}${item.href}` : item.href}>{item.label}</a>
          </li>
        ))}
      </ul>
    </nav>
  )
}
