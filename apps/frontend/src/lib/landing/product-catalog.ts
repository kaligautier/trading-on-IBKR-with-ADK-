export type ProductIdentifier = "deep-copy" | "market-scanner" | "momentum-mcp"
export type ProductJourney = "Observer" | "Connecter" | "Orchestrer"

export class ProductOffering {
  constructor(
    readonly identifier: ProductIdentifier,
    readonly ordinal: string,
    readonly name: string,
    readonly journey: ProductJourney,
    readonly category: string,
    readonly headline: string,
    readonly description: string,
    readonly proof: string,
    readonly availability: string,
    readonly destination: `#${string}`,
    readonly action: string,
  ) {}
}

export class ProductCatalog {
  private constructor(private readonly products: readonly ProductOffering[]) {
    this.assertUniqueDestinations()
  }

  static forLanding(): ProductCatalog {
    return new ProductCatalog([
      new ProductOffering(
        "market-scanner",
        "01",
        "Market Scanner",
        "Observer",
        "Analyse quotidienne des marchés",
        "Comprenez le régime de marché en un coup d’œil.",
        "Chaque jour, Market Scanner analyse les principaux actifs sur huit horizons pour qualifier le marché : Risk-On, Prudent ou Risk-Off.",
        "Indices, volatilité, matières premières, devises et crypto, accessibles sans compte.",
        "Accès libre",
        "#market-scanner",
        "Consulter le Market Scanner",
      ),
      new ProductOffering(
        "momentum-mcp",
        "02",
        "Momentum MCP",
        "Connecter",
        "Analyse d’actions pour agents",
        "Donnez à vos agents accès à des analyses boursières exploitables.",
        "Pour chaque action suivie, Momentum croise fondamentaux, indicateurs techniques, actualités, sentiment et scénarios bull/bear.",
        "Recommandation, prix d’entrée, objectif, stop-loss, taille de position et ratio risque/rendement sont accessibles via MCP.",
        "Public · Sans clé API",
        "#momentum-mcp",
        "Connecter un agent",
      ),
      new ProductOffering(
        "deep-copy",
        "03",
        "Deep Copy",
        "Orchestrer",
        "Workflow agentique",
        "De l’analyse à l’ordre IBKR.",
        "Chaque jour, un workflow Google ADK orchestre des agents spécialisés qui analysent le portefeuille, appliquent les contraintes de risque et exécutent leurs ordres sur Interactive Brokers via MCP.",
        "Passage d’ordres automatisé, contraint par le profil de risque et entièrement journalisé.",
        "Private preview",
        "#deep-copy",
        "Découvrir la démarche",
      ),
    ])
  }

  items(): readonly ProductOffering[] {
    return this.products
  }

  private assertUniqueDestinations(): void {
    const destinations = this.products.map((product) => product.destination)
    const uniqueDestinations = new Set(destinations)

    if (uniqueDestinations.size === destinations.length) return

    throw new Error("Each landing product needs a unique destination")
  }

}
