export type ProductIdentifier = "deep-copy" | "market-scanner" | "momentum-mcp"
export type ProductJourney = "Observe" | "Connect" | "Orchestrate"

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
        "Observe",
        "Daily market analysis",
        "Understand the market regime at a glance.",
        "Every day, Market Scanner analyses major assets across eight horizons to describe the market as Risk-On, Cautious or Risk-Off.",
        "Indices, volatility, commodities, currencies and crypto, available without an account.",
        "Free access",
        "#market-scanner",
        "Read the Market Scanner",
      ),
      new ProductOffering(
        "momentum-mcp",
        "02",
        "Momentum MCP",
        "Connect",
        "Stock analysis for agents",
        "Give your agents access to actionable stock analysis.",
        "For each stock it follows, Momentum combines fundamentals, technical indicators, news, sentiment and bull/bear scenarios.",
        "Recommendations, entry prices, targets, stop-loss levels, position sizes and risk/reward ratios are available through MCP.",
        "Public · No API key",
        "#momentum-mcp",
        "Connect an agent",
      ),
      new ProductOffering(
        "deep-copy",
        "03",
        "Deep Copy",
        "Orchestrate",
        "Agent workflow",
        "From analysis to an IBKR order.",
        "Every day, a Google ADK workflow orchestrates specialised agents that analyse the portfolio, apply risk constraints and execute orders on Interactive Brokers through MCP.",
        "Automated order placement, constrained by the risk profile and fully logged.",
        "Private preview",
        "#deep-copy",
        "Explore the approach",
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
