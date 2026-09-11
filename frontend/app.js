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
    asset_selection_required: "Choose this asset from the verified candidate list before saving.",
    asset_auto_selected: "Verified asset selected automatically.",
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
    question_ready: "Uses your current portfolio. Enter to ask · Shift+Enter for a new line.",
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
    import_starting_positions: "Import starting positions",
    import_review_title: "Review before saving",
    draft_only_note: "Draft only · nothing is saved yet",
    import_review_hint: "Type a ticker in the position row, paste text, or add screenshots to prepare an editable draft.",
    import_methods: "Import methods",
    manual_import: "Manual search",
    text_import: "Text import",
    screenshot_import: "Screenshot",
    asset_search_label: "Search symbol or company name",
    asset_search_placeholder: "Search symbol or company name",
    search_assets: "Search",
    asset_candidate_heading: "Choose the verified symbol",
    searching_assets: "Searching…",
    use_asset: "Use this asset",
    asset_selected: "Asset selected. Complete the remaining fields, then confirm with Save.",
    asset_search_empty: "Enter a symbol or company name to search.",
    asset_no_match: "No supported US stock or ETF matched that search.",
    asset_search_failed: "Asset search is temporarily unavailable. Try again later.",
    asset_provider_auth_failed: "Asset search is not configured. Configure the provider before selecting an asset.",
    asset_rate_limited: "Asset search is rate limited. Try again later.",
    asset_invalid_response: "Asset search returned an invalid response.",
    text_import_label: "Paste the holdings text",
    text_import_placeholder: "Paste rows from your broker statement",
    prepare_text_draft: "Prepare editable draft",
    preparing_text_draft: "Preparing text draft…",
    screenshot_import_label: "Choose up to two broker screenshots",
    prepare_screenshot_draft: "Prepare editable draft",
    preparing_screenshot_draft: "Preparing screenshot draft…",
    start_recognition: "Start recognition",
    attachment_drop_prompt: "Add portfolio screenshots",
    attachment_drop_hint: "Click, drop, or paste · up to 2 images · 10 MB each",
    attachment_ready: "Images ready. Nothing is uploaded until you start recognition.",
    attachment_limit: "You can attach up to two images at a time.",
    attachment_remove: "Remove",
    attachment_preview_open: "View full image",
    attachment_preview_image: "Uploaded image",
    attachment_file_required: "Choose, drop, or paste an image first.",
    screenshot_privacy_notice: "Selected screenshots are sent to Alibaba Model Studio only after you start recognition. PositionPilot does not save them; the Provider's fixed retention period is not publicly disclosed.",
    screenshot_file_required: "Choose a JPEG, PNG, or WebP screenshot first.",
    screenshot_file_invalid: "Choose a supported JPEG, PNG, or WebP screenshot.",
    screenshot_file_too_large: "That screenshot is too large. Choose an image no larger than 10 MB.",
    recognition_invalid_request: "The import input is not valid. Check the text or screenshot and try again.",
    recognition_auth_failed: "Screenshot recognition is not configured. You can search and select the holdings manually.",
    recognition_rate_limited: "Recognition is rate limited. Try again later or search and select the holdings manually.",
    recognition_provider_failed: "Recognition is temporarily unavailable. You can search and select the holdings manually.",
    recognition_invalid_response: "Recognition returned an invalid response. Review the fields manually.",
    recognition_empty: "No holding rows were recognized. Add a row manually to continue.",
    draft_review_signal: "Review cue",
    draft_status_present: "recognized",
    draft_status_missing: "missing — enter this field",
    draft_status_invalid: "needs correction",
    draft_status_ambiguous: "ambiguous — choose a matching asset",
    confidence_signal: "Recognition confidence",
    confidence_unavailable: "not provided",
    find_matching_assets: "Find matching assets",
    recognition_draft_ready: "Draft ready. Verified symbols are ready to save; review the remaining fields.",
    recognition_input_text: "Text import",
    recognition_input_screenshot: "Screenshot import",
    imported_warning: "Provider warning",
    asset_verified_exact: "Verified",
    reconciliation_title: "Reconcile from a broker screenshot",
    reconciliation_summary: "Update selected positions from a current screenshot. Unlisted positions stay unchanged, and no trade or cash record is created.",
    reconciliation_broker_label: "Broker or source (optional)",
    reconciliation_broker_placeholder: "e.g. Fidelity, Schwab, IBKR",
    reconciliation_screenshot_label: "Attach current positions screenshots",
    reconciliation_revalidate: "Revalidate all assets",
    reconciliation_revalidate_running: "Revalidating assets…",
    reconciliation_save: "Save reconciliation",
    reconciliation_saved: "Position reconciliation saved",
    reconciliation_no_positions: "Recognize a screenshot and confirm at least one position first.",
    reconciliation_not_validated: "Revalidate and explicitly choose a verified asset before saving.",
    reconciliation_canonical_match: "Canonical match found. Confirm to bind",
    reconciliation_provider_unavailable: "Asset provider is unavailable. Try revalidation again later.",
    reconciliation_invalid_asset: "No verified candidate matched this ticker.",
    reconciliation_records: "Position reconciliation records",
    source: "Source",
    broker: "Broker",
    source_info: "Source details",
    confirmed_at: "Confirmed at",
    mutation_unknown: "Result unknown. Do not retry automatically. Reload and inspect the latest portfolio state.",
    refresh_failed: "The write may have succeeded, but the latest portfolio could not be loaded. Reload before continuing.",
    invalid_form: "Check the highlighted fields and try again.",
    insufficient_cash: "Insufficient cash for this purchase and backend-calculated fees.",
    insufficient_shares: "Insufficient shares in this position type.",
    opening_sealed: "Existing positions can only be added before the first trade, cash entry, or position reconciliation.",
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
    chat_intro_eyebrow: "你的投资组合已连接", chat_intro_title: "你正在思考什么投资决策？", chat_intro_body: "提出一个具体问题。PositionPilot 会使用你的持仓及问题所需的当前信息。", no_memory_notice: "问题仅保留在当前浏览器标签页，不构成模型记忆。", investment_question: "投资问题", question_placeholder: "例如：GOOG 今天还能加一点吗？", question_ready: "将使用你的当前投资组合。Enter 提交 · Shift+Enter 换行。", ask: "询问 PositionPilot ↗", asking: "分析中…",
    portfolio_reload: "刷新", portfolio_sections: "投资组合分区", overview_tab: "持仓", trade_tab: "交易", cash_tab: "现金记录", available_cash: "可用现金", ledger_derived: "账本计算 · USD", portfolio_context: "投资组合上下文", session_owned: "当前 Session 所属", session_owned_hint: "身份来自你的本地私有 Session。", opening_state: "起始状态", existing_positions_setup: "添加已有持仓", starting_facts: "一次性起始事实", opening_explainer: "记录开始跟踪前已经持有的仓位，不改变现金，也不创建虚假交易。", skip_for_now: "暂时跳过", save_opening_positions: "保存已有持仓", add_existing_positions: "添加已有持仓", open_positions: "当前持仓", portfolio_empty_loaded: "目前没有持仓。", opening_records: "起始持仓记录", records_empty: "暂无记录。", import_starting_positions: "导入起始持仓", import_review_title: "保存前请复核", draft_only_note: "仅为 Draft · 尚未保存", import_review_hint: "可以手动搜索、粘贴文本或选择一张截图，生成可编辑 Draft。请确认下面每个字段后再保存。", import_methods: "导入方式", manual_import: "手动搜索", text_import: "文本导入", screenshot_import: "截图识别", asset_search_label: "搜索标的或公司名称", asset_search_placeholder: "搜索标的或公司名称", search_assets: "搜索", asset_candidate_heading: "请选择已验证的标的", searching_assets: "搜索中…", use_asset: "使用此标的", asset_selected: "已选择标的。请补完其余字段，再点击保存完成确认。", asset_search_empty: "请输入标的或公司名称后搜索。", asset_no_match: "没有匹配的可用美国股票或 ETF。", asset_search_failed: "标的搜索暂时不可用。请稍后重试。", asset_provider_auth_failed: "标的搜索尚未配置，请先配置 Provider。", asset_rate_limited: "标的搜索已达到限流，请稍后重试。", asset_invalid_response: "标的搜索返回了无效响应。", text_import_label: "粘贴持仓文本", text_import_placeholder: "粘贴券商对账单中的持仓行", prepare_text_draft: "生成可编辑 Draft", preparing_text_draft: "正在生成文本 Draft…", screenshot_import_label: "选择一张券商持仓截图", prepare_screenshot_draft: "生成可编辑 Draft", preparing_screenshot_draft: "正在生成截图 Draft…", start_recognition: "开始识别", attachment_drop_prompt: "将图片拖到这里，或直接粘贴截图", attachment_drop_hint: "JPEG、PNG 或 WebP · 最大 10 MB", attachment_ready: "附件已准备好。点击“开始识别”前不会上传。", attachment_remove: "移除", attachment_file_required: "请先选择、拖入或粘贴图片。", screenshot_privacy_notice: "截图会发送至 Alibaba Model Studio 进行识别。PositionPilot 不保存图片；Provider 的固定保留时长尚未公开。", screenshot_file_required: "请先选择 JPEG、PNG 或 WebP 截图。", screenshot_file_invalid: "请选择受支持的 JPEG、PNG 或 WebP 截图。", screenshot_file_too_large: "截图过大，请选择不超过 10 MB 的图片。", recognition_invalid_request: "导入输入无效。请检查文本或截图后重试。", recognition_auth_failed: "截图识别尚未配置。你也可以手动搜索并选择持仓。", recognition_rate_limited: "识别请求已达到限流，请稍后重试或手动搜索并选择持仓。", recognition_provider_failed: "识别暂时不可用，你可以手动搜索并选择持仓。", recognition_invalid_response: "识别返回了无效响应，请手动复核字段。", recognition_empty: "没有识别出持仓行。请手动添加一行后继续。", draft_review_signal: "复核提示", draft_status_present: "已识别", draft_status_missing: "缺失 — 请填写", draft_status_invalid: "需要修正", draft_status_ambiguous: "有歧义 — 请选择匹配标的", confidence_signal: "识别置信度", confidence_unavailable: "未提供", find_matching_assets: "查找匹配标的", asset_selection_required: "保存前必须从已验证的候选列表中选择此标的。", asset_auto_selected: "已自动选择经过验证的标的。", recognition_draft_ready: "Draft 已生成。请复核每个字段，再点击保存完成确认。", recognition_input_text: "文本导入", recognition_input_screenshot: "截图导入", imported_warning: "Provider 提示", reconciliation_title: "用券商截图校准持仓", reconciliation_summary: "根据当前截图更新选中的持仓。截图中未出现的持仓保持不变，也不会创建交易或现金记录。", reconciliation_broker_label: "券商或来源（可选）", reconciliation_broker_placeholder: "例如：Fidelity、Schwab、IBKR", reconciliation_screenshot_label: "附加当前持仓截图", reconciliation_revalidate: "重新验证全部标的", reconciliation_revalidate_running: "正在重新验证标的…", reconciliation_save: "保存持仓校准", reconciliation_saved: "持仓校准已保存", reconciliation_no_positions: "请先识别截图，并确认至少一条持仓。", reconciliation_not_validated: "请重新验证并明确选择已验证的标的后再保存。", reconciliation_canonical_match: "找到规范标的。点击确认绑定", reconciliation_provider_unavailable: "标的 Provider 暂时不可用，请稍后重试。", reconciliation_invalid_asset: "没有找到与该 ticker 匹配的已验证候选。",
    reconciliation_records: "持仓校准记录", source: "来源", broker: "券商", source_info: "来源详情", confirmed_at: "确认时间",
    transaction_entry: "交易", trade_entry: "交易记录", immutable_entry: "追加不可变记录", action: "操作", price: "价格", occurred_at_optional: "发生时间（可选）", occurred_at_hint: "留空使用后端应用时间。", reason_optional: "原因（可选）", save_trade: "保存交易", transaction_history: "交易历史", cash_activity: "现金活动", cash_entry: "现金记录", cash_event_type: "现金类型", amount: "金额", save_cash: "保存现金记录", cash_history: "现金历史", cost_basis: "成本基础", commission: "手续费", fee_schedule: "费用规则", occurred_at: "发生时间", reason: "原因", sequence: "序号", recorded_at: "记录时间", not_provided: "未填写", trade_saved: "交易已保存", cash_saved: "现金记录已保存", opening_saved: "已有持仓已保存", mutation_unknown: "结果未知。请勿自动重试，请刷新并检查最新投资组合状态。", refresh_failed: "写入可能已成功，但最新投资组合加载失败。继续前请先刷新。", invalid_form: "请检查标记的字段后再提交。", insufficient_cash: "可用现金不足以覆盖本次买入及后端计算的费用。", insufficient_shares: "该仓位类型下的股数不足。", opening_sealed: "已有持仓只能在第一笔交易、现金记录或持仓校准前添加。", future_time: "发生时间不能晚于当前时间。", session_expired: "本地 Session 已过期，请重新登录。",
    working_title: "正在整理决策上下文", working_answer: "正在读取你的投资组合并选择当前信息。", answer_label: "回答", sources_used: "使用的来源", source_explainer: "支持本次回答的上下文。", answer_ready: "基于投资组合的回答", answer_degraded: "上下文有限的回答", answer_failed: "暂时无法回答", source_ticker: "标的", source_provider: "数据提供方", source_feed: "数据源", source_market_time: "市场时间", source_fetched: "获取时间", source_portfolio: "投资组合持仓与现金", source_quote: "当前市场报价", source_history: "价格历史", source_news: "近期新闻", source_market: "市场环境", no_sources: "本次未返回支持来源。", question_required: "请输入一个具体的投资问题。", question_failed: "PositionPilot 未能完成本次问题，请查看状态后重试。",
  },
};

Object.assign(translations.zh, {
  import_review_hint: "在持仓行输入 ticker、粘贴文本，或添加截图来生成可编辑 Draft。",
  screenshot_import_label: "选择最多两张券商持仓截图",
  attachment_drop_prompt: "添加持仓截图",
  attachment_drop_hint: "点击、拖入或粘贴 · 最多 2 张 · 每张不超过 10 MB",
  attachment_ready: "图片已准备好。点击“开始识别”前不会上传。",
  attachment_limit: "一次最多添加两张图片。",
  attachment_preview_open: "查看大图",
  attachment_preview_image: "已上传图片",
  screenshot_privacy_notice: "只有点击“开始识别”后，所选截图才会发送至 Alibaba Model Studio。PositionPilot 不保存图片；Provider 的固定保留时长尚未公开。",
  recognition_draft_ready: "Draft 已生成。已验证标的可直接保存，请复核其余字段。",
  asset_verified_exact: "已验证",
  reconciliation_screenshot_label: "添加当前持仓截图",
});

Object.assign(translations.en, {
  hero_summary: "Track the positions you own, record trades and cash activity, and ask focused questions using current portfolio and market context.",
  proof_ledger: "Trade and cash history",
  setup_eyebrow: "Portfolio setup",
  setup_title: "Add your cash and current holdings.",
  setup_summary: "Start with what you hold today, or begin with an empty portfolio.",
  opening_positions: "Current holdings",
  opening_optional_hint: "Optional. Add stocks you already own, or start with none.",
  structured_state: "Portfolio",
  portfolio_manage_title: "Current Portfolio",
  current_portfolio: "Current Portfolio",
  positions_count_label: "positions",
  last_price: "Last",
  time: "Time",
  side: "Side",
  status: "Status",
  position_type: "Type",
  buy: "Buy",
  sell: "Sell",
  buy_stock: "Buy stock",
  sell_stock: "Sell stock",
  import_action: "Import",
  import_holdings: "Import holdings",
  add_screenshot: "Add screenshot",
  cash_action: "Deposit / Withdraw",
  deposit: "Deposit",
  withdrawal: "Withdrawal",
  source_optional: "Source (optional)",
  screenshot_privacy_short: "Sent to Alibaba Model Studio for recognition.",
  edit_current: "Edit current",
  add_holding: "Add holding",
  save: "Save",
  sell_from: "Sell from",
  fee_calculated: "Fee is calculated automatically.",
  buy_first_stock: "Buy your first stock",
  edit_lot: "Edit lot",
  price_cost: "Price / Cost",
  edited: "Edited",
  completed: "Completed",
  details: "Details",
  edit: "Edit",
  current_values: "Current values",
  original_values: "Original values",
  edit_history: "Edit history",
  edit_unavailable: "Editing is available for current buy lots.",
  aggregate_edit_unavailable: "This type contains multiple lots. You can still change this lot's type.",
  reconciliation_revalidate: "Verify tickers",
  holding_name: "Holding",
  unrealized_pnl: "Unrealized P&L",
  unrealized_pnl_percent: "P&L %",
  market_value: "Market value",
  purchase_time: "Purchased",
  imported_holding: "Imported holding",
  strategy_swing: "Swing",
  strategy_long_term: "Long term",
  manual_calibration: "Edit current holdings manually",
  select_sell_lots: "Select lots to sell",
  allocation_total_hint: "Allocated shares must equal the trade shares.",
  valuation_unavailable: "Valuation unavailable",
  lot_type_saved: "Lot type updated",
  transaction_correction: "Transaction correction",
  correct_purchase: "Correct purchase lot",
  save_correction: "Save correction",
  correction_saved: "Purchase correction saved",
  edit_purchase: "Edit purchase",
  no_aggregate_holdings_to_calibrate: "No imported aggregate holdings can be edited here. Edit purchase lots from the holdings list.",
});

Object.assign(translations.zh, {
  hero_summary: "记录当前持仓、交易和资金变化，并结合投资组合与市场信息提出具体问题。",
  proof_ledger: "交易与资金历史",
  setup_eyebrow: "投资组合设置",
  setup_title: "添加现金和当前持仓",
  setup_summary: "录入你现在持有的资产，也可以从空投资组合开始。",
  opening_positions: "当前持仓",
  opening_optional_hint: "可选。添加已经持有的股票，或暂时不添加。",
  structured_state: "投资组合",
  portfolio_manage_title: "当前持仓",
  current_portfolio: "当前持仓",
  positions_count_label: "个持仓",
  last_price: "现价",
  time: "时间",
  side: "方向",
  status: "状态",
  position_type: "类型",
  buy: "买入",
  sell: "卖出",
  buy_stock: "买入股票",
  sell_stock: "卖出股票",
  import_action: "导入",
  import_holdings: "导入持仓",
  add_screenshot: "添加截图",
  cash_action: "入金 / 出金",
  deposit: "入金",
  withdrawal: "出金",
  source_optional: "来源（可选）",
  screenshot_privacy_short: "截图将发送至阿里云 Model Studio 识别。",
  edit_current: "编辑当前持仓",
  add_holding: "添加持仓",
  save: "保存",
  sell_from: "从以下批次卖出",
  fee_calculated: "手续费由系统自动计算。",
  buy_first_stock: "买入第一只股票",
  edit_lot: "编辑批次",
  price_cost: "价格 / 成本",
  edited: "已编辑",
  completed: "已完成",
  details: "详情",
  edit: "编辑",
  current_values: "当前值",
  original_values: "原始值",
  edit_history: "编辑记录",
  edit_unavailable: "目前仅支持编辑仍在持有的买入批次。",
  aggregate_edit_unavailable: "这个类型包含多个批次；当前仍可修改此批次的持仓类型。",
  reconciliation_revalidate: "验证标的",
  holding_name: "持仓",
  unrealized_pnl: "未实现盈亏",
  unrealized_pnl_percent: "盈亏 %",
  market_value: "市场价值",
  purchase_time: "购买时间",
  imported_holding: "导入持仓",
  strategy_swing: "波段仓",
  strategy_long_term: "长期仓",
  manual_calibration: "手工校准当前持仓",
  select_sell_lots: "选择卖出批次",
  allocation_total_hint: "分配股数之和必须等于成交股数。",
  valuation_unavailable: "估值不可用",
  lot_type_saved: "批次类型已更新",
  transaction_correction: "交易更正",
  correct_purchase: "修正购买批次",
  save_correction: "保存更正",
  correction_saved: "购买批次更正已保存",
  edit_purchase: "修改购买记录",
  no_aggregate_holdings_to_calibrate: "没有可在这里修改的导入汇总持仓；请在持仓列表中修改购买批次。",
});

const state = {
  language: "en",
  account: null,
  loadedUserId: null,
  snapshot: null,
  valuation: null,
  valuationController: null,
  openingRecords: [],
  reconciliationRecords: [],
  reconciliationSource: "SCREENSHOT",
  transactionRecords: [],
  buyCorrectionRecords: [],
  cashRecords: [],
  openingDismissed: false,
  writeState: "idle",
  portfolioReadState: "idle",
  authTransition: "idle",
  authGeneration: 0,
  portfolioGeneration: 0,
  questionGeneration: 0,
  portfolioController: null,
  importController: null,
  importGeneration: 0,
  importPending: false,
  questionController: null,
  questionPending: false,
  questionComposing: false,
  pendingQuestionView: null,
  questionCount: 0,
  activeView: "chat",
  selectedLot: null,
};

const DECIMAL_PATTERN = /^(?:0|[1-9]\d*)(?:\.\d{1,8})?$/;
const IMPORT_IMAGE_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);
const MAX_IMPORT_IMAGE_BYTES = 10 * 1024 * 1024;
const MAX_IMPORT_IMAGES = 2;
const ASSET_AUTOCOMPLETE_DELAY_MS = 250;
const assetAutocompleteStates = new WeakMap();
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

function importElements(prefix) {
  return {
    root: byId(`${prefix}-import-tools`),
    tabs: [...document.querySelectorAll(`#${prefix}-import-tools [data-import-mode]`)],
    panels: {
      text: byId(`${prefix}-import-text-panel`),
      screenshot: byId(`${prefix}-import-screenshot-panel`),
    },
    textInput: byId(`${prefix}-import-text`),
    textSubmit: byId(`${prefix}-import-text-submit`),
    textMessage: byId(`${prefix}-import-text-message`),
    screenshotInput: byId(`${prefix}-import-screenshot`),
    screenshotSubmit: byId(`${prefix}-import-screenshot-submit`),
    screenshotMessage: byId(`${prefix}-import-screenshot-message`),
    attachmentComposer: byId(`${prefix}-attachment-composer`),
    attachmentDropzone: byId(`${prefix}-attachment-dropzone`),
    attachmentPreview: byId(`${prefix}-attachment-preview`),
    attachments: [],
    defaultMode: document.querySelector(`#${prefix}-import-tools [data-import-mode]`)?.dataset.importMode
      ?? (byId(`${prefix}-import-text-panel`) ? "text" : "screenshot"),
    draftFeedback: byId(`${prefix}-import-draft-feedback`),
  };
}

const elements = {
  languageToggle: byId("language-toggle"), engineeringSmokeBanner: byId("engineering-smoke-banner"), homeView: byId("home-view"), authView: byId("auth-view"), setupView: byId("setup-view"), appShell: byId("app-shell"),
  homeRegister: byId("home-register-button"), homeLogin: byId("home-login-button"), heroRegister: byId("hero-register-button"), heroLogin: byId("hero-login-button"), authHome: byId("auth-home-button"), authBack: byId("auth-back-button"), authTitle: byId("auth-title"),
  registerTab: byId("register-tab"), loginTab: byId("login-tab"), registerPanel: byId("register-panel"), loginPanel: byId("login-panel"), registerForm: byId("register-form"), registerFields: byId("register-fields"), registerName: byId("register-name"), registerEmail: byId("register-email"), registerPassword: byId("register-password"), registerConfirm: byId("register-confirm"), registerMessage: byId("register-message"), loginForm: byId("login-form"), loginFields: byId("login-fields"), loginEmail: byId("login-email"), loginPassword: byId("login-password"), loginMessage: byId("login-message"),
  setupAccountName: byId("setup-account-name"), setupLogout: byId("setup-logout-button"), setupForm: byId("setup-form"), setupFields: byId("setup-fields"), setupCash: byId("setup-initial-cash"), setupRows: byId("setup-draft-rows"), setupAddRow: byId("setup-add-row"), setupZero: byId("setup-zero-button"), setupMessage: byId("setup-message"), setupImport: importElements("setup"),
  navChat: byId("nav-chat"), navPortfolio: byId("nav-portfolio"), newQuestion: byId("new-question-button"), chatView: byId("chat-view"), portfolioView: byId("portfolio-view"), viewTitle: byId("view-title"), viewEyebrow: byId("view-eyebrow"), portfolioState: byId("portfolio-state"), writeState: byId("write-state"), reloadPortfolio: byId("reload-portfolio-button"), accountName: byId("account-display-name"), accountEmail: byId("account-email"), headerAccountName: byId("header-account-name"), headerAccountInitial: byId("header-account-initial"), accountMessage: byId("account-message"), logout: byId("logout-button"), headerLogout: byId("header-logout-button"),
  chatIntro: byId("chat-intro"), conversationScroll: byId("conversation-scroll"), conversationList: byId("conversation-list"), sessionEmpty: byId("session-empty"), sessionList: byId("session-list"), questionForm: byId("question-form"), question: byId("question"), questionHint: byId("question-hint"), ask: byId("ask-button"), responseTemplate: byId("assistant-response-template"),
  portfolioTabs: [], portfolioPanels: [], availableCash: byId("available-cash"), positionCount: byId("position-count"), positionsEmpty: byId("positions-empty"), positionList: byId("position-list"), emptyBuy: byId("empty-buy-button"), openBuy: byId("open-buy-dialog"), openImport: byId("open-import-dialog"), openCash: byId("open-cash-dialog"),
  openingSetup: byId("opening-setup"), reopenOpening: byId("reopen-opening-setup"), openingForm: byId("opening-form"), openingFields: byId("opening-fields"), openingRows: byId("opening-draft-rows"), addOpeningRow: byId("add-opening-row"), skipOpening: byId("skip-opening-setup"), openingMessage: byId("opening-message"), openingImport: importElements("opening"), reconciliationCard: byId("position-reconciliation"), reconciliationForm: byId("reconciliation-form"), reconciliationFields: byId("reconciliation-fields"), reconciliationRows: byId("reconciliation-draft-rows"), reconciliationBroker: byId("reconciliation-broker"), reconciliationAddRow: byId("reconciliation-add-row"), reconciliationLoadCurrent: byId("reconciliation-load-current"), reconciliationRevalidate: byId("reconciliation-revalidate"), reconciliationSubmit: byId("reconciliation-submit"), reconciliationMessage: byId("reconciliation-message"), reconciliationImport: importElements("reconciliation"),
  tradeDialog: byId("trade-dialog"), tradeDialogTitle: byId("trade-dialog-title"), tradeDialogClose: byId("trade-dialog-close"), tradeBuyMode: byId("trade-buy-mode"), tradeSellMode: byId("trade-sell-mode"), tradeForm: byId("trade-form"), tradeFields: byId("trade-fields"), tradeAction: byId("trade-action"), tradeType: byId("trade-position-type"), tradeTicker: byId("trade-ticker"), tradePrice: byId("trade-price"), tradeShares: byId("trade-shares"), tradeTime: byId("trade-occurred-at"), tradeReason: byId("trade-reason"), tradeMessage: byId("trade-message"), tradeLotAllocation: byId("trade-lot-allocation"), tradeLotList: byId("trade-lot-list"), transactionCount: byId("transaction-count"), transactionsEmpty: byId("transactions-empty"), transactionList: byId("transaction-list"),
  cashDialog: byId("cash-dialog"), cashDialogClose: byId("cash-dialog-close"), cashForm: byId("cash-form"), cashFields: byId("cash-fields"), cashType: byId("cash-event-type"), cashAmount: byId("cash-amount"), cashTime: byId("cash-occurred-at"), cashReason: byId("cash-reason"), cashMessage: byId("cash-message"), cashCount: byId("cash-event-count"), cashEmpty: byId("cash-events-empty"), cashList: byId("cash-event-list"),
  importDialog: byId("import-dialog"), importDialogClose: byId("import-dialog-close"),
  imagePreviewDialog: byId("image-preview-dialog"), imagePreviewClose: byId("image-preview-close"), imagePreviewFull: byId("image-preview-full"), imagePreviewCaption: byId("image-preview-caption"),
  correctionDialog: byId("buy-correction-dialog"), correctionForm: byId("buy-correction-form"), correctionClose: byId("buy-correction-close"), correctionLotId: byId("buy-correction-lot-id"), correctionSymbol: byId("buy-correction-symbol"), correctionPrice: byId("buy-correction-price"), correctionShares: byId("buy-correction-shares"), correctionTime: byId("buy-correction-time"), correctionType: byId("buy-correction-type"), correctionReason: byId("buy-correction-reason"), correctionMessage: byId("buy-correction-message"),
  transactionDetailDialog: byId("transaction-detail-dialog"), transactionDetailTitle: byId("transaction-detail-title"), transactionDetailSubtitle: byId("transaction-detail-subtitle"), transactionDetailContent: byId("transaction-detail-content"), transactionDetailActions: byId("transaction-detail-actions"), transactionDetailClose: byId("transaction-detail-close"),
};

const importConfigs = [
  { key: "setup", controls: elements.setupImport, rows: elements.setupRows },
  { key: "opening", controls: elements.openingImport, rows: elements.openingRows },
  { key: "reconciliation", controls: elements.reconciliationImport, rows: elements.reconciliationRows },
];

function translate(key) {
  return translations[state.language][key] ?? translations.en[key] ?? key;
}

function setLocalizedText(element, key) {
  if (!element) return;
  element.dataset.i18n = key;
  element.textContent = translate(key);
}

function setMessage(element, keyOrText, tone = "danger", localized = true) {
  if (!element) return;
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
  if (!element) return;
  delete element.dataset.i18n;
  element.textContent = "";
}

function clearElement(element) {
  if (!element) return;
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

const ASSET_STATUS_MESSAGES = {
  NO_MATCH: "asset_no_match",
  INVALID_REQUEST: "asset_search_empty",
  AUTHENTICATION_FAILED: "asset_provider_auth_failed",
  RATE_LIMITED: "asset_rate_limited",
  PROVIDER_UNAVAILABLE: "asset_search_failed",
  INVALID_PROVIDER_RESPONSE: "asset_invalid_response",
  INVALID_SYMBOL: "asset_no_match",
};

const RECOGNITION_STATUS_MESSAGES = {
  INVALID_REQUEST: "recognition_invalid_request",
  AUTHENTICATION_FAILED: "recognition_auth_failed",
  RATE_LIMITED: "recognition_rate_limited",
  PROVIDER_UNAVAILABLE: "recognition_provider_failed",
  INVALID_PROVIDER_RESPONSE: "recognition_invalid_response",
};

function clearAttachments(config) {
  const controls = config.controls;
  for (const attachment of controls.attachments) URL.revokeObjectURL(attachment.previewUrl);
  controls.attachments = [];
  if (controls.screenshotInput) controls.screenshotInput.value = "";
  if (controls.attachmentPreview) {
    clearElement(controls.attachmentPreview);
    controls.attachmentPreview.hidden = true;
  }
  controls.attachmentDropzone?.classList.remove("is-dragging");
}

function formatAttachmentSize(bytes) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function openImagePreview(attachment, opener) {
  elements.imagePreviewFull.src = attachment.previewUrl;
  elements.imagePreviewFull.alt = attachment.file.name || translate("attachment_preview_image");
  elements.imagePreviewCaption.textContent = attachment.file.name || translate("attachment_preview_image");
  elements.imagePreviewDialog.dataset.openerId = opener.id;
  elements.imagePreviewDialog.showModal();
}

function closeImagePreview() {
  if (elements.imagePreviewDialog.open) elements.imagePreviewDialog.close();
}

function renderAttachmentPreviews(config) {
  const controls = config.controls;
  clearElement(controls.attachmentPreview);
  for (const attachment of controls.attachments) {
    const card = makeElement("article", "attachment-preview-card");
    const preview = makeElement("button", "attachment-preview-open");
    preview.type = "button";
    preview.id = `attachment-preview-${attachment.id}`;
    preview.setAttribute("aria-label", `${translate("attachment_preview_open")} ${attachment.file.name || translate("attachment_preview_image")}`);
    const image = makeElement("img");
    image.src = attachment.previewUrl;
    image.alt = "";
    preview.append(image);
    preview.addEventListener("click", () => openImagePreview(attachment, preview));
    const copy = makeElement("div", "attachment-preview-copy");
    copy.append(
      makeElement("strong", "", attachment.file.name || "Pasted image"),
      makeElement(
        "span",
        "",
        `${attachment.file.type} · ${formatAttachmentSize(attachment.file.size)}`,
      ),
    );
    const remove = makeElement("button", "attachment-remove", "×");
    remove.type = "button";
    remove.setAttribute("aria-label", `${translate("attachment_remove")} ${attachment.file.name || "image"}`);
    remove.addEventListener("click", () => {
      URL.revokeObjectURL(attachment.previewUrl);
      controls.attachments = controls.attachments.filter((item) => item.id !== attachment.id);
      renderAttachmentPreviews(config);
    });
    card.append(preview, copy, remove);
    controls.attachmentPreview.append(card);
  }
  controls.attachmentPreview.hidden = controls.attachments.length === 0;
  if (controls.attachments.length) {
    setMessage(controls.screenshotMessage, "attachment_ready", "success");
  } else {
    clearMessage(controls.screenshotMessage);
  }
}

function stageAttachments(config, files) {
  const controls = config.controls;
  const pendingFiles = [...files].filter(Boolean);
  clearMessage(controls.screenshotMessage);
  if (!pendingFiles.length) {
    setMessage(controls.screenshotMessage, "attachment_file_required", "neutral");
    return false;
  }
  if (controls.attachments.length + pendingFiles.length > MAX_IMPORT_IMAGES) {
    setMessage(controls.screenshotMessage, "attachment_limit", "neutral");
    return false;
  }
  for (const file of pendingFiles) {
    const mimeType = String(file.type || "").toLowerCase();
    if (!IMPORT_IMAGE_TYPES.has(mimeType)) {
      setMessage(controls.screenshotMessage, "screenshot_file_invalid");
      return false;
    }
    if (file.size > MAX_IMPORT_IMAGE_BYTES) {
      setMessage(controls.screenshotMessage, "screenshot_file_too_large");
      return false;
    }
  }
  controls.attachments.push(
    ...pendingFiles.map((file) => ({
      id: crypto.randomUUID(),
      kind: "image",
      file,
      previewUrl: URL.createObjectURL(file),
      dataUrl: null,
    })),
  );
  if (controls.screenshotInput) controls.screenshotInput.value = "";
  renderAttachmentPreviews(config);
  return true;
}

function pastedImageFile(event) {
  const items = [...(event.clipboardData?.items ?? [])];
  const imageItem = items.find((item) => item.kind === "file" && String(item.type || "").toLowerCase().startsWith("image/"));
  if (!imageItem) return null;
  const file = imageItem.getAsFile();
  if (!file) return null;
  return file.name ? file : new File([file], "pasted-screenshot", { type: file.type, lastModified: Date.now() });
}

function bindAttachmentComposer(config) {
  const controls = config.controls;
  if (!controls.attachmentComposer || !controls.screenshotInput) return;
  controls.screenshotInput.multiple = true;
  if (controls.attachmentDropzone && !controls.attachmentDropzone.querySelector(".attachment-add-icon")) {
    const icon = makeElement("span", "attachment-add-icon", "＋");
    icon.setAttribute("aria-hidden", "true");
    controls.attachmentDropzone.prepend(icon);
  }
  controls.screenshotInput.addEventListener("change", () => stageAttachments(config, controls.screenshotInput.files ?? []));
  controls.attachmentDropzone?.addEventListener("click", () => controls.screenshotInput.click());
  controls.attachmentDropzone?.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    controls.screenshotInput.click();
  });
  controls.attachmentComposer.addEventListener("dragenter", (event) => {
    event.preventDefault();
    controls.attachmentDropzone?.classList.add("is-dragging");
  });
  controls.attachmentComposer.addEventListener("dragover", (event) => {
    event.preventDefault();
    controls.attachmentDropzone?.classList.add("is-dragging");
  });
  controls.attachmentComposer.addEventListener("dragleave", (event) => {
    if (event.relatedTarget && controls.attachmentComposer.contains(event.relatedTarget)) return;
    controls.attachmentDropzone?.classList.remove("is-dragging");
  });
  controls.attachmentComposer.addEventListener("drop", (event) => {
    event.preventDefault();
    controls.attachmentDropzone?.classList.remove("is-dragging");
    stageAttachments(config, event.dataTransfer?.files ?? []);
  });
  controls.attachmentComposer.addEventListener("paste", (event) => {
    const file = pastedImageFile(event);
    if (!file) return;
    event.preventDefault();
    stageAttachments(config, [file]);
  });
}

function resetImportControls(config) {
  const controls = config.controls;
  controls.mode = controls.defaultMode;
  controls.tabs.forEach((tab, index) => {
    const active = tab.dataset.importMode === controls.defaultMode;
    tab.classList.toggle("is-active", active);
    tab.setAttribute("aria-selected", String(active));
  });
  for (const [panelMode, panel] of Object.entries(controls.panels)) if (panel) panel.hidden = panelMode !== controls.defaultMode;
  if (controls.textInput) controls.textInput.value = "";
  if (controls.screenshotInput) controls.screenshotInput.value = "";
  clearAttachments(config);
  clearElement(controls.draftFeedback);
  clearMessage(controls.textMessage);
  clearMessage(controls.screenshotMessage);
}

function switchImportMode(config, mode) {
  if (!["text", "screenshot"].includes(mode)) return;
  config.controls.mode = mode;
  config.controls.tabs.forEach((tab) => {
    const active = tab.dataset.importMode === mode;
    tab.classList.toggle("is-active", active);
    tab.setAttribute("aria-selected", String(active));
  });
  for (const [panelMode, panel] of Object.entries(config.controls.panels)) if (panel) panel.hidden = panelMode !== mode;
  const focusTarget = mode === "text" ? config.controls.textInput : config.controls.attachmentDropzone ?? config.controls.screenshotInput;
  focusTarget?.focus();
}

function beginImportRequest() {
  state.importGeneration += 1;
  state.importController?.abort();
  for (const config of importConfigs) {
    setLocalizedText(config.controls.textSubmit, "prepare_text_draft");
    setLocalizedText(config.controls.screenshotSubmit, "start_recognition");
  }
  const generation = state.importGeneration;
  const controller = new AbortController();
  state.importController = controller;
  state.importPending = true;
  updateControls();
  return { generation, controller };
}

function finishImportRequest(generation) {
  if (generation !== state.importGeneration) return;
  state.importController = null;
  state.importPending = false;
  updateControls();
}

function importStatusMessage(element, status, messages, fallback = "unexpected_server_error") {
  const key = messages[status] ?? fallback;
  setMessage(element, key, status === "NO_MATCH" ? "neutral" : "danger");
}

function importFailureMessage(config, messageElement, error, messages) {
  if (error?.name === "AbortError") return;
  if (error instanceof ApiError && error.status === 401) {
    enterHome("session_expired");
    return;
  }
  if (error instanceof ApiError) {
    importStatusMessage(messageElement, error.code, messages);
    return;
  }
  setMessage(messageElement, messages.PROVIDER_UNAVAILABLE ?? "unexpected_server_error");
}

function normalizeDraftField(field) {
  if (!field || typeof field !== "object") return { value: "", status: "MISSING" };
  const rawValue = field.value;
  return {
    value: rawValue === null || rawValue === undefined ? "" : String(rawValue).trim(),
    status: typeof field.status === "string" ? field.status.toUpperCase() : "MISSING",
  };
}

function reviewStatusText(status) {
  return translate({
    PRESENT: "draft_status_present",
    MISSING: "draft_status_missing",
    INVALID: "draft_status_invalid",
    AMBIGUOUS: "draft_status_ambiguous",
  }[status] ?? "draft_status_invalid");
}

function addFieldReviewCue(field, status, fieldName) {
  field.dataset.reviewStatus = status;
  if (status === "PRESENT") return;
  const cue = makeElement("span", "field-review-cue", reviewStatusText(status));
  cue.dataset.fieldCue = fieldName;
  field.insertAdjacentElement("afterend", cue);
}

function clearFieldReviewCue(field) {
  delete field.dataset.reviewStatus;
  field.parentElement?.querySelector(`[data-field-cue="${field.dataset.fieldName}"]`)?.remove();
}

function setDraftField(row, fieldName, draftField, valueOverride = null) {
  const field = row.querySelector(`[data-field='${fieldName}']`);
  if (!field) return;
  const parsed = normalizeDraftField(draftField);
  field.value = valueOverride === null ? parsed.value : valueOverride;
  field.dataset.fieldName = fieldName;
  addFieldReviewCue(field, parsed.status, fieldName);
  field.addEventListener("input", () => {
    clearFieldReviewCue(field);
    field.dataset.fieldName = fieldName;
  }, { once: false });
  field.addEventListener("change", () => {
    clearFieldReviewCue(field);
    field.dataset.fieldName = fieldName;
  }, { once: false });
  return parsed;
}

function clearSelectedAsset(row) {
  delete row.dataset.assetSymbol;
  delete row.dataset.assetDisplayName;
  delete row.dataset.assetExchange;
  row.querySelector(".draft-asset-resolution")?.remove();
  row.querySelector(".reconciliation-asset-options")?.remove();
  row.querySelector(".reconciliation-asset-status")?.remove();
  delete row.dataset.revalidationStatus;
}

function applySelectedAsset(row, candidate) {
  const symbol = String(candidate?.canonical_symbol ?? "").trim().toUpperCase();
  if (!symbol) return false;
  const ticker = row.querySelector("[data-field='ticker']");
  ticker.value = symbol;
  row.dataset.assetSymbol = symbol;
  row.dataset.assetDisplayName = String(candidate.display_name ?? "").trim();
  row.dataset.assetExchange = String(candidate.exchange ?? "").trim();
  row.querySelector(".draft-asset-resolution")?.remove();
  clearFieldReviewCue(ticker);
  ticker.dataset.fieldName = "ticker";
  return true;
}

function setTickerDraftFields(row, tickerField, suggestedField) {
  const ticker = normalizeDraftField(tickerField);
  const suggested = normalizeDraftField(suggestedField);
  const suggestedIsUsable = suggested.value && suggested.status === "PRESENT";
  const tickerValue = suggestedIsUsable ? suggested.value : ticker.value;
  const tickerStatus = suggestedIsUsable ? "PRESENT" : (suggested.status !== "MISSING" ? suggested.status : ticker.status);
  const visibleTicker = row.querySelector("[data-field='ticker']");
  visibleTicker.value = tickerValue;
  visibleTicker.dataset.fieldName = "ticker";
  addFieldReviewCue(visibleTicker, tickerStatus, "ticker");
  for (const eventName of ["input", "change"]) {
    visibleTicker.addEventListener(eventName, () => {
      clearFieldReviewCue(visibleTicker);
      visibleTicker.dataset.fieldName = "ticker";
    });
  }
  clearSelectedAsset(row);
  return { value: tickerValue, status: tickerStatus };
}

function confidenceText(value) {
  if (value === null || value === undefined || value === "") return translate("confidence_unavailable");
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return String(value);
  return `${Math.round(Math.max(0, Math.min(1, numeric)) * 100)}%`;
}

function renderRecognitionDraft(config, payload, messageElement) {
  const draft = payload?.draft;
  if (!draft || !Array.isArray(draft.rows)) {
    importStatusMessage(messageElement, "INVALID_PROVIDER_RESPONSE", RECOGNITION_STATUS_MESSAGES);
    return false;
  }
  clearElement(config.rows);
  clearElement(config.controls.draftFeedback);
  const inputLabel = draft.input_kind === "SCREENSHOT" ? "recognition_input_screenshot" : "recognition_input_text";
  const feedback = makeElement("div", "draft-feedback-summary");
  const feedbackTitle = makeElement("strong", "draft-feedback-title", `${translate("draft_review_signal")} · ${translate(inputLabel)}`);
  feedback.append(feedbackTitle);
  const ready = makeElement("span", "draft-feedback-copy", translate("recognition_draft_ready"));
  feedback.append(ready);
  if (Array.isArray(draft.warnings) && draft.warnings.length) {
    const warningList = makeElement("ul", "import-warning-list");
    for (const warning of draft.warnings) {
      const item = makeElement("li");
      const label = makeElement("strong", "", `${translate("imported_warning")}: `);
      item.append(label, makeElement("span", "", String(warning)));
      warningList.append(item);
    }
    feedback.append(warningList);
  }
  config.controls.draftFeedback.append(feedback);
  if (!draft.rows.length) {
    const empty = makeElement("p", "draft-empty", translate("recognition_empty"));
    config.rows.append(empty);
    setMessage(messageElement, "recognition_empty", "neutral");
    return false;
  }
  for (const rowData of draft.rows) {
    const row = createOpeningRow(config.rows);
    const tickerDraft = setTickerDraftFields(row, rowData.ticker, rowData.suggested_symbol);
    const resolution = rowData.asset_resolution;
    const canonical = String(resolution?.candidate?.canonical_symbol ?? "").trim().toUpperCase();
    const visibleTicker = tickerDraft.value.trim().toUpperCase();
    const automaticallySelected = resolution?.status === "OK"
      && canonical === visibleTicker
      && applySelectedAsset(row, resolution.candidate);
    if (resolution?.status === "OK" && resolution.candidate && !automaticallySelected) {
      renderRevalidationCandidate(row, resolution.candidate);
    }
    setDraftField(row, "shares", rowData.shares);
    setDraftField(row, "average_cost", rowData.average_cost);
    const positionType = normalizeDraftField(rowData.position_type);
    const typeValue = ["LONG_TERM", "SWING"].includes(positionType.value) ? positionType.value : "";
    const optionalPositionType = positionType.status === "MISSING" ? { value: "", status: "PRESENT" } : positionType;
    setDraftField(row, "position_type", optionalPositionType, typeValue);
    const confidence = makeElement("span", "draft-confidence", `${translate("confidence_signal")}: ${confidenceText(rowData.confidence)}`);
    const review = makeElement("div", "draft-row-review");
    review.append(confidence);
    if (automaticallySelected) {
      review.append(makeElement("span", "draft-asset-resolution", translate("asset_auto_selected")));
    } else if (resolution?.status && ASSET_STATUS_MESSAGES[resolution.status]) {
      review.append(makeElement("span", "draft-asset-resolution", translate(ASSET_STATUS_MESSAGES[resolution.status])));
    }
    row.append(review);
  }
  return true;
}

function closeAssetAutocomplete(input) {
  const autocomplete = assetAutocompleteStates.get(input);
  if (!autocomplete) return;
  clearTimeout(autocomplete.timer);
  autocomplete.timer = null;
  autocomplete.generation += 1;
  autocomplete.controller?.abort();
  autocomplete.controller = null;
  autocomplete.activeIndex = -1;
  clearElement(autocomplete.list);
  autocomplete.list.hidden = true;
  input.removeAttribute("aria-activedescendant");
  input.setAttribute("aria-expanded", "false");
}

function selectAutocompleteCandidate(input, candidate) {
  const autocomplete = assetAutocompleteStates.get(input);
  if (!autocomplete) return;
  autocomplete.onSelect(candidate);
  closeAssetAutocomplete(input);
}

function renderAutocompleteCandidates(input, payload) {
  const autocomplete = assetAutocompleteStates.get(input);
  if (!autocomplete) return;
  clearElement(autocomplete.list);
  autocomplete.activeIndex = -1;
  const candidates = payload?.status === "OK" && Array.isArray(payload.candidates)
    ? payload.candidates.filter((candidate) => candidate && typeof candidate === "object").slice(0, 3)
    : [];
  for (const [index, candidate] of candidates.entries()) {
    const option = makeElement("button", "asset-autocomplete-option");
    option.type = "button";
    option.id = `${input.id}-asset-option-${index}`;
    option.setAttribute("role", "option");
    option.dataset.index = String(index);
    option.append(
      makeElement("strong", "asset-candidate-symbol", String(candidate.canonical_symbol ?? "")),
      makeElement("span", "asset-candidate-name", String(candidate.display_name ?? "")),
      makeElement("span", "asset-candidate-exchange", String(candidate.exchange ?? "")),
    );
    option.addEventListener("mousedown", (event) => event.preventDefault());
    option.addEventListener("click", () => selectAutocompleteCandidate(input, candidate));
    autocomplete.list.append(option);
  }
  autocomplete.candidates = candidates;
  autocomplete.list.hidden = candidates.length === 0;
  input.setAttribute("aria-expanded", String(candidates.length > 0));
}

async function searchAssetAutocomplete(input, query, generation) {
  const autocomplete = assetAutocompleteStates.get(input);
  if (!autocomplete || generation !== autocomplete.generation) return;
  autocomplete.controller?.abort();
  const controller = new AbortController();
  autocomplete.controller = controller;
  try {
    const params = new URLSearchParams({ query, limit: "3" });
    const payload = await requestJson(`/v1/assets/search?${params.toString()}`, { signal: controller.signal });
    const current = assetAutocompleteStates.get(input);
    if (!current || current.generation !== generation || input.value.trim() !== query) return;
    renderAutocompleteCandidates(input, payload);
  } catch (error) {
    if (error?.name === "AbortError") return;
    if (error instanceof ApiError && error.status === 401) enterHome("session_expired");
    closeAssetAutocomplete(input);
  }
}

function moveAutocompleteSelection(input, direction) {
  const autocomplete = assetAutocompleteStates.get(input);
  if (!autocomplete || autocomplete.list.hidden || autocomplete.candidates.length === 0) return false;
  const count = autocomplete.candidates.length;
  autocomplete.activeIndex = (autocomplete.activeIndex + direction + count) % count;
  const options = [...autocomplete.list.querySelectorAll("[role='option']")];
  options.forEach((option, index) => option.classList.toggle("is-active", index === autocomplete.activeIndex));
  const active = options[autocomplete.activeIndex];
  input.setAttribute("aria-activedescendant", active.id);
  active.scrollIntoView({ block: "nearest" });
  return true;
}

function bindAssetAutocomplete(input, onSelect) {
  if (!input || assetAutocompleteStates.has(input)) return;
  const wrapper = makeElement("div", "asset-autocomplete-field");
  const list = makeElement("div", "asset-autocomplete-list");
  list.id = `${input.id}-asset-options`;
  list.hidden = true;
  list.setAttribute("role", "listbox");
  input.parentNode.insertBefore(wrapper, input);
  wrapper.append(input, list);
  input.setAttribute("role", "combobox");
  input.setAttribute("aria-autocomplete", "list");
  input.setAttribute("aria-controls", list.id);
  input.setAttribute("aria-expanded", "false");
  assetAutocompleteStates.set(input, {
    activeIndex: -1,
    candidates: [],
    controller: null,
    generation: 0,
    list,
    onSelect,
    timer: null,
  });
  input.addEventListener("input", () => {
    const autocomplete = assetAutocompleteStates.get(input);
    autocomplete.generation += 1;
    autocomplete.controller?.abort();
    clearTimeout(autocomplete.timer);
    const query = input.value.trim();
    if (!query) {
      closeAssetAutocomplete(input);
      return;
    }
    const generation = autocomplete.generation;
    autocomplete.timer = setTimeout(
      () => searchAssetAutocomplete(input, query, generation),
      ASSET_AUTOCOMPLETE_DELAY_MS,
    );
  });
  input.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown" && moveAutocompleteSelection(input, 1)) event.preventDefault();
    else if (event.key === "ArrowUp" && moveAutocompleteSelection(input, -1)) event.preventDefault();
    else if (event.key === "Enter") {
      const autocomplete = assetAutocompleteStates.get(input);
      if (autocomplete?.activeIndex >= 0) {
        event.preventDefault();
        selectAutocompleteCandidate(input, autocomplete.candidates[autocomplete.activeIndex]);
      }
    } else if (event.key === "Escape") closeAssetAutocomplete(input);
  });
  input.addEventListener("blur", () => setTimeout(() => closeAssetAutocomplete(input), 0));
}

function readFileAsDataUrl(file, signal) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    const cleanup = () => signal?.removeEventListener("abort", abortRead);
    const abortRead = () => reader.abort();
    reader.addEventListener("load", () => {
      cleanup();
      resolve(typeof reader.result === "string" ? reader.result : "");
    });
    reader.addEventListener("error", () => {
      cleanup();
      reject(new Error("FileReader failed"));
    });
    reader.addEventListener("abort", () => {
      cleanup();
      const error = new Error("FileReader aborted");
      error.name = "AbortError";
      reject(error);
    });
    if (signal?.aborted) {
      const error = new Error("FileReader aborted");
      error.name = "AbortError";
      reject(error);
      return;
    }
    signal?.addEventListener("abort", abortRead, { once: true });
    reader.readAsDataURL(file);
  });
}

async function handleTextImport(event, config) {
  event?.preventDefault();
  if (state.importPending) return;
  const text = config.controls.textInput.value.trim();
  clearMessage(config.controls.textMessage);
  if (!text) {
    setMessage(config.controls.textMessage, "recognition_invalid_request", "neutral");
    config.controls.textInput.focus();
    return;
  }
  const task = beginImportRequest();
  setLocalizedText(config.controls.textSubmit, "preparing_text_draft");
  try {
    const payload = await requestJson("/v1/portfolio/import/recognize-text", { method: "POST", body: JSON.stringify({ text }), signal: task.controller.signal });
    if (task.generation !== state.importGeneration) return;
    if (payload?.status !== "OK") {
      importStatusMessage(config.controls.textMessage, payload?.status, RECOGNITION_STATUS_MESSAGES);
      return;
    }
    if (renderRecognitionDraft(config, payload, config.controls.textMessage)) {
      setMessage(config.controls.textMessage, "recognition_draft_ready", "success");
    }
  } catch (error) {
    if (task.generation === state.importGeneration) importFailureMessage(config, config.controls.textMessage, error, RECOGNITION_STATUS_MESSAGES);
  } finally {
    if (task.generation === state.importGeneration) {
      setLocalizedText(config.controls.textSubmit, "prepare_text_draft");
      finishImportRequest(task.generation);
    }
  }
}

async function handleScreenshotImport(event, config) {
  event?.preventDefault();
  if (state.importPending) return;
  const attachments = [...config.controls.attachments];
  clearMessage(config.controls.screenshotMessage);
  if (!attachments.length) {
    setMessage(config.controls.screenshotMessage, "attachment_file_required", "neutral");
    config.controls.attachmentDropzone?.focus();
    return;
  }
  const task = beginImportRequest();
  setLocalizedText(config.controls.screenshotSubmit, "preparing_screenshot_draft");
  try {
    const combinedDraft = { rows: [], warnings: [], input_kind: "SCREENSHOT" };
    for (const attachment of attachments) {
      const dataUrl = await readFileAsDataUrl(attachment.file, task.controller.signal);
      if (task.generation !== state.importGeneration) return;
      const separator = dataUrl.indexOf(",");
      const imageBase64 = separator >= 0 ? dataUrl.slice(separator + 1) : "";
      if (!imageBase64) {
        setMessage(config.controls.screenshotMessage, "screenshot_file_invalid");
        return;
      }
      const payload = await requestJson("/v1/portfolio/import/recognize-screenshot", {
        method: "POST",
        body: JSON.stringify({ mime_type: attachment.file.type, image_base64: imageBase64 }),
        signal: task.controller.signal,
      });
      if (task.generation !== state.importGeneration) return;
      if (payload?.status !== "OK" || !payload.draft) {
        importStatusMessage(config.controls.screenshotMessage, payload?.status, RECOGNITION_STATUS_MESSAGES);
        return;
      }
      combinedDraft.rows.push(...(payload.draft.rows ?? []));
      combinedDraft.warnings.push(...(payload.draft.warnings ?? []));
    }
    if (renderRecognitionDraft(config, { draft: combinedDraft }, config.controls.screenshotMessage)) {
      if (config.key === "reconciliation") state.reconciliationSource = "SCREENSHOT";
      setMessage(config.controls.screenshotMessage, "recognition_draft_ready", "success");
    }
  } catch (error) {
    if (task.generation === state.importGeneration && error?.name !== "AbortError") {
      if (error instanceof ApiError || error instanceof TypeError) {
        importFailureMessage(config, config.controls.screenshotMessage, error, RECOGNITION_STATUS_MESSAGES);
      } else {
        setMessage(config.controls.screenshotMessage, "screenshot_file_invalid");
      }
    }
  } finally {
    if (task.generation === state.importGeneration) {
      setLocalizedText(config.controls.screenshotSubmit, "start_recognition");
      finishImportRequest(task.generation);
    }
  }
}

function bindImportEvents(config) {
  config.controls.tabs.forEach((tab) => tab.addEventListener("click", () => switchImportMode(config, tab.dataset.importMode)));
  config.controls.textSubmit?.addEventListener("click", () => handleTextImport(null, config));
  config.controls.screenshotSubmit?.addEventListener("click", () => handleScreenshotImport(null, config));
  bindAttachmentComposer(config);
}

function createOpeningRow(container) {
  const row = makeElement("div", "opening-draft-row");
  const rowId = crypto.randomUUID();
  row.dataset.rowId = rowId;
  const fields = makeElement("div", "opening-row-fields");
  const tickerWrap = makeElement("div");
  const tickerLabel = makeElement("label"); setLocalizedText(tickerLabel, "ticker");
  const ticker = makeElement("input"); ticker.id = `opening-${rowId}-ticker`; ticker.type = "text"; ticker.maxLength = 10; ticker.autocomplete = "off"; ticker.dataset.field = "ticker"; tickerLabel.htmlFor = ticker.id;
  for (const eventName of ["input", "change"]) {
    ticker.addEventListener(eventName, () => clearSelectedAsset(row));
  }
  tickerWrap.append(tickerLabel, ticker);
  bindAssetAutocomplete(ticker, (candidate) => {
    if (!applySelectedAsset(row, candidate)) return;
    row.querySelector("[data-field='shares']")?.focus();
  });
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
    if (row.dataset.assetSymbol !== normalizedTicker) { showFieldError(ticker, "asset_selection_required"); valid = false; continue; }
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
  state.valuation = null;
  state.valuationController?.abort();
  state.valuationController = null;
  state.openingRecords = [];
  state.reconciliationRecords = [];
  state.reconciliationSource = "SCREENSHOT";
  state.transactionRecords = [];
  state.buyCorrectionRecords = [];
  state.cashRecords = [];
  state.openingDismissed = false;
  state.writeState = "idle";
  state.portfolioReadState = "idle";
  state.authTransition = "idle";
  state.portfolioGeneration += 1;
  state.importGeneration += 1;
  state.questionGeneration += 1;
  state.portfolioController?.abort();
  state.importController?.abort();
  state.questionController?.abort();
  state.portfolioController = null;
  state.importController = null;
  state.questionController = null;
  state.importPending = false;
  state.questionPending = false;
  state.questionComposing = false;
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
  clearElement(elements.reconciliationRows);
  elements.reconciliationBroker.value = "";
  for (const config of importConfigs) resetImportControls(config);
  for (const message of [elements.setupMessage, elements.accountMessage, elements.openingMessage, elements.reconciliationMessage, elements.tradeMessage, elements.cashMessage]) clearMessage(message);
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
  const busy = writeBusy || readBusy || authBusy || state.questionPending || state.importPending;
  const contextReady = Boolean(state.snapshot) && state.writeState !== "refresh_required";
  elements.logout.disabled = writeBusy || authBusy;
  elements.headerLogout.disabled = writeBusy || authBusy;
  elements.setupLogout.disabled = writeBusy || authBusy;
  elements.setupFields.disabled = authBusy || readBusy || state.writeState !== "idle" || state.importPending;
  elements.reloadPortfolio.disabled = busy;
  for (const control of [elements.openBuy, elements.emptyBuy, elements.openImport, elements.openCash]) {
    if (control) control.disabled = busy || !contextReady;
  }
  elements.tradeFields.disabled = busy || !contextReady;
  elements.cashFields.disabled = busy || !contextReady;
  elements.openingFields.disabled = busy || !contextReady;
  elements.reconciliationFields.disabled = authBusy || readBusy || writeBusy || !contextReady;
  elements.reconciliationAddRow.disabled = busy || !contextReady;
  elements.reconciliationLoadCurrent.disabled = authBusy || readBusy || writeBusy || !contextReady;
  elements.reconciliationRevalidate.disabled = busy || !contextReady;
  elements.reconciliationSubmit.disabled = busy || !contextReady;
  for (const config of importConfigs) {
    if (config.controls.textSubmit) config.controls.textSubmit.disabled = busy;
    if (config.controls.screenshotSubmit) config.controls.screenshotSubmit.disabled = busy;
  }
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
  state.importGeneration += 1;
  state.questionGeneration += 1;
  state.portfolioController?.abort();
  state.importController?.abort();
  state.questionController?.abort();
  state.portfolioController = null;
  state.importController = null;
  state.questionController = null;
  state.portfolioReadState = "idle";
  state.importPending = false;
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
  if (state.writeState !== "idle" || state.authTransition !== "idle" || state.portfolioReadState !== "idle" || state.importPending) return;
  clearFieldErrors(elements.setupForm);
  clearMessage(elements.setupMessage);
  const cash = forceEmpty ? "0" : (elements.setupCash.value.trim() || "0");
  if (!DECIMAL_PATTERN.test(cash)) { showFieldError(elements.setupCash, "invalid_cash"); setMessage(elements.setupMessage, "invalid_form"); return; }
  if (!forceEmpty && !(await validateUnboundDraftAssets(elements.setupRows))) {
    setMessage(elements.setupMessage, "asset_selection_required", "neutral");
    return;
  }
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
  for (const [list, count, empty] of [[elements.transactionList, elements.transactionCount, elements.transactionsEmpty], [elements.cashList, elements.cashCount, elements.cashEmpty]]) {
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

function metricText(metrics, field, fallback = null) {
  const value = metrics?.[field] ?? fallback;
  if (value === null || value === undefined) return "—";
  if (field === "unrealized_pnl_percent") return `${formatDecimal(value)}%`;
  if (["average_cost", "unrealized_pnl", "market_value"].includes(field)) return formatMoney(value);
  return formatDecimal(value);
}

function createHoldingRow({ label, note = null, metrics, fallback, level, toggle = null, lot = null, ticker = null, currentPrice = null }) {
  const row = makeElement("div", `holding-row holding-level-${level}`);
  if (toggle) row.setAttribute("aria-expanded", "false");
  const identity = makeElement("span", "holding-identity");
  if (toggle) {
    const disclosure = makeElement("button", "holding-disclosure");
    disclosure.type = "button";
    disclosure.setAttribute("aria-expanded", "false");
    disclosure.append(makeElement("span", "holding-caret", "›"), makeElement("strong", "", label));
    identity.append(disclosure);
  } else identity.append(makeElement("strong", "", label));
  if (note) identity.append(makeElement("small", "holding-note", note));
  if (lot) {
    const selector = makeElement("select", "lot-type-select");
    selector.setAttribute("aria-label", translate("position_type_optional"));
    for (const [value, key] of [["UNSPECIFIED", "unspecified"], ["SWING", "strategy_swing"], ["LONG_TERM", "strategy_long_term"]]) {
      const option = makeElement("option", "", translate(key));
      option.value = value;
      option.selected = lot.position_type === value;
      selector.append(option);
    }
    selector.addEventListener("click", (event) => event.stopPropagation());
    selector.addEventListener("dblclick", (event) => event.stopPropagation());
    selector.addEventListener("change", (event) => {
      event.stopPropagation();
      changeLotType(lot.id, selector.value, selector);
    });
    identity.append(selector);
    row.addEventListener("dblclick", () => openBuyCorrection(lot));
  }
  const values = [
    metricText(metrics, "shares", fallback?.shares),
    metricText(metrics, "average_cost", fallback?.average_cost),
    currentPrice === null || currentPrice === undefined ? "—" : formatMoney(currentPrice),
    metricText(metrics, "unrealized_pnl"),
    metricText(metrics, "unrealized_pnl_percent"),
    metricText(metrics, "market_value"),
  ];
  const actions = makeElement("span", "holding-actions");
  if (ticker && level === 0) {
    for (const [action, key] of [["BUY", "buy"], ["SELL", "sell"]]) {
      const button = makeElement("button", "row-action", translate(key));
      button.type = "button";
      button.addEventListener("click", (event) => { event.stopPropagation(); openTradeDialog(action, ticker); });
      actions.append(button);
    }
  } else if (lot) {
    const edit = makeElement("button", "lot-menu-button", "···");
    edit.type = "button";
    edit.setAttribute("aria-label", translate("edit_lot"));
    edit.addEventListener("click", (event) => { event.stopPropagation(); openBuyCorrection(lot); });
    actions.append(edit);
  }
  row.append(identity, ...values.map((value) => makeElement("span", "holding-number", value)), actions);
  if (metrics?.unrealized_pnl !== undefined) {
    const tone = Number(metrics.unrealized_pnl) > 0 ? "positive" : Number(metrics.unrealized_pnl) < 0 ? "negative" : "neutral";
    row.children[4].dataset.tone = tone;
    row.children[5].dataset.tone = tone;
  }
  return row;
}

async function changeLotType(lotId, positionType, selector) {
  selector.disabled = true;
  const saved = await runMutation({
    url: `/v1/portfolio/lots/${lotId}/classification`,
    payload: { position_type: positionType },
    messageElement: elements.accountMessage,
    successKey: "lot_type_saved",
    recordId: (result) => result.lot_id,
  });
  if (!saved) selector.disabled = false;
}

function toLocalDateTimeValue(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (part) => String(part).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function openBuyCorrection(lot) {
  state.selectedLot = lot;
  elements.correctionLotId.value = lot.id;
  elements.correctionSymbol.textContent = lot.ticker;
  elements.correctionPrice.value = lot.entry_price ?? lot.average_cost;
  elements.correctionShares.value = lot.source === "BUY" ? lot.acquired_shares : lot.remaining_shares;
  const localTime = toLocalDateTimeValue(lot.purchased_at);
  elements.correctionTime.value = localTime;
  elements.correctionTime.disabled = lot.source !== "BUY";
  elements.correctionTime.dataset.originalIso = lot.purchased_at;
  elements.correctionTime.dataset.originalLocalValue = localTime;
  elements.correctionType.value = lot.position_type;
  elements.correctionReason.value = "";
  clearMessage(elements.correctionMessage);
  const sameTypeLots = (state.snapshot?.lots ?? []).filter((item) => item.ticker === lot.ticker && item.position_type === lot.position_type);
  const aggregateFieldsLocked = lot.source !== "BUY" && sameTypeLots.length > 1;
  elements.correctionShares.disabled = aggregateFieldsLocked;
  elements.correctionPrice.disabled = aggregateFieldsLocked;
  if (aggregateFieldsLocked) setMessage(elements.correctionMessage, "aggregate_edit_unavailable", "neutral");
  elements.correctionDialog.showModal();
  (aggregateFieldsLocked ? elements.correctionType : elements.correctionShares).focus();
}

async function handleBuyCorrection(event) {
  event.preventDefault();
  const lot = state.selectedLot;
  if (!lot) return;
  clearFieldErrors(elements.correctionForm);
  const price = validateRequiredPositive(elements.correctionPrice);
  const shares = validateRequiredPositive(elements.correctionShares);
  const occurredAt = lot.source === "BUY" ? (elements.correctionTime.value === elements.correctionTime.dataset.originalLocalValue
    ? elements.correctionTime.dataset.originalIso
    : localDateTimeToIso(elements.correctionTime)) : null;
  if (!price || !shares || (lot.source === "BUY" && !occurredAt)) {
    if (lot.source === "BUY" && !occurredAt) showFieldError(elements.correctionTime, "invalid_form");
    setMessage(elements.correctionMessage, "invalid_form");
    return;
  }
  const typeChanged = elements.correctionType.value !== lot.position_type;
  let saved = true;
  if (lot.source === "BUY") {
    const detailsChanged = price !== String(lot.entry_price) || shares !== String(lot.acquired_shares)
      || occurredAt !== lot.purchased_at || elements.correctionReason.value.trim();
    if (detailsChanged) {
      const payload = { price, shares, occurred_at: occurredAt };
      if (elements.correctionReason.value.trim()) payload.reason = elements.correctionReason.value.trim();
      saved = await runMutation({ url: `/v1/portfolio/lots/${lot.id}/correction`, payload, messageElement: elements.correctionMessage, successKey: "correction_saved", recordId: (result) => result.correction_id });
    }
  } else {
    const dataChanged = !elements.correctionShares.disabled && (price !== String(lot.average_cost) || shares !== String(lot.remaining_shares));
    let editableLotId = lot.id;
    if (dataChanged) {
      const payload = { positions: [{ ticker: lot.ticker, target_shares: shares, target_average_cost: price, position_type: elements.correctionType.value }], source: "MANUAL" };
      payload.positions[0].position_type = lot.position_type;
      const result = await runMutation({ url: "/v1/portfolio/reconciliations", payload, messageElement: elements.correctionMessage, successKey: "correction_saved", recordId: (value) => value.reconciliations?.[0]?.id });
      saved = Boolean(result);
      if (result) editableLotId = result.reconciliations?.[0]?.id ?? editableLotId;
    }
    if (saved && typeChanged) saved = Boolean(await runMutation({ url: `/v1/portfolio/lots/${editableLotId}/classification`, payload: { position_type: elements.correctionType.value }, messageElement: elements.correctionMessage, successKey: "lot_type_saved", recordId: (result) => result.lot_id }));
  }
  if (saved && lot.source === "BUY" && typeChanged) saved = await runMutation({ url: `/v1/portfolio/lots/${lot.id}/classification`, payload: { position_type: elements.correctionType.value }, messageElement: elements.correctionMessage, successKey: "lot_type_saved", recordId: (result) => result.lot_id });
  if (saved) { state.selectedLot = null; elements.correctionDialog.close(); }
}

function createHoldingTree(ticker) {
  const valuation = state.valuation?.tickers?.find((item) => item.ticker === ticker) ?? null;
  const lots = (state.snapshot?.lots ?? []).filter((lot) => lot.ticker === ticker);
  const positions = (state.snapshot?.positions ?? []).filter((position) => position.ticker === ticker);
  const totalShares = lots.reduce((total, lot) => total + Number(lot.remaining_shares), 0);
  const fallback = { shares: totalShares, average_cost: totalShares ? positions.reduce((total, position) => total + Number(position.cost_basis), 0) / totalShares : 0 };
  const group = makeElement("section", "holding-group");
  group.dataset.ticker = ticker;
  const details = makeElement("div", "holding-details");
  details.hidden = true;
  const header = createHoldingRow({ label: ticker, metrics: valuation?.metrics, fallback, level: 0, toggle: true, ticker, currentPrice: valuation?.current_price });
  const toggleDetails = () => {
    const expanded = header.getAttribute("aria-expanded") !== "true";
    header.setAttribute("aria-expanded", String(expanded));
    header.querySelector(".holding-disclosure").setAttribute("aria-expanded", String(expanded));
    details.hidden = !expanded;
  };
  header.querySelector(".holding-disclosure").addEventListener("click", (event) => { event.stopPropagation(); toggleDetails(); });
  header.addEventListener("click", (event) => { if (!event.target.closest("button, select")) toggleDetails(); });
  const lotValuations = new Map((valuation?.lots ?? []).map((item) => [item.lot_id, item.metrics]));
  const typeValuations = new Map((valuation?.position_types ?? []).map((item) => [item.position_type, item.metrics]));
  const appendLot = (lot) => {
    const time = lot.purchased_at ? new Intl.DateTimeFormat(state.language === "zh" ? "zh-CN" : "en-US", { month: "2-digit", day: "2-digit" }).format(new Date(lot.purchased_at)) : "—";
    details.append(createHoldingRow({
      label: time,
      metrics: lotValuations.get(lot.id),
      fallback: { shares: lot.remaining_shares, average_cost: lot.average_cost },
      level: 2,
      lot,
      currentPrice: valuation?.current_price,
    }));
  };
  const sortedLots = [...lots].sort((left, right) => {
    if (!left.purchased_at && right.purchased_at) return 1;
    if (left.purchased_at && !right.purchased_at) return -1;
    return String(left.purchased_at ?? left.id).localeCompare(String(right.purchased_at ?? right.id));
  });
  sortedLots.filter((lot) => lot.position_type === "UNSPECIFIED").forEach(appendLot);
  for (const [type, key] of [["SWING", "strategy_swing"], ["LONG_TERM", "strategy_long_term"]]) {
    const typeLots = sortedLots.filter((lot) => lot.position_type === type);
    if (!typeLots.length) continue;
    const position = positions.find((item) => item.position_type === type);
    details.append(createHoldingRow({ label: translate(key), metrics: typeValuations.get(type), fallback: position, level: 1, currentPrice: valuation?.current_price }));
    typeLots.forEach(appendLot);
  }
  group.append(header, details);
  return group;
}

function latestCorrection(transactionId) {
  return [...state.buyCorrectionRecords]
    .filter((item) => item.transaction_id === transactionId)
    .sort((left, right) => String(right.corrected_at).localeCompare(String(left.corrected_at)))[0] ?? null;
}

function effectiveTransaction(record) {
  const correction = latestCorrection(record.id);
  return correction ? { ...record, price: correction.price, shares: correction.shares, occurred_at: correction.occurred_at, reason: correction.reason, edited: true } : { ...record, edited: false };
}

function historyDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat(state.language === "zh" ? "zh-CN" : "en-US", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false }).format(date);
}

function openTransactionDetail(record, kind) {
  const isTrade = kind === "trade";
  const effective = isTrade ? effectiveTransaction(record) : record;
  elements.transactionDetailTitle.textContent = isTrade ? `${effective.ticker} · ${effective.action}` : translate(record.event_type === "DEPOSIT" ? "deposit" : "withdrawal");
  elements.transactionDetailSubtitle.textContent = formatTimestamp(effective.occurred_at);
  clearElement(elements.transactionDetailContent);
  const facts = isTrade
    ? [["shares", effective.shares, "decimal"], ["price", effective.price, "decimal"], ["commission", effective.commission, "decimal"], ["position_type", effective.position_type === "UNSPECIFIED" ? translate("unspecified") : effective.position_type], ["reason", effective.reason]]
    : [["amount", effective.amount, "decimal"], ["reason", effective.reason]];
  elements.transactionDetailContent.append(createFactList(facts));
  if (isTrade && effective.edited) {
    const original = makeElement("details", "correction-history");
    const summary = makeElement("summary", "", translate("edit_history"));
    original.append(summary);
    const versions = [
      { label: translate("original_values"), value: record, changedAt: null },
      ...state.buyCorrectionRecords.filter((item) => item.transaction_id === record.id).sort((left, right) => String(left.corrected_at).localeCompare(String(right.corrected_at))).map((item) => ({ label: translate("edited"), value: item, changedAt: item.corrected_at })),
    ];
    for (const version of versions) {
      const block = makeElement("section", "correction-version");
      const label = version.changedAt ? `${version.label} · ${formatTimestamp(version.changedAt)}` : version.label;
      block.append(makeElement("strong", "", label), createFactList([["shares", version.value.shares, "decimal"], ["price", version.value.price, "decimal"], ["occurred_at", version.value.occurred_at, "timestamp"], ["reason", version.value.reason]]));
      original.append(block);
    }
    elements.transactionDetailContent.append(original);
  }
  clearElement(elements.transactionDetailActions);
  const lot = isTrade && effective.action === "BUY" ? (state.snapshot?.lots ?? []).find((item) => item.id === record.id) : null;
  if (lot) {
    const edit = makeElement("button", "primary-button compact-button", translate("edit"));
    edit.type = "button";
    edit.addEventListener("click", () => { elements.transactionDetailDialog.close(); openBuyCorrection(lot); });
    elements.transactionDetailActions.append(edit);
  } else if (isTrade) elements.transactionDetailActions.append(makeElement("small", "muted-note", translate("edit_unavailable")));
  elements.transactionDetailDialog.showModal();
}

function createHistoryRow(record, kind) {
  const isTrade = kind === "trade";
  const effective = isTrade ? effectiveTransaction(record) : record;
  const row = makeElement("button", "history-row");
  row.type = "button";
  const side = isTrade ? effective.action : translate(effective.event_type === "DEPOSIT" ? "deposit" : "withdrawal");
  const status = isTrade && effective.edited ? translate("edited") : translate("completed");
  row.append(
    makeElement("span", "history-time", historyDate(effective.occurred_at)),
    makeElement("strong", "history-ticker", isTrade ? effective.ticker : "USD"),
    makeElement("span", `history-side ${isTrade ? effective.action.toLowerCase() : effective.event_type.toLowerCase()}`, side),
    makeElement("span", "history-number", isTrade ? formatDecimal(effective.shares) : "—"),
    makeElement("span", "history-number", formatMoney(isTrade ? effective.price : effective.amount)),
    makeElement("span", "history-number", isTrade ? formatMoney(effective.commission) : "—"),
    makeElement("span", "history-type", isTrade ? (effective.position_type === "UNSPECIFIED" ? translate("unspecified") : effective.position_type) : "CASH"),
    makeElement("span", `history-status ${effective.edited ? "is-edited" : ""}`, status),
  );
  row.addEventListener("click", () => openTransactionDetail(record, kind));
  return row;
}

function renderOpeningAvailability() {
  elements.openingSetup.hidden = true;
  elements.reopenOpening.hidden = true;
}

function renderPortfolio() {
  const snapshot = state.snapshot;
  if (!snapshot) { renderPortfolioEmpty(); updateControls(); return; }
  elements.availableCash.textContent = formatMoney(snapshot.available_cash);
  const tickers = [...new Set((snapshot.lots ?? []).map((lot) => lot.ticker))].sort();
  elements.positionCount.textContent = String(tickers.length);
  clearElement(elements.positionList);
  elements.positionsEmpty.hidden = tickers.length > 0;
  for (const ticker of tickers) elements.positionList.append(createHoldingTree(ticker));
  const history = [
    ...state.transactionRecords.map((record) => ({ record, kind: "trade" })),
    ...state.cashRecords.map((record) => ({ record, kind: "cash" })),
  ].sort((left, right) => {
    const leftTime = left.kind === "trade" ? effectiveTransaction(left.record).occurred_at : left.record.occurred_at;
    const rightTime = right.kind === "trade" ? effectiveTransaction(right.record).occurred_at : right.record.occurred_at;
    return String(rightTime).localeCompare(String(leftTime));
  });
  clearElement(elements.transactionList);
  for (const item of history) elements.transactionList.append(createHistoryRow(item.record, item.kind));
  elements.transactionCount.textContent = String(history.length);
  elements.transactionsEmpty.hidden = history.length > 0;
  elements.cashCount.textContent = String(state.cashRecords.length);
  elements.cashEmpty.hidden = state.cashRecords.length > 0;
  renderOpeningAvailability();
  renderSellLotAllocation();
  updateControls();
}

async function refreshValuation() {
  if (!state.snapshot || state.valuationController || state.portfolioReadState !== "idle" || state.writeState !== "idle" || state.authTransition !== "idle") return;
  const snapshot = state.snapshot;
  const generation = state.portfolioGeneration;
  const controller = new AbortController();
  state.valuationController = controller;
  try {
    let valuation;
    try {
      valuation = await requestJson("/v1/portfolio/valuation", { signal: controller.signal });
    } catch (error) {
      if (state.snapshot !== snapshot || state.portfolioGeneration !== generation) return;
      if (error instanceof ApiError && error.status === 401) { enterHome("session_expired"); return; }
      valuation = null;
    }
    if (state.snapshot !== snapshot || state.portfolioGeneration !== generation || state.writeState !== "idle") return;
    state.valuation = valuation;
    // 仅替换展示数字，保留正在操作的控件、焦点和展开状态。
    for (const group of elements.positionList.querySelectorAll(".holding-group")) {
      const fresh = createHoldingTree(group.dataset.ticker);
      for (const selector of [".holding-number", ".holding-note"]) {
        const current = group.querySelectorAll(selector);
        fresh.querySelectorAll(selector).forEach((value, index) => {
          current[index].textContent = value.textContent;
          if (value.dataset.tone) current[index].dataset.tone = value.dataset.tone;
          else delete current[index].dataset.tone;
        });
      }
    }
  } finally {
    if (state.valuationController === controller) state.valuationController = null;
  }
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
    const [snapshot, valuation, openings, reconciliations, transactions, corrections, cash] = await Promise.all([
      requestJson("/v1/portfolio", { signal: controller.signal }),
      requestJson("/v1/portfolio/valuation", { signal: controller.signal }).catch((error) => {
        if (error?.name === "AbortError") throw error;
        return null;
      }),
      requestJson("/v1/portfolio/opening-positions", { signal: controller.signal }),
      requestJson("/v1/portfolio/reconciliations", { signal: controller.signal }),
      requestJson("/v1/portfolio/transactions", { signal: controller.signal }),
      requestJson("/v1/portfolio/buy-corrections", { signal: controller.signal }),
      requestJson("/v1/portfolio/cash-events", { signal: controller.signal }),
    ]);
    if (generation !== state.portfolioGeneration) return false;
    state.snapshot = snapshot;
    state.valuation = valuation;
    state.loadedUserId = snapshot.user_id;
    state.openingRecords = openings.items;
    state.reconciliationRecords = reconciliations.items;
    state.transactionRecords = transactions.items;
    state.buyCorrectionRecords = corrections.items;
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
  if (state.writeState !== "idle" || state.portfolioReadState !== "idle" || state.authTransition !== "idle" || state.questionPending || state.importPending || !state.loadedUserId || !state.snapshot) return false;
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
    return result;
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

function decimalUnits(value) {
  if (!DECIMAL_PATTERN.test(value)) return null;
  const [whole, fraction = ""] = value.split(".");
  return BigInt(whole) * 100000000n + BigInt(fraction.padEnd(8, "0"));
}

function setTradeAction(action) {
  elements.tradeAction.value = action;
  const isBuy = action === "BUY";
  elements.tradeBuyMode.classList.toggle("is-active", isBuy);
  elements.tradeSellMode.classList.toggle("is-active", !isBuy);
  setLocalizedText(elements.tradeDialogTitle, isBuy ? "buy_stock" : "sell_stock");
  renderSellLotAllocation();
}

function openTradeDialog(action = "BUY", ticker = "") {
  elements.tradeForm.reset();
  clearMessage(elements.tradeMessage);
  elements.tradeTicker.value = ticker;
  if (ticker) elements.tradeTicker.dataset.assetSymbol = ticker;
  else delete elements.tradeTicker.dataset.assetSymbol;
  setTradeAction(action);
  elements.tradeDialog.showModal();
  (ticker ? elements.tradeShares : elements.tradeTicker).focus();
}

function openCashDialog() {
  elements.cashForm.reset();
  clearMessage(elements.cashMessage);
  elements.cashDialog.showModal();
  elements.cashAmount.focus();
}

function openImportDialog() {
  clearMessage(elements.reconciliationMessage);
  elements.importDialog.showModal();
}

function renderSellLotAllocation() {
  const isSell = elements.tradeAction.value === "SELL";
  elements.tradeType.disabled = isSell;
  elements.tradeType.closest("div").hidden = isSell;
  if (isSell) elements.tradeType.value = "";
  elements.tradeLotAllocation.hidden = !isSell;
  clearElement(elements.tradeLotList);
  if (!isSell) return;
  const ticker = elements.tradeTicker.value.trim().toUpperCase();
  const lots = (state.snapshot?.lots ?? []).filter((lot) => lot.ticker === ticker);
  for (const lot of lots) {
    const row = makeElement("label", "trade-lot-row");
    const copy = makeElement("span", "trade-lot-copy");
    copy.append(
      makeElement("strong", "", lot.position_type === "UNSPECIFIED" ? translate("unspecified") : lot.position_type),
      makeElement("small", "", `${lot.purchased_at ? formatTimestamp(lot.purchased_at) : translate("not_provided")} · ${formatDecimal(lot.remaining_shares)}`),
    );
    const input = makeElement("input");
    input.type = "text";
    input.inputMode = "decimal";
    input.placeholder = "0";
    input.dataset.lotId = lot.id;
    input.dataset.maxShares = lot.remaining_shares;
    row.append(copy, input);
    elements.tradeLotList.append(row);
  }
}

function collectSellAllocations(shares) {
  const allocations = [];
  let total = 0n;
  for (const input of elements.tradeLotList.querySelectorAll("[data-lot-id]")) {
    const value = input.value.trim();
    if (!value) continue;
    const units = decimalUnits(value);
    const maximum = decimalUnits(input.dataset.maxShares);
    if (units === null || units <= 0n || units > maximum) {
      showFieldError(input, "invalid_positive_decimal");
      return null;
    }
    total += units;
    allocations.push({ lot_id: input.dataset.lotId, shares: value });
  }
  if (!allocations.length || total !== decimalUnits(shares)) {
    setMessage(elements.tradeMessage, "allocation_total_hint", "neutral");
    return null;
  }
  return allocations;
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
  if (payload.action === "SELL") {
    const allocations = collectSellAllocations(shares);
    if (!allocations) return;
    payload.allocations = allocations;
  }
  if (payload.action === "BUY" && elements.tradeType.value) payload.position_type = elements.tradeType.value;
  const occurredAt = localDateTimeToIso(elements.tradeTime);
  if (elements.tradeTime.value && !occurredAt) { showFieldError(elements.tradeTime, "invalid_form"); setMessage(elements.tradeMessage, "invalid_form"); return; }
  if (occurredAt) payload.occurred_at = occurredAt;
  if (elements.tradeReason.value.trim()) payload.reason = elements.tradeReason.value.trim();
  const saved = await runMutation({ url: "/v1/portfolio/transactions", payload, messageElement: elements.tradeMessage, successKey: "trade_saved", recordId: (result) => result.transaction?.id });
  if (saved) { elements.tradeForm.reset(); renderSellLotAllocation(); elements.tradeDialog.close(); }
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
  if (saved) { elements.cashForm.reset(); elements.cashDialog.close(); }
}

async function handleOpening(event) {
  event.preventDefault();
  if (state.importPending) return;
  if (!(await validateUnboundDraftAssets(elements.openingRows))) {
    setMessage(elements.openingMessage, "asset_selection_required", "neutral");
    return;
  }
  const positions = collectOpeningPositions(elements.openingRows);
  if (!positions || positions.length === 0) { setMessage(elements.openingMessage, "invalid_form"); return; }
  const saved = await runMutation({ url: "/v1/portfolio/opening-positions", payload: { positions }, messageElement: elements.openingMessage, successKey: "opening_saved", recordId: (result) => result.opening_positions?.[0]?.id });
  if (saved) clearElement(elements.openingRows);
}

function collectReconciliationPositions(container) {
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
    if (!normalizedTicker || !shares.value.trim() || !cost.value.trim()) {
      showFieldError(!normalizedTicker ? ticker : !shares.value.trim() ? shares : cost, "incomplete_position");
      valid = false;
      continue;
    }
    if (row.dataset.assetSymbol !== normalizedTicker) {
      showFieldError(ticker, "reconciliation_not_validated");
      valid = false;
    }
    if (!isPositiveDecimal(shares.value.trim())) { showFieldError(shares, "invalid_positive_decimal"); valid = false; }
    if (!isPositiveDecimal(cost.value.trim())) { showFieldError(cost, "invalid_positive_decimal"); valid = false; }
    const key = `${normalizedTicker}:${type.value || "UNSPECIFIED"}`;
    if (keys.has(key)) { showFieldError(ticker, "duplicate_position"); valid = false; }
    keys.add(key);
    const item = { ticker: normalizedTicker, target_shares: shares.value.trim(), target_average_cost: cost.value.trim() };
    if (type.value) item.position_type = type.value;
    positions.push(item);
  }
  return valid ? positions : null;
}

function clearRevalidationFeedback(row) {
  row.querySelector(".reconciliation-asset-options")?.remove();
  row.querySelector(".reconciliation-asset-status")?.remove();
  delete row.dataset.revalidationStatus;
}

function appendRevalidationStatus(row, key, tone = "warning") {
  clearRevalidationFeedback(row);
  const status = makeElement("span", `reconciliation-asset-status ${tone}`, translate(key));
  status.dataset.i18n = key;
  row.append(status);
}

function renderRevalidationCandidate(row, candidate) {
  clearRevalidationFeedback(row);
  const options = makeElement("div", "reconciliation-asset-options");
  const title = makeElement("span", "reconciliation-asset-options-title", translate("reconciliation_canonical_match"));
  title.dataset.i18n = "reconciliation_canonical_match";
  options.append(title);
  const confirm = makeElement("button", "text-button reconciliation-asset-confirm");
  confirm.type = "button";
  const symbol = String(candidate?.canonical_symbol ?? "").trim().toUpperCase();
  confirm.textContent = symbol || translate("use_asset");
  confirm.addEventListener("click", () => {
    if (!applySelectedAsset(row, candidate)) return;
    appendRevalidationStatus(row, "asset_auto_selected", "success");
  });
  options.append(confirm);
  row.append(options);
}

async function validateUnboundDraftAssets(container) {
  const rows = [...container.querySelectorAll(".opening-draft-row")].filter((row) => {
    const ticker = row.querySelector("[data-field='ticker']")?.value.trim().toUpperCase();
    return ticker && row.dataset.assetSymbol !== ticker;
  });
  if (!rows.length) return true;

  const task = beginImportRequest();
  let allValid = true;
  try {
    for (const row of rows) {
      if (task.generation !== state.importGeneration) return false;
      const ticker = row.querySelector("[data-field='ticker']").value.trim().toUpperCase();
      const params = new URLSearchParams({ symbol: ticker });
      let payload;
      try {
        payload = await requestJson(`/v1/assets/validate?${params.toString()}`, {
          signal: task.controller.signal,
        });
      } catch (error) {
        if (error?.name === "AbortError" || task.generation !== state.importGeneration) {
          return false;
        }
        if (error instanceof ApiError && error.status === 401) {
          enterHome("session_expired");
          return false;
        }
        const statusKey = error instanceof ApiError && error.code === "INVALID_ASSET_SYMBOL"
          ? "reconciliation_invalid_asset"
          : "reconciliation_provider_unavailable";
        appendRevalidationStatus(row, statusKey, "danger");
        allValid = false;
        continue;
      }
      if (task.generation !== state.importGeneration) return false;
      const canonical = String(payload?.candidate?.canonical_symbol ?? "").trim().toUpperCase();
      if (payload?.status === "VALID" && canonical === ticker) {
        applySelectedAsset(row, payload.candidate);
        appendRevalidationStatus(row, "asset_verified_exact", "success");
      } else if (payload?.status === "VALID" && payload.candidate) {
        renderRevalidationCandidate(row, payload.candidate);
        allValid = false;
      } else if (payload?.status === "PROVIDER_UNAVAILABLE") {
        appendRevalidationStatus(row, "reconciliation_provider_unavailable", "danger");
        allValid = false;
      } else {
        appendRevalidationStatus(row, "reconciliation_invalid_asset", "danger");
        allValid = false;
      }
    }
  } finally {
    if (task.generation === state.importGeneration) finishImportRequest(task.generation);
  }
  return allValid;
}

async function revalidateReconciliationAssets(event) {
  event?.preventDefault();
  if (state.importPending) return;
  const rows = [...elements.reconciliationRows.querySelectorAll(".opening-draft-row")].filter((row) => row.querySelector("[data-field='ticker']")?.value.trim());
  if (!rows.length) {
    setMessage(elements.reconciliationMessage, "reconciliation_no_positions", "neutral");
    return;
  }
  const task = beginImportRequest();
  setLocalizedText(elements.reconciliationRevalidate, "reconciliation_revalidate_running");
  clearMessage(elements.reconciliationMessage);
  for (const row of rows) {
    clearRevalidationFeedback(row);
  }
  try {
    for (const row of rows) {
      if (task.generation !== state.importGeneration) return;
      const ticker = row.querySelector("[data-field='ticker']").value.trim().toUpperCase();
      const params = new URLSearchParams({ symbol: ticker });
      const payload = await requestJson(`/v1/assets/validate?${params.toString()}`, { signal: task.controller.signal });
      if (task.generation !== state.importGeneration) return;
      if (payload?.status === "VALID" && payload.candidate) {
        renderRevalidationCandidate(row, payload.candidate);
      } else if (payload?.status === "PROVIDER_UNAVAILABLE") {
        appendRevalidationStatus(row, "reconciliation_provider_unavailable", "danger");
      } else {
        appendRevalidationStatus(row, "reconciliation_invalid_asset", "danger");
      }
    }
    setMessage(elements.reconciliationMessage, "reconciliation_not_validated", "neutral");
  } catch (error) {
    if (task.generation === state.importGeneration) importFailureMessage({ controls: elements.reconciliationImport }, elements.reconciliationMessage, error, { PROVIDER_UNAVAILABLE: "reconciliation_provider_unavailable", INVALID_ASSET_SYMBOL: "reconciliation_invalid_asset", INVALID_SYMBOL: "reconciliation_invalid_asset" });
  } finally {
    if (task.generation === state.importGeneration) {
      setLocalizedText(elements.reconciliationRevalidate, "reconciliation_revalidate");
      finishImportRequest(task.generation);
    }
  }
}

function loadCurrentReconciliationDraft(event) {
  event?.preventDefault();
  if (!state.snapshot) return;
  state.importGeneration += 1;
  state.importController?.abort();
  state.importController = null;
  state.importPending = false;
  updateControls();
  clearElement(elements.reconciliationRows);
  const editablePositions = (state.snapshot.positions ?? []).filter((position) => {
    const matchingLots = (state.snapshot.lots ?? []).filter((lot) => lot.ticker === position.ticker && lot.position_type === position.position_type);
    return matchingLots.length === 1 && matchingLots[0].source !== "BUY";
  });
  for (const position of editablePositions) {
    const row = createOpeningRow(elements.reconciliationRows);
    const ticker = row.querySelector("[data-field='ticker']");
    ticker.value = position.ticker;
    row.dataset.assetSymbol = position.ticker;
    ticker.dataset.assetSymbol = position.ticker;
    row.querySelector("[data-field='shares']").value = position.shares;
    row.querySelector("[data-field='average_cost']").value = position.average_cost;
    row.querySelector("[data-field='position_type']").value = position.position_type === "UNSPECIFIED" ? "" : position.position_type;
  }
  for (const position of state.snapshot.positions ?? []) {
    if (editablePositions.includes(position)) continue;
    const section = makeElement("div", "manual-purchase-records");
    section.append(makeElement("strong", "", `${position.ticker} · ${position.position_type}`));
    for (const lot of state.snapshot.lots ?? []) {
      if (lot.ticker !== position.ticker || lot.position_type !== position.position_type) continue;
      if (lot.source === "BUY") {
        const edit = makeElement("button", "secondary-button compact-button", `${translate("edit_purchase")} · ${formatTimestamp(lot.purchased_at)}`);
        edit.type = "button";
        edit.addEventListener("click", () => openBuyCorrection(lot));
        section.append(edit);
      } else {
        section.append(makeElement("p", "field-note", translate("no_aggregate_holdings_to_calibrate")));
      }
    }
    elements.reconciliationRows.append(section);
  }
  state.reconciliationSource = "MANUAL";
  if (elements.reconciliationRows.childElementCount) clearMessage(elements.reconciliationMessage);
  else setMessage(elements.reconciliationMessage, "no_aggregate_holdings_to_calibrate", "neutral");
  elements.reconciliationRows.querySelector("input")?.focus();
}

async function handleReconciliation(event) {
  event.preventDefault();
  if (state.importPending) return;
  if (!(await validateUnboundDraftAssets(elements.reconciliationRows))) {
    setMessage(elements.reconciliationMessage, "reconciliation_not_validated", "neutral");
    return;
  }
  const positions = collectReconciliationPositions(elements.reconciliationRows);
  if (!positions || positions.length === 0) {
    setMessage(elements.reconciliationMessage, "reconciliation_no_positions", "neutral");
    return;
  }
  const payload = { source: state.reconciliationSource, positions };
  const broker = elements.reconciliationBroker.value.trim();
  if (broker) payload.broker = broker;
  const saved = await runMutation({ url: "/v1/portfolio/reconciliations", payload, messageElement: elements.reconciliationMessage, successKey: "reconciliation_saved", recordId: (result) => result.reconciliations?.[0]?.id });
  if (saved) {
    clearElement(elements.reconciliationRows);
    elements.reconciliationBroker.value = "";
    state.reconciliationSource = "SCREENSHOT";
    resetImportControls(elements.reconciliationImport);
    elements.importDialog.close();
  }
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

function handleQuestionKeydown(event) {
  if (event.key !== "Enter" || event.shiftKey) return;
  if (state.questionComposing || event.isComposing || event.keyCode === 229) return;
  if (event.repeat || state.questionPending) { event.preventDefault(); return; }
  event.preventDefault();
  elements.questionForm.requestSubmit();
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
  elements.viewEyebrow.hidden = !chat;
  setLocalizedText(elements.viewEyebrow, "context_aware");
  setLocalizedText(elements.viewTitle, chat ? "chat_view_title" : "portfolio_nav");
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
  importConfigs.forEach(bindImportEvents);
  elements.logout.addEventListener("click", logout);
  elements.headerLogout.addEventListener("click", logout);
  elements.setupLogout.addEventListener("click", logout);
  elements.navChat.addEventListener("click", () => switchAppView("chat"));
  elements.navPortfolio.addEventListener("click", () => switchAppView("portfolio"));
  elements.newQuestion.addEventListener("click", () => { switchAppView("chat", false); elements.question.focus(); });
  elements.portfolioTabs.forEach((tab, index) => tab.addEventListener("click", () => switchPortfolioTab(index)));
  elements.reloadPortfolio.addEventListener("click", () => refreshPortfolio());
  elements.openBuy.addEventListener("click", () => openTradeDialog("BUY"));
  elements.emptyBuy.addEventListener("click", () => openTradeDialog("BUY"));
  elements.openImport.addEventListener("click", openImportDialog);
  elements.openCash.addEventListener("click", openCashDialog);
  elements.addOpeningRow.addEventListener("click", () => createOpeningRow(elements.openingRows));
  elements.skipOpening.addEventListener("click", () => { state.openingDismissed = true; renderOpeningAvailability(); });
  elements.reopenOpening.addEventListener("click", () => { state.openingDismissed = false; renderOpeningAvailability(); });
  elements.openingForm.addEventListener("submit", handleOpening);
  elements.reconciliationAddRow.addEventListener("click", () => {
    state.reconciliationSource = "MANUAL";
    const row = createOpeningRow(elements.reconciliationRows);
    row.querySelector("[data-field='ticker']")?.focus();
  });
  elements.reconciliationLoadCurrent.addEventListener("click", loadCurrentReconciliationDraft);
  elements.reconciliationRevalidate.addEventListener("click", revalidateReconciliationAssets);
  elements.reconciliationForm.addEventListener("submit", handleReconciliation);
  elements.tradeForm.addEventListener("submit", handleTrade);
  elements.tradeBuyMode.addEventListener("click", () => setTradeAction("BUY"));
  elements.tradeSellMode.addEventListener("click", () => setTradeAction("SELL"));
  elements.tradeDialogClose.addEventListener("click", () => elements.tradeDialog.close());
  elements.cashForm.addEventListener("submit", handleCash);
  elements.cashDialogClose.addEventListener("click", () => elements.cashDialog.close());
  elements.importDialogClose.addEventListener("click", () => elements.importDialog.close());
  elements.tradeTicker.addEventListener("input", () => {
    delete elements.tradeTicker.dataset.assetSymbol;
    renderSellLotAllocation();
  });
  bindAssetAutocomplete(elements.tradeTicker, (candidate) => {
    const symbol = String(candidate?.canonical_symbol ?? "").trim().toUpperCase();
    if (!symbol) return;
    elements.tradeTicker.value = symbol;
    elements.tradeTicker.dataset.assetSymbol = symbol;
    renderSellLotAllocation();
    elements.tradePrice.focus();
  });
  elements.imagePreviewClose.addEventListener("click", closeImagePreview);
  elements.imagePreviewDialog.addEventListener("click", (event) => {
    if (event.target === elements.imagePreviewDialog) closeImagePreview();
  });
  elements.imagePreviewDialog.addEventListener("close", () => {
    elements.imagePreviewFull.removeAttribute("src");
    const opener = byId(elements.imagePreviewDialog.dataset.openerId);
    delete elements.imagePreviewDialog.dataset.openerId;
    opener?.focus();
  });
  elements.correctionClose.addEventListener("click", () => elements.correctionDialog.close());
  elements.correctionForm.addEventListener("submit", handleBuyCorrection);
  elements.transactionDetailClose.addEventListener("click", () => elements.transactionDetailDialog.close());
  elements.question.addEventListener("compositionstart", () => { state.questionComposing = true; });
  elements.question.addEventListener("compositionend", () => { state.questionComposing = false; });
  elements.question.addEventListener("keydown", handleQuestionKeydown);
  elements.questionForm.addEventListener("submit", handleQuestion);
}

state.language = navigator.language?.toLowerCase().startsWith("zh") ? "zh" : "en";
elements.engineeringSmokeBanner.hidden = new URLSearchParams(window.location.search).get("engineering_smoke") !== "1";
bindEvents();
applyTranslations();
renderPortfolioEmpty();
updateControls();
restoreSession();
setInterval(() => {
  if (!document.hidden && state.activeView === "portfolio" && state.account?.portfolio_ready) {
    refreshValuation();
  }
}, 30000);
