workspace "Deepcopy" "Architecture from source and Terraform at 627a4ac, 2026-10-23. Not a live deployment attestation." {
    !impliedRelationships false

    model {
        visitor = person "Website visitor" "Reads the daily market report."
        operator = person "Authorized operator" "Runs jobs, queries private readers and administers inference."

        data = softwareSystem "Market data providers" "Yahoo Finance, US Treasury; optional FRED, Polymarket and Alpha Vantage." {
            tags "External"
        }
        providers = softwareSystem "Model providers" "Vertex AI Gemini; additional API-key providers are configurable." {
            tags "External"
        }
        postgres = softwareSystem "Managed PostgreSQL" "Separate market_scanner, momentum and litellm databases." {
            tags "External,Database"

        }
        redis = softwareSystem "Redis / Valkey (optional)" "Shared inference state when configured; external to Terraform." {
            tags "External,Optional"
        }

        deepcopy = softwareSystem "Deepcopy" "Market research, daily reports and stock analysis." {
            frontend = container "Public website" "Server-rendered reports; no browser database access." "Next.js / React / Cloud Run" {
                tags "Frontend"
            }
            scheduler = container "Daily schedule" "07:00 Europe/Paris." "Cloud Scheduler"
            scannerService = container "Scanner ADK service" "Private ADK interface and daily-job dispatcher." "FastAPI / Google ADK / Cloud Run"
            scannerReader = container "Scanner reader" "Read-only persisted report consultation." "FastAPI / Cloud Run"
            scannerJob = container "Scanner job" "Daily analysis; shares workflow with ADK service." "Google ADK / Cloud Run Job" {
                tags "AI"
                sRuntime = component "Job runner" "Creates session; runs the complete graph." "ADK Runner"
                sCollect = component "Collect + trends" "Yahoo / Treasury data; deterministic indicators." "Python"
                sResearch = component "Researcher" "Explains movements with research tools." "LlmAgent" {
                    tags "AI"
                }
                sCritic = component "Critic" "Checks gaps and research quality." "LlmAgent" {
                    tags "AI"
                }
                sSynth = component "Synthesizer" "Produces typed market analysis." "LlmAgent" {
                    tags "AI"
                }
                sAssemble = component "Enrich + assemble" "Validates analysis; joins asset observations." "Pydantic / Python"
                sPersist = component "Persist report" "Commits report, assets and horizons together." "SQLAlchemy"
                sTools = component "Research tools" "News, macro indicators and prediction markets." "Python / HTTP"
            }
            momentumReader = container "Momentum reader" "History, latest per ticker and recommendations." "FastAPI / Cloud Run"
            momentumJob = container "Momentum job" "One analysis request; private job execution." "Google ADK / Cloud Run Job" {
                tags "AI"
                mRuntime = component "Execution + runner" "Admits request; prepares memory; starts or resumes invocation." "ADK Runner"
                mMemory = component "Trading memory" "Reads durable context and resolves pending outcomes; records reflections in PostgreSQL." "Python / PostgreSQL"
                mAnalysts = component "Selected analysts" "Parallel market, social, news and fundamentals." "ADK sub-branches" {
                    tags "AI"
                }
                mResearch = component "Investment debate" "Bounded bull / bear rounds; research manager." "ADK nodes" {
                    tags "AI"
                }
                mTrader = component "Trader proposal" "Builds a typed trade proposal." "LlmAgent" {
                    tags "AI"
                }
                mRisk = component "Risk debate" "Aggressive, conservative and neutral views." "ADK nodes" {
                    tags "AI"
                }
                mPortfolio = component "Portfolio decision" "Produces the final research decision." "LlmAgent" {
                    tags "AI"
                }
                mResult = component "Result + next analysis" "Typed reports, statistics and next review date." "Python / LlmAgent"
                mPersist = component "Result repository" "Atomically reserves memory, writes results and records reflections." "SQLAlchemy"
                mTools = component "Market data tools" "Yahoo default; alternate vendor adapters." "Python / HTTP"
            }
            gateway = container "Private inference" "Nginx route filter + LiteLLM sidecar; virtual keys." "Cloud Run / internal ingress" {
                tags "AI"
            }
            admin = container "Inference admin" "Separate IAP-protected LiteLLM service." "Cloud Run / IAP"
        }

        // Context relationships are explicit: no accidental implied dependencies.
        visitor -> deepcopy "Reads reports" "HTTPS"
        operator -> deepcopy "Operates private services" "IAM / IAP"
        deepcopy -> data "Retrieves market evidence" "HTTPS"
        deepcopy -> providers "Requests model inference" "HTTPS via LiteLLM"
        deepcopy -> postgres "Persists and reads domain data" "SQL / TLS"

        // Container relationships describe source wiring and Terraform definitions.
        visitor -> frontend "Reads reports" "HTTPS"
        operator -> momentumJob "Submits analysis request" "Cloud Run Jobs API"
        operator -> momentumReader "Queries analyses" "HTTPS / IAM"
        operator -> admin "Manages inference" "HTTPS / IAP"
        frontend -> scannerReader "Loads latest report" "HTTPS / ID token"
        scheduler -> scannerService "POST daily-scan" "HTTPS / OIDC"
        scannerService -> scannerJob "Submits execution" "Cloud Run Jobs API"
        scannerService -> postgres "Sessions + interactive reports" "SQL / TLS"
        scannerService -> data "Interactive market research" "HTTPS"
        scannerService -> gateway "Interactive inference" "Gemini API / virtual key"
        scannerJob -> postgres "Writes market_scanner" "SQL / TLS"
        scannerJob -> data "Collects market evidence" "HTTPS"
        scannerJob -> gateway "Research / critique / synthesis" "Gemini API / virtual key"
        scannerReader -> postgres "Reads market_scanner only" "SQL / TLS"
        momentumJob -> postgres "Writes momentum" "SQL / TLS"
        momentumJob -> data "Retrieves stock evidence" "HTTPS"
        momentumJob -> gateway "Quick + deep model calls" "Gemini API / virtual key"
        momentumReader -> postgres "Reads momentum only" "SQL / TLS"
        gateway -> providers "Routes configured models" "HTTPS"
        gateway -> postgres "Keys, budgets and spend" "SQL / TLS"
        admin -> postgres "Manages inference configuration" "SQL / TLS"
        admin -> providers "Configured model access" "HTTPS"
        gateway -> redis "Optional shared state" "TLS"
        admin -> redis "Optional shared state" "TLS"

        // Scanner workflow: the service imports this same graph.
        scannerService -> sRuntime "Dispatches the daily job" "Jobs API"
        sRuntime -> sCollect "Starts workflow"
        sRuntime -> postgres "Stores session events" "market_scanner / _sessions"
        sCollect -> data "Fetches prices / public debt" "HTTPS"
        sCollect -> sResearch "Trend snapshot"
        sResearch -> sCritic "Research findings"
        sCritic -> sSynth "Critique + findings"
        sSynth -> sAssemble "Typed analysis"
        sAssemble -> sPersist "Complete report"
        sPersist -> postgres "Commits normalized report" "market_scanner / _analysis"
        sResearch -> sTools "Calls tools"
        sTools -> data "News / macro / probabilities" "HTTPS"
        sResearch -> gateway "Inference + Google Search tool" "Gemini API"
        sCritic -> gateway "Inference" "Gemini API"
        sSynth -> gateway "Inference" "Gemini API"

        // Momentum graph; result persistence follows successful workflow execution.
        operator -> mRuntime "Supplies AnalysisRequest" "Job environment"
        mRuntime -> mMemory "Prepares past context"
        mRuntime -> postgres "Persists resumable events" "momentum / _sessions"
        mRuntime -> mAnalysts "Starts / resumes graph"
        mAnalysts -> mResearch "Selected analyst reports"
        mResearch -> mTrader "Research plan"
        mTrader -> mRisk "Trade proposal"
        mRisk -> mPortfolio "Risk perspectives"
        mPortfolio -> mResult "Decision"
        mResult -> mPersist "Completed execution"
        mPersist -> postgres "Commits correlated results" "momentum / _analysis"
        mPersist -> mMemory "Then records completion"
        mAnalysts -> mTools "Collectors call tools"
        mTools -> data "Stock data / news" "HTTPS"
        mAnalysts -> gateway "Quick models + reflections" "Gemini API"
        mResearch -> gateway "Quick + deep models" "Gemini API"
        mTrader -> gateway "Quick model" "Gemini API"
        mRisk -> gateway "Quick models" "Gemini API"
        mPortfolio -> gateway "Deep model" "Gemini API"
        mResult -> gateway "Next review date" "Gemini API"
    }

    views {
        systemContext deepcopy "01-SystemContext" {
            title "01 | Deepcopy - system context"
            description "Current repository scope. Public MCP and IBKR execution are documented externally, not implemented here."
            include visitor operator deepcopy data providers postgres
            autoLayout lr
        }
        container deepcopy "02-Containers" {
            title "02 | Deepcopy - services and storage"
            description "Source and Terraform topology, not proof of deployment. PostgreSQL contains three separate databases."
            include visitor operator frontend scheduler scannerService scannerJob scannerReader momentumJob momentumReader gateway admin postgres data providers redis
            autoLayout lr
        }
        component scannerJob "03-ScannerComponents" {
            title "03 | Market Scanner - analysis pipeline"
            description "Daily job and interactive service share the same workflow. ADK events and business reports use different schemas."
            include sRuntime sCollect sResearch sCritic sSynth sAssemble sPersist sTools postgres data gateway
            autoLayout tb
        }
        component momentumJob "04-MomentumComponents" {
            title "04 | Momentum - analysis via private inference"
            description "Analysis only: no broker orders. All agent inference uses the private gateway. Durable memory and results use PostgreSQL."
            include mRuntime mMemory mAnalysts mResearch mTrader mRisk mPortfolio mResult mPersist mTools postgres data
            autoLayout tb
        }
        styles {
            element "Element" {
                color #18344d
                stroke #627d94
                fontSize 22
            }
            element "Person" {
                shape Person
                background #16324f
                color #ffffff
            }
            element "Software System" {
                background #146b87
                color #ffffff
            }
            element "Container" {
                background #e3eef8
            }
            element "Component" {
                background #e6f3ed
            }
            element "External" {
                background #eef1f5
                color #31475d
            }
            element "Database" {
                shape Cylinder
                background #fff0cc
                color #674c16
            }
            element "AI" {
                background #eee5fa
                color #533474
            }
            element "Frontend" {
                background #d9f1ec
            }
            element "Optional" {
                background #f5f2ed
                color #686054
            }
            relationship "Relationship" {
                color #627d94
                thickness 2
            }
        }
    }
}
