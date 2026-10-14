import { ArrowDownRight } from "lucide-react"
import { ProductCatalog, ProductOffering } from "@/lib/landing/product-catalog"

export function ProductSuiteSection() {
  const products = ProductCatalog.forLanding().items()

  return (
    <section id="products" aria-labelledby="products-title" className="bg-on-surface py-20 text-surface-lowest md:py-28">
      <div className="mx-auto max-w-6xl px-6">
        <div data-animate="section-heading" className="grid gap-7 pb-14 md:grid-cols-12 md:pb-16">
          <h2 id="products-title" className="max-w-3xl font-display text-4xl font-semibold leading-[1.12] tracking-[-0.03em] md:col-span-8 md:text-6xl md:leading-[1.08]">
            Observer. Connecter. Orchestrer.
            <br />
            <span className="font-medium text-surface-highest">Un écosystème, trois usages.</span>
          </h2>
          <p className="max-w-md self-end text-base leading-relaxed text-surface-highest md:col-span-4">
            Observez le régime de marché, connectez vos agents aux analyses d’actions, puis
            orchestrez leur passage à l’action sur Interactive Brokers.
          </p>
        </div>

        <ol data-animate="product-list" className="border-t border-inverse-divider">
          {products.map((product, index) => (
            <ProductRow key={product.identifier} product={product} index={index} />
          ))}
        </ol>
      </div>
    </section>
  )
}

function ProductRow({ product, index }: { product: ProductOffering; index: number }) {
  return (
    <li data-motion-item={index} className="product-row grid gap-6 border-b border-inverse-divider py-9 md:grid-cols-12 md:gap-8 md:py-11">
      <div className="flex items-start justify-between gap-4 md:col-span-3 md:block">
        <p className="font-mono text-xs text-primary-container">{product.ordinal}</p>
        <div className="md:mt-5">
          <h3 className="font-display text-xl font-semibold tracking-[-0.02em]">{product.name}</h3>
          <p className="mt-1 text-sm text-surface-highest">{product.category}</p>
        </div>
      </div>

      <div className="md:col-span-5">
        <p className="mb-3 text-xs font-semibold uppercase tracking-[0.15em] text-primary-container">
          {product.journey}
        </p>
        <p className="font-display text-2xl font-semibold tracking-[-0.025em] md:text-3xl">
          {product.headline}
        </p>
        <p className="mt-4 max-w-xl text-sm leading-relaxed text-surface-highest md:text-base">
          {product.description}
        </p>
      </div>

      <div className="flex flex-col items-start md:col-span-4">
        <p className="text-sm leading-relaxed text-surface-highest">{product.proof}</p>
        <p className="mt-4 text-xs font-semibold text-primary-container">{product.availability}</p>
        <a
          href={product.destination}
          className="product-destination mt-6 inline-flex min-h-11 items-center gap-2 text-sm font-semibold text-surface-lowest transition-colors hover:text-primary-container"
        >
          {product.action}
          <ArrowDownRight className="product-destination-icon h-4 w-4" aria-hidden="true" />
        </a>
      </div>
    </li>
  )
}
