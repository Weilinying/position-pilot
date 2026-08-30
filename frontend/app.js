const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const LOCAL_POINTER_KEY = "positionpilot.local-portfolio.v1";
const DECIMAL_INPUT_PATTERN = /^\d+(?:\.\d{1,8})?$/;

const translations = {
  en: {
    meta_description:
      "PositionPilot — investment decision support grounded in your portfolio and current market context.",
    brand_home: "PositionPilot home",
    language_switch: "Switch to Chinese",
    language_target: "中文",
    local_workspace: "Local decision workspace",
    onboarding_eyebrow: "Portfolio-grounded AI",
    onboarding_title: "Start with the state that makes every answer yours.",
    onboarding_summary:
      "Create a local portfolio or recover an existing one. No account or cloud registration is required.",
    local_only_notice: "Local-only workspace · UUID is a recovery pointer, not a credential.",
    new_workspace: "New workspace",
    existing_workspace: "Existing workspace",
    recover_portfolio: "Recover with UUID",
    back_to_workspace: "Back to workspace",
    workspace_navigation: "Workspace navigation",
    primary_navigation: "Primary navigation",
    new_question: "New question",
    ask_nav: "Ask",
    portfolio_nav: "Portfolio",
    this_session: "This session",
    question_history: "Question history",
    session_only: "Not saved",
    no_questions: "No questions yet.",
    current_portfolio: "Current portfolio",
    switch_portfolio: "Switch or recover",
    chat_view_title: "Decision questions",
    portfolio_manage_title: "Portfolio workspace",
    portfolio_manage_summary:
      "Review deterministic state or append an immutable trade or cash record.",
    portfolio_sections: "Portfolio sections",
    overview_tab: "Positions",
    trade_tab: "Transactions",
    cash_tab: "Cash activity",
    uuid_boundary: "Local recovery pointer · not a credential",
    transaction_entry: "Transaction",
    cash_activity: "Cash activity",
    chat_intro_eyebrow: "Your portfolio is connected",
    chat_intro_title: "What decision are you working through?",
    chat_intro_body:
      "Ask one focused question. PositionPilot will use your loaded portfolio and only the market context the question needs.",
    no_memory_notice: "Questions remain in this browser tab only and are not model memory.",
    question_jump: "Jump to question",
    structured_state: "Structured state",
    your_portfolio: "Your portfolio",
    start_here: "Start here",
    create_portfolio: "Create a local portfolio",
    portfolio_name: "Portfolio name",
    portfolio_name_placeholder: "e.g. Long-term plan",
    initial_cash: "Initial cash",
    initial_cash_placeholder: "0.00",
    create_hint:
      "Defaults to 0. Enter the cash available when PositionPilot starts tracking this portfolio.",
    create: "Create portfolio",
    creating: "Creating…",
    create_success: "Portfolio created and loaded.",
    create_refresh_failed:
      "Portfolio created, but refreshing its current state failed. Use Load to try again.",
    create_response_unknown: "Portfolio creation result unknown. Do not automatically retry.",
    create_contract_error:
      "The portfolio creation response was invalid. The result may be unknown; do not automatically retry.",
    create_service_unreachable:
      "The portfolio service could not be reached. The creation result is unknown.",
    forget_pointer: "Forget local pointer",
    forget_success: "Local pointer forgotten. The server portfolio was not deleted.",
    portfolio_not_loaded: "Not loaded",
    portfolio_stale: "Stale",
    portfolio_loading: "Loading…",
    portfolio_loaded: "Loaded",
    portfolio_invalid_id: "Invalid ID",
    portfolio_network_error: "Network error",
    portfolio_invalid_response: "Invalid response",
    portfolio_identity_mismatch: "Identity mismatch",
    portfolio_user_id: "Portfolio User ID",
    load: "Load",
    loading: "Loading…",
    seed_hint: "Use an existing UUID to recover a local portfolio.",
    available_cash: "Available cash",
    ledger_derived: "Ledger-derived · USD",
    open_positions: "Open positions",
    portfolio_empty_initial: "Load a portfolio to reveal the complete current position set.",
    portfolio_empty_loaded: "This portfolio currently has no open positions.",
    context_aware: "Context-aware decision support",
    hero_title: "Know the position. Read the moment.",
    hero_summary:
      "Ask a focused investment question. PositionPilot combines your actual ledger state with only the market context the question needs.",
    investment_question: "Investment question",
    question_placeholder: "For example: Can I add a little more GOOG today?",
    question_load_first: "Load a portfolio before asking.",
    question_loaded_id: "The loaded Portfolio User ID will be used for this request.",
    question_enter: "Enter a question before submitting.",
    ask: "Ask PositionPilot ↗",
    analyzing: "Analyzing…",
    decision_response: "Decision response",
    result_awaiting: "Awaiting a question",
    response_idle: "Idle",
    answer_initial: "Your answer will appear here with the exact context sources used.",
    context_sources: "Context sources",
    sources_none: "No sources yet.",
    source_none_declared: "This answer declared no external context sources.",
    source_none_accepted: "No answer or sources were accepted for this request.",
    footer_disclaimer: "Decision support, not automated trading.",
    footer_boundary: "Facts · Inference · Unknown",
    shares: "Shares",
    average_cost: "Average cost",
    cost_basis: "Cost basis",
    source_ticker: "Ticker",
    source_provider: "Provider",
    source_feed: "Feed",
    source_market_time: "Market time",
    source_fetched: "Fetched",
    source_portfolio_state: "Structured portfolio state",
    maintain_portfolio: "Maintain portfolio",
    ledger_entries: "Ledger entries",
    trade_entry: "Trade entry",
    cash_entry: "Cash entry",
    immutable_entry: "Appends an immutable record",
    action: "Action",
    buy: "BUY",
    sell: "SELL",
    ticker: "Ticker",
    ticker_placeholder: "e.g. GOOG",
    price: "Price",
    price_placeholder: "e.g. 180.25",
    shares_placeholder: "e.g. 2",
    position_type: "Position type",
    position_type_optional: "Position type (optional)",
    unspecified: "Unspecified",
    long_term: "LONG_TERM",
    swing: "SWING",
    opening_state: "Opening state",
    existing_positions_setup: "Add existing positions",
    add_existing_positions: "Add existing positions",
    starting_facts: "One-time starting facts",
    opening_explainer:
      "Record holdings you already owned when tracking begins. This does not change cash or create a trade.",
    add_position: "Add another position",
    remove_position: "Remove",
    skip_for_now: "Skip for now",
    save_opening_positions: "Save existing positions",
    opening_position_saved: "Existing positions saved",
    opening_records: "Opening position records",
    transaction_history: "Transaction history",
    cash_history: "Cash history",
    records_loading: "Load a portfolio to view records.",
    records_empty: "No records yet.",
    records_unavailable: "Record history could not be loaded. Reload the portfolio to try again.",
    opening_ticker: "Ticker",
    opening_shares: "Shares",
    opening_average_cost: "Average cost",
    opening_position_type: "Position type (optional)",
    opening_invalid_input: "Complete every existing-position row before saving.",
    opening_duplicate: "Each ticker and position type may appear only once.",
    opening_setup_skipped: "Existing-position setup skipped for now.",
    api_opening_state_sealed:
      "Existing positions can only be initialized before the first position, trade, or cash record.",
    api_invalid_opening_state: "The existing positions did not satisfy the opening-state rules.",
    sequence: "Sequence",
    recorded_at: "Recorded",
    occurred_at: "Occurred",
    trade_amount: "Trade amount",
    commission: "Commission",
    fee_schedule: "Fee schedule",
    event_type: "Event",
    reason: "Reason",
    not_provided: "Not provided",
    occurred_at_optional: "Occurred at (optional)",
    occurred_at_hint:
      "Leave blank to use backend application time. Enter a past local time only for history.",
    reason_optional: "Reason (optional)",
    save_trade: "Save trade",
    cash_event_type: "Cash event",
    deposit: "DEPOSIT",
    withdrawal: "WITHDRAWAL",
    amount: "Amount",
    amount_placeholder: "e.g. 500",
    save_cash: "Save cash event",
    write_idle: "Idle",
    write_submitting: "Saving…",
    write_refresh_required: "Refresh required",
    mutation_load_first: "Load a portfolio before adding a ledger entry.",
    mutation_refresh_required: "Refresh the portfolio before adding a ledger entry.",
    mutation_in_progress: "Saving a ledger entry. Identity controls are locked.",
    mutation_invalid_input: "Check the entry fields before submitting.",
    portfolio_name_required: "Enter a portfolio name.",
    initial_cash_invalid: "Initial cash must be 0 or a positive number with at most 8 decimal places.",
    ticker_required: "Enter a ticker. The gray example is not an entered value.",
    price_required: "Enter a price. The gray example is not an entered value.",
    shares_required: "Enter shares. The gray “e.g. 2” is an example, not an entered value.",
    price_invalid: "Price must be a positive number with at most 8 decimal places.",
    shares_invalid: "Shares must be a positive number with at most 8 decimal places.",
    amount_required: "Enter an amount. The gray example is not an entered value.",
    amount_invalid: "Amount must be a positive number with at most 8 decimal places.",
    api_insufficient_cash:
      "Insufficient cash. Review available cash, trade amount, and commission.",
    api_insufficient_shares:
      "Insufficient shares for this position type. Review ticker, shares, and the selected or unclassified position type.",
    api_invalid_transaction: "The trade did not satisfy the ledger rules.",
    api_invalid_cash_event: "The cash entry did not satisfy the ledger rules.",
    api_user_not_found: "The loaded portfolio no longer exists.",
    invalid_occurred_at: "Enter a valid local date and time, or leave it blank.",
    write_success: "Ledger entry saved.",
    trade_saved: "Trade saved",
    cash_saved: "Cash event saved",
    write_result_unknown:
      "Write result unknown. Do not automatically retry. Reload the current portfolio to inspect its state.",
    write_failed_refresh_required:
      "The write failed. Reload the current portfolio before continuing.",
    write_succeeded_refresh_failed:
      "The write succeeded, but refreshing the current portfolio failed. Reload before continuing.",
    write_contract_error:
      "The write response did not satisfy the expected contract. Reload before continuing.",
    trade_service_unreachable:
      "The trade service could not be reached. The write result is unknown.",
    cash_service_unreachable:
      "The cash service could not be reached. The write result is unknown.",
    portfolio_reload: "Reload",
    portfolio_context_changed: "Portfolio context changed. Reload it before asking a question.",
    portfolio_user_changed: "User ID changed. Load the new portfolio to continue.",
    portfolio_user_changed_loading:
      "User ID changed while loading. Load the intended portfolio again.",
    portfolio_enter_valid_id: "Enter a valid Portfolio User ID.",
    portfolio_loading_context:
      "Loading a portfolio. The previous decision context is no longer active.",
    portfolio_contract_error: "The portfolio response did not satisfy the expected contract.",
    portfolio_identity_error:
      "The portfolio response belonged to a different User ID and was rejected.",
    portfolio_service_unreachable: "The portfolio service could not be reached.",
    portfolio_display_error: "The portfolio response could not be safely displayed.",
    portfolio_context_stale: "Portfolio context is stale. Load it again before asking.",
    request_failed: "The request could not be completed.",
    answer_degraded: "Answer with data gaps",
    answer_assembled: "Decision context assembled",
    answer_failed: "Request could not form an answer",
    answer_assembling: "Assembling decision context",
    response_working: "Working",
    answer_loading:
      "Reading the loaded portfolio and selecting only the context this question needs.",
    answer_contract_error: "The investment response did not satisfy the expected contract.",
    answer_service_unreachable: "The investment service could not be reached.",
    answer_display_error: "The investment response could not be safely displayed.",
  },
  zh: {
    meta_description: "PositionPilot — 基于真实持仓与当前市场上下文的投资决策辅助界面。",
    brand_home: "PositionPilot 首页",
    language_switch: "切换到英文",
    language_target: "EN",
    local_workspace: "本地决策工作台",
    onboarding_eyebrow: "以真实持仓为基础的 AI",
    onboarding_title: "先建立真实状态，让每个回答真正属于你。",
    onboarding_summary: "创建本地投资组合，或恢复已有组合。无需账号或云端注册。",
    local_only_notice: "仅限本地工作区 · UUID 是恢复引用，不是访问凭证。",
    new_workspace: "新工作区",
    existing_workspace: "已有工作区",
    recover_portfolio: "使用 UUID 恢复",
    back_to_workspace: "返回工作区",
    workspace_navigation: "工作区导航",
    primary_navigation: "主导航",
    new_question: "新问题",
    ask_nav: "提问",
    portfolio_nav: "投资组合",
    this_session: "当前会话",
    question_history: "问题历史",
    session_only: "不会保存",
    no_questions: "还没有问题。",
    current_portfolio: "当前投资组合",
    switch_portfolio: "切换或恢复",
    chat_view_title: "投资问题",
    portfolio_manage_title: "投资组合工作区",
    portfolio_manage_summary: "查看确定性状态，或追加不可变的交易与现金记录。",
    portfolio_sections: "投资组合分区",
    overview_tab: "现有仓位",
    trade_tab: "交易记录",
    cash_tab: "现金活动",
    uuid_boundary: "本地恢复引用 · 不是访问凭证",
    transaction_entry: "交易",
    cash_activity: "现金活动",
    chat_intro_eyebrow: "投资组合已连接",
    chat_intro_title: "你正在思考哪个投资决策？",
    chat_intro_body: "提出一个聚焦的问题。PositionPilot 会使用已加载的持仓，并只读取问题所需的市场上下文。",
    no_memory_notice: "问题只保留在当前浏览器标签页，不属于模型记忆。",
    question_jump: "跳转到问题",
    structured_state: "结构化状态",
    your_portfolio: "你的投资组合",
    start_here: "从这里开始",
    create_portfolio: "创建本地投资组合",
    portfolio_name: "投资组合名称",
    portfolio_name_placeholder: "例如：长期计划",
    initial_cash: "初始现金",
    initial_cash_placeholder: "0.00",
    create_hint: "默认是 0。请填写 PositionPilot 开始跟踪该组合时实际可用的现金。",
    create: "创建投资组合",
    creating: "创建中…",
    create_success: "投资组合已创建并加载。",
    create_refresh_failed: "投资组合已创建，但刷新当前状态失败。请使用“加载”重试。",
    create_response_unknown: "投资组合创建结果未知，请勿自动重试。",
    create_contract_error: "投资组合创建响应无效，结果可能未知，请勿自动重试。",
    create_service_unreachable: "无法连接投资组合服务，创建结果未知。",
    forget_pointer: "忘记本地引用",
    forget_success: "已忘记本地引用，服务器上的投资组合未被删除。",
    portfolio_not_loaded: "未加载",
    portfolio_stale: "已失效",
    portfolio_loading: "加载中…",
    portfolio_loaded: "已加载",
    portfolio_invalid_id: "ID 无效",
    portfolio_network_error: "网络错误",
    portfolio_invalid_response: "响应无效",
    portfolio_identity_mismatch: "身份不匹配",
    portfolio_user_id: "投资组合用户 ID",
    load: "加载",
    loading: "加载中…",
    seed_hint: "使用已有 UUID 恢复本地投资组合。",
    available_cash: "可用现金",
    ledger_derived: "账本计算 · USD",
    open_positions: "当前持仓",
    portfolio_empty_initial: "加载投资组合后，将显示完整的当前持仓。",
    portfolio_empty_loaded: "该投资组合当前没有持仓。",
    context_aware: "上下文感知的决策支持",
    hero_title: "看清仓位，把握当下。",
    hero_summary:
      "提出一个聚焦的投资问题。PositionPilot 会结合真实账本状态，并只选取本次问题所需的市场上下文。",
    investment_question: "投资问题",
    question_placeholder: "例如：GOOG 今天还能加一点吗？",
    question_load_first: "请先加载投资组合再提问。",
    question_loaded_id: "本次请求将使用已加载投资组合的用户 ID。",
    question_enter: "请输入问题后再提交。",
    ask: "询问 PositionPilot ↗",
    analyzing: "分析中…",
    decision_response: "决策响应",
    result_awaiting: "等待提问",
    response_idle: "空闲",
    answer_initial: "回答将在这里显示，并附上本次请求实际使用的上下文来源。",
    context_sources: "上下文来源",
    sources_none: "暂无来源。",
    source_none_declared: "该回答声明未使用外部上下文来源。",
    source_none_accepted: "本次请求没有可接受的回答或来源。",
    footer_disclaimer: "提供决策支持，不进行自动交易。",
    footer_boundary: "事实 · 推断 · 未知",
    shares: "股数",
    average_cost: "平均成本",
    cost_basis: "成本基础",
    source_ticker: "标的",
    source_provider: "数据提供方",
    source_feed: "数据源",
    source_market_time: "市场时间",
    source_fetched: "获取时间",
    source_portfolio_state: "结构化投资组合状态",
    maintain_portfolio: "维护投资组合",
    ledger_entries: "账本记录",
    trade_entry: "交易记录",
    cash_entry: "现金记录",
    immutable_entry: "追加不可变记录",
    action: "操作",
    buy: "BUY",
    sell: "SELL",
    ticker: "标的",
    ticker_placeholder: "例如：GOOG",
    price: "价格",
    price_placeholder: "例如：180.25",
    shares_placeholder: "例如：2",
    position_type: "仓位类型",
    position_type_optional: "仓位类型（可选）",
    unspecified: "未分类",
    long_term: "LONG_TERM",
    swing: "SWING",
    opening_state: "期初状态",
    existing_positions_setup: "录入现有仓位",
    add_existing_positions: "录入现有仓位",
    starting_facts: "一次性期初事实",
    opening_explainer: "录入开始跟踪前已经持有的仓位。此操作不扣减现金，也不会生成交易记录。",
    add_position: "继续添加仓位",
    remove_position: "移除",
    skip_for_now: "暂时跳过",
    save_opening_positions: "保存现有仓位",
    opening_position_saved: "现有仓位已保存",
    opening_records: "期初仓位记录",
    transaction_history: "交易历史",
    cash_history: "现金历史",
    records_loading: "加载投资组合后可查看记录。",
    records_empty: "暂无记录。",
    records_unavailable: "无法加载记录历史，请重新加载投资组合后重试。",
    opening_ticker: "标的",
    opening_shares: "股数",
    opening_average_cost: "平均成本",
    opening_position_type: "仓位类型（可选）",
    opening_invalid_input: "请完整填写每一行现有仓位后再保存。",
    opening_duplicate: "同一标的与仓位类型只能出现一次。",
    opening_setup_skipped: "已暂时跳过现有仓位录入。",
    api_opening_state_sealed: "现有仓位只能在首条仓位、交易或现金记录之前初始化。",
    api_invalid_opening_state: "现有仓位不符合期初状态规则。",
    sequence: "序号",
    recorded_at: "记录时间",
    occurred_at: "发生时间",
    trade_amount: "交易金额",
    commission: "手续费",
    fee_schedule: "费率方案",
    event_type: "事件",
    reason: "原因",
    not_provided: "未填写",
    occurred_at_optional: "发生时间（可选）",
    occurred_at_hint: "留空使用后端应用时间。只有补录历史时才填写过去的本地时间。",
    reason_optional: "原因（可选）",
    save_trade: "保存交易",
    cash_event_type: "现金事件",
    deposit: "DEPOSIT",
    withdrawal: "WITHDRAWAL",
    amount: "金额",
    amount_placeholder: "例如：500",
    save_cash: "保存现金事件",
    write_idle: "空闲",
    write_submitting: "保存中…",
    write_refresh_required: "需要刷新",
    mutation_load_first: "请先加载投资组合，再添加账本记录。",
    mutation_refresh_required: "请先刷新投资组合，再添加账本记录。",
    mutation_in_progress: "正在保存账本记录，身份操作已锁定。",
    mutation_invalid_input: "请检查记录表单字段后再提交。",
    portfolio_name_required: "请填写投资组合名称。",
    initial_cash_invalid: "初始现金必须是 0 或正数，且最多包含 8 位小数。",
    ticker_required: "请填写标的。灰色示例不是已经输入的值。",
    price_required: "请填写价格。灰色示例不是已经输入的值。",
    shares_required: "请填写股数。灰色的“例如：2”只是示例，不是已经输入的值。",
    price_invalid: "价格必须是正数，且最多包含 8 位小数。",
    shares_invalid: "股数必须是正数，且最多包含 8 位小数。",
    amount_required: "请填写金额。灰色示例不是已经输入的值。",
    amount_invalid: "金额必须是正数，且最多包含 8 位小数。",
    api_insufficient_cash: "可用现金不足。请检查可用现金、交易金额和手续费。",
    api_insufficient_shares: "该仓位类型的股数不足。请检查标的、股数以及所选或未分类的仓位类型。",
    api_invalid_transaction: "该交易不符合账本规则。",
    api_invalid_cash_event: "该现金记录不符合账本规则。",
    api_user_not_found: "当前加载的投资组合已不存在。",
    invalid_occurred_at: "请输入有效的本地日期时间，或留空。",
    write_success: "账本记录已保存。",
    trade_saved: "交易已保存",
    cash_saved: "现金事件已保存",
    write_result_unknown: "写入结果未知，请勿自动重试。请重新加载当前投资组合以检查状态。",
    write_failed_refresh_required: "写入失败，请重新加载当前投资组合后继续。",
    write_succeeded_refresh_failed: "写入成功，但刷新当前投资组合失败。请重新加载后继续。",
    write_contract_error: "写入响应不符合预期的数据契约，请重新加载后继续。",
    trade_service_unreachable: "无法连接交易服务，写入结果未知。",
    cash_service_unreachable: "无法连接现金服务，写入结果未知。",
    portfolio_reload: "重新加载",
    portfolio_context_changed: "投资组合上下文已变化，请重新加载后再提问。",
    portfolio_user_changed: "用户 ID 已变化，请加载新的投资组合后继续。",
    portfolio_user_changed_loading: "加载期间用户 ID 发生变化，请重新加载目标投资组合。",
    portfolio_enter_valid_id: "请输入有效的投资组合用户 ID。",
    portfolio_loading_context: "正在加载投资组合，之前的决策上下文已失效。",
    portfolio_contract_error: "投资组合响应不符合预期的数据契约。",
    portfolio_identity_error: "投资组合响应属于其他用户，已拒绝显示。",
    portfolio_service_unreachable: "无法连接投资组合服务。",
    portfolio_display_error: "无法安全显示投资组合响应。",
    portfolio_context_stale: "投资组合上下文已失效，请重新加载后再提问。",
    request_failed: "请求无法完成。",
    answer_degraded: "回答存在数据缺口",
    answer_assembled: "决策上下文已完成",
    answer_failed: "请求未能形成回答",
    answer_assembling: "正在组装决策上下文",
    response_working: "处理中",
    answer_loading: "正在读取已加载的投资组合，并仅选择本次问题所需的上下文。",
    answer_contract_error: "投资回答不符合预期的数据契约。",
    answer_service_unreachable: "无法连接投资分析服务。",
    answer_display_error: "无法安全显示投资回答。",
  },
};

let activeLanguage = navigator.language.toLowerCase().startsWith("zh") ? "zh" : "en";
let openingDraftCounter = 0;

const elements = {
  onboardingView: document.querySelector("#onboarding-view"),
  appShell: document.querySelector("#app-shell"),
  cancelOnboardingButton: document.querySelector("#cancel-onboarding-button"),
  switchPortfolioButton: document.querySelector("#switch-portfolio-button"),
  newQuestionButton: document.querySelector("#new-question-button"),
  navChat: document.querySelector("#nav-chat"),
  navPortfolio: document.querySelector("#nav-portfolio"),
  chatView: document.querySelector("#chat-view"),
  portfolioView: document.querySelector("#portfolio-view"),
  viewEyebrow: document.querySelector("#view-eyebrow"),
  viewTitle: document.querySelector("#view-title"),
  sessionEmpty: document.querySelector("#session-empty"),
  sessionList: document.querySelector("#session-list"),
  conversationScroll: document.querySelector("#conversation-scroll"),
  chatIntro: document.querySelector("#chat-intro"),
  conversationList: document.querySelector("#conversation-list"),
  responseTemplate: document.querySelector("#assistant-response-template"),
  portfolioTabOverview: document.querySelector("#portfolio-tab-overview"),
  portfolioTabTrade: document.querySelector("#portfolio-tab-trade"),
  portfolioTabCash: document.querySelector("#portfolio-tab-cash"),
  portfolioOverviewPanel: document.querySelector("#portfolio-overview-panel"),
  portfolioTradePanel: document.querySelector("#portfolio-trade-panel"),
  portfolioCashPanel: document.querySelector("#portfolio-cash-panel"),
  loadedUserId: document.querySelector("#loaded-user-id"),
  sidebarPortfolioId: document.querySelector("#sidebar-portfolio-id"),
  reloadPortfolioButton: document.querySelector("#reload-portfolio-button"),
  createForm: document.querySelector("#create-form"),
  createFields: document.querySelector("#create-fields"),
  portfolioName: document.querySelector("#portfolio-name"),
  initialCash: document.querySelector("#initial-cash"),
  createButton: document.querySelector("#create-button"),
  createMessage: document.querySelector("#create-message"),
  portfolioForm: document.querySelector("#portfolio-form"),
  portfolioLoadButton: document.querySelector("#load-button"),
  userIdInput: document.querySelector("#user-id"),
  forgetPointerButton: document.querySelector("#forget-pointer-button"),
  portfolioState: document.querySelector("#portfolio-state"),
  availableCash: document.querySelector("#available-cash"),
  positionCount: document.querySelector("#position-count"),
  positionsEmpty: document.querySelector("#positions-empty"),
  positionList: document.querySelector("#position-list"),
  openingSetup: document.querySelector("#opening-setup"),
  openingForm: document.querySelector("#opening-form"),
  openingFields: document.querySelector("#opening-fields"),
  openingDraftRows: document.querySelector("#opening-draft-rows"),
  addOpeningRowButton: document.querySelector("#add-opening-row"),
  skipOpeningSetupButton: document.querySelector("#skip-opening-setup"),
  reopenOpeningSetupButton: document.querySelector("#reopen-opening-setup"),
  openingSubmit: document.querySelector("#save-opening-positions"),
  openingMessage: document.querySelector("#opening-message"),
  openingRecordCount: document.querySelector("#opening-record-count"),
  openingRecordsEmpty: document.querySelector("#opening-records-empty"),
  openingRecordList: document.querySelector("#opening-record-list"),
  portfolioMessage: document.querySelector("#portfolio-message"),
  writeState: document.querySelector("#write-state"),
  tradeForm: document.querySelector("#trade-form"),
  tradeFields: document.querySelector("#trade-fields"),
  tradeAction: document.querySelector("#trade-action"),
  tradeTicker: document.querySelector("#trade-ticker"),
  tradePrice: document.querySelector("#trade-price"),
  tradeShares: document.querySelector("#trade-shares"),
  tradePositionType: document.querySelector("#trade-position-type"),
  tradeOccurredAt: document.querySelector("#trade-occurred-at"),
  tradeReason: document.querySelector("#trade-reason"),
  tradeSubmit: document.querySelector("#trade-submit"),
  tradeMessage: document.querySelector("#trade-message"),
  transactionCount: document.querySelector("#transaction-count"),
  transactionsEmpty: document.querySelector("#transactions-empty"),
  transactionList: document.querySelector("#transaction-list"),
  cashForm: document.querySelector("#cash-form"),
  cashFields: document.querySelector("#cash-fields"),
  cashEventType: document.querySelector("#cash-event-type"),
  cashAmount: document.querySelector("#cash-amount"),
  cashOccurredAt: document.querySelector("#cash-occurred-at"),
  cashReason: document.querySelector("#cash-reason"),
  cashSubmit: document.querySelector("#cash-submit"),
  cashMessage: document.querySelector("#cash-message"),
  cashEventCount: document.querySelector("#cash-event-count"),
  cashEventsEmpty: document.querySelector("#cash-events-empty"),
  cashEventList: document.querySelector("#cash-event-list"),
  questionForm: document.querySelector("#question-form"),
  question: document.querySelector("#question"),
  questionHint: document.querySelector("#question-hint"),
  askButton: document.querySelector("#ask-button"),
  languageToggle: document.querySelector("#language-toggle"),
};

const clientState = {
  userIdInput: "",
  loadedUserId: null,
  portfolioGeneration: 0,
  questionGeneration: 0,
  portfolioController: null,
  questionController: null,
  createController: null,
  writeState: "idle",
  activeView: "chat",
  portfolioSection: "overview",
  activeResponse: null,
  questionHistoryCount: 0,
  openingPositions: [],
  transactions: [],
  cashEvents: [],
  recordsLoaded: false,
  openingSetupSkipped: false,
};

function normalizeUserId(value) {
  return value.trim().toLowerCase();
}

function formatDecimalForDisplay(value) {
  return /^-?0(?:\.0+)?(?:e[+-]?\d+)?$/i.test(value) ? "0.00000000" : value;
}

function isValidUserId(value) {
  return UUID_PATTERN.test(value);
}

function isPortfolioPayload(payload) {
  return (
    payload !== null &&
    typeof payload === "object" &&
    typeof payload.user_id === "string" &&
    typeof payload.available_cash === "string" &&
    payload.positions_are_complete === true &&
    Array.isArray(payload.positions) &&
    payload.positions.every(
      (position) =>
        position !== null &&
        typeof position === "object" &&
        typeof position.ticker === "string" &&
        typeof position.position_type === "string" &&
        typeof position.shares === "string" &&
        typeof position.average_cost === "string" &&
        typeof position.cost_basis === "string",
    )
  );
}

function isAnswerPayload(payload) {
  return (
    payload !== null &&
    typeof payload === "object" &&
    (payload.status === "OK" || payload.status === "DEGRADED") &&
    typeof payload.answer === "string" &&
    Array.isArray(payload.sources) &&
    payload.sources.every(
      (source) =>
        source !== null &&
        typeof source === "object" &&
        typeof source.type === "string" &&
        typeof source.status === "string",
    )
  );
}

function isCreatedPortfolioPayload(payload) {
  return (
    payload !== null &&
    typeof payload === "object" &&
    typeof payload.user_id === "string" &&
    typeof payload.display_name === "string" &&
    typeof payload.initial_cash === "string" &&
    typeof payload.created_at === "string"
  );
}

function isOpeningPositionRecord(record, userId) {
  return (
    record !== null &&
    typeof record === "object" &&
    normalizeUserId(record.user_id ?? "") === userId &&
    typeof record.id === "string" &&
    typeof record.ticker === "string" &&
    typeof record.shares === "string" &&
    typeof record.average_cost === "string" &&
    typeof record.cost_basis === "string" &&
    typeof record.position_type === "string" &&
    typeof record.recorded_at === "string" &&
    !("sequence" in record)
  );
}

function isTransactionRecord(record, userId) {
  return (
    record !== null &&
    typeof record === "object" &&
    normalizeUserId(record.user_id ?? "") === userId &&
    typeof record.id === "string" &&
    Number.isInteger(record.sequence) &&
    typeof record.ticker === "string" &&
    typeof record.action === "string" &&
    typeof record.price === "string" &&
    typeof record.shares === "string" &&
    typeof record.amount === "string" &&
    typeof record.commission === "string" &&
    typeof record.fee_schedule === "string" &&
    typeof record.position_type === "string" &&
    typeof record.occurred_at === "string"
  );
}

function isCashEventRecord(record, userId) {
  return (
    record !== null &&
    typeof record === "object" &&
    normalizeUserId(record.user_id ?? "") === userId &&
    typeof record.id === "string" &&
    Number.isInteger(record.sequence) &&
    typeof record.event_type === "string" &&
    typeof record.amount === "string" &&
    typeof record.occurred_at === "string"
  );
}

function isRecordListPayload(payload, userId, validator) {
  return (
    payload !== null &&
    typeof payload === "object" &&
    payload.items_are_complete === true &&
    Array.isArray(payload.items) &&
    payload.items.every((record) => validator(record, userId))
  );
}

function isOpeningPositionsWritePayload(payload, userId) {
  return (
    payload !== null &&
    typeof payload === "object" &&
    payload.items_are_complete === true &&
    Array.isArray(payload.opening_positions) &&
    payload.opening_positions.every((record) => isOpeningPositionRecord(record, userId))
  );
}

function isTransactionWritePayload(payload, userId) {
  const transaction = payload?.transaction;
  return isTransactionRecord(transaction, userId);
}

function isCashWritePayload(payload, userId) {
  const cashEvent = payload?.cash_event;
  return (
    isCashEventRecord(cashEvent, userId) &&
    typeof payload.available_cash === "string"
  );
}

function translate(key) {
  return translations[activeLanguage][key] ?? translations.en[key] ?? key;
}

function setLocalizedText(element, key) {
  element.dataset.i18n = key;
  element.textContent = translate(key);
}

function setRawText(element, value) {
  delete element.dataset.i18n;
  element.textContent = value;
}

function applyLanguage() {
  document.documentElement.lang = activeLanguage === "zh" ? "zh-CN" : "en";
  for (const element of document.querySelectorAll("[data-i18n]")) {
    element.textContent = translate(element.dataset.i18n);
  }
  for (const element of document.querySelectorAll("[data-i18n-placeholder]")) {
    element.placeholder = translate(element.dataset.i18nPlaceholder);
  }
  for (const element of document.querySelectorAll("[data-i18n-aria-label]")) {
    element.setAttribute("aria-label", translate(element.dataset.i18nAriaLabel));
  }
  for (const element of document.querySelectorAll("[data-i18n-content]")) {
    element.setAttribute("content", translate(element.dataset.i18nContent));
  }
  for (const element of document.querySelectorAll("[data-timestamp]")) {
    element.textContent = formatTimestamp(element.dataset.timestamp);
  }
  for (const element of document.querySelectorAll(".session-question[data-question]")) {
    element.setAttribute(
      "aria-label",
      `${translate("question_jump")}: ${element.dataset.question}`,
    );
  }
  elements.languageToggle.textContent = translate("language_target");
  elements.languageToggle.setAttribute("aria-label", translate("language_switch"));
}

function toggleLanguage() {
  activeLanguage = activeLanguage === "en" ? "zh" : "en";
  applyLanguage();
}

function switchAppView(view, { focus = true } = {}) {
  clientState.activeView = view;
  const showChat = view === "chat";
  elements.chatView.hidden = !showChat;
  elements.portfolioView.hidden = showChat;
  elements.navChat.classList.toggle("is-active", showChat);
  elements.navPortfolio.classList.toggle("is-active", !showChat);
  if (showChat) {
    elements.navChat.setAttribute("aria-current", "page");
    elements.navPortfolio.removeAttribute("aria-current");
  } else {
    elements.navChat.removeAttribute("aria-current");
    elements.navPortfolio.setAttribute("aria-current", "page");
  }
  setLocalizedText(elements.viewEyebrow, showChat ? "context_aware" : "structured_state");
  setLocalizedText(elements.viewTitle, showChat ? "chat_view_title" : "portfolio_nav");
  if (focus) {
    if (showChat && !elements.question.disabled) {
      elements.question.focus();
    } else {
      elements.viewTitle.focus();
    }
  }
}

function switchPortfolioSection(section) {
  clientState.portfolioSection = section;
  const definitions = [
    ["overview", elements.portfolioTabOverview, elements.portfolioOverviewPanel],
    ["trade", elements.portfolioTabTrade, elements.portfolioTradePanel],
    ["cash", elements.portfolioTabCash, elements.portfolioCashPanel],
  ];
  for (const [name, tab, panel] of definitions) {
    const active = name === section;
    tab.classList.toggle("is-active", active);
    tab.setAttribute("aria-selected", String(active));
    panel.hidden = !active;
  }
}

function showOnboarding() {
  elements.onboardingView.hidden = false;
  elements.appShell.hidden = true;
  elements.cancelOnboardingButton.hidden = clientState.loadedUserId === null;
}

function showWorkspace(view = clientState.activeView) {
  elements.onboardingView.hidden = true;
  elements.appShell.hidden = false;
  elements.cancelOnboardingButton.hidden = true;
  switchAppView(view, { focus: false });
}

function setPortfolioState(label, tone = "neutral", localized = true) {
  if (localized) {
    setLocalizedText(elements.portfolioState, label);
  } else {
    setRawText(elements.portfolioState, label);
  }
  elements.portfolioState.dataset.tone = tone;
}

function setResponseState(view, label, tone = "neutral", localized = true) {
  if (localized) {
    setLocalizedText(view.responseStatus, label);
  } else {
    setRawText(view.responseStatus, label);
  }
  view.responseStatus.dataset.tone = tone;
}

function clearElement(element) {
  element.replaceChildren();
}

function isLoadedPortfolioCurrent() {
  return (
    clientState.loadedUserId !== null &&
    clientState.loadedUserId === clientState.userIdInput
  );
}

function setQuestionEnabled(enabled, hintKey = "question_load_first") {
  elements.question.disabled = !enabled;
  elements.askButton.disabled = !enabled;
  setLocalizedText(elements.questionHint, enabled ? "question_loaded_id" : hintKey);
}

function setWriteState(state) {
  clientState.writeState = state;
  const stateKeys = {
    idle: "write_idle",
    submitting: "write_submitting",
    refresh_required: "write_refresh_required",
  };
  const stateTones = {
    idle: "neutral",
    submitting: "warning",
    refresh_required: "danger",
  };
  setLocalizedText(elements.writeState, stateKeys[state]);
  elements.writeState.dataset.tone = stateTones[state];
}

function markSnapshotRefreshRequired() {
  setWriteState("refresh_required");
  setPortfolioState("portfolio_stale", "warning");
  resetPortfolio("mutation_refresh_required");
}

function readLocalPointer() {
  try {
    const storedValue = window.localStorage.getItem(LOCAL_POINTER_KEY);
    if (!storedValue) {
      return null;
    }
    const normalized = normalizeUserId(storedValue);
    if (!isValidUserId(normalized)) {
      window.localStorage.removeItem(LOCAL_POINTER_KEY);
      return null;
    }
    return normalized;
  } catch {
    // 受限浏览器中的 Storage 不可用时，按没有本地恢复指针处理。
    return null;
  }
}

function saveLocalPointer(userId) {
  try {
    window.localStorage.setItem(LOCAL_POINTER_KEY, userId);
  } catch {
    // Storage 不是数据源；不可写时仍允许当前页面继续使用内存状态。
  }
}

function clearLocalPointer(expectedUserId = null) {
  try {
    const storedValue = window.localStorage.getItem(LOCAL_POINTER_KEY);
    if (expectedUserId === null || normalizeUserId(storedValue ?? "") === expectedUserId) {
      window.localStorage.removeItem(LOCAL_POINTER_KEY);
    }
  } catch {
    // 受限 Storage 无法清理时，不影响服务器上的 Ledger。
  }
}

function updateUrlUserId(userId) {
  const url = new URL(window.location.href);
  url.searchParams.set("user_id", userId);
  window.history.replaceState({}, "", url);
}

function clearUrlUserId() {
  const url = new URL(window.location.href);
  url.searchParams.delete("user_id");
  window.history.replaceState({}, "", url);
}

function setActionMessageWithValue(element, messageKey, value) {
  clearElement(element);
  element.dataset.tone = "success";
  const message = document.createElement("span");
  setLocalizedText(message, messageKey);
  const detail = document.createElement("span");
  detail.textContent = ` · ${value}`;
  element.append(message, detail);
}

function clearLedgerMessages() {
  setRawText(elements.openingMessage, "");
  setRawText(elements.tradeMessage, "");
  setRawText(elements.cashMessage, "");
  delete elements.openingMessage.dataset.tone;
  delete elements.tradeMessage.dataset.tone;
  delete elements.cashMessage.dataset.tone;
}

function hasLocalPointer() {
  return readLocalPointer() !== null;
}

function updateControls() {
  const identityLocked =
    clientState.writeState === "submitting" || clientState.createController !== null;
  const portfolioLoading = clientState.portfolioController !== null;
  const questionLoading = clientState.questionController !== null;
  const portfolioReady =
    isLoadedPortfolioCurrent() &&
    clientState.writeState === "idle" &&
    !portfolioLoading;

  elements.userIdInput.disabled = identityLocked;
  elements.portfolioLoadButton.disabled = identityLocked || portfolioLoading;
  elements.forgetPointerButton.disabled =
    identityLocked || portfolioLoading || !hasLocalPointer();
  elements.createFields.disabled = identityLocked || portfolioLoading;
  elements.switchPortfolioButton.disabled = identityLocked;
  elements.cancelOnboardingButton.disabled = identityLocked;
  elements.reloadPortfolioButton.disabled =
    identityLocked || portfolioLoading || clientState.loadedUserId === null;

  const ledgerEnabled = portfolioReady && !identityLocked;
  elements.tradeFields.disabled = !ledgerEnabled;
  elements.cashFields.disabled = !ledgerEnabled;
  const openingEligible =
    portfolioReady &&
    clientState.recordsLoaded &&
    clientState.openingPositions.length === 0 &&
    clientState.transactions.length === 0 &&
    clientState.cashEvents.length === 0;
  elements.openingFields.disabled = !openingEligible || identityLocked;
  elements.openingSetup.hidden = !openingEligible || clientState.openingSetupSkipped;
  elements.reopenOpeningSetupButton.hidden =
    !openingEligible || !clientState.openingSetupSkipped;

  const questionEnabled = portfolioReady && !questionLoading;
  if (questionEnabled) {
    setQuestionEnabled(true);
  } else if (clientState.writeState === "submitting") {
    setQuestionEnabled(false, "mutation_in_progress");
  } else if (clientState.createController !== null) {
    setQuestionEnabled(false, "portfolio_loading_context");
  } else if (clientState.writeState === "refresh_required") {
    setQuestionEnabled(false, "mutation_refresh_required");
  } else {
    setQuestionEnabled(false);
  }
}

function resetResult(message = "answer_initial", localized = true) {
  clientState.activeResponse = null;
  clientState.questionHistoryCount = 0;
  clearElement(elements.conversationList);
  clearElement(elements.sessionList);
  elements.sessionEmpty.hidden = false;
  elements.chatIntro.hidden = false;
  const introBody = elements.chatIntro.querySelector("p:not(.eyebrow)");
  const messageKey = message === "answer_initial" ? "chat_intro_body" : message;
  if (localized) {
    setLocalizedText(introBody, messageKey);
  } else {
    setRawText(introBody, message);
  }
}

function resetRecordLists(messageKey = "records_loading") {
  clientState.openingPositions = [];
  clientState.transactions = [];
  clientState.cashEvents = [];
  clientState.recordsLoaded = false;
  for (const list of [
    elements.openingRecordList,
    elements.transactionList,
    elements.cashEventList,
  ]) {
    clearElement(list);
  }
  for (const count of [
    elements.openingRecordCount,
    elements.transactionCount,
    elements.cashEventCount,
  ]) {
    count.textContent = "—";
  }
  for (const empty of [
    elements.openingRecordsEmpty,
    elements.transactionsEmpty,
    elements.cashEventsEmpty,
  ]) {
    empty.hidden = false;
    setLocalizedText(empty, messageKey);
  }
  elements.openingSetup.hidden = true;
  elements.reopenOpeningSetupButton.hidden = true;
}

function resetPortfolio(message = "", localized = true) {
  elements.availableCash.textContent = "—";
  elements.positionCount.textContent = "—";
  clearElement(elements.positionList);
  elements.positionsEmpty.hidden = false;
  if (clientState.loadedUserId === null) {
    elements.loadedUserId.textContent = "—";
    elements.sidebarPortfolioId.textContent = "—";
  }
  setLocalizedText(elements.positionsEmpty.querySelector("p"), "portfolio_empty_initial");
  resetRecordLists();
  if (localized && message) {
    setLocalizedText(elements.portfolioMessage, message);
  } else {
    setRawText(elements.portfolioMessage, message);
  }
}

function invalidateQuestionContext(resultMessage, { clearHistory = true } = {}) {
  clientState.questionGeneration += 1;
  clientState.questionController?.abort();
  clientState.questionController = null;
  setLocalizedText(elements.askButton, "ask");
  setQuestionEnabled(false);
  if (clearHistory) {
    resetResult(resultMessage);
  } else if (clientState.activeResponse !== null) {
    renderQuestionError(
      { code: "STALE_CONTEXT", messageKey: resultMessage },
      clientState.activeResponse,
    );
    clientState.activeResponse = null;
  }
}

function invalidateLoadedPortfolio(message) {
  clientState.portfolioGeneration += 1;
  clientState.portfolioController?.abort();
  clientState.portfolioController = null;
  clientState.loadedUserId = null;
  clientState.openingSetupSkipped = false;
  clearElement(elements.openingDraftRows);
  setLocalizedText(elements.portfolioLoadButton, "load");
  setPortfolioState("portfolio_stale", "warning");
  resetPortfolio(message);
  clearLedgerMessages();
  invalidateQuestionContext("portfolio_context_changed");
  updateControls();
}

function handleUserIdInput() {
  clientState.userIdInput = normalizeUserId(elements.userIdInput.value);
  if (clientState.writeState === "submitting") {
    // 正常用户无法编辑 disabled 输入框；此保护避免脚本修改破坏 Mutation 绑定。
    return;
  }
  if (clientState.loadedUserId !== null) {
    if (clientState.userIdInput !== clientState.loadedUserId) {
      invalidateLoadedPortfolio("portfolio_user_changed");
    }
    updateControls();
    return;
  }
  if (clientState.portfolioController !== null) {
    invalidateLoadedPortfolio("portfolio_user_changed_loading");
    return;
  }
  if (clientState.writeState !== "refresh_required") {
    setPortfolioState("portfolio_not_loaded");
  }
  resetPortfolio();
  updateControls();
}

function createPositionCard(position) {
  const card = document.createElement("article");
  card.className = "position-card";

  const heading = document.createElement("div");
  heading.className = "position-card-heading";
  const ticker = document.createElement("strong");
  ticker.textContent = position.ticker;
  const positionType = document.createElement("span");
  positionType.className = "position-type";
  positionType.dataset.type = position.position_type.toLowerCase().replace("_", "-");
  if (position.position_type === "UNSPECIFIED") {
    setLocalizedText(positionType, "unspecified");
  } else {
    positionType.textContent = position.position_type;
  }
  heading.append(ticker, positionType);

  const facts = document.createElement("dl");
  facts.className = "position-facts";
  const factValues = [
    ["shares", position.shares],
    ["average_cost", position.average_cost],
    ["cost_basis", position.cost_basis],
  ];
  for (const [label, value] of factValues) {
    const group = document.createElement("div");
    const term = document.createElement("dt");
    setLocalizedText(term, label);
    const description = document.createElement("dd");
    description.textContent = value;
    group.append(term, description);
    facts.append(group);
  }

  card.append(heading, facts);
  return card;
}

function appendRecordFact(list, labelKey, value, { timestamp = false } = {}) {
  const group = document.createElement("div");
  const term = document.createElement("dt");
  setLocalizedText(term, labelKey);
  const description = document.createElement("dd");
  if (timestamp) {
    description.dataset.timestamp = value;
    description.textContent = formatTimestamp(value);
  } else if (value === null || value === undefined || value === "") {
    setLocalizedText(description, "not_provided");
  } else {
    description.textContent = value;
  }
  group.append(term, description);
  list.append(group);
}

function createRecordCard(title, positionType, facts) {
  const card = document.createElement("article");
  card.className = "record-card";
  const heading = document.createElement("div");
  heading.className = "position-card-heading";
  const strong = document.createElement("strong");
  strong.textContent = title;
  heading.append(strong);
  if (positionType) {
    const badge = document.createElement("span");
    badge.className = "position-type";
    badge.dataset.type = positionType.toLowerCase().replace("_", "-");
    if (positionType === "UNSPECIFIED") {
      setLocalizedText(badge, "unspecified");
    } else {
      badge.textContent = positionType;
    }
    heading.append(badge);
  }
  const factList = document.createElement("dl");
  factList.className = "record-facts";
  for (const fact of facts) {
    appendRecordFact(factList, fact[0], fact[1], fact[2]);
  }
  card.append(heading, factList);
  return card;
}

function renderRecordLists() {
  const definitions = [
    [
      clientState.openingPositions,
      elements.openingRecordList,
      elements.openingRecordsEmpty,
      elements.openingRecordCount,
      (record) =>
        createRecordCard(record.ticker, record.position_type, [
          ["shares", record.shares],
          ["average_cost", record.average_cost],
          ["cost_basis", record.cost_basis],
          ["recorded_at", record.recorded_at, { timestamp: true }],
        ]),
    ],
    [
      clientState.transactions,
      elements.transactionList,
      elements.transactionsEmpty,
      elements.transactionCount,
      (record) =>
        createRecordCard(`${record.action} · ${record.ticker}`, record.position_type, [
          ["sequence", `#${record.sequence}`],
          ["price", record.price],
          ["shares", record.shares],
          ["trade_amount", record.amount],
          ["commission", record.commission],
          ["fee_schedule", record.fee_schedule],
          ["occurred_at", record.occurred_at, { timestamp: true }],
          ["reason", record.reason],
        ]),
    ],
    [
      clientState.cashEvents,
      elements.cashEventList,
      elements.cashEventsEmpty,
      elements.cashEventCount,
      (record) =>
        createRecordCard(record.event_type, null, [
          ["sequence", `#${record.sequence}`],
          ["amount", record.amount],
          ["occurred_at", record.occurred_at, { timestamp: true }],
          ["reason", record.reason],
        ]),
    ],
  ];

  for (const [records, list, empty, count, createCard] of definitions) {
    clearElement(list);
    count.textContent = String(records.length);
    empty.hidden = records.length > 0;
    setLocalizedText(empty, "records_empty");
    for (const record of records) {
      list.append(createCard(record));
    }
  }
  if (elements.openingDraftRows.childElementCount === 0) {
    addOpeningDraftRow();
  }
  updateControls();
}

async function loadPortfolioRecords(userId, signal) {
  const resources = [
    ["openingPositions", "opening-positions", isOpeningPositionRecord],
    ["transactions", "transactions", isTransactionRecord],
    ["cashEvents", "cash-events", isCashEventRecord],
  ];
  const responses = await Promise.all(
    resources.map(([, path]) =>
      fetch(`/v1/portfolios/${encodeURIComponent(userId)}/${path}`, {
        signal,
        headers: { Accept: "application/json" },
      }),
    ),
  );
  if (responses.some((response) => !response.ok)) {
    throw new Error("RECORD_LIST_REQUEST_FAILED");
  }
  const payloads = await Promise.all(responses.map((response) => response.json()));
  const records = {};
  for (let index = 0; index < resources.length; index += 1) {
    const [stateKey, , validator] = resources[index];
    const payload = payloads[index];
    if (!isRecordListPayload(payload, userId, validator)) {
      throw new Error("RECORD_LIST_CONTRACT_FAILED");
    }
    records[stateKey] = payload.items;
  }
  return records;
}

function renderPortfolio(portfolio) {
  elements.availableCash.textContent = `$${formatDecimalForDisplay(portfolio.available_cash)}`;
  elements.positionCount.textContent = String(portfolio.positions.length);
  elements.loadedUserId.textContent = portfolio.user_id;
  elements.sidebarPortfolioId.textContent = portfolio.user_id;
  setRawText(elements.portfolioMessage, "");
  clearElement(elements.positionList);
  elements.positionsEmpty.hidden = portfolio.positions.length > 0;

  if (portfolio.positions.length === 0) {
    const emptyMessage = elements.positionsEmpty.querySelector("p");
    setLocalizedText(emptyMessage, "portfolio_empty_loaded");
  } else {
    for (const position of portfolio.positions) {
      elements.positionList.append(createPositionCard(position));
    }
  }
  setPortfolioState("portfolio_loaded", "success");
  updateControls();
}

async function parseApiError(response) {
  try {
    const payload = await response.json();
    if (payload?.detail?.message) {
      return {
        code: payload.detail.code ?? `HTTP_${response.status}`,
        message: payload.detail.message,
      };
    }
    if (Array.isArray(payload?.detail)) {
      const messages = payload.detail
        .map((item) => {
          if (typeof item?.msg !== "string") {
            return null;
          }
          const fieldPath = Array.isArray(item.loc)
            ? item.loc.filter((part) => part !== "body").join(".")
            : "";
          return fieldPath ? `${fieldPath}: ${item.msg}` : item.msg;
        })
        .filter(Boolean);
      if (messages.length > 0) {
        return {
          code: `HTTP_${response.status}`,
          message: messages.join("; "),
        };
      }
    }
  } catch {
    // 非 JSON Failure 使用稳定的 HTTP 回退信息。
  }
  return {
    code: `HTTP_${response.status}`,
    messageKey: "request_failed",
  };
}

function clearUrlUserIdIfMatches(userId) {
  const current = normalizeUserId(new URL(window.location.href).searchParams.get("user_id") ?? "");
  if (current === userId) {
    clearUrlUserId();
  }
}

async function loadPortfolioById(
  requestedUserId,
  {
    resolveWriteState = true,
    preserveRecoveryPointer = false,
    preserveConversation = false,
  } = {},
) {
  if (requestedUserId !== clientState.loadedUserId) {
    clientState.openingSetupSkipped = false;
    clearElement(elements.openingDraftRows);
  }
  clientState.userIdInput = requestedUserId;
  elements.userIdInput.value = requestedUserId;

  if (!isValidUserId(requestedUserId)) {
    invalidateLoadedPortfolio("portfolio_enter_valid_id");
    setPortfolioState("portfolio_invalid_id", "danger");
    return false;
  }

  clientState.portfolioGeneration += 1;
  const generation = clientState.portfolioGeneration;
  clientState.portfolioController?.abort();
  const controller = new AbortController();
  clientState.portfolioController = controller;
  if (!preserveConversation) {
    clientState.loadedUserId = null;
  }
  invalidateQuestionContext("portfolio_loading_context", {
    clearHistory: !preserveConversation,
  });

  setPortfolioState("portfolio_loading");
  setLocalizedText(elements.portfolioLoadButton, "loading");
  resetPortfolio("");
  clearLedgerMessages();
  updateControls();

  try {
    const response = await fetch(`/v1/portfolios/${encodeURIComponent(requestedUserId)}`, {
      signal: controller.signal,
      headers: { Accept: "application/json" },
    });
    if (
      generation !== clientState.portfolioGeneration ||
      requestedUserId !== clientState.userIdInput
    ) {
      return false;
    }
    if (!response.ok) {
      const error = await parseApiError(response);
      if (generation !== clientState.portfolioGeneration) {
        return false;
      }
      if (response.status === 404 && !preserveRecoveryPointer) {
        clearLocalPointer(requestedUserId);
        clearUrlUserIdIfMatches(requestedUserId);
      }
      setPortfolioState(error.code, "danger", false);
      resetPortfolio(error.messageKey ?? error.message, Boolean(error.messageKey));
      return false;
    }

    const portfolio = await response.json();
    if (
      generation !== clientState.portfolioGeneration ||
      requestedUserId !== clientState.userIdInput
    ) {
      return false;
    }
    if (!isPortfolioPayload(portfolio)) {
      setPortfolioState("portfolio_invalid_response", "danger");
      resetPortfolio("portfolio_contract_error");
      return false;
    }
    const responseUserId = normalizeUserId(portfolio.user_id ?? "");
    if (responseUserId !== requestedUserId) {
      setPortfolioState("portfolio_identity_mismatch", "danger");
      resetPortfolio("portfolio_identity_error");
      return false;
    }

    clientState.loadedUserId = responseUserId;
    saveLocalPointer(responseUserId);
    updateUrlUserId(responseUserId);
    if (resolveWriteState) {
      setWriteState("idle");
    }
    if (!preserveConversation) {
      switchPortfolioSection("overview");
      resetResult();
    }
    renderPortfolio(portfolio);
    try {
      const records = await loadPortfolioRecords(responseUserId, controller.signal);
      if (
        generation !== clientState.portfolioGeneration ||
        responseUserId !== clientState.userIdInput
      ) {
        return false;
      }
      clientState.openingPositions = records.openingPositions;
      clientState.transactions = records.transactions;
      clientState.cashEvents = records.cashEvents;
      clientState.recordsLoaded = true;
      renderRecordLists();
    } catch (error) {
      if (error.name === "AbortError") {
        throw error;
      }
      resetRecordLists("records_unavailable");
    }
    const shouldOfferOpeningSetup =
      clientState.recordsLoaded &&
      clientState.openingPositions.length === 0 &&
      clientState.transactions.length === 0 &&
      clientState.cashEvents.length === 0;
    showWorkspace(
      preserveConversation
        ? clientState.activeView
        : shouldOfferOpeningSetup
          ? "portfolio"
          : "chat",
    );
    return true;
  } catch (error) {
    if (error.name === "AbortError" || generation !== clientState.portfolioGeneration) {
      return false;
    }
    const isNetworkError = error instanceof TypeError;
    setPortfolioState(
      isNetworkError ? "portfolio_network_error" : "portfolio_invalid_response",
      "danger",
    );
    resetPortfolio(isNetworkError ? "portfolio_service_unreachable" : "portfolio_display_error");
    return false;
  } finally {
    if (generation === clientState.portfolioGeneration) {
      clientState.portfolioController = null;
      setLocalizedText(elements.portfolioLoadButton, "load");
      updateControls();
    }
  }
}

async function loadPortfolio(event) {
  event.preventDefault();
  setRawText(elements.createMessage, "");
  await loadPortfolioById(normalizeUserId(elements.userIdInput.value));
}

function sourceTone(status) {
  if (status === "OK") {
    return "success";
  }
  if (status === "NO_DATA" || status === "NO_NEWS_FOUND") {
    return "warning";
  }
  return "danger";
}

function formatTimestamp(value) {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(activeLanguage === "zh" ? "zh-CN" : "en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function createSourceCard(source) {
  const card = document.createElement("article");
  card.className = "source-card";
  card.dataset.tone = sourceTone(source.status);

  const top = document.createElement("div");
  top.className = "source-card-top";
  const title = document.createElement("strong");
  title.textContent = source.type;
  const status = document.createElement("span");
  status.className = "source-status";
  status.textContent = source.status;
  top.append(title, status);

  const metadata = document.createElement("div");
  metadata.className = "source-metadata";
  const fields = [
    ["source_ticker", source.ticker],
    ["source_provider", source.provider],
    ["source_feed", source.feed],
    ["source_market_time", source.market_timestamp],
    ["source_fetched", source.fetched_at],
  ].filter(([, value]) => Boolean(value));
  if (fields.length === 0) {
    const context = document.createElement("span");
    context.className = "source-context-note";
    setLocalizedText(context, "source_portfolio_state");
    metadata.append(context);
  } else {
    for (const [labelKey, value] of fields) {
      const item = document.createElement("div");
      item.className = "source-metadata-item";
      const label = document.createElement("span");
      label.className = "source-metadata-label";
      setLocalizedText(label, labelKey);
      const content = document.createElement("span");
      content.className = "source-metadata-value";
      if (labelKey === "source_market_time" || labelKey === "source_fetched") {
        content.dataset.timestamp = value;
        content.textContent = formatTimestamp(value);
      } else {
        setRawText(content, value);
      }
      item.append(label, content);
      metadata.append(item);
    }
  }

  card.append(top, metadata);
  return card;
}

function createQuestionExchange(question) {
  clientState.questionHistoryCount += 1;
  const exchangeId = `question-history-${clientState.questionHistoryCount}`;
  const exchange = document.createElement("section");
  exchange.className = "conversation-exchange";
  exchange.id = exchangeId;

  const userMessage = document.createElement("div");
  userMessage.className = "user-message";
  userMessage.textContent = question;

  const responseFragment = elements.responseTemplate.content.cloneNode(true);
  const assistantMessage = responseFragment.querySelector(".assistant-message");
  const responseView = {
    resultTitle: responseFragment.querySelector(".result-title"),
    responseStatus: responseFragment.querySelector(".response-status"),
    answerCopy: responseFragment.querySelector(".answer-copy"),
    sourceCount: responseFragment.querySelector(".source-count"),
    sourceList: responseFragment.querySelector(".source-list"),
  };
  setLocalizedText(responseView.resultTitle, "answer_assembling");
  setResponseState(responseView, "response_working");
  setLocalizedText(responseView.answerCopy, "answer_loading");
  responseView.sourceCount.textContent = "0";
  const sourceHeading = responseFragment.querySelector(".source-heading-label");
  setLocalizedText(sourceHeading, "context_sources");

  exchange.append(userMessage, responseFragment);
  elements.chatIntro.hidden = true;
  elements.conversationList.append(exchange);
  elements.sessionEmpty.hidden = true;

  const sessionButton = document.createElement("button");
  sessionButton.className = "session-question";
  sessionButton.type = "button";
  sessionButton.dataset.question = question;
  sessionButton.textContent = question.length > 54 ? `${question.slice(0, 53)}…` : question;
  sessionButton.setAttribute("aria-label", `${translate("question_jump")}: ${question}`);
  sessionButton.addEventListener("click", () => {
    switchAppView("chat", { focus: false });
    exchange.scrollIntoView({ block: "start" });
  });
  elements.sessionList.append(sessionButton);
  elements.conversationScroll.scrollTop = elements.conversationScroll.scrollHeight;
  assistantMessage.setAttribute("aria-live", "polite");
  clientState.activeResponse = responseView;
  return responseView;
}

function renderAnswer(payload, view) {
  const isDegraded = payload.status === "DEGRADED";
  setLocalizedText(view.resultTitle, isDegraded ? "answer_degraded" : "answer_assembled");
  setResponseState(view, payload.status, isDegraded ? "warning" : "success", false);
  setRawText(view.answerCopy, payload.answer);
  view.sourceCount.textContent = String(payload.sources.length);
  clearElement(view.sourceList);
  if (payload.sources.length === 0) {
    const placeholder = document.createElement("div");
    placeholder.className = "source-placeholder";
    setLocalizedText(placeholder, "source_none_declared");
    view.sourceList.append(placeholder);
    return;
  }
  for (const source of payload.sources) {
    view.sourceList.append(createSourceCard(source));
  }
}

function renderQuestionError(error, view) {
  setLocalizedText(view.resultTitle, "answer_failed");
  setResponseState(view, error.code, "danger", false);
  if (error.messageKey) {
    setLocalizedText(view.answerCopy, error.messageKey);
  } else {
    setRawText(view.answerCopy, error.message);
  }
  view.sourceCount.textContent = "0";
  clearElement(view.sourceList);
  const placeholder = document.createElement("div");
  placeholder.className = "source-placeholder";
  setLocalizedText(placeholder, "source_none_accepted");
  view.sourceList.append(placeholder);
}

function setApiErrorMessage(element, error) {
  element.dataset.tone = "danger";
  if (error.messageKey) {
    setLocalizedText(element, error.messageKey);
    return;
  }
  const summaryKeys = {
    INSUFFICIENT_CASH: "api_insufficient_cash",
    INSUFFICIENT_SHARES: "api_insufficient_shares",
    INVALID_TRANSACTION: "api_invalid_transaction",
    INVALID_CASH_EVENT: "api_invalid_cash_event",
    INVALID_OPENING_STATE: "api_invalid_opening_state",
    OPENING_STATE_SEALED: "api_opening_state_sealed",
    USER_NOT_FOUND: "api_user_not_found",
  };
  const summaryKey = summaryKeys[error.code];
  if (!summaryKey) {
    setRawText(element, `${error.code}: ${error.message}`);
    return;
  }

  clearElement(element);
  const summary = document.createElement("span");
  setLocalizedText(summary, summaryKey);
  const detail = document.createElement("span");
  detail.className = "error-detail";
  detail.textContent = `${error.code}: ${error.message}`;
  element.append(summary, detail);
}

function isValidDecimalInput(value, { allowZero = false } = {}) {
  if (!DECIMAL_INPUT_PATTERN.test(value)) {
    return false;
  }
  return allowZero || /[1-9]/.test(value);
}

function showFieldError(input, messageElement, messageKey) {
  input.setAttribute("aria-invalid", "true");
  messageElement.dataset.tone = "danger";
  messageElement.dataset.validationFor = input.id;
  setLocalizedText(messageElement, messageKey);
  input.focus();
}

function clearFieldError(input, messageElement) {
  input.removeAttribute("aria-invalid");
  if (messageElement.dataset.validationFor === input.id) {
    delete messageElement.dataset.validationFor;
    delete messageElement.dataset.tone;
    setRawText(messageElement, "");
  }
}

function parseOptionalOccurredAt(input) {
  const rawValue = input.value.trim();
  if (!rawValue) {
    return { valid: true, value: null };
  }
  const occurredAt = new Date(rawValue);
  if (Number.isNaN(occurredAt.getTime())) {
    return { valid: false, value: null };
  }
  return { valid: true, value: occurredAt.toISOString() };
}

function createOpeningField(labelKey, input) {
  const group = document.createElement("div");
  const label = document.createElement("label");
  label.htmlFor = input.id;
  setLocalizedText(label, labelKey);
  group.append(label, input);
  return group;
}

function createOpeningInput(id, name, placeholderKey) {
  const input = document.createElement("input");
  input.id = id;
  input.name = name;
  input.type = "text";
  input.autocomplete = "off";
  input.dataset.i18nPlaceholder = placeholderKey;
  input.placeholder = translate(placeholderKey);
  return input;
}

function addOpeningDraftRow() {
  openingDraftCounter += 1;
  const suffix = String(openingDraftCounter);
  const row = document.createElement("div");
  row.className = "opening-draft-row";

  const ticker = createOpeningInput(`opening-ticker-${suffix}`, "ticker", "ticker_placeholder");
  ticker.maxLength = 10;
  const shares = createOpeningInput(`opening-shares-${suffix}`, "shares", "shares_placeholder");
  shares.inputMode = "decimal";
  const averageCost = createOpeningInput(
    `opening-average-cost-${suffix}`,
    "average-cost",
    "price_placeholder",
  );
  averageCost.inputMode = "decimal";

  const positionType = document.createElement("select");
  positionType.id = `opening-position-type-${suffix}`;
  positionType.name = "position-type";
  for (const [value, labelKey] of [
    ["", "unspecified"],
    ["LONG_TERM", "long_term"],
    ["SWING", "swing"],
  ]) {
    const option = document.createElement("option");
    option.value = value;
    setLocalizedText(option, labelKey);
    positionType.append(option);
  }

  const remove = document.createElement("button");
  remove.className = "text-button opening-remove";
  remove.type = "button";
  setLocalizedText(remove, "remove_position");
  remove.addEventListener("click", () => {
    row.remove();
    if (elements.openingDraftRows.childElementCount === 0) {
      addOpeningDraftRow();
    }
  });

  row.append(
    createOpeningField("opening_ticker", ticker),
    createOpeningField("opening_shares", shares),
    createOpeningField("opening_average_cost", averageCost),
    createOpeningField("opening_position_type", positionType),
    remove,
  );
  elements.openingDraftRows.append(row);
}

function readOpeningPositionsDraft() {
  const positions = [];
  const uniqueKeys = new Set();
  for (const row of elements.openingDraftRows.querySelectorAll(".opening-draft-row")) {
    const tickerInput = row.querySelector('[name="ticker"]');
    const sharesInput = row.querySelector('[name="shares"]');
    const averageCostInput = row.querySelector('[name="average-cost"]');
    const positionTypeInput = row.querySelector('[name="position-type"]');
    const ticker = tickerInput.value.trim().toUpperCase();
    const shares = sharesInput.value.trim();
    const averageCost = averageCostInput.value.trim();
    if (!ticker || !isValidDecimalInput(shares) || !isValidDecimalInput(averageCost)) {
      return { valid: false, messageKey: "opening_invalid_input", positions: [] };
    }
    const normalizedType = positionTypeInput.value || "UNSPECIFIED";
    const uniqueKey = `${ticker}:${normalizedType}`;
    if (uniqueKeys.has(uniqueKey)) {
      return { valid: false, messageKey: "opening_duplicate", positions: [] };
    }
    uniqueKeys.add(uniqueKey);
    const position = { ticker, shares, average_cost: averageCost };
    if (positionTypeInput.value) {
      position.position_type = positionTypeInput.value;
    }
    positions.push(position);
  }
  return { valid: positions.length > 0, messageKey: "opening_invalid_input", positions };
}

async function saveOpeningPositions(event) {
  event.preventDefault();
  const draft = readOpeningPositionsDraft();
  if (!draft.valid) {
    elements.openingMessage.dataset.tone = "danger";
    setLocalizedText(elements.openingMessage, draft.messageKey);
    return;
  }
  const saved = await submitLedgerMutation({
    endpoint: (userId) =>
      `/v1/portfolios/${encodeURIComponent(userId)}/opening-positions`,
    payload: { positions: draft.positions },
    validateResponse: isOpeningPositionsWritePayload,
    successDetail: (response) => {
      const [firstPosition] = response.opening_positions;
      const remaining = response.opening_positions.length > 1 ? " · …" : "";
      return `${response.opening_positions.length} · ${firstPosition.id}${remaining}`;
    },
    messageElement: elements.openingMessage,
    successKey: "opening_position_saved",
  });
  if (saved) {
    clearElement(elements.openingDraftRows);
    clientState.openingSetupSkipped = false;
    updateControls();
  }
}

async function createPortfolio(event) {
  event.preventDefault();
  if (clientState.createController !== null || clientState.writeState === "submitting") {
    return;
  }

  const displayName = elements.portfolioName.value.trim();
  const initialCash = elements.initialCash.value.trim();
  if (!displayName) {
    showFieldError(elements.portfolioName, elements.createMessage, "portfolio_name_required");
    return;
  }
  if (!isValidDecimalInput(initialCash, { allowZero: true })) {
    showFieldError(elements.initialCash, elements.createMessage, "initial_cash_invalid");
    return;
  }

  const controller = new AbortController();
  clientState.createController = controller;
  if (clientState.loadedUserId !== null) {
    clientState.loadedUserId = null;
    clientState.openingSetupSkipped = false;
    clearElement(elements.openingDraftRows);
    setPortfolioState("portfolio_stale", "warning");
    resetPortfolio("portfolio_context_changed");
  }
  if (clientState.portfolioController !== null) {
    clientState.portfolioGeneration += 1;
    clientState.portfolioController.abort();
    clientState.portfolioController = null;
    clientState.loadedUserId = null;
    setPortfolioState("portfolio_stale", "warning");
    resetPortfolio("portfolio_context_changed");
  }
  invalidateQuestionContext("portfolio_context_changed");
  setLocalizedText(elements.createButton, "creating");
  setRawText(elements.createMessage, "");
  clearLedgerMessages();
  updateControls();

  try {
    const response = await fetch("/v1/portfolios", {
      method: "POST",
      signal: controller.signal,
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ display_name: displayName, initial_cash: initialCash }),
    });
    if (!response.ok) {
      setApiErrorMessage(elements.createMessage, await parseApiError(response));
      return;
    }
    const payload = await response.json();
    const createdUserId = normalizeUserId(payload?.user_id ?? "");
    if (!isCreatedPortfolioPayload(payload) || !isValidUserId(createdUserId)) {
      setLocalizedText(elements.createMessage, "create_contract_error");
      return;
    }

    saveLocalPointer(createdUserId);
    updateUrlUserId(createdUserId);
    const loaded = await loadPortfolioById(createdUserId, {
      preserveRecoveryPointer: true,
    });
    setLocalizedText(elements.createMessage, loaded ? "create_success" : "create_refresh_failed");
  } catch (error) {
    if (error.name === "AbortError" || error instanceof TypeError) {
      setLocalizedText(elements.createMessage, "create_response_unknown");
    } else {
      setLocalizedText(elements.createMessage, "create_contract_error");
    }
  } finally {
    if (clientState.createController === controller) {
      clientState.createController = null;
      setLocalizedText(elements.createButton, "create");
      updateControls();
    }
  }
}

function forgetLocalPointer() {
  if (clientState.writeState === "submitting" || clientState.createController !== null) {
    return;
  }
  clearLocalPointer();
  clearUrlUserId();
  clientState.portfolioGeneration += 1;
  clientState.portfolioController?.abort();
  clientState.portfolioController = null;
  clientState.loadedUserId = null;
  clientState.userIdInput = "";
  clientState.openingSetupSkipped = false;
  clearElement(elements.openingDraftRows);
  elements.userIdInput.value = "";
  setWriteState("idle");
  setPortfolioState("portfolio_not_loaded");
  resetPortfolio("forget_success");
  invalidateQuestionContext("answer_initial");
  setRawText(elements.createMessage, "");
  clearLedgerMessages();
  showOnboarding();
  updateControls();
}

async function submitLedgerMutation({
  endpoint,
  payload,
  validateResponse,
  successDetail,
  messageElement,
  successKey,
}) {
  const userId = clientState.loadedUserId;
  if (!isLoadedPortfolioCurrent() || clientState.writeState !== "idle" || userId === null) {
    setLocalizedText(
      messageElement,
      clientState.writeState === "refresh_required"
        ? "mutation_refresh_required"
        : "mutation_load_first",
    );
    return false;
  }

  setWriteState("submitting");
  invalidateQuestionContext("mutation_in_progress", { clearHistory: false });
  setRawText(messageElement, "");
  updateControls();

  try {
    const response = await fetch(endpoint(userId), {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const error = await parseApiError(response);
      markSnapshotRefreshRequired();
      setApiErrorMessage(messageElement, error);
      return false;
    }
    const responsePayload = await response.json();
    if (!validateResponse(responsePayload, userId)) {
      markSnapshotRefreshRequired();
      setLocalizedText(messageElement, "write_contract_error");
      return false;
    }

    const refreshed = await loadPortfolioById(userId, {
      resolveWriteState: false,
      preserveConversation: true,
    });
    if (!refreshed) {
      markSnapshotRefreshRequired();
      setLocalizedText(messageElement, "write_succeeded_refresh_failed");
      return false;
    }
    setWriteState("idle");
    setActionMessageWithValue(messageElement, successKey, successDetail(responsePayload));
    return true;
  } catch (error) {
    markSnapshotRefreshRequired();
    setLocalizedText(
      messageElement,
      error instanceof TypeError ? "write_result_unknown" : "write_contract_error",
    );
    return false;
  } finally {
    updateControls();
  }
}

async function recordTrade(event) {
  event.preventDefault();
  const occurredAt = parseOptionalOccurredAt(elements.tradeOccurredAt);
  const ticker = elements.tradeTicker.value.trim().toUpperCase();
  const price = elements.tradePrice.value.trim();
  const shares = elements.tradeShares.value.trim();
  if (!occurredAt.valid) {
    showFieldError(elements.tradeOccurredAt, elements.tradeMessage, "invalid_occurred_at");
    return;
  }
  if (!ticker) {
    showFieldError(elements.tradeTicker, elements.tradeMessage, "ticker_required");
    return;
  }
  if (!price) {
    showFieldError(elements.tradePrice, elements.tradeMessage, "price_required");
    return;
  }
  if (!isValidDecimalInput(price)) {
    showFieldError(elements.tradePrice, elements.tradeMessage, "price_invalid");
    return;
  }
  if (!shares) {
    showFieldError(elements.tradeShares, elements.tradeMessage, "shares_required");
    return;
  }
  if (!isValidDecimalInput(shares)) {
    showFieldError(elements.tradeShares, elements.tradeMessage, "shares_invalid");
    return;
  }

  const payload = {
    ticker,
    action: elements.tradeAction.value,
    price,
    shares,
  };
  if (elements.tradePositionType.value) {
    payload.position_type = elements.tradePositionType.value;
  }
  if (occurredAt.value !== null) {
    payload.occurred_at = occurredAt.value;
  }
  const reason = elements.tradeReason.value.trim();
  if (reason) {
    payload.reason = reason;
  }

  const saved = await submitLedgerMutation({
    endpoint: (userId) => `/v1/portfolios/${encodeURIComponent(userId)}/transactions`,
    payload,
    validateResponse: isTransactionWritePayload,
    successDetail: (response) =>
      `#${response.transaction.sequence} · ${response.transaction.id}`,
    messageElement: elements.tradeMessage,
    successKey: "trade_saved",
  });
  if (saved) {
    elements.tradeTicker.value = "";
    elements.tradePrice.value = "";
    elements.tradeShares.value = "";
    elements.tradeOccurredAt.value = "";
    elements.tradeReason.value = "";
  }
}

async function recordCashEvent(event) {
  event.preventDefault();
  const occurredAt = parseOptionalOccurredAt(elements.cashOccurredAt);
  const amount = elements.cashAmount.value.trim();
  if (!occurredAt.valid) {
    showFieldError(elements.cashOccurredAt, elements.cashMessage, "invalid_occurred_at");
    return;
  }
  if (!amount) {
    showFieldError(elements.cashAmount, elements.cashMessage, "amount_required");
    return;
  }
  if (!isValidDecimalInput(amount)) {
    showFieldError(elements.cashAmount, elements.cashMessage, "amount_invalid");
    return;
  }

  const payload = {
    event_type: elements.cashEventType.value,
    amount,
  };
  if (occurredAt.value !== null) {
    payload.occurred_at = occurredAt.value;
  }
  const reason = elements.cashReason.value.trim();
  if (reason) {
    payload.reason = reason;
  }

  const saved = await submitLedgerMutation({
    endpoint: (userId) => `/v1/portfolios/${encodeURIComponent(userId)}/cash-events`,
    payload,
    validateResponse: isCashWritePayload,
    successDetail: (response) =>
      `#${response.cash_event.sequence} · ${response.cash_event.id}`,
    messageElement: elements.cashMessage,
    successKey: "cash_saved",
  });
  if (saved) {
    elements.cashAmount.value = "";
    elements.cashOccurredAt.value = "";
    elements.cashReason.value = "";
  }
}

async function askQuestion(event) {
  event.preventDefault();
  const question = elements.question.value.trim();
  const requestedUserId = clientState.loadedUserId;

  if (
    clientState.writeState !== "idle" ||
    requestedUserId === null ||
    requestedUserId !== clientState.userIdInput
  ) {
    invalidateLoadedPortfolio("portfolio_context_stale");
    return;
  }
  if (!question) {
    setLocalizedText(elements.questionHint, "question_enter");
    elements.question.focus();
    return;
  }

  clientState.questionGeneration += 1;
  const generation = clientState.questionGeneration;
  clientState.questionController?.abort();
  const controller = new AbortController();
  clientState.questionController = controller;
  const responseView = createQuestionExchange(question);
  elements.question.value = "";

  elements.askButton.disabled = true;
  setLocalizedText(elements.askButton, "analyzing");
  elements.question.disabled = true;

  try {
    const response = await fetch("/v1/investment/questions", {
      method: "POST",
      signal: controller.signal,
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ user_id: requestedUserId, question }),
    });
    if (
      generation !== clientState.questionGeneration ||
      requestedUserId !== clientState.loadedUserId ||
      requestedUserId !== clientState.userIdInput
    ) {
      return;
    }
    if (!response.ok) {
      const error = await parseApiError(response);
      if (
        generation !== clientState.questionGeneration ||
        requestedUserId !== clientState.loadedUserId ||
        requestedUserId !== clientState.userIdInput
      ) {
        return;
      }
      renderQuestionError(error, responseView);
      return;
    }
    const payload = await response.json();
    if (
      generation !== clientState.questionGeneration ||
      requestedUserId !== clientState.loadedUserId ||
      requestedUserId !== clientState.userIdInput
    ) {
      return;
    }
    if (!isAnswerPayload(payload)) {
      renderQuestionError(
        {
          code: "INVALID_RESPONSE",
          messageKey: "answer_contract_error",
        },
        responseView,
      );
      return;
    }
    renderAnswer(payload, responseView);
  } catch (error) {
    if (error.name === "AbortError" || generation !== clientState.questionGeneration) {
      return;
    }
    const isNetworkError = error instanceof TypeError;
    renderQuestionError(
      {
        code: isNetworkError ? "NETWORK_ERROR" : "INVALID_RESPONSE",
        messageKey: isNetworkError ? "answer_service_unreachable" : "answer_display_error",
      },
      responseView,
    );
  } finally {
    if (
      generation === clientState.questionGeneration &&
      requestedUserId === clientState.loadedUserId &&
      requestedUserId === clientState.userIdInput
    ) {
      clientState.questionController = null;
      clientState.activeResponse = null;
      setLocalizedText(elements.askButton, "ask");
      updateControls();
    }
  }
}

async function initializeApp() {
  resetPortfolio();
  resetResult();
  setPortfolioState("portfolio_not_loaded");
  setWriteState("idle");
  applyLanguage();
  switchPortfolioSection("overview");
  showOnboarding();

  const urlUserId = normalizeUserId(
    new URLSearchParams(window.location.search).get("user_id") ?? "",
  );
  const pointerUserId = readLocalPointer();
  const initialUserId = isValidUserId(urlUserId) ? urlUserId : pointerUserId;
  if (urlUserId && !isValidUserId(urlUserId)) {
    clearUrlUserId();
  }
  if (initialUserId) {
    await loadPortfolioById(initialUserId);
  } else {
    updateControls();
  }
}

elements.userIdInput.addEventListener("input", handleUserIdInput);
elements.portfolioForm.addEventListener("submit", loadPortfolio);
elements.createForm.addEventListener("submit", createPortfolio);
elements.forgetPointerButton.addEventListener("click", forgetLocalPointer);
elements.switchPortfolioButton.addEventListener("click", () => {
  showOnboarding();
  elements.userIdInput.focus();
});
elements.cancelOnboardingButton.addEventListener("click", () => {
  if (clientState.loadedUserId !== null) {
    showWorkspace();
  }
});
elements.navChat.addEventListener("click", () => switchAppView("chat"));
elements.navPortfolio.addEventListener("click", () => switchAppView("portfolio"));
elements.newQuestionButton.addEventListener("click", () => {
  switchAppView("chat", { focus: false });
  if (!elements.question.disabled) {
    elements.question.focus();
  }
});
elements.portfolioTabOverview.addEventListener("click", () =>
  switchPortfolioSection("overview"),
);
elements.portfolioTabTrade.addEventListener("click", () => switchPortfolioSection("trade"));
elements.portfolioTabCash.addEventListener("click", () => switchPortfolioSection("cash"));
elements.reloadPortfolioButton.addEventListener("click", async () => {
  if (clientState.loadedUserId !== null) {
    await loadPortfolioById(clientState.loadedUserId, { preserveConversation: true });
  }
});
elements.openingForm.addEventListener("submit", saveOpeningPositions);
elements.addOpeningRowButton.addEventListener("click", addOpeningDraftRow);
elements.skipOpeningSetupButton.addEventListener("click", () => {
  clientState.openingSetupSkipped = true;
  setLocalizedText(elements.openingMessage, "opening_setup_skipped");
  updateControls();
});
elements.reopenOpeningSetupButton.addEventListener("click", () => {
  clientState.openingSetupSkipped = false;
  setRawText(elements.openingMessage, "");
  updateControls();
});
elements.tradeForm.addEventListener("submit", recordTrade);
elements.cashForm.addEventListener("submit", recordCashEvent);
elements.questionForm.addEventListener("submit", askQuestion);
elements.question.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    elements.questionForm.requestSubmit();
  }
});
elements.languageToggle.addEventListener("click", toggleLanguage);

const validatedFields = [
  [elements.portfolioName, elements.createMessage],
  [elements.initialCash, elements.createMessage],
  [elements.tradeTicker, elements.tradeMessage],
  [elements.tradePrice, elements.tradeMessage],
  [elements.tradeShares, elements.tradeMessage],
  [elements.tradeOccurredAt, elements.tradeMessage],
  [elements.cashAmount, elements.cashMessage],
  [elements.cashOccurredAt, elements.cashMessage],
];
for (const [input, messageElement] of validatedFields) {
  input.addEventListener("input", () => clearFieldError(input, messageElement));
}

initializeApp();
