"""Constants for the Finance integration."""

DOMAIN = "finance_dashboard"
PLATFORMS = ["sensor", "number", "select"]

# Version — must match manifest.json and companion config.yaml
VERSION = "0.25.3"

# Panel
PANEL_URL_PATH = "finance-dashboard"
PANEL_TITLE = "Personal Bankin"
PANEL_ICON = "mdi:finance"
PANEL_COMPONENT_NAME = "finance-dashboard-panel"
PANEL_MODULE_PATH = f"/api/{DOMAIN}/static/finance-dashboard-panel.js?v={VERSION}"

# Storage keys — all sensitive data stored in HA .storage/
STORAGE_KEY_CREDENTIALS = f"{DOMAIN}_credentials"
STORAGE_KEY_TOKENS = f"{DOMAIN}_tokens"
STORAGE_KEY_AUDIT = f"{DOMAIN}_audit_log"
STORAGE_VERSION = 1

# Enable Banking
ENABLEBANKING_BASE_URL = "https://api.enablebanking.com"
# Fallback when the HA core country setting is not configured
DEFAULT_COUNTRY = "DE"
# Sandbox uses a different app registration
ENABLEBANKING_SANDBOX_URL = "https://api.enablebanking.com"
TOKEN_MAX_AGE_DAYS = 90  # Force re-auth after 90 days (our own policy)
SESSION_MAX_DAYS = 180  # Enable Banking session validity
HISTORY_RETENTION_MONTHS = 24  # How far back to keep accumulated transactions
INITIAL_SYNC_DAYS = 365  # Days to fetch on the very first successful refresh
DEFAULT_REFRESH_DAYS = 90  # Days for all subsequent refreshes
# Progressively smaller windows tried when a bank rejects the requested
# transaction period with HTTP 422 WRONG_TRANSACTIONS_PERIOD. Each must be
# strictly smaller than DEFAULT_REFRESH_DAYS so the retry is a real fallback
# (some ASPSPs cap history well below 90 days once a consent ages).
TX_FALLBACK_WINDOWS = [30, 7]
SESSION_TIMEOUT_MINUTES = 30
ENABLEBANKING_RATE_LIMIT_DAILY = 4

# Automatic daily refresh (opt-in scheduler).
# A single user-triggered live fetch per day at a fixed hour — NOT background
# polling. Disabled by default; the 4/day per-ASPSP rate limit still applies,
# so one scheduled refresh leaves headroom for manual refreshes.
CONF_AUTO_REFRESH_ENABLED = "auto_refresh_enabled"
CONF_AUTO_REFRESH_HOUR = "auto_refresh_hour"
DEFAULT_AUTO_REFRESH_HOUR = 6

# Transaction categorization
CATEGORY_HOUSING = "housing"
CATEGORY_FOOD = "food"  # legacy alias — kept so cached "food" transactions still resolve
CATEGORY_GROCERIES = "groceries"
CATEGORY_DINING = "dining"
CATEGORY_TRANSPORT = "transport"
CATEGORY_INSURANCE = "insurance"
CATEGORY_SUBSCRIPTIONS = "subscriptions"
CATEGORY_LOANS = "loans"
CATEGORY_UTILITIES = "utilities"
CATEGORY_HEALTH = "health"
CATEGORY_LEISURE = "leisure"
CATEGORY_INCOME = "income"
CATEGORY_TRANSFERS = "transfers"
CATEGORY_OTHER = "other"
CATEGORY_EXCLUDED = "excluded"  # User-marked as non-computable (internal transfers, ignored txns)

DEFAULT_CATEGORIES = [
    CATEGORY_HOUSING,
    CATEGORY_GROCERIES,
    CATEGORY_DINING,
    CATEGORY_TRANSPORT,
    CATEGORY_INSURANCE,
    CATEGORY_SUBSCRIPTIONS,
    CATEGORY_LOANS,
    CATEGORY_UTILITIES,
    CATEGORY_HEALTH,
    CATEGORY_LEISURE,
    CATEGORY_INCOME,
    CATEGORY_TRANSFERS,
    CATEGORY_EXCLUDED,
    CATEGORY_OTHER,
]

# Categorization rule directions — a keyword rule may be scoped to a
# transaction sign so the same text can resolve to different categories per
# direction (e.g. a person's name on both an incoming salary and an outgoing
# transfer to their own untracked account).
RULE_DIRECTION_ANY = "any"
RULE_DIRECTION_CREDIT = "credit"  # matches only positive amounts (money in)
RULE_DIRECTION_DEBIT = "debit"  # matches only negative amounts (money out)
RULE_DIRECTIONS = (RULE_DIRECTION_ANY, RULE_DIRECTION_CREDIT, RULE_DIRECTION_DEBIT)

# Categories that are inherently credit-only: a keyword resolving here must
# never tag a debit — an outgoing amount is never "income".
CREDIT_ONLY_CATEGORIES = {CATEGORY_INCOME}

# Categorization rules — keyword-based auto-detection
# These are default patterns; users can customize via UI.
# Tuned for Spanish banks (Caja Rural, BBVA) plus international merchants.
# Matching is a lowercased substring check WITHOUT accent folding, so
# keywords with accents are listed in both accented and plain forms
# (bank statements usually arrive uppercase without accents).
CATEGORIZATION_RULES = {
    CATEGORY_HOUSING: [
        "alquiler",
        "hipoteca",
        "comunidad de propietarios",
        "comunidad prop",
        "rent",
    ],
    CATEGORY_GROCERIES: [
        "mercadona",
        "carrefour",
        "lidl",
        "aldi",
        "eroski",
        "alcampo",
        "consum",
        "supermercado",
        "supercor",
        "gadis",
        "froiz",
        "dia ",
        "hipercor",
        "el corte ingles alimentacion",
        "el corte inglés alimentación",
    ],
    CATEGORY_DINING: [
        "restaurante",
        "restaurant",
        "glovo",
        "just eat",
        "uber eats",
        "telepizza",
        "mcdonald",
        "burger king",
        "dominos",
        "kfc",
        "five guys",
        "bar ",
        "cafeteria",
        "cafetería",
        "heladeria",
        "heladería",
    ],
    CATEGORY_TRANSPORT: [
        "renfe",
        "alsa",
        "cabify",
        "bolt.eu",
        "repsol",
        "cepsa",
        "galp",
        "ballenoil",
        "plenoil",
        "gasolinera",
        "peaje",
        "autopista",
        "parking",
        "shell",
        "uber",
        "taxi",
    ],
    CATEGORY_INSURANCE: [
        "seguro",
        "insurance",
        "mapfre",
        "mutua madril",
        "axa",
        "allianz",
        "linea directa",
        "línea directa",
        "adeslas",
        "sanitas",
        "dkv",
        "generali",
        "caser",
        "santalucia",
        "santa lucia",
        "ocaso",
    ],
    CATEGORY_SUBSCRIPTIONS: [
        "netflix",
        "spotify",
        "amazon prime",
        "disney",
        "xbox",
        "google one",
        "icloud",
        "youtube premium",
        "hbo",
        "dazn",
        "filmin",
        "apple.com",
        "movistar plus",
    ],
    CATEGORY_LOANS: [
        "prestamo",
        "préstamo",
        "financiacion",
        "financiación",
        "amortizacion",
        "amortización",
        "cofidis",
        "cetelem",
        "loan",
    ],
    CATEGORY_UTILITIES: [
        "iberdrola",
        "endesa",
        "naturgy",
        "holaluz",
        "totalenergies",
        "curenergia",
        "aqualia",
        "canal de isabel",
        "movistar",
        "vodafone",
        "o2",
        "orange",
        "digi spain",
        "pepephone",
        "lowi",
        "masmovil",
        "telefonica",
        "telefónica",
        "euskaltel",
        "octopus",
    ],
    CATEGORY_HEALTH: [
        "farmacia",
        "parafarmacia",
        "clinica",
        "clínica",
        "dentista",
        "fisioterapia",
        "fisio",
        "medico",
        "médico",
        "hospital",
        "laboratorio",
        "optica",
        "óptica",
        "psicolog",
        "nutricion",
        "nutrición",
    ],
    CATEGORY_LEISURE: [
        "cine",
        "teatro",
        "concierto",
        "entradas",
        "ticketmaster",
        "eventbrite",
        "gym",
        "gimnasio",
        "deporte",
        "decathlon",
        "bowling",
        "karting",
        "escape room",
        "parque de atracciones",
        "zoo",
        "museo",
        "aquapark",
    ],
    CATEGORY_INCOME: [
        "nomina",
        "nómina",
        "salario",
        "salary",
        "pension",
        "pensión",
    ],
    CATEGORY_TRANSFERS: [
        "transferencia",
        "traspaso",
        "bizum",
        "transfer",
    ],
}

# Custom categorization rules — user-added keywords persisted in .storage/
STORAGE_KEY_CUSTOM_RULES = f"{DOMAIN}_custom_rules"

# Services
SERVICE_FETCH_FULL_HISTORY = "fetch_full_history"
SERVICE_REFRESH_ACCOUNTS = "refresh_accounts"
SERVICE_REFRESH_TRANSACTIONS = "refresh_transactions"
SERVICE_CATEGORIZE = "categorize_transactions"
SERVICE_ADD_RULE = "add_categorization_rule"
SERVICE_REMOVE_RULE = "remove_categorization_rule"
SERVICE_GET_BALANCE = "get_balance"
SERVICE_GET_SUMMARY = "get_monthly_summary"
SERVICE_SET_BUDGET_LIMIT = "set_budget_limit"
SERVICE_EXPORT_CSV = "export_csv"

# Audit log
AUDIT_EVENT_AUTH = "authentication"
AUDIT_EVENT_TOKEN_REFRESH = "token_refresh"
AUDIT_EVENT_DATA_ACCESS = "data_access"
AUDIT_EVENT_CONFIG_CHANGE = "config_change"
AUDIT_EVENT_ERROR = "error"
AUDIT_MAX_ENTRIES = 1000

# Transfer chain detection
TRANSFER_AMOUNT_TOLERANCE = 0.50  # EUR tolerance for fee differences
TRANSFER_TIME_WINDOW_DAYS = 3  # ±days for date matching
TRANSFER_REFUND_WINDOW_DAYS = 14  # Lookback for refund matching
TRANSFER_AUTO_CONFIDENCE = 0.60  # Auto-link threshold (0.0-1.0)
STORAGE_KEY_TRANSFER_OVERRIDES = f"{DOMAIN}_transfer_overrides"

# Refund keywords — transaction text must contain one for refund detection
REFUND_KEYWORDS = [
    "devolucion",
    "devolución",
    "reembolso",
    "retrocesion",
    "retrocesión",
    "refund",
    "reversal",
    "chargeback",
]

# Household model
DEFAULT_SPLIT_MODEL = "proportional"  # proportional, equal, custom

# Demo mode
SERVICE_TOGGLE_DEMO = "toggle_demo"
