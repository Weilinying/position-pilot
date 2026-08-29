const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const translations = {
  en: {
    meta_description:
      "PositionPilot — investment decision support grounded in your portfolio and current market context.",
    brand_home: "PositionPilot home",
    language_switch: "Switch to Chinese",
    language_target: "中文",
    local_workspace: "Local decision workspace",
    structured_state: "Structured state",
    your_portfolio: "Your portfolio",
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
    seed_hint: "Use the ID printed by the local demo seed.",
    available_cash: "Available cash",
    ledger_derived: "Ledger-derived · USD",
    open_positions: "Open positions",
    portfolio_empty_initial: "Load a portfolio to reveal the complete current position set.",
    portfolio_empty_loaded: "This portfolio has no open positions.",
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
    structured_state: "结构化状态",
    your_portfolio: "你的投资组合",
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
    seed_hint: "使用本地 Demo Seed 输出的用户 ID。",
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

const elements = {
  portfolioForm: document.querySelector("#portfolio-form"),
  portfolioLoadButton: document.querySelector("#portfolio-form button"),
  userIdInput: document.querySelector("#user-id"),
  portfolioState: document.querySelector("#portfolio-state"),
  availableCash: document.querySelector("#available-cash"),
  positionCount: document.querySelector("#position-count"),
  positionsEmpty: document.querySelector("#positions-empty"),
  positionList: document.querySelector("#position-list"),
  portfolioMessage: document.querySelector("#portfolio-message"),
  questionForm: document.querySelector("#question-form"),
  question: document.querySelector("#question"),
  questionHint: document.querySelector("#question-hint"),
  askButton: document.querySelector("#ask-button"),
  resultTitle: document.querySelector("#result-title"),
  responseStatus: document.querySelector("#response-status"),
  answerCopy: document.querySelector("#answer-copy"),
  sourceCount: document.querySelector("#source-count"),
  sourceList: document.querySelector("#source-list"),
  languageToggle: document.querySelector("#language-toggle"),
};

const clientState = {
  userIdInput: "",
  loadedUserId: null,
  portfolioGeneration: 0,
  questionGeneration: 0,
  portfolioController: null,
  questionController: null,
};

function normalizeUserId(value) {
  return value.trim().toLowerCase();
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
  elements.languageToggle.textContent = translate("language_target");
  elements.languageToggle.setAttribute("aria-label", translate("language_switch"));
}

function toggleLanguage() {
  activeLanguage = activeLanguage === "en" ? "zh" : "en";
  applyLanguage();
}

function setPortfolioState(label, tone = "neutral", localized = true) {
  if (localized) {
    setLocalizedText(elements.portfolioState, label);
  } else {
    setRawText(elements.portfolioState, label);
  }
  elements.portfolioState.dataset.tone = tone;
}

function setResponseState(label, tone = "neutral", localized = true) {
  if (localized) {
    setLocalizedText(elements.responseStatus, label);
  } else {
    setRawText(elements.responseStatus, label);
  }
  elements.responseStatus.dataset.tone = tone;
}

function clearElement(element) {
  element.replaceChildren();
}

function setQuestionEnabled(enabled) {
  elements.question.disabled = !enabled;
  elements.askButton.disabled = !enabled;
  setLocalizedText(elements.questionHint, enabled ? "question_loaded_id" : "question_load_first");
}

function resetResult(message = "answer_initial", localized = true) {
  setLocalizedText(elements.resultTitle, "result_awaiting");
  setResponseState("response_idle");
  if (localized) {
    setLocalizedText(elements.answerCopy, message);
  } else {
    setRawText(elements.answerCopy, message);
  }
  elements.sourceCount.textContent = "0";
  clearElement(elements.sourceList);
  const placeholder = document.createElement("div");
  placeholder.className = "source-placeholder";
  setLocalizedText(placeholder, "sources_none");
  elements.sourceList.append(placeholder);
}

function resetPortfolio(message = "", localized = true) {
  elements.availableCash.textContent = "—";
  elements.positionCount.textContent = "—";
  clearElement(elements.positionList);
  elements.positionsEmpty.hidden = false;
  setLocalizedText(elements.positionsEmpty.querySelector("p"), "portfolio_empty_initial");
  if (localized && message) {
    setLocalizedText(elements.portfolioMessage, message);
  } else {
    setRawText(elements.portfolioMessage, message);
  }
}

function invalidateQuestionContext(resultMessage) {
  clientState.questionGeneration += 1;
  clientState.questionController?.abort();
  clientState.questionController = null;
  setLocalizedText(elements.askButton, "ask");
  setQuestionEnabled(false);
  resetResult(resultMessage);
}

function invalidateLoadedPortfolio(message) {
  clientState.portfolioGeneration += 1;
  clientState.portfolioController?.abort();
  clientState.portfolioController = null;
  clientState.loadedUserId = null;
  elements.portfolioLoadButton.disabled = false;
  setLocalizedText(elements.portfolioLoadButton, "load");
  setPortfolioState("portfolio_stale", "warning");
  resetPortfolio(message);
  invalidateQuestionContext("portfolio_context_changed");
}

function handleUserIdInput() {
  clientState.userIdInput = normalizeUserId(elements.userIdInput.value);
  if (clientState.loadedUserId !== null) {
    if (clientState.userIdInput !== clientState.loadedUserId) {
      invalidateLoadedPortfolio("portfolio_user_changed");
    }
    return;
  }
  if (clientState.portfolioController !== null) {
    invalidateLoadedPortfolio("portfolio_user_changed_loading");
    return;
  }
  setPortfolioState("portfolio_not_loaded");
  resetPortfolio();
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
  positionType.dataset.type = position.position_type === "SWING" ? "swing" : "long-term";
  positionType.textContent = position.position_type;
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

function renderPortfolio(portfolio) {
  elements.availableCash.textContent = `$${portfolio.available_cash}`;
  elements.positionCount.textContent = String(portfolio.positions.length);
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
  setQuestionEnabled(true);
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
  } catch {
    // 非 JSON Failure 使用稳定的 HTTP 回退信息。
  }
  return {
    code: `HTTP_${response.status}`,
    messageKey: "request_failed",
  };
}

async function loadPortfolio(event) {
  event.preventDefault();
  const requestedUserId = normalizeUserId(elements.userIdInput.value);
  clientState.userIdInput = requestedUserId;

  if (!isValidUserId(requestedUserId)) {
    invalidateLoadedPortfolio("portfolio_enter_valid_id");
    setPortfolioState("portfolio_invalid_id", "danger");
    return;
  }

  clientState.portfolioGeneration += 1;
  const generation = clientState.portfolioGeneration;
  clientState.portfolioController?.abort();
  const controller = new AbortController();
  clientState.portfolioController = controller;
  clientState.loadedUserId = null;
  invalidateQuestionContext("portfolio_loading_context");

  setPortfolioState("portfolio_loading");
  elements.portfolioLoadButton.disabled = true;
  setLocalizedText(elements.portfolioLoadButton, "loading");
  resetPortfolio("");

  try {
    const response = await fetch(`/v1/portfolios/${encodeURIComponent(requestedUserId)}`, {
      signal: controller.signal,
      headers: { Accept: "application/json" },
    });
    if (
      generation !== clientState.portfolioGeneration ||
      requestedUserId !== clientState.userIdInput
    ) {
      return;
    }
    if (!response.ok) {
      const error = await parseApiError(response);
      if (generation !== clientState.portfolioGeneration) {
        return;
      }
      setPortfolioState(error.code, "danger", false);
      resetPortfolio(error.messageKey ?? error.message, Boolean(error.messageKey));
      return;
    }

    const portfolio = await response.json();
    if (
      generation !== clientState.portfolioGeneration ||
      requestedUserId !== clientState.userIdInput
    ) {
      return;
    }
    if (!isPortfolioPayload(portfolio)) {
      setPortfolioState("portfolio_invalid_response", "danger");
      resetPortfolio("portfolio_contract_error");
      return;
    }
    const responseUserId = normalizeUserId(portfolio.user_id ?? "");
    if (responseUserId !== requestedUserId) {
      setPortfolioState("portfolio_identity_mismatch", "danger");
      resetPortfolio("portfolio_identity_error");
      return;
    }

    clientState.loadedUserId = responseUserId;
    renderPortfolio(portfolio);
    const url = new URL(window.location.href);
    url.searchParams.set("user_id", responseUserId);
    window.history.replaceState({}, "", url);
  } catch (error) {
    if (error.name === "AbortError" || generation !== clientState.portfolioGeneration) {
      return;
    }
    const isNetworkError = error instanceof TypeError;
    setPortfolioState(
      isNetworkError ? "portfolio_network_error" : "portfolio_invalid_response",
      "danger",
    );
    resetPortfolio(isNetworkError ? "portfolio_service_unreachable" : "portfolio_display_error");
  } finally {
    if (generation === clientState.portfolioGeneration) {
      clientState.portfolioController = null;
      elements.portfolioLoadButton.disabled = false;
      setLocalizedText(elements.portfolioLoadButton, "load");
    }
  }
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

function renderAnswer(payload) {
  const isDegraded = payload.status === "DEGRADED";
  setLocalizedText(elements.resultTitle, isDegraded ? "answer_degraded" : "answer_assembled");
  setResponseState(payload.status, isDegraded ? "warning" : "success", false);
  setRawText(elements.answerCopy, payload.answer);
  elements.sourceCount.textContent = String(payload.sources.length);
  clearElement(elements.sourceList);
  if (payload.sources.length === 0) {
    const placeholder = document.createElement("div");
    placeholder.className = "source-placeholder";
    setLocalizedText(placeholder, "source_none_declared");
    elements.sourceList.append(placeholder);
    return;
  }
  for (const source of payload.sources) {
    elements.sourceList.append(createSourceCard(source));
  }
}

function renderQuestionError(error) {
  setLocalizedText(elements.resultTitle, "answer_failed");
  setResponseState(error.code, "danger", false);
  if (error.messageKey) {
    setLocalizedText(elements.answerCopy, error.messageKey);
  } else {
    setRawText(elements.answerCopy, error.message);
  }
  elements.sourceCount.textContent = "0";
  clearElement(elements.sourceList);
  const placeholder = document.createElement("div");
  placeholder.className = "source-placeholder";
  setLocalizedText(placeholder, "source_none_accepted");
  elements.sourceList.append(placeholder);
}

async function askQuestion(event) {
  event.preventDefault();
  const question = elements.question.value.trim();
  const requestedUserId = clientState.loadedUserId;

  if (requestedUserId === null || requestedUserId !== clientState.userIdInput) {
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

  elements.askButton.disabled = true;
  setLocalizedText(elements.askButton, "analyzing");
  elements.question.disabled = true;
  setLocalizedText(elements.resultTitle, "answer_assembling");
  setResponseState("response_working");
  setLocalizedText(elements.answerCopy, "answer_loading");
  elements.sourceCount.textContent = "0";
  clearElement(elements.sourceList);

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
      renderQuestionError(error);
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
      renderQuestionError({
        code: "INVALID_RESPONSE",
        messageKey: "answer_contract_error",
      });
      return;
    }
    renderAnswer(payload);
  } catch (error) {
    if (error.name === "AbortError" || generation !== clientState.questionGeneration) {
      return;
    }
    const isNetworkError = error instanceof TypeError;
    renderQuestionError({
      code: isNetworkError ? "NETWORK_ERROR" : "INVALID_RESPONSE",
      messageKey: isNetworkError ? "answer_service_unreachable" : "answer_display_error",
    });
  } finally {
    if (
      generation === clientState.questionGeneration &&
      requestedUserId === clientState.loadedUserId &&
      requestedUserId === clientState.userIdInput
    ) {
      clientState.questionController = null;
      elements.question.disabled = false;
      elements.askButton.disabled = false;
      setLocalizedText(elements.askButton, "ask");
      setLocalizedText(elements.questionHint, "question_loaded_id");
    }
  }
}

elements.userIdInput.addEventListener("input", handleUserIdInput);
elements.portfolioForm.addEventListener("submit", loadPortfolio);
elements.questionForm.addEventListener("submit", askQuestion);
elements.languageToggle.addEventListener("click", toggleLanguage);

const initialUserId = normalizeUserId(new URLSearchParams(window.location.search).get("user_id") ?? "");
if (initialUserId) {
  elements.userIdInput.value = initialUserId;
  clientState.userIdInput = initialUserId;
}
resetPortfolio();
resetResult();
setPortfolioState("portfolio_not_loaded");
applyLanguage();
