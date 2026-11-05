# Pagination explicite des outils Momentum MCP

Statut : implémentée localement, livraison distante non effectuée — 2026-11-04.

## Contrat

Le format des curseurs HTTP est conservé. La limite de `/v1/recommendations`
et de son outil MCP est de 50 ; les autres listes restent à 100.
Chaque appel valide à un outil de liste effectue une seule requête HTTP métier.
La gateway ne suit plus automatiquement les curseurs et n'accumule plus les pages.

| Outil | Filtres conservés | `page_size` par défaut | Maximum |
| --- | --- | --- | --- |
| `momentum_list_analyses` | `ticker` optionnel | 50 | 100 |
| `momentum_latest_analyses` | `ticker`, `rating` optionnels | 50 | 100 |
| `momentum_get_recommendations` | `rating`, défaut `Buy,Overweight` | 10 | 50 |

Les trois outils acceptent :

- `page_size` : entier de 1 au maximum propre à chaque outil, bornes incluses.
- `page_token` : chaîne opaque de 512 caractères maximum, vide pour commencer.

Les contraintes et les valeurs par défaut figurent dans leurs schémas MCP.
Les entrées invalides sont rejetées avant toute requête API.

Le résultat est le DTO existant `ReaderPage`, directement dans
`structuredContent` :

```json
{
  "items": [],
  "next_page_token": ""
}
```

Les champs des résumés d'analyse sont conservés. Le client lit les `items`, puis
rappelle le même outil avec les mêmes filtres et le `next_page_token` reçu comme
`page_token`. Seul le token vide indique la fin : une page courte ou vide peut
porter un curseur, et une page pleine peut être la dernière.

## Compatibilité avec Momentum API

`MomentumClient` utilise toujours `/v1/analyses`, `/v1/analyses/latest` et
`/v1/recommendations`, avec le DTO HTTP `AnalysisPageRequest`. La gateway transmet
la taille demandée et le curseur sans transformation. `ReaderPage` conserve le
curseur retourné par l'API ; aucun curseur MCP supplémentaire n'est construit.

Le format, le décodage et la validation restent la responsabilité de Momentum API.
Son `Cursor` encode une position `(created_at, id)`, une version et une empreinte
liée à la vue et aux filtres normalisés. Un token d'un autre endpoint ou d'autres
filtres est rejeté par l'API. Le MCP conserve cette erreur, expurgée comme les
autres erreurs amont ; il ne renvoie pas une liste vide à la place.

Les tests de compatibilité importent **le véritable encodeur et validateur** de
`apps/backend/momentum-api/src/app/domain/analyses/search.py`. Ils vérifient le
passage aller-retour, le changement autorisé de taille de page, le rejet d'un
changement de filtre et le rejet d'un changement d'endpoint. Les fixtures de la
simulation Postman utilisent également des tokens générés avec cet encodeur.

La limite de recommandations est déclarée séparément dans l'API et le MCP ;
les deux contrats sont alignés explicitement, sans synchronisation automatique.
Aucune table, dépendance ou configuration de déploiement n'est modifiée.
La ressource Market Scanner continue d'appeler `/market-scans/latest` et renvoie
un seul scan ; aucun outil de parcours des scans n'est ajouté.

## Migration des consommateurs

Cette modification remplace le contrat des trois outils :

- `limit` et `offset` sont supprimés et rejetés, jamais ignorés silencieusement.
- `page_size` remplace la taille demandée, avec un maximum de 100 pour les analyses, 50 pour les recommandations.
- Pour avancer, le client suit les curseurs au lieu de relire des pages jusqu'à
  un offset.
- `structuredContent.result` devient `structuredContent.items`, accompagné de
  `structuredContent.next_page_token`.
- `momentum_latest_analyses` ne retourne plus toutes les pages dans un seul appel.

Les descriptions d'outils, le prompt `momentum_analyze_ticker`, le README, la documentation
frontend, la collection Postman et `scripts/verify_live.py` utilisent ce contrat.
Les autres outils conservent leurs entrées et sorties.

## Invariants

- Les filtres restent normalisés et leurs valeurs sont conservées entre pages.
- Le délai de 45 secondes borne un appel ; aucune boucle de chargement implicite.
- Les erreurs HTTP, délais dépassés et réponses invalides conservent les erreurs
  publiques expurgées, sans succès partiel ni corps d'erreur privé.
- Les identités séparées par API, signatures HMAC, annotations et liste des
  capacités publiques sont conservées.
- Aucun état de pagination ou session HTTP n'est créé. Le parcours n'est pas
  un instantané des données modifiées entre les appels.
- `DEFAULT_PAGE_SIZE` / `list_page_size` paginent uniquement la découverte des
  composants MCP ; ils ne configurent pas les pages de données métier.

## Organisation

Chemins relatifs à `apps/backend/momentum-public-mcp/` :

| Chemin | Responsabilité |
| --- | --- |
| `core_components/tools/public_tools.py` sous `src/app/` | Signatures, schémas et descriptions des outils. |
| `core_components/gateway.py` sous `src/app/` | Une lecture de page via le client HTTP. |
| `domain.py` sous `src/app/` | Validation de la demande MCP `AnalysisPage`. |
| `api/momentum/` sous `src/app/` | Clients et DTO HTTP réutilisés sans changer l'API. |
| `tests/postman/` | Vérification du serveur réel contre des API simulées. |

## Vérification reproductible

Depuis `apps/backend/momentum-public-mcp/` :

```sh
.venv/bin/python -m pytest -q
.venv/bin/ruff check src tests scripts
.venv/bin/ruff format --check src tests scripts
.venv/bin/python scripts/simulation.py
uv build --out-dir dist
```

La simulation démarre le vrai serveur MCP, appelle les clients HTTP réels et
contrôle les réponses des deux mocks locaux. Les scénarios existants couvrent
la découverte, les lectures, la ressource Scanner, les suggestions simulées,
les erreurs et la latence.

Ces vérifications locales ne constituent pas une validation de données Aiven,
d'IAM déployé ou d'un déploiement de la nouvelle version. Aucun appel de production
ni écriture de données réelles n'est nécessaire pour ces tests.
