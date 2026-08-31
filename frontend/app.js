const translations = {
  en: {
    meta_description: "PositionPilot — portfolio-grounded investment decision support.",
    brand_home: "PositionPilot home",
    account_actions: "Account actions",
    product_capabilities: "Product capabilities",
    authentication: "Authentication",
    create_account: "Create account",
    log_in: "Log in",
    log_out: "Log out",
    hero_eyebrow: "Your portfolio, before the opinion",
    hero_title: "Investment answers grounded in what you actually own.",
    hero_summary: "Record your starting holdings, keep an immutable ledger, and ask focused questions using current portfolio and market context.",
    start_local_account: "Start a local account ↗",
    already_have_account: "I already have an account",
    local_auth_boundary: "Local-only account · The recommended server binds to 127.0.0.1.",
    proof_state: "Deterministic portfolio state",
    proof_ledger: "Immutable trade and cash ledger",
    proof_agent: "Real context-aware Agent answers",
    engineering_smoke_notice: "Engineering smoke · Fake Agent and fixture data · Not real investment analysis",
    decision_support_notice: "Decision support, not automated trading.",
    footer_disclaimer: "Decision support, not automated trading.",
    footer_boundary: "Facts · Inference · Unknown",
    local_workspace: "Local decision workspace",
    account_eyebrow: "One account. One portfolio.",
    register_title: "Create your local account.",
    login_title: "Welcome back.",
    auth_summary: "Your password is hashed locally. Portfolio identity is restored by a private browser session, not a UUID.",
    register: "Register",
    display_name: "Display name",
    display_name_placeholder: "How should we address you?",
    email: "Email",
    password: "Password",
    password_hint: "Use 8–128 characters. This local V1 does not provide password reset.",
    confirm_password: "Confirm password",
    back_home: "Back to home",
    required_fields: "Complete all required fields.",
    invalid_email: "Enter a valid email address.",
    invalid_password: "Password must contain 8–128 characters.",
    password_mismatch: "Passwords do not match.",
    registering: "Creating your local account…",
    logging_in: "Signing in…",
    register_unknown: "Account creation result unknown. Do not retry automatically; try logging in with the same email.",
    login_network_error: "Could not reach the local server. Check that PositionPilot is running and try again.",
    session_restore_failed: "Could not verify your current session. Reload this page after checking the local server; do not register or log in again yet.",
    unexpected_server_error: "The local server could not complete this request. Reload to recover the current state before trying again.",
    invalid_credentials: "Email or password is incorrect.",
    email_registered: "That email is already registered. Log in instead.",
    logging_out: "Signing out…",
    logout_failed: "Sign out did not complete. You are still signed in; check the local server and try again.",
    setup_required: "Complete portfolio setup before continuing.",
    portfolio_unavailable: "This portfolio is unavailable for the current session.",
    invalid_account: "Check the account details and try again.",
    portfolio_already_exists: "A portfolio already exists for this account. Reload to recover it.",
    invalid_portfolio: "Check the starting cash and positions, then try again.",
    invalid_opening_state: "Check the existing-position rows and try again.",
    invalid_transaction: "Check the transaction fields and try again.",
    invalid_cash_event: "Check the cash-entry fields and try again.",
    setup_eyebrow: "Starting state",
    setup_title: "Tell PositionPilot where you are starting.",
    setup_summary: "Cash and existing positions form your opening state. They are not fabricated trades, and you can start with zero.",
    cash_balance: "Cash balance",
    initial_cash: "Initial cash",
    initial_cash_usd: "Available cash (USD)",
    cash_zero_hint: "If you do not enter cash, the portfolio starts at 0.",
    existing_holdings: "Existing holdings",
    opening_positions: "Opening positions",
    opening_optional_hint: "Optional. Add stocks you already own, or add them later before the first trade or cash entry.",
    add_position: "Add another position",
    start_empty: "Start with zero",
    save_and_continue: "Save and continue ↗",
    ticker: "Ticker",
    shares: "Shares",
    average_cost: "Average cost",
    position_type_optional: "Position type (optional)",
    unspecified: "Unspecified",
    remove: "Remove",
    invalid_cash: "Cash must be zero or a positive decimal with at most 8 decimal places.",
    incomplete_position: "Complete ticker, shares, and average cost, or remove this row.",
    invalid_positive_decimal: "Use a positive decimal with at most 8 decimal places.",
    duplicate_position: "Each ticker and position type combination may appear only once.",
    setup_saving: "Saving your starting state…",
    setup_unknown: "Portfolio setup result unknown. Do not retry automatically; reload this page to recover the current state.",
    workspace_navigation: "Workspace navigation",
    primary_navigation: "Primary navigation",
    new_question: "New question",
    ask_nav: "Ask",
    portfolio_nav: "Portfolio",
    question_history: "Question history",
    session_only: "This tab only",
    no_questions: "No questions yet.",
    signed_in_as: "Signed in as",
    context_aware: "Context-aware decision support",
    chat_view_title: "Decision questions",
    structured_state: "Structured state",
    portfolio_manage_title: "Portfolio workspace",
    portfolio_manage_summary: "Review deterministic state or append an immutable trade or cash record.",
    portfolio_ready: "Portfolio ready",
    portfolio_loading: "Loading portfolio",
    portfolio_stale: "Refresh required",
    idle: "Idle",
    submitting: "Saving",
    refresh_required: "Refresh required",
    chat_intro_eyebrow: "Your portfolio is connected",
    chat_intro_title: "What decision are you working through?",
    chat_intro_body: "Ask one focused question. PositionPilot uses your portfolio and only the current context the question needs.",
    no_memory_notice: "Questions remain in this browser tab only and are not model memory.",
    investment_question: "Investment question",
    question_placeholder: "For example: Can I add a little more GOOG today?",
    question_ready: "Uses your current portfolio.",
    ask: "Ask PositionPilot ↗",
    asking: "Thinking…",
    portfolio_reload: "Reload",
    portfolio_sections: "Portfolio sections",
    overview_tab: "Positions",
    trade_tab: "Transactions",
    cash_tab: "Cash activity",
    available_cash: "Available cash",
    ledger_derived: "Ledger-derived · USD",
    portfolio_context: "Portfolio context",
    session_owned: "Session-owned",
    session_owned_hint: "Identity comes from your private local session.",
    opening_state: "Opening state",
    existing_positions_setup: "Add existing positions",
    starting_facts: "One-time starting facts",
    opening_explainer: "Record holdings you already owned when tracking begins. This does not change cash or create a trade.",
    skip_for_now: "Skip for now",
    save_opening_positions: "Save existing positions",
    add_existing_positions: "Add existing positions",
    open_positions: "Open positions",
    portfolio_empty_loaded: "No open positions yet.",
    opening_records: "Opening position records",
    records_empty: "No records yet.",
    transaction_entry: "Transaction",
    trade_entry: "Trade entry",
    immutable_entry: "Appends an immutable record",
    action: "Action",
    price: "Price",
    occurred_at_optional: "Occurred at (optional)",
    occurred_at_hint: "Leave blank to use backend application time.",
    reason_optional: "Reason (optional)",
    save_trade: "Save trade",
    transaction_history: "Transaction history",
    cash_activity: "Cash activity",
    cash_entry: "Cash entry",
    cash_event_type: "Cash event",
    amount: "Amount",
    save_cash: "Save cash event",
    cash_history: "Cash history",
    cost_basis: "Cost basis",
    commission: "Commission",
    fee_schedule: "Fee schedule",
    occurred_at: "Occurred at",
    reason: "Reason",
    sequence: "Sequence",
    recorded_at: "Recorded at",
    not_provided: "Not provided",
    trade_saved: "Trade saved",
    cash_saved: "Cash event saved",
    opening_saved: "Existing positions saved",
    mutation_unknown: "Result unknown. Do not retry automatically. Reload and inspect the latest portfolio state.",
    refresh_failed: "The write may have succeeded, but the latest portfolio could not be loaded. Reload before continuing.",
    invalid_form: "Check the highlighted fields and try again.",
    insufficient_cash: "Insufficient cash for this purchase and backend-calculated fees.",
    insufficient_shares: "Insufficient shares in this position type.",
    opening_sealed: "Existing positions can only be added before the first trade or cash entry.",
    future_time: "Occurred at cannot be in the future.",
    session_expired: "Your local session expired. Log in again.",
    working_title: "Assembling decision context",
    working_answer: "Reading your portfolio and selecting current context.",
    answer_label: "Answer",
    sources_used: "Sources used",
    source_explainer: "Supporting context for this answer.",
    answer_ready: "Portfolio-grounded answer",
    answer_degraded: "Answer with limited context",
    answer_failed: "Answer unavailable",
    source_ticker: "Ticker",
    source_provider: "Provider",
    source_feed: "Feed",
    source_market_time: "Market time",
    source_fetched: "Fetched",
    source_portfolio: "Portfolio holdings and cash",
    source_quote: "Current market quote",
    source_history: "Price history",
    source_news: "Recent news",
    source_market: "Market context",
    no_sources: "No supporting sources were returned.",
    question_required: "Enter a focused investment question.",
    question_failed: "PositionPilot could not complete this question. Review the status and try again.",
  },
  zh: {
    meta_description: "PositionPilot — 基于真实投资组合的投资决策支持。", brand_home: "PositionPilot 主页", account_actions: "账户操作", product_capabilities: "产品能力", authentication: "身份验证", create_account: "注册账户", log_in: "登录", log_out: "退出登录",
    hero_eyebrow: "先看持仓，再谈观点", hero_title: "基于你真实持仓的投资分析。", hero_summary: "录入起始持仓，维护不可变交易账本，并结合当前投资组合和市场信息提出具体问题。", start_local_account: "注册本地账户 ↗", already_have_account: "我已有账户", local_auth_boundary: "仅限本地账户 · 推荐服务只绑定 127.0.0.1。", proof_state: "确定性投资组合状态", proof_ledger: "不可变交易与现金账本", proof_agent: "真实的上下文 Agent 回答", engineering_smoke_notice: "工程 Smoke · Fake Agent 与固定测试数据 · 不是真实投资分析", decision_support_notice: "仅提供决策支持，不执行自动交易。", footer_disclaimer: "仅提供决策支持，不执行自动交易。", footer_boundary: "事实 · 推断 · 未知", local_workspace: "本地决策工作区",
    account_eyebrow: "一个账户，一个投资组合。", register_title: "注册你的本地账户。", login_title: "欢迎回来。", auth_summary: "密码只在本地进行哈希保存；系统通过浏览器私有 Session 恢复身份，不再使用 UUID。", register: "注册", display_name: "显示名称", display_name_placeholder: "希望我们如何称呼你？", email: "邮箱", password: "密码", password_hint: "请输入 8–128 个字符。此本地 V1 暂不提供密码重置。", confirm_password: "确认密码", back_home: "返回主页", required_fields: "请填写所有必填字段。", invalid_email: "请输入有效邮箱。", invalid_password: "密码必须为 8–128 个字符。", password_mismatch: "两次输入的密码不一致。", registering: "正在创建本地账户…", logging_in: "正在登录…", register_unknown: "账户创建结果未知。请勿自动重试；请使用相同邮箱尝试登录。", login_network_error: "无法连接本地服务。请确认 PositionPilot 已启动后重试。", session_restore_failed: "无法确认当前 Session。请检查本地服务后刷新本页；在恢复前不要重复注册或登录。", unexpected_server_error: "本地服务未能完成本次请求。请先刷新恢复当前状态，再决定是否重试。", invalid_credentials: "邮箱或密码错误。", email_registered: "该邮箱已经注册，请直接登录。", logging_out: "正在退出…", logout_failed: "退出未完成，你仍处于登录状态。请检查本地服务后重试。", setup_required: "请先完成投资组合设置。", portfolio_unavailable: "当前 Session 无法访问此投资组合。", invalid_account: "请检查账户信息后重试。", portfolio_already_exists: "该账户已经存在投资组合，请刷新页面恢复。", invalid_portfolio: "请检查起始现金与持仓后重试。", invalid_opening_state: "请检查已有持仓记录后重试。", invalid_transaction: "请检查交易记录字段后重试。", invalid_cash_event: "请检查现金记录字段后重试。",
    setup_eyebrow: "起始状态", setup_title: "告诉 PositionPilot 你的起点。", setup_summary: "现金和已有持仓共同构成起始状态，不会被伪造成交易；也可以从零开始。", cash_balance: "现金余额", initial_cash: "初始现金", initial_cash_usd: "可用现金（USD）", cash_zero_hint: "未填写现金时，投资组合默认从 0 开始。", existing_holdings: "已有持仓", opening_positions: "起始持仓", opening_optional_hint: "可选。现在录入已持有股票，也可在第一笔交易或现金记录前稍后添加。", add_position: "添加一行持仓", start_empty: "从零开始", save_and_continue: "保存并继续 ↗", ticker: "标的", shares: "股数", average_cost: "平均成本", position_type_optional: "仓位类型（可选）", unspecified: "未分类", remove: "移除", invalid_cash: "现金必须是零或正数，且最多 8 位小数。", incomplete_position: "请完整填写标的、股数和平均成本，或移除此行。", invalid_positive_decimal: "请输入正数，且最多 8 位小数。", duplicate_position: "同一标的与仓位类型组合不能重复。", setup_saving: "正在保存起始状态…", setup_unknown: "投资组合设置结果未知。请勿自动重试；刷新页面以恢复当前状态。",
    workspace_navigation: "工作区导航", primary_navigation: "主要导航", new_question: "新问题", ask_nav: "提问", portfolio_nav: "投资组合", question_history: "问题记录", session_only: "仅当前标签页", no_questions: "还没有问题。", signed_in_as: "当前账户", context_aware: "上下文感知决策支持", chat_view_title: "投资问题", structured_state: "结构化状态", portfolio_manage_title: "投资组合工作区", portfolio_manage_summary: "查看确定性状态，或追加不可变交易与现金记录。", portfolio_ready: "投资组合已加载", portfolio_loading: "正在加载投资组合", portfolio_stale: "需要刷新", idle: "空闲", submitting: "正在保存", refresh_required: "需要刷新",
    chat_intro_eyebrow: "你的投资组合已连接", chat_intro_title: "你正在思考什么投资决策？", chat_intro_body: "提出一个具体问题。PositionPilot 会使用你的持仓及问题所需的当前信息。", no_memory_notice: "问题仅保留在当前浏览器标签页，不构成模型记忆。", investment_question: "投资问题", question_placeholder: "例如：GOOG 今天还能加一点吗？", question_ready: "将使用你的当前投资组合。", ask: "询问 PositionPilot ↗", asking: "分析中…",
    portfolio_reload: "刷新", portfolio_sections: "投资组合分区", overview_tab: "持仓", trade_tab: "交易", cash_tab: "现金记录", available_cash: "可用现金", ledger_derived: "账本计算 · USD", portfolio_context: "投资组合上下文", session_owned: "当前 Session 所属", session_owned_hint: "身份来自你的本地私有 Session。", opening_state: "起始状态", existing_positions_setup: "添加已有持仓", starting_facts: "一次性起始事实", opening_explainer: "记录开始跟踪前已经持有的仓位，不改变现金，也不创建虚假交易。", skip_for_now: "暂时跳过", save_opening_positions: "保存已有持仓", add_existing_positions: "添加已有持仓", open_positions: "当前持仓", portfolio_empty_loaded: "目前没有持仓。", opening_records: "起始持仓记录", records_empty: "暂无记录。",
    transaction_entry: "交易", trade_entry: "交易记录", immutable_entry: "追加不可变记录", action: "操作", price: "价格", occurred_at_optional: "发生时间（可选）", occurred_at_hint: "留空使用后端应用时间。", reason_optional: "原因（可选）", save_trade: "保存交易", transaction_history: "交易历史", cash_activity: "现金活动", cash_entry: "现金记录", cash_event_type: "现金类型", amount: "金额", save_cash: "保存现金记录", cash_history: "现金历史", cost_basis: "成本基础", commission: "手续费", fee_schedule: "费用规则", occurred_at: "发生时间", reason: "原因", sequence: "序号", recorded_at: "记录时间", not_provided: "未填写", trade_saved: "交易已保存", cash_saved: "现金记录已保存", opening_saved: "已有持仓已保存", mutation_unknown: "结果未知。请勿自动重试，请刷新并检查最新投资组合状态。", refresh_failed: "写入可能已成功，但最新投资组合加载失败。继续前请先刷新。", invalid_form: "请检查标记的字段后再提交。", insufficient_cash: "可用现金不足以覆盖本次买入及后端计算的费用。", insufficient_shares: "该仓位类型下的股数不足。", opening_sealed: "已有持仓只能在第一笔交易或现金记录前添加。", future_time: "发生时间不能晚于当前时间。", session_expired: "本地 Session 已过期，请重新登录。",
    working_title: "正在整理决策上下文", working_answer: "正在读取你的投资组合并选择当前信息。", answer_label: "回答", sources_used: "使用的来源", source_explainer: "支持本次回答的上下文。", answer_ready: "基于投资组合的回答", answer_degraded: "上下文有限的回答", answer_failed: "暂时无法回答", source_ticker: "标的", source_provider: "数据提供方", source_feed: "数据源", source_market_time: "市场时间", source_fetched: "获取时间", source_portfolio: "投资组合持仓与现金", source_quote: "当前市场报价", source_history: "价格历史", source_news: "近期新闻", source_market: "市场环境", no_sources: "本次未返回支持来源。", question_required: "请输入一个具体的投资问题。", question_failed: "PositionPilot 未能完成本次问题，请查看状态后重试。",
  },
};

const state = {
  language: "en",
  account: null,
  loadedUserId: null,
  snapshot: null,
  openingRecords: [],
  transactionRecords: [],
  cashRecords: [],
  openingDismissed: false,
  writeState: "idle",
  portfolioReadState: "idle",
  authTransition: "idle",
  authGeneration: 0,
  portfolioGeneration: 0,
  questionGeneration: 0,
  portfolioController: null,
  questionController: null,
  questionPending: false,
  pendingQuestionView: null,
  questionCount: 0,
  activeView: "chat",
};

const DECIMAL_PATTERN = /^(?:0|[1-9]\d*)(?:\.\d{1,8})?$/;
const SOURCE_LABELS = {
  PORTFOLIO_SNAPSHOT: "source_portfolio",
  CURRENT_QUOTE: "source_quote",
  PRICE_HISTORY: "source_history",
  RECENT_NEWS: "source_news",
  MARKET_CONTEXT: "source_market",
};
const ERROR_LABELS = {
  HTTP_500: "unexpected_server_error",
  AUTHENTICATION_REQUIRED: "session_expired",
  PORTFOLIO_SETUP_REQUIRED: "setup_required",
  PORTFOLIO_NOT_FOUND: "portfolio_unavailable",
  USER_NOT_FOUND: "portfolio_unavailable",
  INVALID_CREDENTIALS: "invalid_credentials",
  EMAIL_ALREADY_REGISTERED: "email_registered",
  INVALID_ACCOUNT: "invalid_account",
  PORTFOLIO_ALREADY_EXISTS: "portfolio_already_exists",
  INVALID_PORTFOLIO: "invalid_portfolio",
  INVALID_OPENING_STATE: "invalid_opening_state",
  INVALID_TRANSACTION: "invalid_transaction",
  INVALID_CASH_EVENT: "invalid_cash_event",
  VALIDATION_ERROR: "invalid_form",
  INSUFFICIENT_CASH: "insufficient_cash",
  INSUFFICIENT_SHARES: "insufficient_shares",
  OPENING_STATE_SEALED: "opening_sealed",
  FUTURE_TIMESTAMP: "future_time",
  INVALID_QUESTION: "question_failed",
  INVALID_TOOL_CALL: "question_failed",
  TOOL_CALL_LIMIT_EXCEEDED: "question_failed",
  TOOL_ROUND_LIMIT_EXCEEDED: "question_failed",
  LLM_INVALID_REQUEST: "question_failed",
  LLM_AUTHENTICATION_FAILED: "question_failed",
  LLM_RATE_LIMITED: "question_failed",
  LLM_PROVIDER_UNAVAILABLE: "question_failed",
  LLM_INVALID_PROVIDER_RESPONSE: "question_failed",
};

function byId(id) {
  return document.getElementById(id);
}

const elements = {
  languageToggle: byId("language-toggle"), engineeringSmokeBanner: byId("engineering-smoke-banner"), homeView: byId("home-view"), authView: byId("auth-view"), setupView: byId("setup-view"), appShell: byId("app-shell"),
  homeRegister: byId("home-register-button"), homeLogin: byId("home-login-button"), heroRegister: byId("hero-register-button"), heroLogin: byId("hero-login-button"), authHome: byId("auth-home-button"), authBack: byId("auth-back-button"), authTitle: byId("auth-title"),
  registerTab: byId("register-tab"), loginTab: byId("login-tab"), registerPanel: byId("register-panel"), loginPanel: byId("login-panel"), registerForm: byId("register-form"), registerFields: byId("register-fields"), registerName: byId("register-name"), registerEmail: byId("register-email"), registerPassword: byId("register-password"), registerConfirm: byId("register-confirm"), registerMessage: byId("register-message"), loginForm: byId("login-form"), loginFields: byId("login-fields"), loginEmail: byId("login-email"), loginPassword: byId("login-password"), loginMessage: byId("login-message"),
  setupAccountName: byId("setup-account-name"), setupLogout: byId("setup-logout-button"), setupForm: byId("setup-form"), setupFields: byId("setup-fields"), setupCash: byId("setup-initial-cash"), setupRows: byId("setup-draft-rows"), setupAddRow: byId("setup-add-row"), setupZero: byId("setup-zero-button"), setupMessage: byId("setup-message"),
  navChat: byId("nav-chat"), navPortfolio: byId("nav-portfolio"), newQuestion: byId("new-question-button"), chatView: byId("chat-view"), portfolioView: byId("portfolio-view"), viewTitle: byId("view-title"), viewEyebrow: byId("view-eyebrow"), portfolioState: byId("portfolio-state"), writeState: byId("write-state"), reloadPortfolio: byId("reload-portfolio-button"), accountName: byId("account-display-name"), accountEmail: byId("account-email"), headerAccountName: byId("header-account-name"), headerAccountInitial: byId("header-account-initial"), accountMessage: byId("account-message"), logout: byId("logout-button"), headerLogout: byId("header-logout-button"),
  chatIntro: byId("chat-intro"), conversationScroll: byId("conversation-scroll"), conversationList: byId("conversation-list"), sessionEmpty: byId("session-empty"), sessionList: byId("session-list"), questionForm: byId("question-form"), question: byId("question"), questionHint: byId("question-hint"), ask: byId("ask-button"), responseTemplate: byId("assistant-response-template"),
  portfolioTabs: [byId("portfolio-tab-overview"), byId("portfolio-tab-trade"), byId("portfolio-tab-cash")], portfolioPanels: [byId("portfolio-overview-panel"), byId("portfolio-trade-panel"), byId("portfolio-cash-panel")], availableCash: byId("available-cash"), positionCount: byId("position-count"), positionsEmpty: byId("positions-empty"), positionList: byId("position-list"),
  openingSetup: byId("opening-setup"), reopenOpening: byId("reopen-opening-setup"), openingForm: byId("opening-form"), openingFields: byId("opening-fields"), openingRows: byId("opening-draft-rows"), addOpeningRow: byId("add-opening-row"), skipOpening: byId("skip-opening-setup"), openingMessage: byId("opening-message"), openingRecordCount: byId("opening-record-count"), openingRecordsEmpty: byId("opening-records-empty"), openingRecordList: byId("opening-record-list"),
  tradeForm: byId("trade-form"), tradeFields: byId("trade-fields"), tradeAction: byId("trade-action"), tradeType: byId("trade-position-type"), tradeTicker: byId("trade-ticker"), tradePrice: byId("trade-price"), tradeShares: byId("trade-shares"), tradeTime: byId("trade-occurred-at"), tradeReason: byId("trade-reason"), tradeMessage: byId("trade-message"), transactionCount: byId("transaction-count"), transactionsEmpty: byId("transactions-empty"), transactionList: byId("transaction-list"),
  cashForm: byId("cash-form"), cashFields: byId("cash-fields"), cashType: byId("cash-event-type"), cashAmount: byId("cash-amount"), cashTime: byId("cash-occurred-at"), cashReason: byId("cash-reason"), cashMessage: byId("cash-message"), cashCount: byId("cash-event-count"), cashEmpty: byId("cash-events-empty"), cashList: byId("cash-event-list"),
};

function translate(key) {
  return translations[state.language][key] ?? translations.en[key] ?? key;
}

function setLocalizedText(element, key) {
  if (!element) return;
  element.dataset.i18n = key;
  element.textContent = translate(key);
}

function setMessage(element, keyOrText, tone = "danger", localized = true) {
  element.dataset.tone = tone;
  if (localized) {
    element.dataset.i18n = keyOrText;
    element.textContent = translate(keyOrText);
  } else {
    delete element.dataset.i18n;
    element.textContent = keyOrText;
  }
}

function clearMessage(element) {
  delete element.dataset.i18n;
  element.textContent = "";
}

function clearElement(element) {
  element.replaceChildren();
}

function makeElement(tag, className = "", text = "") {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== "") element.textContent = text;
  return element;
}

function applyTranslations() {
  document.documentElement.lang = state.language === "zh" ? "zh-CN" : "en";
  document.querySelectorAll("[data-i18n]").forEach((element) => {
    element.textContent = translate(element.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
    element.placeholder = translate(element.dataset.i18nPlaceholder);
  });
  document.querySelectorAll("[data-i18n-aria-label]").forEach((element) => {
    element.setAttribute("aria-label", translate(element.dataset.i18nAriaLabel));
  });
  document.querySelectorAll("[data-i18n-content]").forEach((element) => {
    element.setAttribute("content", translate(element.dataset.i18nContent));
  });
  elements.languageToggle.textContent = state.language === "en" ? "中文" : "EN";
  elements.languageToggle.setAttribute("aria-label", state.language === "en" ? "切换到中文" : "Switch to English");
  document.querySelectorAll("[data-timestamp]").forEach((element) => {
    element.textContent = formatTimestamp(element.dataset.timestamp);
  });
  renderPortfolioState();
  renderWriteState();
}

function showOnly(view) {
  for (const section of [elements.homeView, elements.authView, elements.setupView, elements.appShell]) section.hidden = section !== view;
}

class ApiError extends Error {
  constructor(status, code, message) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: options.body ? { "Content-Type": "application/json", ...(options.headers ?? {}) } : options.headers,
  });
  let payload = null;
  if (response.status !== 204) {
    try { payload = await response.json(); } catch { payload = null; }
  }
  if (!response.ok) {
    const detail = payload?.detail;
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) => {
          const path = Array.isArray(item?.loc) ? item.loc.filter((part) => part !== "body").join(".") : "";
          const message = typeof item?.msg === "string" ? item.msg : "";
          return path && message ? `${path}: ${message}` : message || path;
        })
        .filter(Boolean);
      throw new ApiError(response.status, "VALIDATION_ERROR", messages.join("; ") || `HTTP ${response.status}`);
    }
    if (typeof detail === "string") throw new ApiError(response.status, `HTTP_${response.status}`, detail);
    throw new ApiError(response.status, detail?.code ?? `HTTP_${response.status}`, detail?.message ?? `HTTP ${response.status}`);
  }
  return payload;
}

function apiMessageKey(error) {
  return ERROR_LABELS[error.code] ?? "unexpected_server_error";
}

function formatDecimal(value) {
  const raw = String(value ?? "0");
  const [integerRaw, fractionRaw = ""] = raw.split(".");
  const integer = integerRaw.replace(/^(-?)0+(?=\d)/, "$1");
  const grouped = integer.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const fraction = fractionRaw.replace(/0+$/, "");
  return fraction ? `${grouped}.${fraction}` : grouped;
}

function formatMoney(value) {
  return `$${formatDecimal(value)}`;
}

function formatTimestamp(value) {
  if (!value) return translate("not_provided");
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat(state.language === "zh" ? "zh-CN" : "en-US", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function clearFieldErrors(scope) {
  scope.querySelectorAll("[aria-invalid='true']").forEach((field) => field.removeAttribute("aria-invalid"));
  scope.querySelectorAll(".field-error").forEach((error) => error.remove());
}

function showFieldError(field, key) {
  field.setAttribute("aria-invalid", "true");
  const error = makeElement("p", "field-error", translate(key));
  error.setAttribute("role", "alert");
  field.insertAdjacentElement("afterend", error);
}

function setAuthMode(mode) {
  const register = mode === "register";
  elements.registerPanel.hidden = !register;
  elements.loginPanel.hidden = register;
  elements.registerTab.classList.toggle("is-active", register);
  elements.loginTab.classList.toggle("is-active", !register);
  elements.registerTab.setAttribute("aria-selected", String(register));
  elements.loginTab.setAttribute("aria-selected", String(!register));
  setLocalizedText(elements.authTitle, register ? "register_title" : "login_title");
  showOnly(elements.authView);
  (register ? elements.registerName : elements.loginEmail).focus();
}

function createOpeningRow(container) {
  const row = makeElement("div", "opening-draft-row");
  const rowId = crypto.randomUUID();
  const fields = makeElement("div", "opening-row-fields");
  const tickerWrap = makeElement("div");
  const tickerLabel = makeElement("label"); setLocalizedText(tickerLabel, "ticker");
  const ticker = makeElement("input"); ticker.id = `opening-${rowId}-ticker`; ticker.type = "text"; ticker.maxLength = 10; ticker.autocomplete = "off"; ticker.dataset.field = "ticker"; tickerLabel.htmlFor = ticker.id;
  tickerWrap.append(tickerLabel, ticker);
  const sharesWrap = makeElement("div");
  const sharesLabel = makeElement("label"); setLocalizedText(sharesLabel, "shares");
  const shares = makeElement("input"); shares.id = `opening-${rowId}-shares`; shares.type = "text"; shares.inputMode = "decimal"; shares.autocomplete = "off"; shares.dataset.field = "shares"; sharesLabel.htmlFor = shares.id;
  sharesWrap.append(sharesLabel, shares);
  const costWrap = makeElement("div");
  const costLabel = makeElement("label"); setLocalizedText(costLabel, "average_cost");
  const cost = makeElement("input"); cost.id = `opening-${rowId}-cost`; cost.type = "text"; cost.inputMode = "decimal"; cost.autocomplete = "off"; cost.dataset.field = "average_cost"; costLabel.htmlFor = cost.id;
  costWrap.append(costLabel, cost);
  const typeWrap = makeElement("div");
  const typeLabel = makeElement("label"); setLocalizedText(typeLabel, "position_type_optional");
  const type = makeElement("select"); type.id = `opening-${rowId}-type`; type.dataset.field = "position_type"; typeLabel.htmlFor = type.id;
  for (const [value, labelKey] of [["", "unspecified"], ["LONG_TERM", "LONG_TERM"], ["SWING", "SWING"]]) {
    const option = makeElement("option", "", labelKey === "unspecified" ? translate(labelKey) : labelKey); option.value = value; if (labelKey === "unspecified") option.dataset.i18n = labelKey; type.append(option);
  }
  typeWrap.append(typeLabel, type);
  const remove = makeElement("button", "text-button opening-remove", translate("remove")); remove.type = "button"; remove.dataset.i18n = "remove"; remove.addEventListener("click", () => row.remove());
  fields.append(tickerWrap, sharesWrap, costWrap, typeWrap);
  row.append(fields, remove); container.append(row);
  return row;
}

function collectOpeningPositions(container) {
  clearFieldErrors(container);
  const positions = [];
  const keys = new Set();
  let valid = true;
  for (const row of container.querySelectorAll(".opening-draft-row")) {
    const ticker = row.querySelector("[data-field='ticker']");
    const shares = row.querySelector("[data-field='shares']");
    const cost = row.querySelector("[data-field='average_cost']");
    const type = row.querySelector("[data-field='position_type']");
    const normalizedTicker = ticker.value.trim().toUpperCase();
    const any = normalizedTicker || shares.value.trim() || cost.value.trim() || type.value;
    if (!any) continue;
    if (!normalizedTicker || !shares.value.trim() || !cost.value.trim()) { showFieldError(!normalizedTicker ? ticker : !shares.value.trim() ? shares : cost, "incomplete_position"); valid = false; continue; }
    if (!isPositiveDecimal(shares.value.trim())) { showFieldError(shares, "invalid_positive_decimal"); valid = false; }
    if (!isPositiveDecimal(cost.value.trim())) { showFieldError(cost, "invalid_positive_decimal"); valid = false; }
    const key = `${normalizedTicker}:${type.value || "UNSPECIFIED"}`;
    if (keys.has(key)) { showFieldError(ticker, "duplicate_position"); valid = false; }
    keys.add(key);
    const item = { ticker: normalizedTicker, shares: shares.value.trim(), average_cost: cost.value.trim() };
    if (type.value) item.position_type = type.value;
    positions.push(item);
  }
  return valid ? positions : null;
}

function isPositiveDecimal(value) {
  return DECIMAL_PATTERN.test(value) && !/^0(?:\.0+)?$/.test(value);
}

function resetSensitiveState() {
  state.account = null;
  state.loadedUserId = null;
  state.snapshot = null;
  state.openingRecords = [];
  state.transactionRecords = [];
  state.cashRecords = [];
  state.openingDismissed = false;
  state.writeState = "idle";
  state.portfolioReadState = "idle";
  state.authTransition = "idle";
  state.portfolioGeneration += 1;
  state.questionGeneration += 1;
  state.portfolioController?.abort();
  state.questionController?.abort();
  state.portfolioController = null;
  state.questionController = null;
  state.questionPending = false;
  state.pendingQuestionView = null;
  state.questionCount = 0;
  clearElement(elements.conversationList);
  clearElement(elements.sessionList);
  elements.sessionEmpty.hidden = false;
  elements.chatIntro.hidden = false;
  elements.question.value = "";
  elements.setupForm.reset();
  elements.tradeForm.reset();
  elements.cashForm.reset();
  clearElement(elements.setupRows);
  clearElement(elements.openingRows);
  for (const message of [elements.setupMessage, elements.accountMessage, elements.openingMessage, elements.tradeMessage, elements.cashMessage]) clearMessage(message);
  elements.accountName.textContent = "";
  elements.accountEmail.textContent = "";
  elements.headerAccountName.textContent = "—";
  elements.headerAccountInitial.textContent = "—";
  elements.setupAccountName.textContent = "";
  renderPortfolioEmpty();
  updateControls();
}

function renderAccount() {
  if (!state.account) return;
  elements.accountName.textContent = state.account.display_name;
  elements.accountEmail.textContent = state.account.email;
  elements.headerAccountName.textContent = state.account.display_name;
  elements.headerAccountInitial.textContent = state.account.display_name.trim().slice(0, 1).toUpperCase() || "?";
  elements.setupAccountName.textContent = state.account.display_name;
}

function renderPortfolioState() {
  if (!elements.portfolioState) return;
  const key = state.portfolioReadState === "loading" ? "portfolio_loading" : state.writeState === "refresh_required" ? "portfolio_stale" : state.snapshot ? "portfolio_ready" : "portfolio_loading";
  setLocalizedText(elements.portfolioState, key);
  elements.portfolioState.dataset.tone = key === "portfolio_stale" ? "warning" : "success";
}

function renderWriteState() {
  if (!elements.writeState) return;
  setLocalizedText(elements.writeState, state.writeState);
  elements.writeState.dataset.tone = state.writeState === "refresh_required" ? "warning" : state.writeState === "submitting" ? "active" : "neutral";
}

function updateControls() {
  const writeBusy = state.writeState === "submitting";
  const readBusy = state.portfolioReadState === "loading";
  const authBusy = state.authTransition !== "idle";
  const busy = writeBusy || readBusy || authBusy || state.questionPending;
  const contextReady = Boolean(state.snapshot) && state.writeState !== "refresh_required";
  elements.logout.disabled = writeBusy || authBusy;
  elements.headerLogout.disabled = writeBusy || authBusy;
  elements.setupLogout.disabled = writeBusy || authBusy;
  elements.setupFields.disabled = authBusy || readBusy || state.writeState !== "idle";
  elements.reloadPortfolio.disabled = busy;
  elements.tradeFields.disabled = busy || !contextReady;
  elements.cashFields.disabled = busy || !contextReady;
  elements.openingFields.disabled = busy || !contextReady;
  elements.question.disabled = busy || !contextReady;
  elements.ask.disabled = busy || !contextReady;
  elements.navChat.disabled = busy;
  elements.navPortfolio.disabled = busy;
  elements.newQuestion.disabled = busy;
  renderPortfolioState();
  renderWriteState();
}

function enterHome(messageKey = null) {
  resetSensitiveState();
  showOnly(elements.homeView);
  if (messageKey) {
    setAuthMode("login");
    setMessage(elements.loginMessage, messageKey);
  }
}

function clearAuthSecrets() {
  elements.registerPassword.value = "";
  elements.registerConfirm.value = "";
  elements.loginPassword.value = "";
}

function setAuthNavigationDisabled(disabled) {
  for (const control of [elements.authHome, elements.authBack, elements.registerTab, elements.loginTab]) control.disabled = disabled;
}

async function restoreSession() {
  const generation = ++state.authGeneration;
  state.authTransition = "restoring";
  try {
    const payload = await requestJson("/v1/auth/session");
    if (generation !== state.authGeneration) return;
    state.authTransition = "idle";
    state.account = payload.account;
    renderAccount();
    if (state.account.portfolio_ready) {
      showOnly(elements.appShell);
      await refreshPortfolio();
    } else {
      showSetup();
    }
  } catch (error) {
    if (generation !== state.authGeneration) return;
    if (error instanceof ApiError && error.status === 401) enterHome();
    else {
      resetSensitiveState();
      setAuthMode("login");
      state.authTransition = "session_error";
      elements.registerFields.disabled = true;
      elements.loginFields.disabled = true;
      setAuthNavigationDisabled(true);
      setMessage(elements.loginMessage, "session_restore_failed");
    }
  }
}

function showSetup() {
  showOnly(elements.setupView);
  renderAccount();
  if (elements.setupRows.childElementCount === 0) createOpeningRow(elements.setupRows);
  elements.setupCash.focus();
}

function validateEmail(value) {
  return /^[^@\s]+@[^@\s]+$/.test(value);
}

async function handleRegister(event) {
  event.preventDefault();
  if (state.authTransition !== "idle") return;
  clearFieldErrors(elements.registerForm);
  clearMessage(elements.registerMessage);
  const name = elements.registerName.value.trim();
  const email = elements.registerEmail.value.trim();
  const password = elements.registerPassword.value;
  const confirm = elements.registerConfirm.value;
  let valid = true;
  if (!name) { showFieldError(elements.registerName, "required_fields"); valid = false; }
  if (!validateEmail(email)) { showFieldError(elements.registerEmail, "invalid_email"); valid = false; }
  if (password.length < 8 || password.length > 128) { showFieldError(elements.registerPassword, "invalid_password"); valid = false; }
  if (confirm !== password) { showFieldError(elements.registerConfirm, "password_mismatch"); valid = false; }
  if (!valid) { setMessage(elements.registerMessage, "invalid_form"); return; }
  const generation = ++state.authGeneration;
  state.authTransition = "registering";
  elements.registerFields.disabled = true;
  setAuthNavigationDisabled(true);
  setMessage(elements.registerMessage, "registering", "active");
  try {
    const payload = await requestJson("/v1/auth/register", { method: "POST", body: JSON.stringify({ display_name: name, email, password }) });
    if (generation !== state.authGeneration) return;
    state.authTransition = "idle";
    state.account = payload.account;
    elements.registerPassword.value = "";
    elements.registerConfirm.value = "";
    renderAccount();
    showSetup();
  } catch (error) {
    if (generation !== state.authGeneration) return;
    state.authTransition = "idle";
    if (error instanceof TypeError) setMessage(elements.registerMessage, "register_unknown");
    else if (error instanceof ApiError) setMessage(elements.registerMessage, apiMessageKey(error));
    else setMessage(elements.registerMessage, "login_network_error");
  } finally {
    if (generation === state.authGeneration) {
      state.authTransition = "idle";
      elements.registerFields.disabled = false;
      setAuthNavigationDisabled(false);
    }
  }
}

async function handleLogin(event) {
  event.preventDefault();
  if (state.authTransition !== "idle") return;
  clearFieldErrors(elements.loginForm);
  clearMessage(elements.loginMessage);
  const email = elements.loginEmail.value.trim();
  const password = elements.loginPassword.value;
  if (!validateEmail(email)) { showFieldError(elements.loginEmail, "invalid_email"); setMessage(elements.loginMessage, "invalid_form"); return; }
  if (!password || password.length > 128) { showFieldError(elements.loginPassword, "invalid_password"); setMessage(elements.loginMessage, "invalid_form"); return; }
  const generation = ++state.authGeneration;
  state.authTransition = "logging_in";
  elements.loginFields.disabled = true;
  setAuthNavigationDisabled(true);
  setMessage(elements.loginMessage, "logging_in", "active");
  try {
    const payload = await requestJson("/v1/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
    if (generation !== state.authGeneration) return;
    state.authTransition = "idle";
    state.account = payload.account;
    elements.loginPassword.value = "";
    renderAccount();
    if (state.account.portfolio_ready) { showOnly(elements.appShell); await refreshPortfolio(); } else showSetup();
  } catch (error) {
    if (generation !== state.authGeneration) return;
    state.authTransition = "idle";
    if (error instanceof TypeError) setMessage(elements.loginMessage, "login_network_error");
    else if (error instanceof ApiError) setMessage(elements.loginMessage, apiMessageKey(error));
    else setMessage(elements.loginMessage, "login_network_error");
  } finally {
    if (generation === state.authGeneration) {
      state.authTransition = "idle";
      elements.loginFields.disabled = false;
      setAuthNavigationDisabled(false);
    }
  }
}

async function logout() {
  if (state.authTransition !== "idle" || state.writeState === "submitting") return;
  const cancelledQuestionView = state.pendingQuestionView;
  state.portfolioGeneration += 1;
  state.questionGeneration += 1;
  state.portfolioController?.abort();
  state.questionController?.abort();
  state.portfolioController = null;
  state.questionController = null;
  state.portfolioReadState = "idle";
  state.questionPending = false;
  state.pendingQuestionView = null;
  state.authTransition = "logging_out";
  ++state.authGeneration;
  const messageElement = elements.setupView.hidden ? elements.accountMessage : elements.setupMessage;
  setMessage(messageElement, "logging_out", "active");
  updateControls();
  try {
    await requestJson("/v1/auth/logout", { method: "POST" });
    enterHome();
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) enterHome("session_expired");
    else {
      state.authTransition = "idle";
      if (cancelledQuestionView) renderQuestionError(cancelledQuestionView, new Error("Question cancelled during sign out"));
      setLocalizedText(elements.ask, "ask");
      setLocalizedText(elements.questionHint, "question_ready");
      setMessage(messageElement, "logout_failed");
      updateControls();
    }
  }
}

async function handleSetup(event, forceEmpty = false) {
  event?.preventDefault();
  if (state.writeState !== "idle" || state.authTransition !== "idle" || state.portfolioReadState !== "idle") return;
  clearFieldErrors(elements.setupForm);
  clearMessage(elements.setupMessage);
  const cash = forceEmpty ? "0" : (elements.setupCash.value.trim() || "0");
  if (!DECIMAL_PATTERN.test(cash)) { showFieldError(elements.setupCash, "invalid_cash"); setMessage(elements.setupMessage, "invalid_form"); return; }
  const positions = forceEmpty ? [] : collectOpeningPositions(elements.setupRows);
  if (positions === null) { setMessage(elements.setupMessage, "invalid_form"); return; }
  state.writeState = "submitting";
  updateControls();
  setMessage(elements.setupMessage, "setup_saving", "active");
  try {
    const snapshot = await requestJson("/v1/portfolio", { method: "POST", body: JSON.stringify({ initial_cash: cash, opening_positions: positions }) });
    state.account = { ...state.account, portfolio_ready: true };
    state.snapshot = snapshot;
    state.loadedUserId = snapshot.user_id;
    state.openingDismissed = positions.length === 0;
    clearElement(elements.setupRows);
    showOnly(elements.appShell);
    const refreshed = await refreshPortfolio({ afterMutation: true });
    if (!state.account) return;
    state.writeState = refreshed ? "idle" : "refresh_required";
  } catch (error) {
    state.writeState = error instanceof TypeError || (error instanceof ApiError && error.code === "PORTFOLIO_ALREADY_EXISTS") ? "refresh_required" : "idle";
    if (error instanceof TypeError) setMessage(elements.setupMessage, "setup_unknown");
    else if (error instanceof ApiError && error.status === 401) enterHome("session_expired");
    else if (error instanceof ApiError) setMessage(elements.setupMessage, apiMessageKey(error));
    else { state.writeState = "refresh_required"; setMessage(elements.setupMessage, "setup_unknown"); }
  } finally {
    updateControls();
  }
}

function renderPortfolioEmpty() {
  elements.availableCash.textContent = "—";
  elements.positionCount.textContent = "0";
  clearElement(elements.positionList);
  elements.positionsEmpty.hidden = false;
  for (const [list, count, empty] of [[elements.openingRecordList, elements.openingRecordCount, elements.openingRecordsEmpty], [elements.transactionList, elements.transactionCount, elements.transactionsEmpty], [elements.cashList, elements.cashCount, elements.cashEmpty]]) {
    clearElement(list); count.textContent = "0"; empty.hidden = false;
  }
}

function createFactList(facts) {
  const list = makeElement("dl", "record-facts");
  for (const [labelKey, value, mode] of facts) {
    const group = makeElement("div");
    const term = makeElement("dt"); setLocalizedText(term, labelKey);
    const description = makeElement("dd");
    if (mode === "timestamp") { description.dataset.timestamp = value; description.textContent = formatTimestamp(value); }
    else if (value === null || value === undefined || value === "") setLocalizedText(description, "not_provided");
    else description.textContent = mode === "decimal" ? formatDecimal(value) : String(value);
    group.append(term, description); list.append(group);
  }
  return list;
}

function createPositionCard(position) {
  const card = makeElement("article", "position-card");
  const heading = makeElement("div", "position-card-heading");
  const ticker = makeElement("strong", "", position.ticker);
  const badge = makeElement("span", "position-type", position.position_type === "UNSPECIFIED" ? translate("unspecified") : position.position_type);
  if (position.position_type === "UNSPECIFIED") badge.dataset.i18n = "unspecified";
  heading.append(ticker, badge);
  card.append(heading, createFactList([["shares", position.shares, "decimal"], ["average_cost", position.average_cost, "decimal"], ["cost_basis", position.cost_basis, "decimal"]]));
  return card;
}

function createRecordCard(title, badgeText, facts) {
  const card = makeElement("article", "record-card");
  const heading = makeElement("div", "position-card-heading");
  heading.append(makeElement("strong", "", title));
  if (badgeText) {
    const badge = makeElement("span", "position-type", badgeText === "UNSPECIFIED" ? translate("unspecified") : badgeText);
    if (badgeText === "UNSPECIFIED") badge.dataset.i18n = "unspecified";
    heading.append(badge);
  }
  card.append(heading, createFactList(facts));
  return card;
}

function renderRecordCollection(list, empty, count, records, factory) {
  clearElement(list);
  count.textContent = String(records.length);
  empty.hidden = records.length > 0;
  for (const record of records) list.append(factory(record));
}

function renderOpeningAvailability() {
  const eligible = state.openingRecords.length === 0 && state.transactionRecords.length === 0 && state.cashRecords.length === 0;
  elements.openingSetup.hidden = !eligible || state.openingDismissed;
  elements.reopenOpening.hidden = !eligible || !state.openingDismissed;
  if (eligible && !state.openingDismissed && elements.openingRows.childElementCount === 0) createOpeningRow(elements.openingRows);
}

function renderPortfolio() {
  const snapshot = state.snapshot;
  if (!snapshot) { renderPortfolioEmpty(); updateControls(); return; }
  elements.availableCash.textContent = formatMoney(snapshot.available_cash);
  elements.positionCount.textContent = String(snapshot.positions.length);
  clearElement(elements.positionList);
  elements.positionsEmpty.hidden = snapshot.positions.length > 0;
  for (const position of snapshot.positions) elements.positionList.append(createPositionCard(position));
  renderRecordCollection(elements.openingRecordList, elements.openingRecordsEmpty, elements.openingRecordCount, state.openingRecords, (record) => createRecordCard(record.ticker, record.position_type, [["shares", record.shares, "decimal"], ["average_cost", record.average_cost, "decimal"], ["cost_basis", record.cost_basis, "decimal"], ["recorded_at", record.recorded_at, "timestamp"]]));
  renderRecordCollection(elements.transactionList, elements.transactionsEmpty, elements.transactionCount, state.transactionRecords, (record) => createRecordCard(`${record.action} · ${record.ticker}`, record.position_type, [["sequence", record.sequence], ["price", record.price, "decimal"], ["shares", record.shares, "decimal"], ["amount", record.amount, "decimal"], ["commission", record.commission, "decimal"], ["fee_schedule", record.fee_schedule], ["occurred_at", record.occurred_at, "timestamp"], ["reason", record.reason]]));
  renderRecordCollection(elements.cashList, elements.cashEmpty, elements.cashCount, state.cashRecords, (record) => createRecordCard(record.event_type, null, [["sequence", record.sequence], ["amount", record.amount, "decimal"], ["occurred_at", record.occurred_at, "timestamp"], ["reason", record.reason]]));
  renderOpeningAvailability();
  updateControls();
}

async function refreshPortfolio({ afterMutation = false } = {}) {
  if (state.authTransition !== "idle" || state.questionPending || state.portfolioReadState !== "idle" || (state.writeState === "submitting" && !afterMutation)) return false;
  const generation = ++state.portfolioGeneration;
  state.portfolioController?.abort();
  const controller = new AbortController();
  state.portfolioController = controller;
  state.portfolioReadState = "loading";
  updateControls();
  try {
    const [snapshot, openings, transactions, cash] = await Promise.all([
      requestJson("/v1/portfolio", { signal: controller.signal }),
      requestJson("/v1/portfolio/opening-positions", { signal: controller.signal }),
      requestJson("/v1/portfolio/transactions", { signal: controller.signal }),
      requestJson("/v1/portfolio/cash-events", { signal: controller.signal }),
    ]);
    if (generation !== state.portfolioGeneration) return false;
    state.snapshot = snapshot;
    state.loadedUserId = snapshot.user_id;
    state.openingRecords = openings.items;
    state.transactionRecords = transactions.items;
    state.cashRecords = cash.items;
    if (!afterMutation) state.writeState = "idle";
    renderPortfolio();
    return true;
  } catch (error) {
    if (error?.name === "AbortError" || generation !== state.portfolioGeneration) return false;
    if (error instanceof ApiError && error.status === 401) { enterHome("session_expired"); return false; }
    state.writeState = "refresh_required";
    renderPortfolioState(); renderWriteState(); updateControls();
    return false;
  } finally {
    if (generation === state.portfolioGeneration) {
      state.portfolioController = null;
      state.portfolioReadState = "idle";
      updateControls();
    }
  }
}

function localDateTimeToIso(input) {
  const raw = input.value;
  if (!raw) return null;
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return null;
  return date.toISOString();
}

async function runMutation({ url, payload, messageElement, successKey, recordId }) {
  if (state.writeState !== "idle" || state.portfolioReadState !== "idle" || state.authTransition !== "idle" || state.questionPending || !state.loadedUserId || !state.snapshot) return false;
  const capturedUserId = state.loadedUserId;
  state.writeState = "submitting";
  clearMessage(messageElement);
  updateControls();
  try {
    const result = await requestJson(url, { method: "POST", body: JSON.stringify(payload) });
    if (state.loadedUserId !== capturedUserId) return false;
    const refreshed = await refreshPortfolio({ afterMutation: true });
    if (!refreshed) {
      if (!state.account) return false;
      state.writeState = "refresh_required";
      setMessage(messageElement, "refresh_failed");
      return false;
    }
    state.writeState = "idle";
    const id = recordId(result);
    setMessage(messageElement, id ? `${translate(successKey)} · ${id}` : translate(successKey), "success", false);
    return true;
  } catch (error) {
    if (error instanceof TypeError) { state.writeState = "refresh_required"; setMessage(messageElement, "mutation_unknown"); }
    else if (error instanceof ApiError && error.status === 401) enterHome("session_expired");
    else if (error instanceof ApiError) { state.writeState = "idle"; setMessage(messageElement, apiMessageKey(error)); }
    else { state.writeState = "refresh_required"; setMessage(messageElement, "mutation_unknown"); }
    return false;
  } finally {
    if (state.writeState === "submitting") state.writeState = "idle";
    updateControls();
  }
}

function validateRequiredPositive(field) {
  const value = field.value.trim();
  if (!isPositiveDecimal(value)) { showFieldError(field, "invalid_positive_decimal"); return null; }
  return value;
}

async function handleTrade(event) {
  event.preventDefault();
  clearFieldErrors(elements.tradeForm);
  clearMessage(elements.tradeMessage);
  const ticker = elements.tradeTicker.value.trim().toUpperCase();
  if (!ticker) showFieldError(elements.tradeTicker, "required_fields");
  const price = validateRequiredPositive(elements.tradePrice);
  const shares = validateRequiredPositive(elements.tradeShares);
  if (!ticker || !price || !shares) { setMessage(elements.tradeMessage, "invalid_form"); return; }
  const payload = { ticker, action: elements.tradeAction.value, price, shares };
  if (elements.tradeType.value) payload.position_type = elements.tradeType.value;
  const occurredAt = localDateTimeToIso(elements.tradeTime);
  if (elements.tradeTime.value && !occurredAt) { showFieldError(elements.tradeTime, "invalid_form"); setMessage(elements.tradeMessage, "invalid_form"); return; }
  if (occurredAt) payload.occurred_at = occurredAt;
  if (elements.tradeReason.value.trim()) payload.reason = elements.tradeReason.value.trim();
  const saved = await runMutation({ url: "/v1/portfolio/transactions", payload, messageElement: elements.tradeMessage, successKey: "trade_saved", recordId: (result) => result.transaction?.id });
  if (saved) { elements.tradeTicker.value = ""; elements.tradePrice.value = ""; elements.tradeShares.value = ""; elements.tradeTime.value = ""; elements.tradeReason.value = ""; }
}

async function handleCash(event) {
  event.preventDefault();
  clearFieldErrors(elements.cashForm);
  clearMessage(elements.cashMessage);
  const amount = validateRequiredPositive(elements.cashAmount);
  if (!amount) { setMessage(elements.cashMessage, "invalid_form"); return; }
  const payload = { event_type: elements.cashType.value, amount };
  const occurredAt = localDateTimeToIso(elements.cashTime);
  if (elements.cashTime.value && !occurredAt) { showFieldError(elements.cashTime, "invalid_form"); setMessage(elements.cashMessage, "invalid_form"); return; }
  if (occurredAt) payload.occurred_at = occurredAt;
  if (elements.cashReason.value.trim()) payload.reason = elements.cashReason.value.trim();
  const saved = await runMutation({ url: "/v1/portfolio/cash-events", payload, messageElement: elements.cashMessage, successKey: "cash_saved", recordId: (result) => result.cash_event?.id });
  if (saved) { elements.cashAmount.value = ""; elements.cashTime.value = ""; elements.cashReason.value = ""; }
}

async function handleOpening(event) {
  event.preventDefault();
  const positions = collectOpeningPositions(elements.openingRows);
  if (!positions || positions.length === 0) { setMessage(elements.openingMessage, "invalid_form"); return; }
  const saved = await runMutation({ url: "/v1/portfolio/opening-positions", payload: { positions }, messageElement: elements.openingMessage, successKey: "opening_saved", recordId: (result) => result.opening_positions?.[0]?.id });
  if (saved) clearElement(elements.openingRows);
}

function sourceTone(status) {
  if (status === "OK") return "success";
  if (status === "NO_DATA") return "neutral";
  return "warning";
}

function createSourceCard(source) {
  const card = makeElement("article", "source-card");
  card.dataset.tone = sourceTone(source.status);
  const top = makeElement("div", "source-card-top");
  const title = makeElement("strong");
  const labelKey = SOURCE_LABELS[source.type];
  if (labelKey) setLocalizedText(title, labelKey); else title.textContent = source.type;
  top.append(title, makeElement("span", "source-status", source.status));
  const metadata = makeElement("div", "source-metadata");
  for (const [key, value, mode] of [["source_ticker", source.ticker], ["source_provider", source.provider], ["source_feed", source.feed], ["source_market_time", source.market_timestamp, "timestamp"], ["source_fetched", source.fetched_at, "timestamp"]]) {
    if (!value) continue;
    const item = makeElement("div", "source-metadata-item");
    const label = makeElement("span", "source-metadata-label"); setLocalizedText(label, key);
    const content = makeElement("span", "source-metadata-value");
    if (mode === "timestamp") { content.dataset.timestamp = value; content.textContent = formatTimestamp(value); } else content.textContent = value;
    item.append(label, content); metadata.append(item);
  }
  card.append(top, metadata); return card;
}

function createQuestionExchange(question) {
  state.questionCount += 1;
  const exchange = makeElement("section", "conversation-exchange");
  exchange.id = `question-${state.questionCount}`;
  exchange.append(makeElement("div", "user-message", question));
  const fragment = elements.responseTemplate.content.cloneNode(true);
  const assistant = fragment.querySelector(".assistant-message");
  const view = { title: fragment.querySelector(".result-title"), status: fragment.querySelector(".response-status"), answer: fragment.querySelector(".answer-copy"), details: fragment.querySelector(".source-disclosure"), count: fragment.querySelector(".source-count"), sources: fragment.querySelector(".source-list") };
  setLocalizedText(view.title, "working_title");
  setLocalizedText(view.answer, "working_answer");
  setLocalizedText(fragment.querySelector(".answer-label"), "answer_label");
  setLocalizedText(fragment.querySelector(".source-disclosure summary span:first-child"), "sources_used");
  setLocalizedText(fragment.querySelector(".source-explainer"), "source_explainer");
  assistant.setAttribute("aria-live", "polite");
  exchange.append(fragment);
  elements.conversationList.append(exchange);
  elements.chatIntro.hidden = true;
  elements.sessionEmpty.hidden = true;
  const history = makeElement("button", "session-question", question.length > 54 ? `${question.slice(0, 53)}…` : question);
  history.type = "button";
  history.addEventListener("click", () => { switchAppView("chat", false); exchange.scrollIntoView({ block: "start" }); });
  elements.sessionList.append(history);
  elements.conversationScroll.scrollTop = elements.conversationScroll.scrollHeight;
  return view;
}

function renderQuestionResult(view, payload) {
  setLocalizedText(view.title, payload.status === "DEGRADED" ? "answer_degraded" : "answer_ready");
  view.status.textContent = payload.status;
  view.status.dataset.tone = payload.status === "DEGRADED" ? "warning" : "success";
  view.answer.textContent = payload.answer;
  view.count.textContent = String(payload.sources.length);
  clearElement(view.sources);
  if (payload.sources.length === 0) { const empty = makeElement("p", "source-placeholder"); setLocalizedText(empty, "no_sources"); view.sources.append(empty); }
  else for (const source of payload.sources) view.sources.append(createSourceCard(source));
  view.details.open = false;
}

function renderQuestionError(view, error) {
  setLocalizedText(view.title, "answer_failed");
  view.status.textContent = error.code ?? "ERROR";
  view.status.dataset.tone = "danger";
  setLocalizedText(view.answer, error instanceof ApiError ? apiMessageKey(error) : "question_failed");
  view.count.textContent = "0";
  clearElement(view.sources);
  view.details.open = false;
}

async function handleQuestion(event) {
  event.preventDefault();
  const question = elements.question.value.trim();
  if (!question) { setMessage(elements.questionHint, "question_required"); elements.question.focus(); return; }
  if (state.questionPending || state.writeState !== "idle" || state.portfolioReadState !== "idle" || state.authTransition !== "idle" || !state.loadedUserId || !state.snapshot) return;
  const capturedUserId = state.loadedUserId;
  const generation = ++state.questionGeneration;
  state.questionController?.abort();
  const controller = new AbortController();
  state.questionController = controller;
  state.questionPending = true;
  setLocalizedText(elements.ask, "asking");
  updateControls();
  const view = createQuestionExchange(question);
  state.pendingQuestionView = view;
  elements.question.value = "";
  try {
    const payload = await requestJson("/v1/investment/questions", { method: "POST", body: JSON.stringify({ question }), signal: controller.signal });
    if (generation !== state.questionGeneration || capturedUserId !== state.loadedUserId) return;
    renderQuestionResult(view, payload);
  } catch (error) {
    if (error?.name === "AbortError" || generation !== state.questionGeneration || capturedUserId !== state.loadedUserId) return;
    if (error instanceof ApiError && error.status === 401) enterHome("session_expired");
    else renderQuestionError(view, error);
  } finally {
    if (generation === state.questionGeneration) { state.questionPending = false; state.pendingQuestionView = null; state.questionController = null; setLocalizedText(elements.ask, "ask"); setLocalizedText(elements.questionHint, "question_ready"); updateControls(); }
  }
}

function switchAppView(view, focus = true) {
  state.activeView = view;
  const chat = view === "chat";
  elements.chatView.hidden = !chat;
  elements.portfolioView.hidden = chat;
  elements.navChat.classList.toggle("is-active", chat);
  elements.navPortfolio.classList.toggle("is-active", !chat);
  elements.navChat.toggleAttribute("aria-current", chat);
  elements.navPortfolio.toggleAttribute("aria-current", !chat);
  setLocalizedText(elements.viewEyebrow, chat ? "context_aware" : "structured_state");
  setLocalizedText(elements.viewTitle, chat ? "chat_view_title" : "portfolio_manage_title");
  if (focus) elements.viewTitle.focus();
}

function switchPortfolioTab(index) {
  elements.portfolioTabs.forEach((tab, itemIndex) => { const active = itemIndex === index; tab.classList.toggle("is-active", active); tab.setAttribute("aria-selected", String(active)); elements.portfolioPanels[itemIndex].hidden = !active; });
}

function bindEvents() {
  elements.languageToggle.addEventListener("click", () => { state.language = state.language === "en" ? "zh" : "en"; applyTranslations(); renderPortfolio(); });
  for (const button of [elements.homeRegister, elements.heroRegister]) button.addEventListener("click", () => { if (state.authTransition === "idle") setAuthMode("register"); });
  for (const button of [elements.homeLogin, elements.heroLogin]) button.addEventListener("click", () => { if (state.authTransition === "idle") setAuthMode("login"); });
  for (const button of [elements.authHome, elements.authBack]) button.addEventListener("click", () => { if (state.authTransition !== "idle") return; state.authGeneration += 1; clearAuthSecrets(); showOnly(elements.homeView); });
  elements.registerTab.addEventListener("click", () => { if (state.authTransition === "idle") setAuthMode("register"); });
  elements.loginTab.addEventListener("click", () => { if (state.authTransition === "idle") setAuthMode("login"); });
  elements.registerForm.addEventListener("submit", handleRegister);
  elements.loginForm.addEventListener("submit", handleLogin);
  elements.setupForm.addEventListener("submit", (event) => handleSetup(event));
  elements.setupZero.addEventListener("click", () => handleSetup(null, true));
  elements.setupAddRow.addEventListener("click", () => createOpeningRow(elements.setupRows));
  elements.logout.addEventListener("click", logout);
  elements.headerLogout.addEventListener("click", logout);
  elements.setupLogout.addEventListener("click", logout);
  elements.navChat.addEventListener("click", () => switchAppView("chat"));
  elements.navPortfolio.addEventListener("click", () => switchAppView("portfolio"));
  elements.newQuestion.addEventListener("click", () => { switchAppView("chat", false); elements.question.focus(); });
  elements.portfolioTabs.forEach((tab, index) => tab.addEventListener("click", () => switchPortfolioTab(index)));
  elements.reloadPortfolio.addEventListener("click", () => refreshPortfolio());
  elements.addOpeningRow.addEventListener("click", () => createOpeningRow(elements.openingRows));
  elements.skipOpening.addEventListener("click", () => { state.openingDismissed = true; renderOpeningAvailability(); });
  elements.reopenOpening.addEventListener("click", () => { state.openingDismissed = false; renderOpeningAvailability(); });
  elements.openingForm.addEventListener("submit", handleOpening);
  elements.tradeForm.addEventListener("submit", handleTrade);
  elements.cashForm.addEventListener("submit", handleCash);
  elements.questionForm.addEventListener("submit", handleQuestion);
}

state.language = navigator.language?.toLowerCase().startsWith("zh") ? "zh" : "en";
elements.engineeringSmokeBanner.hidden = new URLSearchParams(window.location.search).get("engineering_smoke") !== "1";
bindEvents();
applyTranslations();
renderPortfolioEmpty();
updateControls();
restoreSession();
